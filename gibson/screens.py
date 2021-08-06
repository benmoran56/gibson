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
        for b in message:
            self.connection.send(bytes([b]))

    def send_unicode(self, string, color=b''):
        # TODO: replace invalid characters
        self.send(color + bytes([ord(s) for s in string]).swapcase())

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
        # TODO: relative cursor movement
        self._go_home()
        self.cursor_x += column
        self.cursor_y += row
        self.send(CURSOR_RIGHT * column + CURSOR_DOWN * row)


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
            self.connection.close()


class LoginScreen(_Screen):
    def activate(self):
        self._reset()

        with open('resources/mainmenu.seq', 'rb') as f:
            self.send(f.read())

        self._go_to(column=15, row=2)
        self.send_unicode("  Log In  ", CYAN)

        self._go_to(column=4, row=6)
        self.send_unicode("[E] Existing Account", LIGHT_GREEN)
        self._go_to(column=4, row=7)
        self.send_unicode("[N] New Account", LIGHT_GREEN)
        self._go_to(column=4, row=8)
        self.send_unicode("[Q] Log off", PINK)

        self._go_to(2, 24)
        self.send_unicode(">", color=YELLOW)

    def handle_input(self, character):
        self.session.set_screen('mainmenu')


class MainMenuScreen(_Screen):

    def activate(self):
        self._reset()

        with open('resources/mainmenu.seq', 'rb') as f:
            seq = f.read()
            self.send(seq)

        self._go_to(column=15, row=2)
        self.send_unicode("Main  Menu", CYAN)

        self._go_to(column=4, row=6)
        self.send_unicode("[B] Browse CBM World", LIGHT_GREEN)
        self._go_to(column=4, row=7)
        self.send_unicode("[V] View the Wall", LIGHT_GREEN)
        self._go_to(column=4, row=8)
        self.send_unicode("[R] Refresh", LIGHT_GREEN)
        self._go_to(column=4, row=10)
        self.send_unicode("[Q] Log off", PINK)
        self._go_to(2, 24)
        self.send_unicode(">", color=YELLOW)

    def handle_input(self, character):

        if character == b'R':
            self.activate()
            return

        elif character == b'Q':
            self.connection.close()
            return

        elif character == b'V':
            self.session.set_screen('wall')

        elif character == b'B':
            self.session.set_screen('cbmworld')


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


# class CBMWorldScreen(_Screen):
#     def activate(self):
#         self._reset()
#
#         import discourse
#
#         client = discourse.Client(host='https://forum.cbm.world', api_username='benjamin',
#                                   api_key='bfb02a361033051f0225dc227a44419c618803294b874e5cf887e34a924924a8', )
#
#         latest = client.get_latest_topics('default')
#
#         for topic in latest:
#             self._send_unicode(topic.created_at[5:10] + " ", GREEN)
#             self._send_unicode(topic.title, WHITE)
#             self.send(RETURN * 2)
#
#         self.send(RETURN)
#
#         self._go_to(1, 23)
#         self._send_unicode("Press any key", PINK)
#         self._send_unicode(">", color=YELLOW)
#
#     def handle_input(self, character):
#         self.send(REVERSE_OFF)
#         self.session.set_screen('mainmenu')
