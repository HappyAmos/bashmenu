#!/usr/bin/env python3
"""
bashmenu.py - A lightweight TUI menu engine loaded from menu and theme files.

Loads menu structures from bashmenu.mnu, user settings from bashmenu.yml, and
color palettes from bashmenu.themes (supporting 256/16/8 color fallbacks).

Includes built-in hybrid text editor with Nano-style shortcuts, configurable
tabstop/spaces support, whitespace visibility toggle, themed interactive file/
directory chooser modal, Yes/No/Cancel confirmation dialogs, dynamic YAML dot-
notation variable interpolation, item hotkey shortcuts, and ymlcheck validator.
"""

import contextlib
import copy
import curses

__version__ = "0.0.1"
__author__ = "HA Bash Menu Development Team"
import getpass
import io
import os
import re
import shlex
import socket
import subprocess
import sys
import termios
import time
from pathlib import Path
import yaml

# Speed up ESC key response time (25ms instead of default 1000ms)
os.environ.setdefault("ESCDELAY", "25")

# Absolute path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASHMENU_DIR = SCRIPT_DIR
CONFIG_FILE = os.path.join(SCRIPT_DIR, "bashmenu.yml")
MENU_FILE = os.path.join(SCRIPT_DIR, "bashmenu.mnu")
THEME_FILE = os.path.join(SCRIPT_DIR, "bashmenu.themes")

# Import ymlcheck validator module if available in application directory
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import ymlcheck
except ImportError:
    ymlcheck = None

USERNAME = getpass.getuser()
USER_HOME = str(Path.home())
BASHRC_PATH = str(Path.home() / ".bashrc")
VIMRC_PATH = str(Path.home() / ".vimrc")
BASH_ALIASES_PATH = str(Path.home() / ".bash_aliases")
HOSTNAME = socket.gethostname()


def get_primary_ip():
    """
    Retrieve primary outbound IPv4 address without external network calls.

    Returns:
        str: Detected local IPv4 address, or '127.0.0.1' on failure.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.1)
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


PRIMARY_IP = get_primary_ip()

# ==============================================================================
# DEFAULT CONFIGURATION
# Auto-created in 'bashmenu.yml' if the file does not exist on startup.
# ==============================================================================
DEFAULT_CONFIG = {
    "version": "0.0.1",
    "theme": "dracula",
    "git_pat": "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN",
    "google_gemini_api_key": "YOUR_GOOGLE_GEMINI_API_KEY",
    "templates": "templates",
    "scripts": "scripts",
    "settings": {
        "templates_dir": "{bashmenu_dir}/templates",
        "scripts_dir": "{bashmenu_dir}/scripts",
        "ping_target": "1.1.1.1",
        "tab_to_spaces": True,
        "tabstop": 8,
        "show_menu_shortcuts": True,
        "use_nerd_fonts": False,
        "dns": {
            "ipv4": {
                "primary": "192.168.4.47",
                "secondary": "1.1.1.1",
            },
            "ipv6": {
                "primary": "fdbd:6905:d4e0:1:7605:d849:9be:4689",
                "secondary": "2606:4700:4700::1111",
            },
        },
    },
}

BLOCK_AUTOEXEC = """
# CODEBLOCK:autoexec.sh:START
if [ -f "$HOME/autoexec.sh" ]; then
  . "$HOME/autoexec.sh"
