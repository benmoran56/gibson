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

        self._sessions = {}
        self._server = None

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

    def _connection_cleanup(self, connection):
        del self._sessions[connection]

    def on_connection(self, connection):
        """Event for new Connections received."""
        print("Connected <---", connection)
        connection.set_handler('on_disconnect', self._connection_cleanup)
        self._sessions[connection] = Session(connection)


Server.register_event_type('on_connection')


class Session:

    def __init__(self, connection):
        connection.set_handler('on_receive', self.on_receive)
        connection.send(CLEAR)

        self.connection = weakref.proxy(connection)

        self._screens = {}
        self._current_screen = None

        self.add_screen('splash', SplashScreen())
        self.add_screen('login', LoginScreen())
        self.add_screen('mainmenu', MainMenuScreen())
        self.add_screen('wall', WallScreen())
        # self.add_screen('cbmworld', CBMWorldScreen())

        self.set_screen('splash')

    def add_screen(self, name, instance):
        instance.session = self
        self._screens[name] = instance
        self._current_screen = instance

    def set_screen(self, name):
        self._current_screen = self._screens.get(name, self._current_screen)
        self._current_screen.activate()

    def on_receive(self, message):
        self._current_screen.handle_input(message)
