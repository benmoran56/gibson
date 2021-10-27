import random

from collections import deque
from datetime import datetime

from .petscii import *


class _Screen:

    echo = False
    session = None
    cursor_x = 0
    cursor_y = 0

    send_colors = deque([LIGHT_GREY, GREY])

    @property
    def connection(self):
        return self.session.connection

    def send(self, message):
        self.connection.send(message)

    def send_unicode(self, string, color=b''):
        # TODO: replace invalid characters
        self.send(color + bytes([ord(s) for s in string]).swapcase())

    def broadcast_message(self, message, color=b""):
        """Send a message to all other Clients & clean up the input afterwards."""
        # First clean up the entry:
        self.send(DELETE * (len(message) + 2))
        # Then tag & send the message to all Clients:
        tagged_message = self.session.handle + YELLOW + b'> ' + self.send_colors[0] + message + RETURN
        self.send_colors.rotate(1)
        self.session.manager.broadcast_message(tagged_message)

    def activate(self):
        raise NotImplementedError

    def handle_input(self, character):
        raise NotImplementedError

    def handle_output(self, message):
        """For sending broadcasts"""
        pass

    def _reset(self):
        self.send(WHITE)
        self.send(CLEAR)
        self._go_home()

    def _go_home(self):
        self.send(HOME)
        self.cursor_x = 0
        self.cursor_y = 0

    def _go_to(self, column, row):
        # TODO: relative cursor movement
        self._go_home()
        self.cursor_x += column
        self.cursor_y += row
        self.send(CURSOR_RIGHT * column + CURSOR_DOWN * row)


class WelcomeScreen(_Screen):

    def activate(self):
        self._reset()
        self.send_unicode("Smash that DEL key!", color=WHITE)

    def handle_input(self, character):
        if character == DELETE:
            self.send(REVERSE_OFF)
            self.send(RETURN)
            self.session.set_screen('login')
        else:
            self.connection.close()


class LoginScreen(_Screen):

    def __init__(self):
        self._buffer = b""

    def activate(self):
        self._reset()

        self.send(RETURN * 10)
        self.send_unicode("  Enter your handle (max 6 characters).", PINK)
        self.send(RETURN * 2)
        self.send_unicode("  Hit RETURN when finished...", PINK)

        self._go_to(0, 24)
        self.send_unicode("> ", color=YELLOW)

    def handle_input(self, character):

        # If the buffer is not empty, and RETURN is pressed:
        if character == RETURN:
            if len(self._buffer) > 1:
                color = random.choice([PINK, GREEN, LIGHT_GREEN, BLUE, LIGHT_BLUE, CYAN])
                self.session.handle = color + self._buffer
                self.session.set_screen('chat')

        # Backspace character:
        elif character == DELETE:
            if len(self._buffer) > 0:
                self._buffer = self._buffer[:-1]
                self.send(character)

        # Only add to the buffer if it's < 6 characters:
        elif len(self._buffer) < 6:
            self._buffer += character
            self.send(character)


class ChatScreen(_Screen):

    def __init__(self):
        # TODO: put a limit on the size of the send_buffer
        self._send_buffer = b""
        self._recv_buffer = b""
        self._in_entry = False
        self._max_len = 72

    def activate(self):
        self._reset()
        self.send_unicode("Welcome to C64 Chat, ")
        self.send(CYAN + self.session.handle)
        self.send_unicode(".", CYAN)
        self.send(RETURN * 23)

    def handle_output(self, message):
        if self._in_entry:
            self._send_buffer += message
        else:
            self.send(self._send_buffer + message)
            self._send_buffer = b''

    def handle_input(self, character):
        # Client is typing a message:
        if not self._in_entry:
            self._in_entry = True
            self._go_to(0, 24)
            self.send_unicode("> ", color=YELLOW)

        # If the buffer is not empty, and RETURN is pressed:
        if character == RETURN:
            if len(self._recv_buffer) > 0:
                self._in_entry = False
                self.broadcast_message(self._recv_buffer)
                self._recv_buffer = b""
            elif len(self._recv_buffer) == 0:
                self._in_entry = False
                self.send(DELETE * 2)

        # Backspace character:
        elif character == DELETE:
            if len(self._recv_buffer) > 0:
                self._recv_buffer = self._recv_buffer[:-1]
                self.send(character)

        # Only add to the buffer if it's < 6 characters:
        elif len(self._recv_buffer) < self._max_len:
            self._recv_buffer += character
            self.send(character)
