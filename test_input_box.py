import sys
import types
from unittest.mock import MagicMock

# Create a mock curses module
curses_mock = types.ModuleType("curses")
curses_mock.A_BOLD = 1
curses_mock.A_REVERSE = 2
curses_mock.A_DIM = 4
curses_mock.KEY_DOWN = 258
curses_mock.KEY_UP = 259
curses_mock.KEY_LEFT = 260
curses_mock.KEY_RIGHT = 261
curses_mock.KEY_HOME = 262
curses_mock.KEY_END = 360
curses_mock.KEY_BACKSPACE = 263
curses_mock.KEY_DC = 330
curses_mock.KEY_ENTER = 343
curses_mock.error = Exception

# Color constants
curses_mock.COLOR_BLACK = 0
curses_mock.COLOR_BLUE = 1
curses_mock.COLOR_CYAN = 2
curses_mock.COLOR_GREEN = 3
curses_mock.COLOR_MAGENTA = 4
curses_mock.COLOR_RED = 5
curses_mock.COLOR_WHITE = 6
curses_mock.COLOR_YELLOW = 7

# Set up some basic attributes so hasattr doesn't fail
curses_mock.COLOR_BLACK = 0
curses_mock.COLOR_RED = 1
curses_mock.COLOR_GREEN = 2
curses_mock.COLOR_YELLOW = 3
curses_mock.COLOR_BLUE = 4
curses_mock.COLOR_MAGENTA = 5
curses_mock.COLOR_CYAN = 6
curses_mock.COLOR_WHITE = 7

def mock_curs_set(val):
    pass
curses_mock.curs_set = mock_curs_set

# Standard theme mock
theme_mock = {
    "text": 0,
    "border": 0,
    "title": 0,
    "highlight": 0,
    "footer": 0,
}

# Keep track of window actions
class MockWindow:
    def __init__(self, h, w, y, x):
        self.keys = []
        self.cursor_y = 0
        self.cursor_x = 0
        self.bkgd_val = None
        self.keypad_val = None

    def bkgd(self, *args):
        self.bkgd_val = args
    def getmaxyx(self):
        return (7, 50)
    def addstr(self, y, x, text, attr=0):
        pass
    def keypad(self, val):
        self.keypad_val = val
    def erase(self):
        pass
    def attron(self, *args):
        pass
    def border(self, *args):
        pass
    def attroff(self, *args):
        pass
    def move(self, y, x):
        self.cursor_y = y
        self.cursor_x = x
    def refresh(self):
        pass
    def getch(self):
        if not self.keys:
            return 27 # ESC
        k = self.keys.pop(0)
        if isinstance(k, str):
            # Simulation of getch returning standard ascii keys as integer
            # If it's emoji/nerd icon, it can't return ascii code easily. It would return 
            # some byte value or -1, but let's simulate the existing getch implementation:
            # key = win.getch() -> returns ord(k) if standard ASCII, otherwise let's return -1 or 
            # if we simulate utf8 bytes:
            if ord(k) > 127:
                # Emojis/nerd icons would return multiple bytes, which are > 127. Let's return the first byte
                return ord(k) # Or mock it as return ord(k) which is > 127
            return ord(k)
        return k

    def get_wch(self):
        if not self.keys:
            return 27 # ESC
        k = self.keys.pop(0)
        return k

def mock_newwin(h, w, y, x):
    global current_win
    current_win = MockWindow(h, w, y, x)
    return current_win

curses_mock.newwin = mock_newwin
sys.modules["curses"] = curses_mock

# Now we can import bashmenu
import bashmenu

if __name__ == "__main__":
    # Let's write a simple direct test
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)
    
    # We will hook mock_newwin to pre-fill keys
    test_keys = []
    def mock_newwin_with_keys(h, w, y, x):
        win = MockWindow(h, w, y, x)
        win.keys = list(test_keys)
        return win
    curses_mock.newwin = mock_newwin_with_keys

    # Case 1: Standard ASCII
    test_keys = ['h', 'e', 'l', 'l', 'o', 10] # 'hello' followed by Enter
    res = bashmenu.show_input_box(stdscr, "Title", "Prompt", default_text="", theme=theme_mock)
    print(f"ASCII paste result: {repr(res)}")
    assert res == "hello", f"Expected 'hello', got {repr(res)}"

    # Case 2: Nerd icon or emoji (under old getch implementation)
    # Nerd icon (e.g. '\uf40a' - ) and Emoji (e.g. '\U0001f680' - 🚀)
    # Since old implementation is using getch(), we simulate standard keys.
    # We will pass '🚀', '', and then Enter.
    test_keys = ['🚀', '', 10]
    res = bashmenu.show_input_box(stdscr, "Title", "Prompt", default_text="", theme=theme_mock)
    print(f"Emoji/Nerd icon paste result: {repr(res)}")
    # If the bug is present, these keys will be ignored because getch() returns value > 126
    # and show_input_box has: elif 32 <= key <= 126:
    if res == "":
        print("BUG REPRODUCED: Emojis and nerd icons are ignored by show_input_box!")
    else:
        print(f"Result was: {repr(res)}")