fi
# CODEBLOCK:autoexec.sh:END
"""


def is_root():
    """
    Check if current process is running with root/sudo privileges.

    Returns:
        bool: True if process UID is 0, False otherwise.
    """
    return os.geteuid() == 0


def get_option_shortcut(index):
    """
    Map option row index to single character shortcut key (0-9, a-z, A-Z).

    Args:
        index (int): Zero-based option index row number.

    Returns:
        str: Shortcut character symbol, or empty string if beyond index 61.
    """
    if 0 <= index <= 9:
        return str(index)
    if 10 <= index <= 35:
        return chr(ord('a') + (index - 10))
    if 36 <= index <= 61:
        return chr(ord('A') + (index - 36))
    return ""


def build_shortcut_map(options_count):
    """
    Build lookup table mapping shortcut key ASCII ordinals to option indexes.

    Args:
        options_count (int): Total number of menu options present.

    Returns:
        dict[int, int]: Mapping of character key ordinals to option index.
    """
    shortcut_map = {}
    for idx in range(min(options_count, 62)):
        shortcut_char = get_option_shortcut(idx)
        if shortcut_char:
            shortcut_map[ord(shortcut_char)] = idx
    return shortcut_map


def deep_merge(default, user):
    """
    Recursively merge user settings into a default configuration dictionary.

    Args:
        default (dict): Base dictionary containing default key-value pairs.
        user (dict): User dictionary whose values override default settings.

    Returns:
        dict: Merged configuration dictionary.
    """
    if not isinstance(user, dict):
        return default
    for key, value in user.items():
        if (
            isinstance(value, dict)
            and key in default
            and isinstance(default[key], dict)
        ):
            deep_merge(default[key], value)
        else:
            default[key] = value
    return default


def get_config_value(config, key_path):
    """
    Retrieve configuration value using dot-notation path ('settings.dns').

    Args:
        config (dict): Configuration dictionary to traverse.
        key_path (str): Dot-separated path to the configuration key.

    Returns:
        str: String representation of found value, or empty string if missing.
    """
    keys = key_path.split(".")
    curr = config
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            return ""
    return str(curr) if curr is not None else ""


def set_config_value(config, key_path, value):
    """
    Set configuration value using dot notation, creating sub-dicts as needed.

    Args:
        config (dict): Configuration dictionary to update.
        key_path (str): Dot-separated key path.
        value (Any): Value to store at specified location.
    """
    keys = key_path.split(".")
    curr = config
    for k in keys[:-1]:
        if k not in curr or not isinstance(curr[k], dict):
            curr[k] = {}
        curr = curr[k]
    curr[keys[-1]] = value


def load_yaml_file(filepath):
    """
    Safely load a YAML file after validating syntax with ymlcheck.

    Args:
        filepath (str): Absolute or relative path to target YAML file.

    Returns:
        tuple[dict | None, str | None]: (Parsed YAML data, error string if any).
    """
    filename = os.path.basename(filepath)
    if not os.path.exists(filepath):
        return None, f"File not found: '{filename}'"

    if ymlcheck and (filename.endswith(".themes") or "theme" in filename):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            valid = ymlcheck.validate_theme_file(filepath)
        out_msg = f.getvalue().strip()
        if not valid:
            return None, f"Theme Validation Error in '{filename}':\n\n{out_msg}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return (data if data is not None else {}), None
    except yaml.YAMLError as exc:
        if ymlcheck and hasattr(ymlcheck, "format_yaml_error"):
            err_msg = (
                f"YAML Error in '{filename}':\n{ymlcheck.format_yaml_error(exc)}"
            )
            return None, err_msg

        if hasattr(exc, "problem_mark"):
            mark = exc.problem_mark
            line = mark.line + 1
            col = mark.column + 1
            problem = getattr(exc, "problem", "Syntax error")
            snippet = ""
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    file_lines = f.readlines()
                    if 0 <= mark.line < len(file_lines):
                        code_line = file_lines[mark.line].rstrip()
                        pointer = " " * (col - 1) + "^"
                        snippet = f"\n\nContext:\n  {code_line}\n  {pointer}"
            except Exception:
                pass
            err_msg = (
                f"YAML Error in '{filename}'\n"
                f"Line: {line}, Column: {col}\n"
                f"Problem: {problem}{snippet}"
            )
            return None, err_msg
        return None, f"YAML Parse Error in '{filename}':\n{exc}"
    except Exception as e:
        return None, f"Error reading '{filename}':\n{e}"


def map_256_to_16(val):
    """
    Map a 256-color palette index to its standard 16-color equivalent.

    Args:
        val (int): Color index in 256-color space.

    Returns:
        int: Equivalent color index in 16-color space.
    """
    if val < 16:
        return val
    if val >= 232:
        return 0 if val < 240 else (8 if val < 248 else (7 if val < 252 else 15))
    idx = val - 16
    r, g, b = idx // 36, (idx % 36) // 6, idx % 6
    if r == g == b:
        return 0 if r < 2 else (8 if r < 4 else 15)
    high = 8 if max(r, g, b) >= 3 else 0
    ans = (1 if r >= 2 else 0) | (2 if g >= 2 else 0) | (4 if b >= 2 else 0)
    return (ans + 8) if high else ans


def map_16_to_8(val):
    """
    Map a 16-color palette index to its standard 8-color base equivalent.

    Args:
        val (int): Color index in 16-color space.

    Returns:
        int: Equivalent color index in 8-color space.
    """
    if val < 8:
        return val
    if val < 16:
        return val - 8
    return map_16_to_8(map_256_to_16(val))


def resolve_curses_color(val):
    """
    Map theme color values or names to curses color IDs with downsampling.

    Args:
        val (int | str): Numeric color code or curses constant name string.

    Returns:
        int: Resolved curses color constant ID.
    """
    num_colors = getattr(curses, "COLORS", 8)
    if isinstance(val, int):
        if num_colors < 16 and val >= 8:
            return map_16_to_8(val)
        elif num_colors < 256 and val >= 16:
            return map_256_to_16(val)
        return val
    if isinstance(val, str):
        if hasattr(curses, val):
            return getattr(curses, val)
        if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
            return resolve_curses_color(int(val))
    return curses.COLOR_WHITE


def load_themes():
    """
    Load raw color palette definitions from the bashmenu.themes file.

    Returns:
        tuple[dict, str | None]: (Theme dictionary, error message if any).
    """
    raw_themes, err = load_yaml_file(THEME_FILE)
    if err:
        return {}, err
    return raw_themes, None


FALLBACK_THEME = {
    "indicator": ">",
    "background": curses.COLOR_BLACK,
    "title": (curses.COLOR_MAGENTA, -1),
    "border": (curses.COLOR_BLUE, -1),
    "text": (curses.COLOR_WHITE, -1),
    "highlight": (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
    "accent": (curses.COLOR_CYAN, -1),
    "footer": (curses.COLOR_BLUE, -1),
    "shadow": (8, curses.COLOR_BLACK),
    "gutter": (8, -1),
    "selection": (curses.COLOR_WHITE, curses.COLOR_BLUE),
    "status_bar": (curses.COLOR_BLACK, curses.COLOR_CYAN),
    "shortcut_key": (curses.COLOR_MAGENTA, -1),
    "shortcut_label": (curses.COLOR_WHITE, -1),
}

THEMES, THEME_ERROR = load_themes()


def safe_addstr(win, y, x, text, attr=0):
    """
    Safely write a string within window boundaries to prevent curses crashes.

    Args:
        win (curses.window): Target curses window object.
        y (int): Row position on window.
        x (int): Column position on window.
        text (str): String content to render.
        attr (int): Curses text attributes/color pairs.
    """
    h, w = win.getmaxyx()
    if y >= h or x >= w:
        return
    max_len = w - x if y < h - 1 else w - x - 1
    if max_len > 0:
        try:
            win.addstr(y, x, text[:max_len], attr)
        except curses.error:
            pass


def draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme=None):
    """
    Draw a drop shadow behind a popup modal window on stdscr.

    Args:
        stdscr (curses.window): Main curses screen window.
        start_y (int): Top row position of modal dialog box.
        start_x (int): Left column position of modal dialog box.
        box_h (int): Height of modal dialog box.
        box_w (int): Width of modal dialog box.
        theme (dict, optional): Active theme pair mapping.
    """
    max_y, max_x = stdscr.getmaxyx()
    shadow_attr = (
        theme["shadow"]
        if (theme and "shadow" in theme)
        else (curses.A_DIM | curses.A_REVERSE)
    )

    for y in range(start_y + 1, min(max_y, start_y + box_h + 1)):
        for x in range(start_x + box_w, min(max_x, start_x + box_w + 2)):
            try:
                ch = stdscr.inch(y, x) & 0xFF
                if ch in [0, 32]:
                    stdscr.addch(y, x, " ", shadow_attr)
                else:
                    stdscr.addch(y, x, ch, shadow_attr | curses.A_DIM)
            except curses.error:
                pass

    for x in range(start_x + 2, min(max_x, start_x + box_w + 2)):
        y = start_y + box_h
        if y < max_y:
            try:
                ch = stdscr.inch(y, x) & 0xFF
                if ch in [0, 32]:
                    stdscr.addch(y, x, " ", shadow_attr)
                else:
                    stdscr.addch(y, x, ch, shadow_attr | curses.A_DIM)
            except curses.error:
                pass

    stdscr.refresh()


def configure_autoexec():
    """
    Create autoexec.sh in user home and append sourcing logic to ~/.bashrc.

    Returns:
        str: Status message indicating outcome of configuration operation.
    """
    autoexec_path = Path.home() / "autoexec.sh"
    bashrc = Path(BASHRC_PATH)
    if not autoexec_path.exists():
        try:
            autoexec_path.touch()
            autoexec_path.chmod(0o755)
        except Exception as e:
            return f"Error creating autoexec.sh: {e}"

    try:
        bashrc_content = bashrc.read_text() if bashrc.exists() else ""
        if "# CODEBLOCK:autoexec.sh:START" not in bashrc_content:
            with bashrc.open("a") as f:
                f.write("\n" + BLOCK_AUTOEXEC + "\n")
        else:
            return "Autoexec sourcing block already present in ~/.bashrc."
    except Exception as e:
        return f"Error updating ~/.bashrc: {e}"

    return "Autoexec configuration completed successfully."


def save_config(config):
    """
    Persist current configuration structure to the bashmenu.yml file.

    Args:
        config (dict): Configuration dictionary to serialize and save.
    """
    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception:
        pass


def load_config():
    """
    Load configuration settings from bashmenu.yml; create default if missing.

    Returns:
        tuple[dict, str | None]: (Loaded configuration dict, error string).
    """
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG), None

    data, err = load_yaml_file(CONFIG_FILE)
    if err:
        return copy.deepcopy(DEFAULT_CONFIG), err

    merged = deep_merge(copy.deepcopy(DEFAULT_CONFIG), data)
    return merged, None


def load_menu():
    """
    Load menu structure definition from bashmenu.mnu.

    Returns:
        tuple[dict, str | None]: (Menu dictionary, error string if any).
    """
    data, err = load_yaml_file(MENU_FILE)
    if err:
        return {
            "title": "YAML Configuration Error",
            "options": [
                {"label": "! Error loading menu layout:"},
                {"label": f"{err}"},
                {"label": "Exit Utility", "type": "exit"},
            ],
        }, err
    return data, None


def reload_environment(stdscr, menu_stack, selected_rows):
    """
    Reload themes, config, and menu layout files into active memory.

    Args:
        stdscr (curses.window): Main screen handle.
        menu_stack (list[dict]): Stack tracking current active menu hierarchy.
        selected_rows (list[int]): Stack tracking highlighted cursor rows.

    Returns:
        tuple[dict, dict]: Updated (theme_pair_map, config_dict).
    """
    global THEMES, THEME_ERROR
    THEMES, THEME_ERROR = load_themes()
    config, config_err = load_config()
    theme = apply_theme(config.get("theme", "dracula"))
    stdscr.bkgd(' ', theme["text"])

    main_menu, menu_err = load_menu()
    inject_dynamic_menus(main_menu)

    menu_stack.clear()
    menu_stack.append(main_menu)
    selected_rows.clear()
    selected_rows.append(0)

    if THEME_ERROR:
        show_popup_message(stdscr, "Theme File Error", THEME_ERROR, theme)
    if config_err:
        show_popup_message(stdscr, "Config File Error", config_err, theme)
    if menu_err:
        show_popup_message(stdscr, "Menu File Error", menu_err, theme)

    return theme, config


def apply_theme(theme_name):
    """
    Register theme color pairs based on system capability (256/16/8 colors).

    Args:
        theme_name (str): Identifier key of target color theme.

    Returns:
        dict: Mapping of theme keys to initialized curses color pair values.
    """
    curses.start_color()
    curses.use_default_colors()
    num_colors = getattr(curses, "COLORS", 8)

    raw_theme = (
        THEMES.get(theme_name.lower(), FALLBACK_THEME)
        if THEMES
        else FALLBACK_THEME
    )

    if isinstance(raw_theme, dict):
        if num_colors >= 256 and (256 in raw_theme or "256" in raw_theme):
            palette = (
                raw_theme.get(256)
                if 256 in raw_theme
                else raw_theme.get("256")
            )
        elif num_colors >= 16 and (16 in raw_theme or "16" in raw_theme):
            palette = (
                raw_theme.get(16) if 16 in raw_theme else raw_theme.get("16")
            )
        elif 8 in raw_theme or "8" in raw_theme:
            palette = raw_theme.get(8) if 8 in raw_theme else raw_theme.get("8")
        elif 16 in raw_theme or "16" in raw_theme:
            palette = (
                raw_theme.get(16) if 16 in raw_theme else raw_theme.get("16")
            )
        elif 256 in raw_theme or "256" in raw_theme:
            palette = (
                raw_theme.get(256)
                if 256 in raw_theme
                else raw_theme.get("256")
            )
        else:
            palette = raw_theme
    else:
        palette = FALLBACK_THEME

    default_bg = resolve_curses_color(palette.get("background", -1))

    keys = [
        "title",
        "border",
        "text",
        "highlight",
        "accent",
        "footer",
        "shadow",
        "gutter",
        "selection",
        "status_bar",
        "shortcut_key",
        "shortcut_label",
    ]
    theme_dict = {}
    for idx, key in enumerate(keys, start=1):
        pair = palette.get(key, (curses.COLOR_WHITE, default_bg))
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            fg = resolve_curses_color(pair[0])
            bg = resolve_curses_color(pair[1])
        else:
            fg, bg = curses.COLOR_WHITE, default_bg

        effective_bg = default_bg if bg == -1 else bg
        try:
            curses.init_pair(idx, fg, effective_bg)
        except curses.error:
            pass
        theme_dict[key] = curses.color_pair(idx)

    # Resolve selection indicator character from theme definition
    indicator_val = ">"
    if isinstance(raw_theme, dict):
        if "indicator" in raw_theme:
            indicator_val = raw_theme["indicator"]
        elif "prefix" in raw_theme:
            indicator_val = raw_theme["prefix"]
        elif isinstance(palette, dict):
            if "indicator" in palette:
                indicator_val = palette["indicator"]
            elif "prefix" in palette:
                indicator_val = palette["prefix"]

    # Support dictionary structure for indicator/symbols with fallback
    config, _ = load_config()
    use_nerd_fonts_val = get_config_value(config, "settings.use_nerd_fonts")
    use_nerd_fonts = False
    if isinstance(use_nerd_fonts_val, bool):
        use_nerd_fonts = use_nerd_fonts_val
    elif isinstance(use_nerd_fonts_val, str):
        use_nerd_fonts = use_nerd_fonts_val.lower() in ("true", "1", "yes")

    if isinstance(indicator_val, dict):
        if use_nerd_fonts and "nerd" in indicator_val:
            indicator = str(indicator_val["nerd"])
        elif "fallback" in indicator_val:
            indicator = str(indicator_val["fallback"])
        else:
            indicator = str(next(iter(indicator_val.values())))
    else:
        indicator = str(indicator_val)

    theme_dict["indicator"] = indicator
    return theme_dict


def build_dynamic_theme_submenu():
    """
    Construct a menu structure array populated with available color themes.

    Returns:
        dict: Submenu definition containing discovered theme options.
    """
    options = []
    if THEMES:
        for theme_key in THEMES.keys():
            formatted_name = theme_key.replace("_", " ").title()
            options.append({"label": formatted_name, "set_theme": theme_key})
    options.append({"label": "Back to Options", "type": "back"})
    return {"title": "Select Color Theme", "options": options}


def inject_dynamic_menus(menu_item):
    """
    Recursively replace 'theme_selector' options with dynamic theme submenus.

    Args:
        menu_item (dict): Menu node or subtree to scan and modify in-place.
    """
    if not isinstance(menu_item, dict):
        return
    options = menu_item.get("options", [])
    for idx, opt in enumerate(options):
        if opt.get("type") == "theme_selector":
            options[idx]["submenu"] = build_dynamic_theme_submenu()
        elif "submenu" in opt:
            inject_dynamic_menus(opt["submenu"])


def show_popup_message(stdscr, title, message, theme):
    """
    Display a modal popup dialog with scrolling support for multi-line text.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Header title of message dialog.
        message (str): Body text or detailed exception content.
        theme (dict): Active color theme mapping.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(8, len(lines) + 4))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(46, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)

    max_visible = box_h - 3
    scroll_offset = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        safe_addstr(
            win,
            0,
            max(2, (box_w - len(title) - 2) // 2),
            f" {title} ",
            theme["title"] | curses.A_BOLD,
        )

        for i in range(max_visible):
            line_idx = scroll_offset + i
            if line_idx < len(lines):
                safe_addstr(win, i + 1, 2, lines[line_idx], theme["text"])

        footer = (
            " [Press ENTER or ESC] "
            if len(lines) <= max_visible
            else " [UP/DN/PgUp/PgDn]: Scroll | [ESC/ENTER]: Close "
        )
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, curses.KEY_ENTER, 10, 13]:
            break
        elif key in [curses.KEY_UP, ord('k')] and scroll_offset > 0:
            scroll_offset -= 1
        elif (
            key in [curses.KEY_DOWN, ord('j')]
            and scroll_offset < len(lines) - max_visible
        ):
            scroll_offset += 1
        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - max_visible)
        elif key == curses.KEY_NPAGE:
            scroll_offset = min(
                max(0, len(lines) - max_visible), scroll_offset + max_visible
            )
        elif key in [curses.KEY_HOME, ord('g')]:
            scroll_offset = 0
        elif key in [curses.KEY_END, ord('G')]:
            scroll_offset = max(0, len(lines) - max_visible)


