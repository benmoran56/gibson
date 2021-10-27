import time
import weakref
import asyncio as _asyncio

from gibson.event import EventDispatcher as _EventDispatcher
from gibson.screens import *


_baud_bps_map = {
    300: 60 / 300 / 8,
    2400: 60 / 2400 / 8,
    9600: 60 / 9600 / 8,
}


class AsyncConnection(_EventDispatcher):

    def __init__(self, reader, writer, bps):
        self._reader = reader
        self._writer = writer

        # Outbound rate limiting.  Convert
        # bits per second to a delay in seconds:
        self._delay = 60 / bps / 8

        self._next_send = time.time()

        self._closed = False
        self._loop = _asyncio.get_event_loop()
        _asyncio.run_coroutine_threadsafe(self._recv(), self._loop)

    def close(self):
        if not self._closed:
            self._writer.transport.close()
            self._closed = True
            self.dispatch_event('on_disconnect', self)

    async def _recv(self):
        while not self._closed:
            try:
                message = await self._reader.readexactly(1)
                self._loop.call_soon(self.dispatch_event, 'on_receive', message)

            except _asyncio.IncompleteReadError:
                self.close()
                break

    async def _send(self, message):
        try:
            now = time.time()
            delay = max(0.0, self._next_send - now)
            self._next_send = max(self._next_send + self._delay, now + delay)

            await _asyncio.sleep(delay)
            await self._writer.write(message)
            await self._writer.drain()
        except ConnectionResetError:
            self.close()

    def send(self, message):
        # Synchrounously send a message in a async coroutine.
        if self._writer.transport is None or self._writer.transport.is_closing():
            self.close()
            return
        _future = _asyncio.run_coroutine_threadsafe(self._send(message), self._loop)

    def on_receive(self, message):
        """Event for received messages."""

    def on_disconnect(self, connection):
        """Event for disconnection. """

    def __repr__(self):
        return f"{self.__class__.__name__}{self._writer.get_extra_info('peername')}"

    def __del__(self):
        print("Garbage Collected: ", self)


AsyncConnection.register_event_type('on_receive')
AsyncConnection.register_event_type('on_disconnect')


class Server(_EventDispatcher):

    def __init__(self, address, port, bps=9600):
        print(f"Listening on {address}:{port}.")

        self._address = address
        self._port = port
        self._bps = bps

        self._server = None
        self._session_manager = SessionManager()

    async def handle_connection(self, reader, writer):
        connection = AsyncConnection(reader, writer, self._bps)
        self.dispatch_event('on_connection', connection)

    async def _start_server(self):
        self._server = await _asyncio.start_server(self.handle_connection, self._address, self._port)
        async with self._server:
            await self._server.serve_forever()

    def run(self):
        try:
            _asyncio.run(self._start_server())
        except KeyboardInterrupt:
            self._server.close()

    def on_connection(self, connection):
        """Event for new Connections received."""
        print("Connected <---", connection)
        self._session_manager.create_session(connection=connection)


Server.register_event_type('on_connection')


class SessionManager:
    """Session Manager

    The Session Manager keeps track of all open Sessions.
    In addition, it provides a way for Sessions to indirectly
    communicate with eath other. All sessions will have a
    reference to the Manager, so they can access it's
    data and methods.
    """

    def __init__(self):
        self._sessions = set()

    @property
    def active_sessions(self):
        return len(self._sessions)

    def create_session(self, connection):
        session = Session(connection, self)
        self._sessions.add(session)
        return session

    def remove_session(self, session):
        self._sessions.remove(session)

    def broadcast_message(self, message):
        for session in self._sessions:
            session.handle_output(message)


class Session:

    def __init__(self, connection, manager):
        connection.set_handler('on_receive', self.handle_input)
        connection.set_handler('on_disconnect', self._on_session_disconnect)
        self.connection = weakref.proxy(connection)
        self.manager = weakref.proxy(manager)

        self._screens = {}
        self._current_screen = None

        self._add_screen('welcome', WelcomeScreen())
        self._add_screen('login', LoginScreen())
        self._add_screen('chat', ChatScreen())

        self.set_screen('welcome')

        # Chat related details

        self.handle = b""

    def _add_screen(self, name, instance):
        instance.session = self
        self._screens[name] = instance
        self._current_screen = instance

    def _on_session_disconnect(self, connection):
        if self.handle:
            sign_off_message = b" " * 13 + self.handle + b' has left the chat.'
            self.manager.broadcast_message(sign_off_message + RETURN)
        self.manager.remove_session(self)

    def set_screen(self, name):
        self._current_screen = self._screens.get(name, self._current_screen)
        self._current_screen.activate()

    def handle_output(self, message):
        self._current_screen.handle_output(message)

    def handle_input(self, message):
        self._current_screen.handle_input(message)
