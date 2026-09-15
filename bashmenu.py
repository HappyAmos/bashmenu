#!/usr/bin/env LANG=en_US.UTF-8 /usr/local/bin/python3
"""
bashmenu.py - A lightweight TUI menu engine loaded from menu and theme files.

Loads menu structures from bashmenu.mnu, user settings from bashmenu.yml, and
color palettes from bashmenu.themes (supporting 256/16/8 color fallbacks).

Includes built-in hybrid text editor with Nano-style shortcuts, configurable
tabstop/spaces support, whitespace visibility toggle, themed interactive file/
directory chooser modal, Yes/No/Cancel confirmation dialogs, dynamic YAML dot-
notation variable interpolation, item hotkey shortcuts, and ymlcheck validator.
"""
__version__ = "0.0.1"
__author__ = "HappyAmos"

import contextlib
import copy
import curses
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
import unicodedata
from pathlib import Path
import yaml
import bashmenu_ui
import bashedit

# Speed up ESC key response time (25ms instead of default 1000ms)
os.environ.setdefault("ESCDELAY", "25")

# Absolute path resolution
BASHMENU_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASHMENU_DIR, "bashmenu.yml")
MENU_FILE = os.path.join(BASHMENU_DIR, "bashmenu.mnu")
THEME_FILE = os.path.join(BASHMENU_DIR, "bashmenu.themes")

# Import ymlcheck validator module if available in application directory
if BASHMENU_DIR not in sys.path:
    sys.path.insert(0, BASHMENU_DIR)

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

safe_isprintable = bashmenu_ui.safe_isprintable
safe_addstr = bashmenu_ui.safe_addstr
draw_shadow = bashmenu_ui.draw_shadow
show_popup_message = bashmenu_ui.show_popup_message
show_confirm_box = bashmenu_ui.show_confirm_box
show_toggle_box = bashmenu_ui.show_toggle_box
show_input_box = bashmenu_ui.show_input_box
show_file_picker = bashmenu_ui.show_file_picker
run_curses_editor = bashedit.run_curses_editor

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
    "version": __version__,
    "theme": "dracula",
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


def build_shortcut_map(options, show_shortcuts=True):
    """
    Build lookup table mapping shortcut key ASCII ordinals to option indexes,
    and a lookup table mapping option indexes to shortcut characters.
    Skips divider items so they don't consume/display shortcuts.

    Args:
        options (list[dict]): Options list.
        show_shortcuts (bool): True if shortcuts should be shown.

    Returns:
        tuple[dict[int, int], dict[int, str]]: (shortcut_map, idx_to_shortcut).
    """
    shortcut_map = {}
    idx_to_shortcut = {}
    if not show_shortcuts:
        return shortcut_map, idx_to_shortcut

    non_divider_idx = 0
    for idx, opt in enumerate(options):
        if opt.get("type") == "divider":
            continue
        shortcut_char = get_option_shortcut(non_divider_idx)
        if shortcut_char:
            idx_to_shortcut[idx] = shortcut_char
            shortcut_map[ord(shortcut_char)] = idx
            non_divider_idx += 1
    return shortcut_map, idx_to_shortcut


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
    "divider": (curses.COLOR_BLUE, -1),
}