def show_confirm_box(stdscr, title, message, theme):
    """
    Display an interactive modal confirmation box (Yes / No / Cancel).

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        message (str): Confirmation prompt query string.
        theme (dict): Active theme color mapping.

    Returns:
        str | None: 'yes', 'no', or None if user pressed ESC or Cancel.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(7, len(lines) + 5))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(52, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(0)

    buttons = ["Yes", "No", "Cancel"]
    active_btn = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        safe_addstr(
            win,
            0,
            max(2, (box_w - len(title) - 2) // 2),
            f" {title} ",
            theme["title"] | curses.A_BOLD,
        )

        for i, line in enumerate(lines[: box_h - 4]):
            safe_addstr(
                win, 2 + i, max(2, (box_w - len(line)) // 2), line, theme["text"]
            )

        btn_y = box_h - 2
        btn_labels = [f" [ {b} ] " for b in buttons]
        total_btns_w = sum(len(b) for b in btn_labels) + 4
        btn_start_x = max(2, (box_w - total_btns_w) // 2)

        curr_x = btn_start_x
        for idx, (btn_name, btn_str) in enumerate(zip(buttons, btn_labels)):
            attr = (
                (theme["highlight"] | curses.A_BOLD)
                if idx == active_btn
                else theme["text"]
            )
            safe_addstr(win, btn_y, curr_x, btn_str, attr)
            curr_x += len(btn_str) + 2

        footer = " [LEFT/RIGHT]: Select | [ENTER]: Confirm | [ESC]: Cancel "
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, ord('c'), ord('C')]:
            return None
        elif key in [ord('y'), ord('Y')]:
            return "yes"
        elif key in [ord('n'), ord('N')]:
            return "no"
        elif key in [curses.KEY_LEFT, curses.KEY_UP, ord('h')]:
            active_btn = (active_btn - 1) % len(buttons)
        elif key in [curses.KEY_RIGHT, curses.KEY_DOWN, 9, ord('l')]:
            active_btn = (active_btn + 1) % len(buttons)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if active_btn == 0:
                return "yes"
            elif active_btn == 1:
                return "no"
            else:
                return None


def show_toggle_box(stdscr, title, message, theme):
    """
    Display an interactive modal toggle box (True / False / Cancel).

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        message (str): Toggle prompt query string.
        theme (dict): Active theme color mapping.

    Returns:
        str | None: 'true', 'false', or None if user pressed ESC or Cancel.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(7, len(lines) + 5))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(52, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(0)

    buttons = ["True", "False", "Cancel"]
    active_btn = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        safe_addstr(
            win,
            0,
            max(2, (box_w - len(title) - 2) // 2),
            f" {title} ",
            theme["title"] | curses.A_BOLD,
        )

        for i, line in enumerate(lines[: box_h - 4]):
            safe_addstr(
                win, 2 + i, max(2, (box_w - len(line)) // 2), line, theme["text"]
            )

        btn_y = box_h - 2
        btn_labels = [f" [ {b} ] " for b in buttons]
        total_btns_w = sum(len(b) for b in btn_labels) + 4
        btn_start_x = max(2, (box_w - total_btns_w) // 2)

        curr_x = btn_start_x
        for idx, (btn_name, btn_str) in enumerate(zip(buttons, btn_labels)):
            attr = (
                (theme["highlight"] | curses.A_BOLD)
                if idx == active_btn
                else theme["text"]
            )
            safe_addstr(win, btn_y, curr_x, btn_str, attr)
            curr_x += len(btn_str) + 2

        footer = " [LEFT/RIGHT]: Select | [ENTER]: Confirm | [ESC]: Cancel "
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, ord('c'), ord('C')]:
            return None
        elif key in [ord('t'), ord('T')]:
            return "true"
        elif key in [ord('f'), ord('F')]:
            return "false"
        elif key in [curses.KEY_LEFT, curses.KEY_UP, ord('h')]:
            active_btn = (active_btn - 1) % len(buttons)
        elif key in [curses.KEY_RIGHT, curses.KEY_DOWN, 9, ord('l')]:
            active_btn = (active_btn + 1) % len(buttons)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if active_btn == 0:
                return "true"
            elif active_btn == 1:
                return "false"
            else:
                return None


def show_input_box(
    stdscr, title, prompt, default_text="", theme=None, masked=False
):
    """
    Display a single-line modal text input prompt.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        prompt (str): Text prompt label displayed above input line.
        default_text (str): Initial string value inside input field.
        theme (dict, optional): Active theme color mapping.
        masked (bool): If True, input characters are rendered as asterisks.

    Returns:
        str | None: User input string, or None if cancelled via ESC.
    """
    height, width = stdscr.getmaxyx()
    box_h = 7
    box_w = min(width - 4, max(50, len(prompt) + 8))
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(1)

    input_text = list(default_text)
    cursor_pos = len(input_text)
    field_w = box_w - 6

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        safe_addstr(
            win,
            0,
            max(2, (box_w - len(title) - 2) // 2),
            f" {title} ",
            theme["title"] | curses.A_BOLD,
        )
        safe_addstr(win, 2, 3, prompt, theme["text"])

        raw_str = "".join(input_text)
        display_str = "*" * len(raw_str) if masked else raw_str

        offset = max(0, cursor_pos - field_w + 1)
        visible_text = display_str[offset : offset + field_w]

        field_padded = visible_text.ljust(field_w)
        safe_addstr(win, 4, 3, f" {field_padded} ", theme["highlight"])
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - 32) // 2),
            " [ENTER]: Confirm | [ESC]: Cancel ",
            theme["footer"],
        )

        win.move(4, 4 + (cursor_pos - offset))
        win.refresh()

        key = win.getch()
        if key == 27:
            curses.curs_set(0)
            return None
        elif key in [curses.KEY_ENTER, 10, 13]:
            curses.curs_set(0)
            return "".join(input_text)
        elif key in [curses.KEY_BACKSPACE, 8, 127]:
            if cursor_pos > 0:
                input_text.pop(cursor_pos - 1)
                cursor_pos -= 1
        elif key == curses.KEY_DC:
            if cursor_pos < len(input_text):
                input_text.pop(cursor_pos)
        elif key == curses.KEY_LEFT:
            if cursor_pos > 0:
                cursor_pos -= 1
        elif key == curses.KEY_RIGHT:
            if cursor_pos < len(input_text):
                cursor_pos += 1
        elif key in [curses.KEY_HOME, 1]:
            cursor_pos = 0
        elif key in [curses.KEY_END, 5]:
            cursor_pos = len(input_text)
        elif 32 <= key <= 126:
            input_text.insert(cursor_pos, chr(key))
            cursor_pos += 1


def show_file_picker(
    stdscr, title, start_dir="~", mode="file", default_val=None, theme=None
):
    """
    Display a themed interactive file and directory chooser modal dialog.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Header title for file picker modal.
        start_dir (str): Initial filesystem path to list.
        mode (str): Selection mode filter ('file', 'dir', or 'any').
        default_val (str, optional): Pre-selected item path.
        theme (dict, optional): Active theme color mapping.

    Returns:
        str | None: Selected absolute path, or None if cancelled via ESC.
    """
    target_item = None
    if default_val:
        resolved_default = os.path.abspath(
            os.path.expanduser(str(default_val).strip())
        )
        if os.path.exists(resolved_default):
            target_item = resolved_default

    current_path = os.path.abspath(os.path.expanduser(start_dir))
    if not os.path.exists(current_path) or not os.path.isdir(current_path):
        if os.path.exists(os.path.dirname(current_path)) and os.path.isdir(
            os.path.dirname(current_path)
        ):
            current_path = os.path.dirname(current_path)
        else:
            current_path = USER_HOME

    cursor_idx = 0
    scroll_offset = 0
    curses.curs_set(0)
    initial_selection_done = False

    config, _ = load_config()
    ind = interpolate_placeholders(theme.get("indicator", ">"), config) if theme else ">"
    prefix_str = f"{ind} " if ind else "  "
    indent_str = " " * len(prefix_str)

    while True:
        entries = []
        try:
            with os.scandir(current_path) as it:
                all_entries = list(it)

            dirs = sorted(
                [e for e in all_entries if e.is_dir()],
                key=lambda e: e.name.lower(),
            )
            files = sorted(
                [e for e in all_entries if not e.is_dir()],
                key=lambda e: e.name.lower(),
            )

            if current_path != "/":
                entries.append({
                    "name": ".. (Parent Directory)",
                    "is_dir": True,
                    "path": os.path.dirname(current_path),
                    "is_parent": True,
                })

            if mode == "dir":
                entries.append({
                    "name": (
                        f"[ Select Current Directory: "
                        f"{os.path.basename(current_path) or '/'} ]"
                    ),
                    "is_dir": True,
                    "path": current_path,
                    "is_self": True,
                })

            for d in dirs:
                entries.append({
                    "name": f"[DIR]  {d.name}/",
                    "is_dir": True,
                    "path": d.path,
                    "is_parent": False,
                })

            if mode != "dir":
                for f in files:
                    entries.append({
                        "name": f"[FILE] {f.name}",
                        "is_dir": False,
                        "path": f.path,
                        "is_parent": False,
                    })

        except PermissionError:
            entries = [{
                "name": "![ Permission Denied ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]
        except Exception as e:
            entries = [{
                "name": f"![ Error: {e} ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]

        if not entries:
            entries = [{
                "name": "[ Empty Directory ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]

        if not initial_selection_done:
            if target_item:
                for idx, ent in enumerate(entries):
                    if (
                        mode == "dir"
                        and ent.get("is_self")
                        and target_item == current_path
                    ):
                        cursor_idx = idx
                        break
                    elif ent.get("path") == target_item:
                        cursor_idx = idx
                        break
            elif mode == "dir":
                for idx, ent in enumerate(entries):
                    if ent.get("is_self"):
                        cursor_idx = idx
                        break
            initial_selection_done = True

        cursor_idx = max(0, min(cursor_idx, len(entries) - 1))

        height, width = stdscr.getmaxyx()
        box_h = max(12, int(height * 0.75))
        box_w = max(50, int(width * 0.75))
        start_y = (height - box_h) // 2
        start_x = (width - box_w) // 2

        draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.bkgd(' ', theme["text"])
        win.keypad(True)

        max_visible = box_h - 4

        if cursor_idx < scroll_offset:
            scroll_offset = cursor_idx
        elif cursor_idx >= scroll_offset + max_visible:
            scroll_offset = cursor_idx - max_visible + 1

        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        header = f" {title} "
        safe_addstr(
            win,
            0,
            max(2, (box_w - len(header)) // 2),
            header,
            theme["title"] | curses.A_BOLD,
        )

        path_disp = f" Path: {current_path} "
        if len(path_disp) > box_w - 4:
            path_disp = " Path: ..." + path_disp[-(box_w - 10) :]
        safe_addstr(win, 1, 2, path_disp, theme["accent"])

        footer = (
            " [ENTER]: Select/Open | [ESC]: Cancel "
            if mode != "dir"
            else " [ENTER]: Open | [SPACE]: Select Current Folder | [ESC]: Cancel "
        )
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        for i in range(max_visible):
            idx = scroll_offset + i
            if idx >= len(entries):
                break

            entry = entries[idx]
            y = 2 + i
            max_len = box_w - 6
            label = entry["name"][:max_len]

            if idx == cursor_idx:
                safe_addstr(
                    win,
                    y,
                    2,
                    f"{prefix_str}{label:<{max_len}}",
                    theme["highlight"] | curses.A_BOLD,
                )
            else:
                attr = theme["accent"] if entry.get("is_dir") else theme["text"]
                safe_addstr(win, y, 2, f"{indent_str}{label}", attr)

        win.refresh()
        key = win.getch()

        if key == 27:
            return None
        elif key in [curses.KEY_UP, ord('k')] and cursor_idx > 0:
            cursor_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')] and cursor_idx < len(entries) - 1:
            cursor_idx += 1
        elif key == curses.KEY_PPAGE:
            cursor_idx = max(0, cursor_idx - max_visible)
        elif key == curses.KEY_NPAGE:
            cursor_idx = min(len(entries) - 1, cursor_idx + max_visible)
        elif key in [curses.KEY_HOME, ord('g')]:
            cursor_idx = 0
        elif key in [curses.KEY_END, ord('G')]:
            cursor_idx = len(entries) - 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            if not entries or cursor_idx >= len(entries):
                continue
            selected = entries[cursor_idx]
            if selected.get("error") or selected.get("path") is None:
                continue
            if selected.get("is_parent") or selected["is_dir"]:
                if selected.get("is_self"):
                    return selected["path"]
                current_path = selected["path"]
                cursor_idx = 0
                scroll_offset = 0
            elif mode in ["file", "any"]:
                return selected["path"]
        elif key == ord(' ') and mode == "dir":
            return current_path


def run_curses_editor(
    stdscr,
    file_path,
    theme,
    show_whitespace=False,
    tab_to_spaces=True,
    tabstop=8,
):
    """
    Launch full-screen curses text editor with Nano-style shortcuts.

    Args:
        stdscr (curses.window): Main screen window handle.
        file_path (str | None): Path of target file to create or edit.
        theme (dict): Active theme color attribute map.
        show_whitespace (bool): Toggle rendering of space/tab glyphs.
        tab_to_spaces (bool): If True, convert Tab key presses to spaces.
        tabstop (int): Number of spaces per tab indentation.
    """
    if file_path:
        expanded_path = os.path.expanduser(file_path)
        abs_path = (
            os.path.abspath(expanded_path)
            if os.path.isabs(expanded_path)
            else os.path.abspath(os.path.join(SCRIPT_DIR, expanded_path))
        )
        rel_name = os.path.basename(abs_path)
    else:
        abs_path = ""
        rel_name = "Untitled"

    fd = sys.stdin.fileno()
    old_settings = None
    try:
        old_settings = termios.tcgetattr(fd)
        new_settings = termios.tcgetattr(fd)
        new_settings[0] &= ~termios.IXON
        termios.tcsetattr(fd, termios.TCSANOW, new_settings)
    except Exception:
        pass

    lines = [""]
    if abs_path and os.path.exists(abs_path):
        try:
            with open(abs_path, "r") as f:
                content = f.read().splitlines()
                lines = content if content else [""]
        except Exception as e:
            lines = [f"# Error opening file: {e}"]

    cursor_y = cursor_x = scroll_y = scroll_x = 0
    modified = False
    status_msg = ""

    cutbuffer = []
    cutbuffer_is_block = last_action_was_cut = mark_active = False
    mark_y = mark_x = 0

    undo_stack = []
    redo_stack = []
    MAX_HISTORY = 100
    typing_group = False

    show_line_numbers = show_help = True

    curses.curs_set(1)
    stdscr.keypad(True)

    def push_undo():
        """Push current editor state onto undo history stack."""
        nonlocal undo_stack, redo_stack
        undo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        if len(undo_stack) > MAX_HISTORY:
            undo_stack.pop(0)
        redo_stack.clear()

    def action_undo():
        """Revert editor to previous state from undo history stack."""
        nonlocal cursor_y, cursor_x, mark_active, mark_y, mark_x, lines
        nonlocal modified, status_msg, typing_group
        typing_group = False
        if not undo_stack:
            status_msg = " [ Nothing to undo ] "
            return
        redo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        prev_lines, cursor_y, cursor_x, mark_active, mark_y, mark_x = (
            undo_stack.pop()
        )
        lines = list(prev_lines)
        modified = True
        status_msg = " [ Undo ] "

    def action_redo():
        """Reapply previously undone changes from redo history stack."""
        nonlocal cursor_y, cursor_x, mark_active, mark_y, mark_x, lines
        nonlocal modified, status_msg, typing_group
        typing_group = False
        if not redo_stack:
            status_msg = " [ Nothing to redo ] "
            return
        undo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        next_lines, cursor_y, cursor_x, mark_active, mark_y, mark_x = (
            redo_stack.pop()
        )
        lines = list(next_lines)
        modified = True
        status_msg = " [ Redo ] "

    def restore_termios():
        """Restore initial terminal attributes prior to editor launch."""
        if old_settings:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, old_settings)
            except Exception:
                pass

    def action_exit():
        """Exit editor, prompting for confirmation if modified."""
        nonlocal typing_group, mark_active, status_msg
        typing_group = False
        if mark_active:
            mark_active = False
            status_msg = " [ Mark Cancelled ] "
            return False
        if modified:
            confirm = show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Do you want to save before closing?",
                theme,
            )
            if confirm is None:
                status_msg = " [ Exit Cancelled ] "
                return False
            elif confirm == "yes":
                save_file()

        restore_termios()
        curses.curs_set(0)
        return True

    def save_file():
        """Save current buffer contents to disk."""
        nonlocal modified, status_msg
        if not abs_path:
            action_save_as()
            return
        try:
            with open(abs_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            modified = False
            status_msg = " [ File Saved Successfully! ] "
        except Exception as e:
            status_msg = f" [ Save Error: {e} ] "

    def action_save_as():
        """Prompt user for destination path and save buffer."""
        nonlocal abs_path, rel_name
        default_p = abs_path if abs_path else "untitled.txt"
        new_path = show_input_box(
            stdscr, "Save As", "Enter destination path:", default_p, theme
        )
        if new_path and new_path.strip():
            expanded = os.path.expanduser(new_path.strip())
            abs_path = (
                os.path.abspath(expanded)
                if os.path.isabs(expanded)
                else os.path.abspath(os.path.join(SCRIPT_DIR, expanded))
            )
            rel_name = os.path.basename(abs_path)
            save_file()

    def action_open():
        """Prompt user for a file to open into the editor."""
        nonlocal lines, cursor_y, cursor_x, scroll_y, scroll_x
        nonlocal abs_path, rel_name, modified, status_msg, typing_group
        if modified:
            confirm = show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Save before opening another file?",
                theme,
            )
            if confirm is None:
                status_msg = " [ Open Cancelled ] "
                return
            elif confirm == "yes":
                save_file()
                if modified:
                    return

        start_d = os.path.dirname(abs_path) if abs_path else USER_HOME
        chosen = show_file_picker(
            stdscr, "Open File", start_dir=start_d, mode="file", theme=theme
        )
        if chosen and os.path.isfile(chosen):
            try:
                with open(chosen, "r") as f:
                    content = f.read().splitlines()
                    lines = content if content else [""]
                abs_path = os.path.abspath(chosen)
                rel_name = os.path.basename(abs_path)
                cursor_y = cursor_x = scroll_y = scroll_x = 0
                modified = False
                undo_stack.clear()
                redo_stack.clear()
                typing_group = False
                status_msg = f" [ Opened '{rel_name}' ] "
            except Exception as e:
                status_msg = f" [ Open Error: {e} ] "

    def action_new():
        """Clear buffer and reset editor for a new document."""
        nonlocal lines, cursor_y, cursor_x, scroll_y, scroll_x
        nonlocal abs_path, rel_name, modified, status_msg, typing_group
        if modified:
            confirm = show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Save before creating a new document?",
                theme,
            )
            if confirm is None:
                status_msg = " [ New Document Cancelled ] "
                return
            elif confirm == "yes":
                save_file()
                if modified:
                    return

        lines = [""]
        abs_path = ""
        rel_name = "Untitled"
        cursor_y = cursor_x = scroll_y = scroll_x = 0
        modified = False
        undo_stack.clear()
        redo_stack.clear()
        typing_group = False
        status_msg = " [ New Document Created ] "

    def open_external_editor():
        """Suspend curses interface and spawn external editor ($EDITOR)."""
        if not abs_path:
            action_save_as()
            if not abs_path:
                return
        restore_termios()
        curses.endwin()
        editor_bin = os.environ.get("EDITOR", "nano")
        print(f"\n--- Launching {editor_bin} for '{rel_name}' ---\n")
        try:
            cmd = shlex.split(editor_bin) + [abs_path]
            subprocess.run(cmd)
        except Exception as e:
            print(f"Error starting editor '{editor_bin}': {e}")
            input("Press [ENTER] to continue...")
        stdscr.clear()
        stdscr.refresh()
        try:
            termios.tcsetattr(fd, termios.TCSANOW, new_settings)
        except Exception:
            pass

    def get_selection_range():
        """Calculate sorted start and end coordinates of selection."""
        if not mark_active:
            return None
        return (
            ((cursor_y, cursor_x), (mark_y, mark_x))
            if (cursor_y, cursor_x) < (mark_y, mark_x)
            else ((mark_y, mark_x), (cursor_y, cursor_x))
        )

    def extract_selected_text():
        """Extract lines or substrings bounded by active selection mark."""
        rng = get_selection_range()
        if not rng:
            return []
        (sy, sx), (ey, ex) = rng
        if sy == ey:
            return [lines[sy][sx:ex]]
        res = [lines[sy][sx:]]
        for y in range(sy + 1, ey):
            res.append(lines[y])
        res.append(lines[ey][:ex])
        return res

    def delete_selected_text():
        """Remove text currently highlighted by selection bounds."""
        nonlocal cursor_y, cursor_x, mark_active, modified, typing_group
        rng = get_selection_range()
        if not rng:
            return
        typing_group = False
        push_undo()
        (sy, sx), (ey, ex) = rng
        if sy == ey:
            lines[sy] = lines[sy][:sx] + lines[sy][ex:]
        else:
            lines[sy] = lines[sy][:sx] + lines[ey][ex:]
            del lines[sy + 1 : ey + 1]
        cursor_y, cursor_x = sy, sx
        mark_active = False
        modified = True
        if not lines:
            lines.append("")

    def action_cut():
        """Cut active line or selected text block into cutbuffer."""
        nonlocal cutbuffer, cutbuffer_is_block, last_action_was_cut, status_msg
        nonlocal modified, cursor_y, cursor_x, mark_active, typing_group
        typing_group = False
        if mark_active:
            cutbuffer = extract_selected_text()
            cutbuffer_is_block = True
            delete_selected_text()
            last_action_was_cut = False
            status_msg = f" [ Cut {len(cutbuffer)} line selection ] "
        else:
            push_undo()
            if last_action_was_cut and not cutbuffer_is_block:
                cutbuffer.append(lines[cursor_y])
            else:
                cutbuffer = [lines[cursor_y]]
                cutbuffer_is_block = False

            if len(lines) > 1:
                lines.pop(cursor_y)
                if cursor_y >= len(lines):
                    cursor_y = len(lines) - 1
                cursor_x = min(cursor_x, len(lines[cursor_y]))
            else:
                lines[0] = ""
                cursor_x = 0
            modified = True
            last_action_was_cut = True
            plural = "s" if len(cutbuffer) > 1 else ""
            status_msg = f" [ Cut {len(cutbuffer)} line{plural} ] "

    def action_copy():
        """Copy active line or selection block into cutbuffer."""
        nonlocal cutbuffer, cutbuffer_is_block, last_action_was_cut
        nonlocal status_msg, mark_active, typing_group
        typing_group = False
        if mark_active:
            cutbuffer = extract_selected_text()
            cutbuffer_is_block = True
            mark_active = False
            status_msg = f" [ Copied {len(cutbuffer)} line selection ] "
        else:
            cutbuffer = [lines[cursor_y]]
            cutbuffer_is_block = False
            status_msg = f" [ Copied Line {cursor_y + 1} ] "
        last_action_was_cut = False

    def action_paste():
        """Paste current cutbuffer contents at cursor location."""
        nonlocal last_action_was_cut, status_msg, modified, cursor_y, cursor_x
        nonlocal mark_active, typing_group
        typing_group = False
        last_action_was_cut = False
        if not cutbuffer:
            status_msg = " [ Cutbuffer is empty ] "
            return

        if mark_active:
            delete_selected_text()
        else:
            push_undo()

        if cutbuffer_is_block:
            if len(cutbuffer) == 1:
                lines[cursor_y] = (
                    lines[cursor_y][:cursor_x]
                    + cutbuffer[0]
                    + lines[cursor_y][cursor_x:]
                )
                cursor_x += len(cutbuffer[0])
            else:
                tail = lines[cursor_y][cursor_x:]
                lines[cursor_y] = lines[cursor_y][:cursor_x] + cutbuffer[0]
                for idx, mid in enumerate(cutbuffer[1:-1]):
                    lines.insert(cursor_y + 1 + idx, mid)
                last_idx = cursor_y + len(cutbuffer) - 1
                lines.insert(last_idx, cutbuffer[-1] + tail)
                cursor_y = last_idx
                cursor_x = len(cutbuffer[-1])
        else:
            for idx, l in enumerate(cutbuffer):
                lines.insert(cursor_y + idx, l)
            cursor_y += len(cutbuffer)
            cursor_x = 0
        modified = True
        plural = "s" if len(cutbuffer) > 1 else ""
        status_msg = f" [ Pasted {len(cutbuffer)} line{plural} ] "

    while True:
        height, width = stdscr.getmaxyx()
        use_help = show_help and height >= 14
        view_h = max(3, height - 1 - 1 - (2 if use_help else 0) - 1)
        gutter_w = 7 if show_line_numbers else 0
        view_w = max(10, width - 2 - gutter_w)

        if cursor_y < scroll_y:
            scroll_y = cursor_y
        elif cursor_y >= scroll_y + view_h:
            scroll_y = cursor_y - view_h + 1

        if cursor_x < scroll_x:
            scroll_x = cursor_x
        elif cursor_x >= scroll_x + view_w:
            scroll_x = cursor_x - view_w + 1

        stdscr.erase()
        stdscr.attron(theme["border"])
        stdscr.border(0)
        stdscr.attroff(theme["border"])

        mod_tag = " *" if modified else ""
        ws_tag = " [WS]" if show_whitespace else ""
        header = f" Editing: {rel_name}{mod_tag}{ws_tag} "
        safe_addstr(
            stdscr,
            0,
            max(2, (width - len(header)) // 2),
            header,
            theme["title"] | curses.A_BOLD,
        )

        rng = get_selection_range()

        for i in range(view_h):
            line_idx = scroll_y + i
            if line_idx >= len(lines):
                break

            line_text = lines[line_idx]
            row_screen_y = i + 1

            if show_line_numbers:
                gutter_attr = (
                    (theme["accent"] | curses.A_BOLD)
                    if line_idx == cursor_y
                    else theme["gutter"]
                )
                safe_addstr(
                    stdscr,
                    row_screen_y,
                    1,
                    f"{line_idx + 1:4d} │ ",
                    gutter_attr,
                )

            text_start_x = 1 + gutter_w
            visible_text = line_text[scroll_x : scroll_x + view_w]
            tab_glyph = "→" + (" " * (max(1, tabstop) - 1))
            disp_text = (
                visible_text.replace(" ", "·").replace("\t", tab_glyph)
                if show_whitespace
                else visible_text.replace("\t", " " * max(1, tabstop))
            )

            if not rng:
                safe_addstr(
                    stdscr, row_screen_y, text_start_x, disp_text, theme["text"]
                )
            else:
                (sy, sx), (ey, ex) = rng
                if line_idx < sy or line_idx > ey:
                    safe_addstr(
                        stdscr,
                        row_screen_y,
                        text_start_x,
                        disp_text,
                        theme["text"],
                    )
                else:
                    sel_start = sx if line_idx == sy else 0
                    sel_end = ex if line_idx == ey else len(line_text) + 1
                    if sy == ey:
                        sel_start, sel_end = sx, ex

                    line_len = len(disp_text)
                    for col_idx in range(line_len):
                        actual_col = scroll_x + col_idx
                        char_attr = (
                            theme["selection"]
                            if (sel_start <= actual_col < sel_end)
                            else theme["text"]
                        )
                        safe_addstr(
                            stdscr,
                            row_screen_y,
                            text_start_x + col_idx,
                            disp_text[col_idx],
                            char_attr,
                        )

        status_y = 1 + view_h
        safe_addstr(
            stdscr, status_y, 1, " " * (width - 2), theme["status_bar"]
        )
        disp_msg = status_msg if status_msg else f" Editing: {rel_name}"
        safe_addstr(
            stdscr,
            status_y,
            2,
            disp_msg[: max(10, width - 28)],
            theme["status_bar"] | curses.A_BOLD,
        )

        mark_badge = "[MARK] " if mark_active else ""
        pos_str = (
            f" {mark_badge}Ln {cursor_y + 1}/{len(lines)}, Col {cursor_x + 1} "
        )
        safe_addstr(
            stdscr,
            status_y,
            max(2, width - len(pos_str) - 2),
            pos_str,
            theme["shortcut_key"] | curses.A_BOLD,
        )

        if use_help:
            shortcuts_r1 = [
                ("^G", "Get Help"),
                ("^O", "WriteOut"),
                ("^R", "Read File"),
                ("^K", "Cut"),
                ("^U", "Paste"),
                ("^C", "Location"),
            ]
            shortcuts_r2 = [
                ("^X", "Exit"),
                ("^S", "SaveAs"),
                ("M-U", "Undo"),
                ("M-E", "Redo"),
                ("M-A", "Mark"),
                ("M-N", "LineNo"),
            ]

            def draw_help_row(row_y, shortcuts):
                """Render shortcut keys and labels on editor status line."""
                safe_addstr(stdscr, row_y, 1, " " * (width - 2), theme["text"])
                col_w = max(10, (width - 2) // len(shortcuts))
                for c_idx, (badge, label) in enumerate(shortcuts):
                    x = 2 + (c_idx * col_w)
                    if x + len(badge) + len(label) + 1 < width - 1:
                        safe_addstr(
                            stdscr,
                            row_y,
                            x,
                            badge,
                            theme["shortcut_key"] | curses.A_BOLD,
                        )
                        safe_addstr(
                            stdscr,
                            row_y,
                            x + len(badge) + 1,
                            label,
                            theme["shortcut_label"],
                        )

            draw_help_row(status_y + 1, shortcuts_r1)
            draw_help_row(status_y + 2, shortcuts_r2)

        screen_y = (cursor_y - scroll_y) + 1
        screen_x = (cursor_x - scroll_x) + 1 + gutter_w
        stdscr.move(
            min(view_h, max(1, screen_y)),
            min(width - 2, max(1 + gutter_w, screen_x)),
        )
        stdscr.refresh()

        key = stdscr.getch()
        status_msg = ""

        if key == 24:  # ^X: Exit
            if action_exit():
                break
        elif key in [15, curses.KEY_F3]:  # ^O, F3: WriteOut / Save
            save_file()
            last_action_was_cut = False
            typing_group = False
        elif key in [18, curses.KEY_F5, curses.KEY_F7]:  # ^R, F5, F7: Read File / Open
            action_open()
            last_action_was_cut = False
            typing_group = False
        elif key in [19, curses.KEY_F6]:  # ^S, F6: Save As
            action_save_as()
            last_action_was_cut = False
            typing_group = False
        elif key in [14, curses.KEY_F4]:  # ^N, F4: New Document
            action_new()
            last_action_was_cut = False
            typing_group = False
        elif key in [7, curses.KEY_F1]:  # ^G, F1: Get Help / Toggle Help Bar
            show_help = not show_help
            status_msg = f" [ Help bar {'enabled' if show_help else 'disabled'} ] "
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_F2]:  # F2: External $EDITOR
            save_file()
            open_external_editor()
            if abs_path and os.path.exists(abs_path):
                with open(abs_path, "r") as f:
                    lines = f.read().splitlines() or [""]
            cursor_y = min(cursor_y, len(lines) - 1)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
            undo_stack.clear()
            redo_stack.clear()
        elif key == 26:
            action_undo()
            last_action_was_cut = False
        elif key == 25:
            action_redo()
            last_action_was_cut = False
        elif key in [11, curses.KEY_F8]:  # ^K, F8: Cut
            action_cut()
        elif key in [21, 22, curses.KEY_F9]:  # ^U, ^V, F9: Paste / Uncut
            action_paste()
        elif key == 30:  # ^^ / Ctrl+^: Toggle Mark
            typing_group = False
            if mark_active:
                mark_active = False
                status_msg = " [ Mark Unset ] "
            else:
                mark_active = True
                mark_y, mark_x = cursor_y, cursor_x
                status_msg = " [ Mark Set ] "
            last_action_was_cut = False
        elif key == 3:  # ^C: Position info or Copy if mark active
            if mark_active:
                action_copy()
            else:
                pct = int((cursor_y + 1) / max(1, len(lines)) * 100)
                status_msg = f" [ Line {cursor_y + 1}/{len(lines)} ({pct}%), Col {cursor_x + 1} ] "
            last_action_was_cut = False
        elif key in [9, ord('\t')]:
            typing_group = False
            if mark_active:
                delete_selected_text()
            else:
                push_undo()

            insert_str = (" " * max(1, tabstop)) if tab_to_spaces else "\t"
            lines[cursor_y] = (
                lines[cursor_y][:cursor_x]
                + insert_str
                + lines[cursor_y][cursor_x:]
            )
            cursor_x += len(insert_str)
            modified = True
            last_action_was_cut = False
        elif key == 27:
            stdscr.timeout(50)
            next_k = stdscr.getch()
            stdscr.timeout(-1)

            if next_k != -1:
                if next_k in [ord('n'), ord('N')]:
                    show_line_numbers = not show_line_numbers
                    status_msg = f" [ Line numbers {'enabled' if show_line_numbers else 'disabled'} ] "
                elif next_k in [ord('p'), ord('P'), ord('w'), ord('W')]:
                    show_whitespace = not show_whitespace
                    status_msg = f" [ Whitespace display {'enabled' if show_whitespace else 'disabled'} ] "
                elif next_k in [ord('u'), ord('U')]:
                    action_undo()
                elif next_k in [ord('e'), ord('E')]:
                    action_redo()
                elif next_k == ord('6'):
                    action_copy()
                elif next_k in [ord('a'), ord('A')]:
                    typing_group = False
                    mark_active = not mark_active
                    mark_y, mark_x = cursor_y, cursor_x
                    status_msg = f" [ Mark {'Set' if mark_active else 'Unset'} ] "
                elif next_k in [ord('g'), ord('G'), ord('h'), ord('H')]:
                    show_help = not show_help
                    status_msg = f" [ Help bar {'enabled' if show_help else 'disabled'} ] "
                last_action_was_cut = False
            else:
                if action_exit():
                    break
                last_action_was_cut = False
        elif key == curses.KEY_UP and cursor_y > 0:
            cursor_y -= 1
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_DOWN and cursor_y < len(lines) - 1:
            cursor_y += 1
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_LEFT:
            if cursor_x > 0:
                cursor_x -= 1
            elif cursor_y > 0:
                cursor_y -= 1
                cursor_x = len(lines[cursor_y])
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_RIGHT:
            if cursor_x < len(lines[cursor_y]):
                cursor_x += 1
            elif cursor_y < len(lines) - 1:
                cursor_y += 1
                cursor_x = 0
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_PPAGE:
            cursor_y = max(0, cursor_y - view_h)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_NPAGE:
            cursor_y = min(len(lines) - 1, cursor_y + view_h)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_HOME, 1]:
            cursor_x = 0
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_END, 5]:
            cursor_x = len(lines[cursor_y])
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_BACKSPACE, 8, 127]:
            if mark_active:
                delete_selected_text()
            elif cursor_x > 0:
                if not typing_group:
                    push_undo()
                    typing_group = True
                lines[cursor_y] = (
                    lines[cursor_y][: cursor_x - 1] + lines[cursor_y][cursor_x:]
                )
                cursor_x -= 1
                modified = True
            elif cursor_y > 0:
                typing_group = False
                push_undo()
                prev_len = len(lines[cursor_y - 1])
                lines[cursor_y - 1] += lines[cursor_y]
                lines.pop(cursor_y)
                cursor_y -= 1
                cursor_x = prev_len
                modified = True
            last_action_was_cut = False
        elif key == curses.KEY_DC:
            if mark_active:
                delete_selected_text()
            elif cursor_x < len(lines[cursor_y]):
                if not typing_group:
                    push_undo()
                    typing_group = True
                lines[cursor_y] = (
                    lines[cursor_y][:cursor_x] + lines[cursor_y][cursor_x + 1 :]
                )
                modified = True
            elif cursor_y < len(lines) - 1:
                typing_group = False
                push_undo()
                lines[cursor_y] += lines[cursor_y + 1]
                lines.pop(cursor_y + 1)
                modified = True
            last_action_was_cut = False
        elif key in [curses.KEY_ENTER, 10, 13]:
            typing_group = False
            if mark_active:
                delete_selected_text()
            else:
                push_undo()
            remainder = lines[cursor_y][cursor_x:]
            lines[cursor_y] = lines[cursor_y][:cursor_x]
            lines.insert(cursor_y + 1, remainder)
            cursor_y += 1
            cursor_x = 0
            modified = True
            last_action_was_cut = False
        elif 32 <= key <= 126:
            if mark_active:
                typing_group = False
                delete_selected_text()
            elif not typing_group or key == 32:
                push_undo()
                typing_group = key != 32
            lines[cursor_y] = (
                lines[cursor_y][:cursor_x] + chr(key) + lines[cursor_y][cursor_x:]
            )
            cursor_x += 1
            modified = True
            last_action_was_cut = False


def run_interactive_action(stdscr, action, quiet=False):
    """
    Temporarily suspend curses and execute shell command in terminal mode.

    Args:
        stdscr (curses.window): Main screen handle.
        action (str): Shell command string to execute.
        quiet (bool): Suppress header and footer banner messages if True.
    """
    curses.endwin()
    if not quiet:
        print(f"\n--- Running: {action} ---\n")
    try:
        subprocess.run(action, shell=True)
    except Exception as e:
        if not quiet:
            print(f"\nExecution Error: {e}")

    if not quiet:
        print("\n--------------------------------------------------")
        input("Execution complete. Press [ENTER] to return to menu...")

    stdscr.clear()
    stdscr.refresh()


def run_action_in_window(stdscr, action, title, theme, stream=False):
    """
    Execute command or function and display output in scrolling popup window.

    Args:
        stdscr (curses.window): Main screen handle.
        action (str | Callable): Shell command string or Python function.
        title (str): Header title for action output box.
        theme (dict): Active theme color mapping.
        stream (bool): Real-time streaming updates if True.
    """
    height, width = stdscr.getmaxyx()
    box_h = max(10, int(height * 0.8))
    box_w = max(40, int(width * 0.8))
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    max_visible_lines = box_h - 4

    def draw_window_frame(
        status_footer=" [UP/DN/PgUp/PgDn]: Scroll | [ESC/ENTER]: Close ",
    ):
        """Draw window border and frame labels."""
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        header = f" Output: {title} "
        safe_addstr(
            win,
            0,
            max(2, (box_w - len(header)) // 2),
            header,
            theme["title"] | curses.A_BOLD,
        )
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(status_footer)) // 2),
            status_footer,
            theme["footer"],
        )

    def sanitize_line(line):
        """Expand tabs and filter printable characters."""
        line = line.expandtabs(4)
        return "".join(c for c in line if c.isprintable())

    output_lines = []

    if callable(action):
        try:
            res = action()
            output_lines = [sanitize_line(l) for l in str(res).splitlines()]
        except Exception as e:
            output_lines = [f"Python Action Error: {e}"]

    elif stream:
        try:
            process = subprocess.Popen(
                action,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            last_update = 0.0
            for line in process.stdout:
                output_lines.append(sanitize_line(line.rstrip("\r\n")))
                now = time.time()
                if now - last_update > 0.033:
                    scroll_offset = max(0, len(output_lines) - max_visible_lines)
                    draw_window_frame(" [ Executing... Please wait ] ")
                    for i in range(max_visible_lines):
                        line_idx = scroll_offset + i
                        if line_idx < len(output_lines):
                            safe_addstr(
                                win,
                                i + 2,
                                2,
                                output_lines[line_idx],
                                theme["text"],
                            )
                    win.refresh()
                    last_update = now
            process.wait()
        except Exception as e:
            output_lines.append(f"Execution Error: {e}")

    else:
        draw_window_frame(" Running... Please wait ")
        win.refresh()
        try:
            result = subprocess.run(
                action,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output_lines = [
                sanitize_line(l) for l in result.stdout.splitlines()
            ]
        except Exception as e:
            output_lines = [f"Error executing command: {e}"]

    if not output_lines:
        output_lines = ["[Command returned no output]"]

    scroll_offset = max(0, len(output_lines) - max_visible_lines)

    while True:
        draw_window_frame()
        for i in range(max_visible_lines):
            line_idx = scroll_offset + i
            if line_idx < len(output_lines):
                safe_addstr(win, i + 2, 2, output_lines[line_idx], theme["text"])

        win.refresh()
        key = win.getch()

        if key in [27, curses.KEY_ENTER, 10, 13]:
            break
        elif key == curses.KEY_UP and scroll_offset > 0:
            scroll_offset -= 1
        elif (
            key == curses.KEY_DOWN
            and scroll_offset < len(output_lines) - max_visible_lines
        ):
            scroll_offset += 1
        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - max_visible_lines)
        elif key == curses.KEY_NPAGE:
            scroll_offset = min(
                max(0, len(output_lines) - max_visible_lines),
                scroll_offset + max_visible_lines,
            )
        elif key in [curses.KEY_HOME, ord('g')]:
            scroll_offset = 0
        elif key in [curses.KEY_END, ord('G')]:
            scroll_offset = max(0, len(output_lines) - max_visible_lines)


def get_char_width(c):
    """
    Get the display width of a single character in terminal columns.
    """
    # Variation selectors have width 0
    if 0xFE00 <= ord(c) <= 0xFE0F:
        return 0
    # Non-ASCII characters (emojis, nerd fonts) usually have width 2 in terminals
    if ord(c) > 127:
        return 2
    return 1


def get_display_width(s):
    """
    Calculate the visual display width of a string on screen,
    ignoring variation selectors and counting non-ASCII chars as double-width.
    """
    if not s:
        return 0
    return sum(get_char_width(c) for c in s)


def resolve_glyph(glyph_str):
    """
    Resolve hex strings starting with '#' (e.g. #f07c) to their unicode characters.
    """
    if glyph_str.startswith("#"):
        try:
            hex_val = glyph_str[1:]
            for prefix in ["U+", "u+", "0x", "\\u", "\\"]:
                if hex_val.startswith(prefix):
                    hex_val = hex_val[len(prefix):]
            return chr(int(hex_val, 16))
        except Exception:
            return glyph_str
    return glyph_str


def interpolate_placeholders(text, config):
    """
    Interpolate dot-notation config keys and environment variables in strings.

    Args:
        text (str): Input string containing placeholder brackets.
        config (dict): Active configuration map for dot-notation resolution.

    Returns:
        str: String with resolved variable substitutions.
    """
    if not isinstance(text, str):
        return text

    templates_val = (
        get_config_value(config, "settings.templates_dir")
        or os.path.join(BASHMENU_DIR, "templates")
    )
    scripts_val = (
        get_config_value(config, "settings.scripts_dir")
        or os.path.join(BASHMENU_DIR, "scripts")
    )
    templates_val = re.sub(r"\{bashmenu_dir\}", BASHMENU_DIR, str(templates_val), flags=re.IGNORECASE)
    scripts_val = re.sub(r"\{bashmenu_dir\}", BASHMENU_DIR, str(scripts_val), flags=re.IGNORECASE)

    replacements = {
        "{user}": USERNAME,
        "{username}": USERNAME,
        "{home}": USER_HOME,
        "{bashrc}": BASHRC_PATH,
        "{vimrc}": VIMRC_PATH,
        "{bash_aliases}": BASH_ALIASES_PATH,
        "{bashmenu_dir}": BASHMENU_DIR,
        "{templates_dir}": templates_val,
        "{scripts_dir}": scripts_val,
    }

    for key, val in replacements.items():
        pattern = re.compile(re.escape(key), re.IGNORECASE)
        text = pattern.sub(str(val), text)

    matches = re.findall(r"\{([a-zA-Z0-9_\.]+)\}", text)
    if matches:
        for key_path in matches:
            config_val = get_config_value(config, key_path)
            if config_val:
                text = text.replace(f"{{{key_path}}}", str(config_val))
        # Re-resolve dynamic variables that may have been loaded from config
        for key, val in replacements.items():
            pattern = re.compile(re.escape(key), re.IGNORECASE)
            text = pattern.sub(str(val), text)

    # Resolve Nerd Fonts dynamic tags nf:FALLBACK:GLYPH
    use_nerd_fonts_val = get_config_value(config, "settings.use_nerd_fonts")
    use_nerd_fonts = False
    if isinstance(use_nerd_fonts_val, bool):
        use_nerd_fonts = use_nerd_fonts_val
    elif isinstance(use_nerd_fonts_val, str):
        use_nerd_fonts = use_nerd_fonts_val.lower() in ("true", "1", "yes")

    if text.startswith("nf:"):
        parts = text.split(":", 2)
        if len(parts) == 3:
            fallback = parts[1]
            glyph = parts[2]
            return resolve_glyph(glyph) if use_nerd_fonts else fallback

    nf_pattern = re.compile(r"\{nf:([^:]*):([^}]+)\}")
    for match in nf_pattern.finditer(text):
        full_match = match.group(0)
        fallback = match.group(1)
        glyph = match.group(2)
        resolved = resolve_glyph(glyph) if use_nerd_fonts else fallback
        text = text.replace(full_match, resolved)

    return text


PYTHON_FUNCTIONS = {
    "configure_autoexec": configure_autoexec,
}


def handle_python_action(action_name, stdscr, config, theme):
    """
    Dispatch and execute internal Python utility actions by name.

    Args:
        action_name (str): Identifier name of Python utility function.
        stdscr (curses.window): Main screen handle.
        config (dict): Configuration mapping.
        theme (dict): Theme pair mapping.
    """
    if action_name in PYTHON_FUNCTIONS:
        func = PYTHON_FUNCTIONS[action_name]
        run_action_in_window(stdscr, func, action_name, theme)


def process_item_action(
    selected_item, stdscr, config, theme, menu_stack, selected_rows
):
    """
    Execute menu entry action based on option dictionary definition type.

    Args:
        selected_item (dict): Menu option object containing action definition.
        stdscr (curses.window): Main screen handle.
        config (dict): Active configuration state.
        theme (dict): Active theme color pair mapping.
        menu_stack (list[dict]): Menu stack hierarchy.
        selected_rows (list[int]): Highlighted row selection stack.

    Returns:
        tuple[str | None, dict, dict]: ('EXIT' or None, new_theme, new_config).
    """
    global THEMES, THEME_ERROR
    item_type = selected_item.get("type")

    if item_type == "exit":
        return "EXIT", theme, config

    elif item_type == "back":
        if len(menu_stack) > 1:
            menu_stack.pop()
            selected_rows.pop()

    elif "submenu" in selected_item:
        menu_stack.append(selected_item["submenu"])
        selected_rows.append(0)

    elif "set_theme" in selected_item:
        new_theme = selected_item["set_theme"]
        config["theme"] = new_theme
        theme = apply_theme(new_theme)
        stdscr.bkgd(' ', theme["text"])
        save_config(config)

    elif item_type in ["message", "popup", "info"]:
        msg_title = interpolate_placeholders(
            selected_item.get("title", selected_item.get("label", "Notice")),
            config,
        )
        msg_text = interpolate_placeholders(
            selected_item.get("message", selected_item.get("text", "")), config
        )
        show_popup_message(stdscr, msg_title, msg_text, theme)

    elif item_type == "confirm":
        conf_title = interpolate_placeholders(
            selected_item.get("title", selected_item.get("label", "Confirm")),
            config,
        )
        conf_msg = interpolate_placeholders(
            selected_item.get(
                "message",
                selected_item.get(
                    "text", selected_item.get("prompt", "Are you sure?")
                ),
            ),
            config,
        )
        res = show_confirm_box(stdscr, conf_title, conf_msg, theme)
        target_action = None
        if res == "yes" and "on_yes" in selected_item:
            target_action = selected_item["on_yes"]
        elif res == "no" and "on_no" in selected_item:
            target_action = selected_item["on_no"]

        if target_action:
            return process_item_action(
                target_action, stdscr, config, theme, menu_stack, selected_rows
            )

    elif item_type in ["toggle", "config_toggle"]:
        key_path = selected_item.get("key", "")
        if key_path:
            title = selected_item.get(
                "title", selected_item.get("label", "Toggle Setting")
            )
            msg = interpolate_placeholders(
                selected_item.get("message", selected_item.get("prompt", f"Configure option {key_path}:")),
                config
            )
            res = show_toggle_box(stdscr, title, msg, theme)
            if res is not None:
                bool_val = res == "true"
                set_config_value(config, key_path, bool_val)
                save_config(config)

    elif item_type == "config":
        key_path = selected_item.get("key", "")
        if key_path:
            title = selected_item.get(
                "title", selected_item.get("label", "Edit Setting")
            )
            picker_mode = selected_item.get("picker")

            if picker_mode in ["file", "dir"]:
                existing_val = get_config_value(config, key_path)
                start_dir = None
                if existing_val:
                    interp_val = interpolate_placeholders(
                        str(existing_val).strip(), config
                    )
                    exp_val = os.path.abspath(os.path.expanduser(interp_val))
                    if os.path.isdir(exp_val):
                        start_dir = exp_val
                    elif os.path.isfile(exp_val) or os.path.isdir(
                        os.path.dirname(exp_val)
                    ):
                        start_dir = os.path.dirname(exp_val)

                if not start_dir:
                    start_dir = interpolate_placeholders(
                        selected_item.get("start_dir", "~"), config
                    )

                chosen_path = show_file_picker(
                    stdscr,
                    title,
                    start_dir,
                    mode=picker_mode,
                    default_val=existing_val if existing_val else None,
                    theme=theme,
                )
                if chosen_path is not None:
                    set_config_value(config, key_path, chosen_path)
                    save_config(config)
            else:
                prompt = selected_item.get("prompt", "Enter new value:")
                masked = selected_item.get("masked", False)
                current_val = get_config_value(config, key_path)

                new_val = show_input_box(
                    stdscr, title, prompt, current_val, theme, masked
                )
                if new_val is not None:
                    parsed_val = new_val.strip()
                    if parsed_val.lower() in ["true", "false"]:
                        parsed_val = parsed_val.lower() == "true"
                    elif parsed_val.isdigit():
                        parsed_val = int(parsed_val)
                    set_config_value(config, key_path, parsed_val)
                    save_config(config)

    elif item_type == "editor":
        target_file = interpolate_placeholders(
            selected_item.get("action", ""), config
        )
        show_ws = selected_item.get(
            "show_whitespace", False
        ) or selected_item.get("whitespace", False)

        tab_spaces_val = get_config_value(config, "settings.tab_to_spaces")
        tab_to_spaces = (
            tab_spaces_val.lower() in ("true", "1", "yes")
            if tab_spaces_val != ""
            else True
        )

        tabstop_val = get_config_value(config, "settings.tabstop")
        if not tabstop_val:
            tabstop_val = get_config_value(config, "settings.tab_size")

        try:
            tabstop = int(tabstop_val) if tabstop_val != "" else 8
        except ValueError:
            tabstop = 8

        if "tab_to_spaces" in selected_item:
            tab_to_spaces = bool(selected_item["tab_to_spaces"])
        if "tabstop" in selected_item:
            tabstop = int(selected_item["tabstop"])
        elif "tab_size" in selected_item:
            tabstop = int(selected_item["tab_size"])

        run_curses_editor(
            stdscr,
            target_file,
            theme,
            show_whitespace=show_ws,
            tab_to_spaces=tab_to_spaces,
            tabstop=tabstop,
        )

        theme, config = reload_environment(stdscr, menu_stack, selected_rows)

    elif item_type == "python":
        action_name = selected_item.get("action")
        handle_python_action(action_name, stdscr, config, theme)

    elif item_type == "inject_block":
        target_path_str = interpolate_placeholders(selected_item.get("target", ""), config)
        template_path_str = interpolate_placeholders(selected_item.get("template", ""), config)
        block_id = interpolate_placeholders(selected_item.get("block_id", "default"), config)

        if not target_path_str or not template_path_str:
            show_popup_message(
                stdscr,
                "Configuration Error",
                "Both 'target' and 'template' paths must be specified for dynamic block injection.",
                theme,
            )
        else:
            target_path = Path(os.path.abspath(os.path.expanduser(target_path_str)))
            if not os.path.isabs(template_path_str):
                template_path = Path(SCRIPT_DIR) / template_path_str
            else:
                template_path = Path(template_path_str)

            if not template_path.exists():
                show_popup_message(
                    stdscr,
                    "Template Error",
                    f"Template file not found:\n{template_path}",
                    theme,
                )
            else:
                try:
                    template_content = template_path.read_text()
                    interpolated_content = interpolate_placeholders(template_content, config)
                except Exception as e:
                    show_popup_message(
                        stdscr,
                        "Read Error",
                        f"Failed to read/interpolate template:\n{e}",
                        theme,
                    )
                    interpolated_content = None

                if interpolated_content is not None:
                    start_marker = f"# CODEBLOCK:{block_id}:START"
                    end_marker = f"# CODEBLOCK:{block_id}:END"
                    block_to_inject = f"\n{start_marker}\n{interpolated_content.strip()}\n{end_marker}\n"

                    target_exists = target_path.exists()
                    block_present = False
                    target_content = ""
                    if target_exists:
                        try:
                            target_content = target_path.read_text()
                            block_present = start_marker in target_content and end_marker in target_content
                        except Exception as e:
                            show_popup_message(
                                stdscr,
                                "Read Error",
                                f"Failed to read target file:\n{e}",
                                theme,
                            )
                            interpolated_content = None

                    if interpolated_content is not None:
                        if block_present:
                            msg = f"Code block '{block_id}' is already present in:\n{target_path}\n\n- Press YES to reinstall/update it.\n- Press NO to uninstall/remove it.\n- Press Cancel to abort."
                            choice = show_confirm_box(stdscr, "Update or Uninstall Block", msg, theme)
                        else:
                            msg = f"Would you like to inject code block '{block_id}' into:\n{target_path}?"
                            choice = show_confirm_box(stdscr, "Install Code Block", msg, theme)

                        if choice == "yes":
                            if block_present:
                                pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)
                                new_content = pattern.sub(block_to_inject.strip(), target_content)
                            else:
                                if target_content and not target_content.endswith("\n"):
                                    new_content = target_content + "\n" + block_to_inject
                                else:
                                    new_content = target_content + block_to_inject

                            try:
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                target_path.write_text(new_content)
                                if target_path.name.endswith(".sh") or "autoexec.sh" in target_path_str:
                                    target_path.chmod(0o755)
                                show_popup_message(
                                    stdscr,
                                    "Success",
                                    f"Code block '{block_id}' successfully installed/updated in:\n{target_path}",
                                    theme,
                                )
                            except Exception as e:
                                show_popup_message(
                                    stdscr,
                                    "Write Error",
                                    f"Failed to write target file:\n{e}",
                                    theme,
                                )
                        elif choice == "no" and block_present:
                            pattern = re.compile(rf"\n?{re.escape(start_marker)}.*?{re.escape(end_marker)}\n?", re.DOTALL)
                            new_content = pattern.sub("", target_content)
                            try:
                                target_path.write_text(new_content)
                                show_popup_message(
                                    stdscr,
                                    "Success",
                                    f"Code block '{block_id}' successfully removed from:\n{target_path}",
                                    theme,
                                )
                            except Exception as e:
                                show_popup_message(
                                    stdscr,
                                    "Write Error",
                                    f"Failed to write target file:\n{e}",
                                    theme,
                                )

    elif item_type in ["command", "script"]:
        mode = selected_item.get("user_mode")
        if mode == "root" and not is_root():
            show_popup_message(
                stdscr,
                "Permission Denied",
                "This operation requires root permissions (run with sudo).",
                theme,
            )
        else:
            action_str = interpolate_placeholders(
                selected_item.get("action", ""), config
            )

            # Check if script should launch in-process (external: false)
            external_val = selected_item.get("external", True)
            is_external = True
            if isinstance(external_val, bool):
                is_external = external_val
            elif isinstance(external_val, str):
                is_external = external_val.lower() not in ("false", "0", "no")

            if item_type == "script" and not is_external:
                script_file = action_str.split(" ", 1)[0]
                if script_file.endswith(".py"):
                    module_name = script_file[:-3]
                    if SCRIPT_DIR not in sys.path:
                        sys.path.insert(0, SCRIPT_DIR)
                    try:
                        import importlib
                        if module_name in sys.modules:
                            module = importlib.reload(sys.modules[module_name])
                        else:
                            module = importlib.import_module(module_name)
                        if hasattr(module, "main"):
                            module.main(stdscr)
                        else:
                            raise AttributeError(f"Module '{module_name}' does not implement 'main(stdscr)'.")
                    except Exception as e:
                        show_popup_message(stdscr, "In-Process Execution Error", str(e), theme)
                else:
                    show_popup_message(
                        stdscr,
                        "In-Process Execution Error",
                        f"Non-python script '{script_file}' cannot be run in-process.",
                        theme
                    )
            else:
                if item_type == "script":
                    script_parts = action_str.split(" ", 1)
                    script_path = os.path.join(SCRIPT_DIR, script_parts[0])
                    args = f" {script_parts[1]}" if len(script_parts) > 1 else ""
                    action_str = f'"{script_path}"{args}'

                if selected_item.get("interactive", False):
                    is_quiet = selected_item.get("quiet", False)
                    run_interactive_action(stdscr, action_str, quiet=is_quiet)
                else:
                    run_action_in_window(
                        stdscr,
                        action_str,
                        interpolate_placeholders(
                            selected_item.get("label", ""), config
                        ),
                        theme,
                        stream=selected_item.get("stream", False),
                    )

    if selected_item.get("refresh", False):
        theme, config = reload_environment(stdscr, menu_stack, selected_rows)

    return None, theme, config


def main(stdscr):
    """
    Main curses execution loop rendering menu interface and handling input.

    Args:
        stdscr (curses.window): Curses main window handle provided by wrapper.
    """
    global THEMES, THEME_ERROR
    curses.curs_set(0)
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)

    stdscr.keypad(True)

    config, config_err = load_config()
    theme = apply_theme(config.get("theme", "dracula"))
    stdscr.bkgd(' ', theme["text"])
    stdscr.clear()
    stdscr.refresh()

    if THEME_ERROR:
        show_popup_message(stdscr, "Theme File Error", THEME_ERROR, theme)
    if config_err:
        show_popup_message(stdscr, "Config File Error", config_err, theme)

    main_menu, menu_err = load_menu()
    inject_dynamic_menus(main_menu)

    if menu_err:
        show_popup_message(stdscr, "Menu File Error", menu_err, theme)

    menu_stack = [main_menu]
    selected_rows = [0]

    marquee_offset = 0
    marquee_pause_ticks = 4
    last_row = -1
    last_menu_len = -1

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        current_menu = menu_stack[-1]
        current_row = selected_rows[-1]
        options = current_menu.get("options", [])

        if current_row != last_row or len(menu_stack) != last_menu_len:
            marquee_offset = 0
            marquee_pause_ticks = 4
            last_row = current_row
            last_menu_len = len(menu_stack)

        show_shortcuts_val = get_config_value(
            config, "settings.show_menu_shortcuts"
        )
        show_shortcuts = (
            show_shortcuts_val.lower() in ("true", "1", "yes")
            if show_shortcuts_val != ""
            else True
        )

        stdscr.attron(theme["border"])
        stdscr.border(0)
        stdscr.attroff(theme["border"])

        title_text = (
            f" {interpolate_placeholders(current_menu.get('title', 'Menu'), config)} "
        )
        safe_addstr(
            stdscr,
            1,
            max(2, (width - len(title_text)) // 2),
            title_text,
            theme["title"] | curses.A_BOLD,
        )

        if height > 4:
            footer_left = (
                " [UP/DN]: Nav | [0-9/a-z]: Direct | [F5]: Keys | "
                "[F4]: Edit | [ESC]: Back "
                if show_shortcuts
                else " [UP/DN]: Nav | [ENTER]: Select | [F5]: Keys | "
                "[F4]: Edit | [ESC]: Back "
            )
            safe_addstr(stdscr, height - 2, 2, footer_left, theme["footer"])

            all_badges = [
                f"Ver: [v{__version__}]",
                f"User: [{USERNAME}]",
                f"Mode: [{'ROOT' if is_root() else 'USER'}]",
                f"Host: [{HOSTNAME}]",
                f"IP: [{PRIMARY_IP}]",
            ]

            avail_w = width - 4 - len(footer_left)
            selected_badges = []
            for b in all_badges:
                candidate = " | ".join(reversed(selected_badges + [b]))
                if len(candidate) + 2 <= avail_w:
                    selected_badges.append(b)
                else:
                    break

            if selected_badges:
                badge_str = f" {' | '.join(reversed(selected_badges))} "
                safe_addstr(
                    stdscr,
                    height - 2,
                    max(2, width - len(badge_str) - 2),
                    badge_str,
                    theme["accent"] | curses.A_BOLD,
                )

        options = current_menu.get("options", [])
        shortcut_map = (
            build_shortcut_map(len(options)) if show_shortcuts else {}
        )
        start_y = 3
        max_pad = max(1, width - 10)

        ind = interpolate_placeholders(theme.get("indicator", ">"), config)
        prefix_active = f"{ind} " if ind else "  "
        prefix_inactive = " " * len(prefix_active)

        has_icons = False
        max_icon_len = 0
        if any("icon" in opt for opt in options):
            icon_lens = []
            for opt in options:
                if "icon" in opt:
                    resolved = interpolate_placeholders(opt.get("icon", ""), config)
                    if resolved:
                        icon_lens.append(get_display_width(resolved))
            if icon_lens:
                has_icons = True
                max_icon_len = max(icon_lens)

        shortcut_len = 4 if show_shortcuts else 0
        icon_part_len = (max_icon_len + 1) if has_icons else 0
        avail_w = max(1, max_pad - shortcut_len - icon_part_len)

        for idx, option in enumerate(options):
            y = start_y + idx
            if y >= height - 3:
                break
            x = 4

            label = interpolate_placeholders(option.get("label", ""), config)
            if option.get("set_theme") == config.get("theme"):
                label += " (Active)"

            match = re.search(r"^(.*?)\s*(\[.*\])\s*$", label)
            if match:
                left_part = match.group(1).strip()
                right_part = match.group(2).strip()
            else:
                left_part = label
                right_part = ""

            prefix = prefix_active if idx == current_row else prefix_inactive

            if right_part:
                left_avail_w = avail_w - len(right_part) - 2
                if left_avail_w < 15:
                    left_avail_w = avail_w
                    right_part = ""
            else:
                left_avail_w = avail_w

            if idx == current_row and len(left_part) > left_avail_w:
                padded_text = left_part + (" " * left_avail_w) + left_part[:left_avail_w]
                scroll_text = padded_text[marquee_offset : marquee_offset + left_avail_w]
                if right_part:
                    spaces = avail_w - len(scroll_text) - len(right_part)
                    disp_label = f"{scroll_text}{' ' * spaces}{right_part}"
                else:
                    disp_label = f"{scroll_text:<{avail_w}}"
            else:
                if right_part:
                    if len(left_part) + 2 + len(right_part) <= avail_w:
                        spaces = avail_w - len(left_part) - len(right_part)
                        disp_label = f"{left_part}{' ' * spaces}{right_part}"
                    elif len(left_part) + 2 < avail_w:
                        max_right_w = avail_w - len(left_part) - 2
                        if (
                            max_right_w >= 3
                            and right_part.startswith("[")
                            and right_part.endswith("]")
                        ):
                            inner_w = max_right_w - 2
                            truncated_right = f"[{right_part[1:-1][:inner_w]}]"
                        elif max_right_w >= 1:
                            truncated_right = right_part[:max_right_w]
                        else:
                            truncated_right = ""

                        if truncated_right:
                            spaces = (
                                avail_w - len(left_part) - len(truncated_right)
                            )
                            disp_label = f"{left_part}{' ' * spaces}{truncated_right}"
                        else:
                            disp_label = f"{left_part[:avail_w]:<{avail_w}}"
                    else:
                        disp_label = f"{left_part[:avail_w]:<{avail_w}}"
                else:
                    disp_label = f"{left_part[:avail_w]:<{avail_w}}"

            attr = (
                (theme["highlight"] | curses.A_BOLD)
                if idx == current_row
                else theme["text"]
            )

            # 1. Print prefix
            safe_addstr(stdscr, y, x, prefix, attr)
            curr_x = x + len(prefix)

            # 2. Print shortcut if showing
            if show_shortcuts:
                shortcut_char = get_option_shortcut(idx)
                if shortcut_char:
                    badge_str = f"[{shortcut_char}]"
                    badge_attr = (
                        (theme["shortcut_key"] | curses.A_BOLD)
                        if idx != current_row
                        else (theme["highlight"] | curses.A_BOLD)
                    )
                    safe_addstr(stdscr, y, curr_x, badge_str, badge_attr)
                    curr_x += len(badge_str)
                    safe_addstr(stdscr, y, curr_x, " ", attr)
                    curr_x += 1
                else:
                    safe_addstr(stdscr, y, curr_x, "    ", attr)
                    curr_x += 4

            # 3. Print icon if has_icons is True
            if has_icons:
                icon_str = option.get("icon", "")
                icon_resolved = interpolate_placeholders(icon_str, config) if icon_str else ""
                if icon_resolved:
                    safe_addstr(stdscr, y, curr_x, icon_resolved, attr)
                    curr_x += get_display_width(icon_resolved)
                    padding = " " * (max_icon_len - get_display_width(icon_resolved)) + " "
                    safe_addstr(stdscr, y, curr_x, padding, attr)
                    curr_x += len(padding)
                else:
                    padding = " " * (max_icon_len + 1)
                    safe_addstr(stdscr, y, curr_x, padding, attr)
                    curr_x += len(padding)

            # 4. Print label (disp_label)
            safe_addstr(stdscr, y, curr_x, disp_label, attr)

        stdscr.refresh()
        stdscr.timeout(250)
        key = stdscr.getch()

        if key == -1:
            if options and current_row < len(options):
                opt = options[current_row]
                lbl = interpolate_placeholders(opt.get("label", ""), config)
                if opt.get("set_theme") == config.get("theme"):
                    lbl += " (Active)"

                m = re.search(r"^(.*?)\s*(\[.*\])\s*$", lbl)
                if m:
                    lp = m.group(1).strip()
                    rp = m.group(2).strip()
                else:
                    lp = lbl
                    rp = ""

                if rp:
                    law = avail_w - len(rp) - 2
                    if law < 15:
                        law = avail_w
                else:
                    law = avail_w

                if len(lp) > law:
                    if marquee_pause_ticks > 0:
                        marquee_pause_ticks -= 1
                    else:
                        marquee_offset += 1
                        if marquee_offset >= len(lp) + law:
                            marquee_offset = 0
                            marquee_pause_ticks = 4
            continue

        if key == curses.KEY_UP:
            selected_rows[-1] = (
                (current_row - 1) % len(options) if options else 0
            )

        elif key == curses.KEY_DOWN:
            selected_rows[-1] = (
                (current_row + 1) % len(options) if options else 0
            )

        elif key in [curses.KEY_PPAGE, curses.KEY_HOME]:
            selected_rows[-1] = 0

        elif key in [curses.KEY_NPAGE, curses.KEY_END]:
            selected_rows[-1] = len(options) - 1 if options else 0

        elif key == curses.KEY_F5:
            show_shortcuts = not show_shortcuts
            set_config_value(
                config, "settings.show_menu_shortcuts", show_shortcuts
            )
            save_config(config)

        elif show_shortcuts and key in shortcut_map:
            target_idx = shortcut_map[key]
            selected_rows[-1] = target_idx
            selected_item = options[target_idx]
            stdscr.timeout(-1)
            res, theme, config = process_item_action(
                selected_item, stdscr, config, theme, menu_stack, selected_rows
            )
            if res == "EXIT":
                break

        elif key == curses.KEY_F4:
            stdscr.timeout(-1)
            try:
                import menuedit
                menuedit.main(stdscr)
            except Exception as e:
                show_popup_message(stdscr, "Error Running Editor", str(e), theme)
            theme, config = reload_environment(
                stdscr, menu_stack, selected_rows
            )

        elif key in [curses.KEY_ENTER, 10, 13]:
            if not options:
                continue

            selected_item = options[current_row]
            stdscr.timeout(-1)
            res, theme, config = process_item_action(
                selected_item, stdscr, config, theme, menu_stack, selected_rows
            )
            if res == "EXIT":
                break

        elif key == 27:
            if len(menu_stack) > 1:
                menu_stack.pop()
                selected_rows.pop()
            else:
                break


if __name__ == "__main__":
    is_tty = os.environ.get("TERM") == "linux" or not os.isatty(
        sys.stdout.fileno()
    )

    sys.stdout.write("\033[?1049h")
    sys.stdout.flush()

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    finally:
        if is_tty:
            sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()
        sys.exit(0)
