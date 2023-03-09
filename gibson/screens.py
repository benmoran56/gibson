import time

from datetime import datetime

from .petscii import *


class _Screen:

    echo = False
    session = None
    cursor_x = 0
    cursor_y = 0

    @property
    def connection(self):
        return self.session.connection

    def send(self, message):
        # TODO: handle cursor offsets
        for b in message:
            self.connection.send(bytes([b]))

    def send_unicode(self, string, color=b''):
        # TODO: replace invalid characters
        byte_string = bytes((color + bytes([ord(s) for s in string]).swapcase()))
        self.connection.send(byte_string)

        self.cursor_x = self.cursor_x + len(string) % 40    # horizontal wrap position
        self.cursor_y += (self.cursor_x + len(string)) // 40  # vertical offset position

    def activate(self):
        raise NotImplementedError

    def handle_input(self, character):
        raise NotImplementedError

    def _reset(self):
        self.send(WHITE)
        self.send(CLEAR)
        self._go_home()

    def _go_home(self):
        self.send(HOME)
        self.cursor_x = 0
        self.cursor_y = 0

    def _go_to(self, column, row):
        x_diff = column - self.cursor_x
        y_diff = row - self.cursor_y

        cmd_bytestring = b""

        if x_diff < 0:
            cmd_bytestring = CURSOR_LEFT * abs(x_diff)
        elif x_diff > 0:
            cmd_bytestring = CURSOR_RIGHT * x_diff

        if y_diff < 0:
            cmd_bytestring += CURSOR_UP * abs(y_diff)
        elif y_diff > 0:
            cmd_bytestring += CURSOR_DOWN * y_diff

        self.send(cmd_bytestring)
        self.cursor_x, self.cursor_y = column, row


class SplashScreen(_Screen):
    def activate(self):
        self._go_home()
        self.send_unicode("Smash that DEL key!", color=WHITE)

    def handle_input(self, character):
        self.send(REVERSE_OFF)
        self._reset()
        if character == DELETE:
            self.session.set_screen('login')
        else:
            self.send_unicode("Sorry, Commodore only :(", color=RED)
            # self.connection.close()


class LoginScreen(_Screen):
    def activate(self):
        self._reset()

        with open('resources/weather.seq', 'rb') as f:
            self.send(f.read())

        # self._go_to(column=15, row=2)
        # self.send_unicode("  Log In  ", CYAN)
        #
        # self._go_to(column=4, row=6)
        # self.send_unicode("[E] Existing Account", LIGHT_GREEN)
        # self._go_to(column=4, row=7)
        # self.send_unicode("[N] New Account", LIGHT_GREEN)
        # self._go_to(column=4, row=8)
        # self.send_unicode("[Q] Log off", PINK)
        #
        # self._go_to(2, 24)
        # self.send_unicode(">", color=YELLOW)

    def handle_input(self, character):
        self.session.set_screen('mainmenu')


class MainMenuScreen(_Screen):

    def activate(self):
        self._reset()

        with open('resources/mainmenu.seq', 'rb') as f:
            self.send(f.read())
            self._go_home()

        self._go_to(column=15, row=2)
        self.send_unicode("Main  Menu", CYAN)

        self._go_to(column=4, row=7)
        self.send_unicode("[V] View the Wall", LIGHT_GREEN)
        self._go_to(column=4, row=8)
        self.send_unicode("[R] Refresh", LIGHT_GREEN)
        self._go_to(column=4, row=21)
        self.send_unicode("[Q] Log off", PINK)

        self._go_to(2, 24)
        self.send_unicode(">", color=YELLOW)

    def handle_input(self, character):

        if character == b'R':
            self.activate()

        elif character == b'Q':
            self.connection.close()

        elif character == b'V':
            self.session.set_screen('wall')


class WallScreen(_Screen):

    entries = [GREEN + b"21-jAN-01> " + LIGHT_BLUE + b"This is a fantastic BBS!".swapcase(),
               GREEN + b"21-jAN-15> " + LIGHT_BLUE + b"Wooo, what a great BBS. The best around!".swapcase()]

    def __init__(self):
        self._in_entry = False
        self._buffer = b''
        self._returns = 0

    @staticmethod
    def _get_timestamp():
        return f"{datetime.now().strftime('%y-%b-%d')}> ".swapcase().encode()

    def activate(self):
        self._reset()

        # Write the existing entries:
        for entry in self.entries:
            self.send(entry)
            self.send(RETURN * 2)
        self._go_home()

        self._go_to(1, 23)
        self.send_unicode("Write an entry? [y/N]", PINK)
        self.send_unicode(">", color=YELLOW)

    def handle_input(self, character):
        if self.echo:
            self.send(character)

        if not self._in_entry:

            if character == b'Y':
                # Print the Instructions:
                self.echo = True
                self._in_entry = True

                self.send(CURSOR_RIGHT + character + RETURN * 2)
                self.send_unicode("Maximum of 80 characters.\r", PINK)
                self.send_unicode("Hit RETURN twice when finished.", PINK)
                self.send(RETURN * 2 + CURSOR_RIGHT * 2)
                self.send_unicode(">", color=YELLOW)

            elif character in (b'N', b'\r'):
                # Just return to the main menu:
                self.session.set_screen('mainmenu')

        elif self._in_entry:

            # Backspace character:
            if character == b'\x14' and len(self._buffer) > 1:
                self._buffer = self._buffer[:-1]

            # Only add to the buffer if it's < 80 characters:
            if len(self._buffer) < 80 or character == RETURN:
                self._buffer += character

            # Return has been entered twice. Save and return:
            if len(self._buffer) > 2 and self._buffer[-2:] == RETURN + RETURN:
                print(self._buffer, self._buffer[-2:])
                if len(self._buffer) > 2:
                    self.entries.append(GREEN + self._get_timestamp() + LIGHT_BLUE + self._buffer[:-1])

                # Reset options before returning:
                self._buffer = b''
                self._in_entry = False
                self.echo = False
                self._returns = 0
                self.send_unicode("Saved!", PINK)
                self.send_unicode("[OK]", color=YELLOW)