THEMES, THEME_ERROR = load_themes()


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
    main_options = main_menu.get("options", [])
    start_idx = 0
    while start_idx < len(main_options) and main_options[start_idx].get("type") == "divider":
        start_idx += 1
    if start_idx >= len(main_options):
        start_idx = 0
    selected_rows.append(start_idx)

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
        return "".join(c for c in line if safe_isprintable(c)) # c.isprintable())

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
    
    # Use standard unicode classification:
    # 'W' (Wide) and 'F' (Fullwidth) are 2 columns wide on standard terminals.
    # 'A' (Ambiguous), 'Na' (Narrow), 'N' (Neutral), 'H' (Halfwidth) are 1 column.
    w = unicodedata.east_asian_width(c)
    if w in ("W", "F"):
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
    Resolve hex strings starting with '#' or standard hex prefixes to their unicode characters.
    """
    if not isinstance(glyph_str, str) or not glyph_str:
        return glyph_str

    # Attempt to peel off leading '#' if present
    temp_str = glyph_str
    has_hash = False
    if temp_str.startswith("#"):
        has_hash = True
        temp_str = temp_str[1:]

    # List of recognized hex prefixes
    prefixes = ["U+", "u+", "0x", "0X", "\\u", "\\U", "\\"]

    # Try with a prefix (either directly or after stripping '#')
    for prefix in prefixes:
        if temp_str.startswith(prefix):
            try:
                hex_val = temp_str[len(prefix):]
                val = int(hex_val, 16)
                if val <= 0x10FFFF:
                    return chr(val)
                return bytes.fromhex(hex_val).decode("utf-8")
            except Exception:
                pass

    # If it was just prefixed by '#' but has no other prefix (e.g., '#e7f0' or '#EE9FB0')
    if has_hash:
        try:
            val = int(temp_str, 16)
            if val <= 0x10FFFF:
                return chr(val)
            return bytes.fromhex(temp_str).decode("utf-8")
        except Exception:
            pass

    # Direct check if the original string starts directly with any of the prefixes
    for prefix in prefixes:
        if glyph_str.startswith(prefix):
            try:
                hex_val = glyph_str[len(prefix):]
                val = int(hex_val, 16)
                if val <= 0x10FFFF:
                    return chr(val)
                return bytes.fromhex(hex_val).decode("utf-8")
            except Exception:
                pass

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

    # Determine if terminal is unicode-capable and not raw Linux console
    is_linux_console = os.environ.get("TERM") == "linux"
    encoding = ""
    try:
        encoding = sys.stdout.encoding or ""
    except Exception:
        pass
    if not encoding:
        import locale
        try:
            encoding = locale.getpreferredencoding() or ""
        except Exception:
            pass
    supports_unicode = "UTF" in encoding.upper() or "utf" in encoding.upper()
    can_display_unicode = supports_unicode and not is_linux_console

    def resolve_nf_parts(char, nerd_font, emoji):
        # 1. Try Emoji (if unicode-capable terminal)
        if can_display_unicode and emoji:
            return emoji
        # 2. Try Nerd Font (if unicode-capable terminal and enabled)
        if can_display_unicode and use_nerd_fonts and nerd_font:
            return resolve_glyph(nerd_font)
        # 3. Try plain text character
        if char:
            return char
        # 4. Fallback to empty string
        return ""

    nf_pattern = re.compile(r"\{nf:([^}]+)\}")
    for match in nf_pattern.finditer(text):
        full_match = match.group(0)
        content = match.group(1)
        parts = content.split(":")
        resolved = full_match
        if len(parts) == 2:
            resolved = resolve_nf_parts("", parts[0], parts[1])
        elif len(parts) == 3:
            resolved = resolve_nf_parts(parts[0], parts[1], parts[2])
        text = text.replace(full_match, resolved)

    return text


def resolve_dynamic_directives(stdscr, action_str, selected_item, config, theme):
    """
    Check for {param}, {file_picker}, and {dir_picker} directives in action_str,
    prompt the user using curses modals, and substitute the values.

    Returns:
        str | None: The fully resolved action string, or None if any dialog was cancelled.
    """
    if not isinstance(action_str, str):
        return action_str

    # Helper to parse starting directory from string prefix of the directive
    def find_start_dir_and_pattern(directive_name):
        prefix = action_str.split(directive_name, 1)[0]
        parts = prefix.split()
        if parts:
            last_arg = parts[-1]
            last_arg_clean = last_arg.strip('"\'').rstrip("/").strip()
            exp_path = os.path.abspath(os.path.expanduser(last_arg_clean))
            if os.path.isdir(exp_path):
                # Found a valid starting directory from prefix path!
                quote_offset = last_arg.find(last_arg_clean)
                if quote_offset == -1:
                    quote_offset = 0
                pattern_prefix = last_arg[quote_offset:]
                full_pattern = pattern_prefix + directive_name
                return exp_path, full_pattern
        
        # Fallback to start_dir configuration or home
        fallback_dir = interpolate_placeholders(
            selected_item.get("start_dir", "~"), config
        )
        return os.path.abspath(os.path.expanduser(fallback_dir)), directive_name

    # 1. Resolve {param}
    if "{param}" in action_str:
        title = selected_item.get("title", "")
        prompt = selected_item.get("prompt", "Enter a parameter:")
        masked = selected_item.get("masked", False)
        param_val = show_input_box(stdscr, title, prompt, "", theme, masked)
        if param_val is None:
            return None
        action_str = action_str.replace("{param}", param_val)

    # 2. Resolve {file_picker}
    if "{file_picker}" in action_str:
        title = selected_item.get("title", "Select File")
        start_dir, pattern_to_replace = find_start_dir_and_pattern("{file_picker}")
        chosen_path = show_file_picker(
            stdscr, title, start_dir, mode="file", theme=theme
        )
        if chosen_path is None:
            return None
        action_str = action_str.replace(pattern_to_replace, chosen_path)

    # 3. Resolve {dir_picker}
    if "{dir_picker}" in action_str:
        title = selected_item.get("title", "Select Directory")
        start_dir, pattern_to_replace = find_start_dir_and_pattern("{dir_picker}")
        chosen_path = show_file_picker(
            stdscr, title, start_dir, mode="dir", theme=theme
        )
        if chosen_path is None:
            return None
        action_str = action_str.replace(pattern_to_replace, chosen_path)

    return action_str


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
        submenu = selected_item["submenu"]
        menu_stack.append(submenu)
        sub_options = submenu.get("options", [])
        start_idx = 0
        while start_idx < len(sub_options) and sub_options[start_idx].get("type") == "divider":
            start_idx += 1
        if start_idx >= len(sub_options):
            start_idx = 0
        selected_rows.append(start_idx)

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

        # Resolve dynamic directives: {param}, {file_picker}, {dir_picker}
        resolved_file = resolve_dynamic_directives(
            stdscr, target_file, selected_item, config, theme
        )
        if resolved_file is None:
            # Cancelled by user
            return None, theme, config
        target_file = resolved_file

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
        resolved_target = resolve_dynamic_directives(
            stdscr, target_path_str, selected_item, config, theme
        )
        if resolved_target is None:
            return None, theme, config
        target_path_str = resolved_target

        template_path_str = interpolate_placeholders(selected_item.get("template", ""), config)
        resolved_template = resolve_dynamic_directives(
            stdscr, template_path_str, selected_item, config, theme
        )
        if resolved_template is None:
            return None, theme, config
        template_path_str = resolved_template

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
                template_path = Path(BASHMENU_DIR) / template_path_str
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

            # Resolve dynamic directives: {param}, {file_picker}, {dir_picker}
            resolved_action = resolve_dynamic_directives(
                stdscr, action_str, selected_item, config, theme
            )
            if resolved_action is None:
                # Cancelled by user
                if selected_item.get("refresh", False):
                    theme, config = reload_environment(stdscr, menu_stack, selected_rows)
                return None, theme, config
            action_str = resolved_action

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
                    if BASHMENU_DIR not in sys.path:
                        sys.path.insert(0, BASHMENU_DIR)
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
                    script_path = os.path.join(BASHMENU_DIR, script_parts[0])
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
    main_options = main_menu.get("options", [])
    start_idx = 0
    while start_idx < len(main_options) and main_options[start_idx].get("type") == "divider":
        start_idx += 1
    if start_idx >= len(main_options):
        start_idx = 0
    selected_rows = [start_idx]

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
        shortcut_map, idx_to_shortcut = build_shortcut_map(options, show_shortcuts)
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
                    resolved = resolve_glyph(resolved)
                    if resolved:
                        icon_lens.append(get_display_width(resolved))
            if icon_lens:
                has_icons = True
                max_icon_len = max(icon_lens)

        shortcut_len = 4 if show_shortcuts else 0
        icon_part_len = (max_icon_len + 2) if has_icons else 0
        avail_w = max(1, max_pad - shortcut_len - icon_part_len)

        for idx, option in enumerate(options):
            y = start_y + idx
            if y >= height - 3:
                break
            x = 4

            if option.get("type") == "divider":
                length = option.get("length", 40)
                try:
                    length = int(length)
                except (ValueError, TypeError):
                    length = 40
                char = option.get("char", "-")
                if not char:
                    char = "-"
                divider_str = (char * length)[:length] if len(char) > 0 else "-" * length
                divider_x = 4 + len(prefix_inactive)
                max_w = width - divider_x - 4
                if len(divider_str) > max_w:
                    divider_str = divider_str[:max_w]
                safe_addstr(stdscr, y, divider_x, divider_str, theme.get("divider", theme.get("border", theme["text"])))
                continue

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
                shortcut_char = idx_to_shortcut.get(idx)
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
                icon_resolved = resolve_glyph(icon_resolved)
                if icon_resolved:
                    safe_addstr(stdscr, y, curr_x, icon_resolved, attr)
                    curr_x += get_display_width(icon_resolved)
                    padding = " " * (max_icon_len - get_display_width(icon_resolved)) + "  "
                    safe_addstr(stdscr, y, curr_x, padding, attr)
                    curr_x += len(padding)
                else:
                    padding = " " * (max_icon_len + 2)
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
            orig = selected_rows[-1]
            idx = (orig - 1) % len(options) if options else 0
            while idx != orig and options[idx].get("type") == "divider":
                idx = (idx - 1) % len(options)
            if options and options[idx].get("type") != "divider":
                selected_rows[-1] = idx

        elif key == curses.KEY_DOWN:
            orig = selected_rows[-1]
            idx = (orig + 1) % len(options) if options else 0
            while idx != orig and options[idx].get("type") == "divider":
                idx = (idx + 1) % len(options)
            if options and options[idx].get("type") != "divider":
                selected_rows[-1] = idx

        elif key in [curses.KEY_PPAGE, curses.KEY_HOME]:
            idx = 0
            while idx < len(options) and options[idx].get("type") == "divider":
                idx += 1
            if idx < len(options):
                selected_rows[-1] = idx

        elif key in [curses.KEY_NPAGE, curses.KEY_END]:
            idx = len(options) - 1
            while idx >= 0 and options[idx].get("type") == "divider":
                idx -= 1
            if idx >= 0:
                selected_rows[-1] = idx

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
                menuedit.main(stdscr, target_path=list(selected_rows))
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
