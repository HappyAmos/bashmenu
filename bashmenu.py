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
__version__ = "0.0.1"
__author__ = "HappyAmos"

import contextlib
import copy
import curses
import getpass
import io
import os
import re
import socket
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import yaml

import bashedit
import bashmenu_ui

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
    except OSError:  # Catch socket/network-related failures safely (e.g. unreachable)
        return "127.0.0.1"


_last_battery_time = 0.0
_cached_battery = "N/A"


def get_battery_info():
    """
    Retrieve current battery percentage on Linux, macOS, or Windows with a 5-second cache.

    Returns:
        str: Battery percentage string (e.g. '84%'), or 'N/A' on failure or no battery.
    """
    global _last_battery_time, _cached_battery
    now = time.time()
    if now - _last_battery_time < 5.0:
        return _cached_battery

    _last_battery_time = now

    # 1. Try Linux /sys/class/power_supply
    try:
        capacities = []
        if os.path.exists("/sys/class/power_supply"):
            for name in os.listdir("/sys/class/power_supply"):
                type_path = os.path.join("/sys/class/power_supply", name, "type")
                is_bat = name.startswith("BAT")
                if not is_bat and os.path.exists(type_path):
                    with open(type_path, "r") as f:
                        if "battery" in f.read().lower():
                            is_bat = True
                if is_bat:
                    cap_path = os.path.join("/sys/class/power_supply", name, "capacity")
                    if os.path.exists(cap_path):
                        with open(cap_path, "r") as f:
                            cap = f.read().strip()
                            if cap.isdigit():
                                capacities.append(int(cap))
        if capacities:
            avg_cap = sum(capacities) // len(capacities)
            _cached_battery = f"{avg_cap}%"
            return _cached_battery
    except (OSError, ValueError, TypeError):  # Catch filesystem access or numeric parsing errors safely
        pass

    # 2. Try macOS pmset
    try:
        import subprocess
        out = subprocess.check_output(["pmset", "-g", "batt"], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
        match = re.search(r"(\d+)%", out)
        if match:
            _cached_battery = f"{match.group(1)}%"
            return _cached_battery
    except (OSError, subprocess.SubprocessError, AttributeError):  # Catch command execution or pattern extraction failures safely
        pass

    # 3. Try Windows WMIC
    try:
        import subprocess
        out = subprocess.check_output(["WMIC", "Path", "Win32_Battery", "Get", "EstimatedChargeRemaining"], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit():
                _cached_battery = f"{line}%"
                return _cached_battery
    except (OSError, subprocess.SubprocessError):  # Catch missing WMIC command or execution failures safely
        pass

    _cached_battery = "N/A"
    return _cached_battery


PRIMARY_IP = get_primary_ip()

# ==============================================================================
# DEFAULT CONFIGURATION
# Auto-created in 'bashmenu.yml' if the file does not exist on startup.
# ==============================================================================
DEFAULT_CONFIG = {
    "version": __version__,
    "theme": "dracula",
    "example_custom_settings": {
        "option_boolean": True,
        "option_filepath": "{bashmenu_dir}",
        "option_string": "A string of text",
    },
    "settings": {
        "check_for_updates": False,
        "templates_dir": "{bashmenu_dir}/templates",
        "scripts_dir": "{bashmenu_dir}/scripts",
        "ping_target": "1.1.1.1",
        "tab_to_spaces": True,
        "tabstop": 8,
        "show_menu_shortcuts": True,
        "use_nerd_fonts": False,
        "status_gutter": "{user} | {battery} | {date_time_24}",
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
            except OSError:  # Catch file IO errors when retrieving error context lines safely
                pass
            err_msg = (
                f"YAML Error in '{filename}'\n"
                f"Line: {line}, Column: {col}\n"
                f"Problem: {problem}{snippet}"
            )
            return None, err_msg
        return None, f"YAML Parse Error in '{filename}':\n{exc}"
    except (OSError, TypeError, ValueError) as e:  # Catch filesystem reading, type mismatches, or serialization issues safely
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
        except OSError as e:  # Catch file touch or permission modification errors on disk
            return f"Error creating autoexec.sh: {e}"

    try:
        bashrc_content = bashrc.read_text() if bashrc.exists() else ""
        if "# CODEBLOCK:autoexec.sh:START" not in bashrc_content:
            with bashrc.open("a") as f:
                f.write("\n" + BLOCK_AUTOEXEC + "\n")
        else:
            return "Autoexec sourcing block already present in ~/.bashrc."
    except OSError as e:  # Catch file read/write access errors on disk safely
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
    except (OSError, yaml.YAMLError, TypeError, ValueError):  # Catch file access, serialization, or type formatting errors safely
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

    saved_path = list(selected_rows)
    menu_stack.clear()
    selected_rows.clear()
    
    menu_stack.append(main_menu)
    curr_menu = main_menu
    
    for i, row_idx in enumerate(saved_path):
        opts = curr_menu.get("options", [])
        if not opts:
            selected_rows.append(0)
            break
            
        safe_idx = max(0, min(row_idx, len(opts) - 1))
        
        while safe_idx >= 0 and opts[safe_idx].get("type") == "divider":
            safe_idx -= 1
        if safe_idx < 0:
            safe_idx = 0
            while safe_idx < len(opts) and opts[safe_idx].get("type") == "divider":
                safe_idx += 1
            if safe_idx >= len(opts):
                safe_idx = 0
                
        selected_rows.append(safe_idx)
        
        # Only descend into a submenu if there is a next level in the saved path
        if i < len(saved_path) - 1:
            selected_item = opts[safe_idx] if safe_idx < len(opts) else {}
            if "submenu" in selected_item:
                curr_menu = selected_item["submenu"]
                menu_stack.append(curr_menu)
            else:
                break

    if not selected_rows:
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
        "divider",
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
        for theme_key in THEMES:
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
        subprocess.run(action, shell=True, check=False)
    except (OSError, subprocess.SubprocessError) as e:  # Catch missing shell executable or process creation failures safely
        if not quiet:
            print(f"\nExecution Error: {e}")

    if not quiet:
        print("\n--------------------------------------------------")
        input("Execution complete. Press [ENTER] to return to menu...")

    stdscr.clear()
    stdscr.refresh()


DYNAMIC_COLOR_PAIRS = {}
DYNAMIC_PAIR_KEYS = {}
NEXT_DYNAMIC_PAIR_SEQ = 0
ANSI_ESCAPE_RE = re.compile(
    r'\x1b\[([0-9;]*)m|'            # Standard SGR parameters (captured in group 1)
    r'\x1b\([a-zA-Z0-9]|'           # Character set selection (G0)
    r'\x1b\)[a-zA-Z0-9]|'           # Character set selection (G1)
    r'\x1b\[[0-9;]*[a-zA-Z]'        # General CSI escape sequences (cursor/screen control, etc.)
)


def get_color_pair(fg, bg):
    """
    Get or dynamically initialize a curses color pair for the given foreground
    and background color IDs. Supports -1 for default terminal colors.
    Uses a circular recycling buffer (slots 16-254) to respect ncurses 8-bit pair limits.
    """
    global NEXT_DYNAMIC_PAIR_SEQ
    if fg is None:
        fg = -1
    if bg is None:
        bg = -1

    key = (fg, bg)
    if key in DYNAMIC_COLOR_PAIRS:
        return DYNAMIC_COLOR_PAIRS[key]

    try:
        # Check if color_pair works (curses is initialized)
        curses.color_pair(0)
    except (curses.error, AttributeError):  # Catch uninitialized curses state gracefully (e.g., during tests)
        return 0

    # Slots 16 to 254 inclusive (239 slots total)
    start_slot = 16
    num_slots = 239

    slot_idx = start_slot + (NEXT_DYNAMIC_PAIR_SEQ % num_slots)
    NEXT_DYNAMIC_PAIR_SEQ += 1

    # If this slot was previously allocated to another color key, evict it from our cache
    if slot_idx in DYNAMIC_PAIR_KEYS:
        old_key = DYNAMIC_PAIR_KEYS[slot_idx]
        DYNAMIC_COLOR_PAIRS.pop(old_key, None)

    try:
        curses.init_pair(slot_idx, fg, bg)
        DYNAMIC_COLOR_PAIRS[key] = curses.color_pair(slot_idx)
        DYNAMIC_PAIR_KEYS[slot_idx] = key
        return DYNAMIC_COLOR_PAIRS[key]
    except (curses.error, TypeError, ValueError, AttributeError):  # Catch curses errors or invalid color parameter types safely
        pass

    try:
        return curses.color_pair(0)
    except (curses.error, AttributeError):  # Catch uninitialized curses or default pair access failures safely
        return 0


def get_style_attr(fg, bg, bold, underline, default_theme_attr):
    """
    Combine styling attributes and dynamic color pair into a single curses attribute.
    """
    attr = 0
    if bold:
        attr |= curses.A_BOLD
    if underline:
        attr |= curses.A_UNDERLINE

    if fg != -1 or bg != -1:
        attr |= get_color_pair(fg, bg)
    else:
        attr |= default_theme_attr

    return attr


def parse_ansi_line(line, default_theme_attr):
    """
    Parse a line containing ANSI color escape sequences into a list of (text, attr) segments.
    """
    segments = []
    current_fg = -1
    current_bg = -1
    current_bold = False
    current_underline = False

    pos = 0
    for match in ANSI_ESCAPE_RE.finditer(line):
        text_before = line[pos:match.start()]
        if text_before:
            attr = get_style_attr(
                current_fg, current_bg, current_bold, current_underline, default_theme_attr
            )
            segments.append((text_before, attr))

        param_str = match.group(1)
        # If param_str is None, it's a character-set or non-SGR sequence; discard it
        if param_str is not None:
            params = (
                [int(p) if p else 0 for p in param_str.split(";")]
                if param_str
                else [0]
            )

            idx = 0
            while idx < len(params):
                p = params[idx]
                if p == 0:
                    # Reset all text formatting and colors
                    current_fg = -1
                    current_bg = -1
                    current_bold = False
                    current_underline = False
                    idx += 1
                elif p == 1:
                    # Enable bold text attribute
                    current_bold = True
                    idx += 1
                elif p == 4:
                    # Enable underline text attribute
                    current_underline = True
                    idx += 1
                elif 30 <= p <= 37:
                    # Standard 8 foreground colors
                    current_fg = p - 30
                    idx += 1
                elif 40 <= p <= 47:
                    # Standard 8 background colors
                    current_bg = p - 40
                    idx += 1
                elif 90 <= p <= 97:
                    # High-intensity (bright) 8 foreground colors
                    current_fg = p - 90 + 8
                    idx += 1
                elif 100 <= p <= 107:
                    # High-intensity (bright) 8 background colors
                    current_bg = p - 100 + 8
                    idx += 1
                elif p == 38:
                    # Extended foreground color (256 colors or true color)
                    if idx + 2 < len(params) and params[idx + 1] == 5:
                        # 256-color mode: sequence is 38;5;n
                        current_fg = params[idx + 2]
                        idx += 3
                    elif idx + 4 < len(params) and params[idx + 1] == 2:
                        # True color mode: 38;2;r;g;b (not fully supported by base curses yet, so we skip it)
                        idx += 5
                    else:
                        idx += 1
                elif p == 48:
                    # Extended background color (256 colors or true color)
                    if idx + 2 < len(params) and params[idx + 1] == 5:
                        # 256-color mode: sequence is 48;5;n
                        current_bg = params[idx + 2]
                        idx += 3
                    elif idx + 4 < len(params) and params[idx + 1] == 2:
                        # True color mode: 48;2;r;g;b (skip unsupported sequence)
                        idx += 5
                    else:
                        idx += 1
                elif p == 39:
                    # Default foreground color
                    current_fg = -1
                    idx += 1
                elif p == 49:
                    # Default background color
                    current_bg = -1
                    idx += 1
                else:
                    # Ignore unsupported parameter
                    idx += 1

        pos = match.end()

    text_after = line[pos:]
    if text_after:
        attr = get_style_attr(
            current_fg, current_bg, current_bold, current_underline, default_theme_attr
        )
        segments.append((text_after, attr))

    return segments


def expand_tabs_in_segments(segments, tabstop=4):
    """
    Expand tabs in a list of (text, attr) segments, keeping track of the visual
    column position to align tab stops correctly regardless of ANSI escape codes.
    """
    expanded_segments = []
    col = 0
    for text, attr in segments:
        new_text_chars = []
        for c in text:
            if c == '\t':
                spaces_needed = tabstop - (col % tabstop)
                new_text_chars.append(' ' * spaces_needed)
                col += spaces_needed
            else:
                new_text_chars.append(c)
                col += get_char_width(c)
        expanded_segments.append(("".join(new_text_chars), attr))
    return expanded_segments


def process_line_to_segments(line, theme_text):
    """
    Expand tabs, parse ANSI colors, sanitize text content, and return
    a list of (text, attr) segments.
    """
    raw_segments = parse_ansi_line(line, theme_text)
    tab_aligned_segments = expand_tabs_in_segments(raw_segments, tabstop=4)

    sanitized_segments = []
    for text, attr in tab_aligned_segments:
        san_text = "".join(c for c in text if safe_isprintable(c))
        if san_text:
            sanitized_segments.append((san_text, attr))

    if not sanitized_segments:
        sanitized_segments = [("", theme_text)]

    return sanitized_segments


def safe_addstr_segments(win, y, start_x, segments):
    """
    Safely write a line composed of multiple (text, attr) segments starting at (y, start_x).
    """
    h, w = win.getmaxyx()
    if y >= h or start_x >= w:
        return

    current_x = start_x
    for text, attr in segments:
        if current_x >= w:
            break

        fit_text = []
        for c in text:
            char_w = get_char_width(c)
            limit = w - 1 if y == h - 1 else w
            if current_x + char_w > limit:
                break
            fit_text.append(c)
            current_x += char_w

        if fit_text:
            try:
                win.addstr(y, start_x, "".join(fit_text), attr)
            except curses.error:
                pass
            start_x = current_x


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

    output_lines = []

    if callable(action):
        try:
            res = action()
            output_lines = [process_line_to_segments(l, theme["text"]) for l in str(res).splitlines()]
        except Exception as e:  # noqa: BLE001
            # Broad exception catch is required here because custom callable actions can raise
            # arbitrary exceptions, and we must ensure the interface does not crash.
            output_lines = [process_line_to_segments(f"Python Action Error: {e}", theme["text"])]

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
                output_lines.append(process_line_to_segments(line.rstrip("\r\n"), theme["text"]))
                now = time.time()
                if now - last_update > 0.033:
                    scroll_offset = max(0, len(output_lines) - max_visible_lines)
                    draw_window_frame(" [ Executing... Please wait ] ")
                    for i in range(max_visible_lines):
                        line_idx = scroll_offset + i
                        if line_idx < len(output_lines):
                            safe_addstr_segments(
                                win,
                                i + 2,
                                2,
                                output_lines[line_idx],
                            )
                    win.refresh()
                    last_update = now
            process.wait()
        except (OSError, subprocess.SubprocessError) as e:  # Catch process execution failures (e.g. missing binary or execution permissions)
            output_lines.append(process_line_to_segments(f"Execution Error: {e}", theme["text"]))

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
                check=False,
            )
            output_lines = [
                process_line_to_segments(l, theme["text"]) for l in result.stdout.splitlines()
            ]
        except (OSError, subprocess.SubprocessError) as e:  # Catch shell invocation or process creation failures safely
            output_lines = [process_line_to_segments(f"Error executing command: {e}", theme["text"])]

    if not output_lines:
        output_lines = [process_line_to_segments("[Command returned no output]", theme["text"])]

    scroll_offset = max(0, len(output_lines) - max_visible_lines)

    while True:
        draw_window_frame()
        for i in range(max_visible_lines):
            line_idx = scroll_offset + i
            if line_idx < len(output_lines):
                safe_addstr_segments(win, i + 2, 2, output_lines[line_idx])

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
            except (ValueError, UnicodeDecodeError, OverflowError):  # Catch invalid characters, out-of-range codepoints, or parsing issues safely
                pass

    # If it was just prefixed by '#' but has no other prefix (e.g., '#e7f0' or '#EE9FB0')
    if has_hash:
        try:
            val = int(temp_str, 16)
            if val <= 0x10FFFF:
                return chr(val)
            return bytes.fromhex(temp_str).decode("utf-8")
        except (ValueError, UnicodeDecodeError, OverflowError):  # Catch invalid hex or codepoint overflow safely
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
            except (ValueError, UnicodeDecodeError, OverflowError):  # Catch invalid characters, out-of-range codepoints, or parsing issues safely
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
        "{host}": HOSTNAME,
        "{user-mode}": "root" if is_root() else "user",
        "{version}": __version__,
        "{date_time_12}": time.strftime("%Y-%m-%d %I:%M:%S %p"),
        "{date_time_24}": time.strftime("%Y-%m-%d %H:%M:%S"),
        "{date}": time.strftime("%Y-%m-%d"),
        "{time_12}": time.strftime("%I:%M:%S %p"),
        "{time_24}": time.strftime("%H:%M:%S"),
        "{battery}": get_battery_info(),
        "{utc_seconds}": str(int(time.time())),
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
    except AttributeError:  # Catch cases where sys.stdout is overridden/mocked without standard attributes
        pass
    if not encoding:
        import locale
        try:
            encoding = locale.getpreferredencoding() or ""
        except (locale.Error, AttributeError, ValueError):  # Catch missing locale capabilities or invalid formats gracefully
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

    def parse_nf_tag(content):
        parts = content.split(":")
        char = ""
        nerd_font = ""
        emoji = ""

        if len(parts) == 3:
            char = parts[0]
            nerd_font = parts[1]
            emoji = parts[2]
        elif len(parts) == 2:
            p0, p1 = parts[0], parts[1]
            is_p0_hex = any(p0.startswith(pre) for pre in ["#", "U+", "u+", "0x", "0X", "\\u", "\\U", "\\"])
            is_p1_hex = any(p1.startswith(pre) for pre in ["#", "U+", "u+", "0x", "0X", "\\u", "\\U", "\\"])

            if not p1:  # Format is {nf:nerd_font:}
                nerd_font = p0
            elif not p0:  # Format is {nf::nerd_font}
                nerd_font = p1
            elif is_p0_hex:  # Format is {nf:nerd_font:emoji}
                nerd_font = p0
                emoji = p1
            elif is_p1_hex:  # Format is {nf:char:nerd_font}
                char = p0
                nerd_font = p1
            else:  # Fallback mapping
                char = p0
                nerd_font = p1
        elif len(parts) == 1:
            char = parts[0]

        return char, nerd_font, emoji

    nf_pattern = re.compile(r"\{nf:([^}]+)\}")
    for match in nf_pattern.finditer(text):
        full_match = match.group(0)
        content = match.group(1)
        char, nerd_font, emoji = parse_nf_tag(content)
        resolved = resolve_nf_parts(char, nerd_font, emoji)
        text = text.replace(full_match, resolved)

    # Resolve {window_width} and {window_height}
    if re.search(r"\{window_width\}", text, flags=re.IGNORECASE) or re.search(r"\{window_height\}", text, flags=re.IGNORECASE):
        try:
            cols = curses.COLS
            lines = curses.LINES
        except (AttributeError, NameError):  # Fall back to shutil if curses window state is uninitialized or missing
            import shutil
            term_size = shutil.get_terminal_size()
            cols = term_size.columns
            lines = term_size.lines
        text = re.sub(r"\{window_width\}", str(cols), text, flags=re.IGNORECASE)
        text = re.sub(r"\{window_height\}", str(lines), text, flags=re.IGNORECASE)

    # Resolve {ascii:decimal}
    ascii_pattern = re.compile(r"\{ascii:(\d+)\}", re.IGNORECASE)
    for match in ascii_pattern.finditer(text):
        full_match = match.group(0)
        try:
            val = int(match.group(1))
            if 0 <= val <= 255:
                resolved = bytes([val]).decode('cp437', errors='replace')
                text = text.replace(full_match, resolved)
        except (ValueError, OverflowError, UnicodeDecodeError):  # Catch out-of-bounds numeric conversion or decoding failures safely
            pass

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

    # 2. Resolve {file_picker} and {file_picker_new}
    has_picker_new = "{file_picker_new}" in action_str or "{file_picker:new}" in action_str
    has_picker_std = "{file_picker}" in action_str

    if has_picker_new or has_picker_std:
        directive = "{file_picker_new}" if "{file_picker_new}" in action_str else ("{file_picker:new}" if "{file_picker:new}" in action_str else "{file_picker}")
        title = selected_item.get("title", "Select File")
        start_dir, pattern_to_replace = find_start_dir_and_pattern(directive)
        allow_new = has_picker_new or selected_item.get("allow_new", False)
        chosen_path = show_file_picker(
            stdscr, title, start_dir, mode="file", theme=theme, allow_new=allow_new
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
    # THEMES and THEME_ERROR are read here from the module scope. No global declaration is needed as they are not mutated.
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
                    allow_new=selected_item.get("allow_new", False),
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
                except (OSError, KeyError, ValueError) as e:  # Catch filesystem access, formatting, or config key errors safely
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
                        except OSError as e:  # Catch filesystem read access errors safely
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
                            except OSError as e:  # Catch disk/filesystem write and permission errors safely
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
                            except OSError as e:  # Catch disk/filesystem write and permission errors safely
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
                    except Exception as e:  # noqa: BLE001
                        # Broad exception catch is required here because imported external scripts or dynamic python
                        # modules run-in-process can raise any user-defined exceptions, and we must handle them
                        # gracefully to prevent the host menu process from crashing.
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
    # THEMES and THEME_ERROR are read here from the module scope. No global declaration is needed as they are not mutated.
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
            footer_left_full = (
                " [UP/DN]: Nav | [0-9/a-z]: Direct | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back "
                if show_shortcuts
                else " [UP/DN]: Nav | [ENTER]: Select | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back "
            )

            # Determine left gutter splitting
            footer_left_top = ""
            footer_left_bottom = footer_left_full
            
            if len(footer_left_full) + 4 > width and height > 5:
                parts = footer_left_full.strip().split(" | ")
                mid = len(parts) // 2 + 1
                footer_left_top = " " + " | ".join(parts[:mid]) + " | "
                footer_left_bottom = " " + " | ".join(parts[mid:]) + " "
            elif len(footer_left_full) + 4 > width:
                footer_left_bottom = footer_left_full[:width - 4]

            if footer_left_top:
                safe_addstr(stdscr, height - 3, 2, footer_left_top, theme["footer"])
            safe_addstr(stdscr, height - 2, 2, footer_left_bottom, theme["footer"])

            status_gutter_raw = get_config_value(config, "settings.status_gutter")
            if not isinstance(status_gutter_raw, str):
                status_gutter_raw = "{user} | {battery} | {date_time_24}"

            raw_badges = [b.strip() for b in status_gutter_raw.split("|")]
            all_badges = [interpolate_placeholders(b, config) for b in raw_badges if b.strip()]

            avail_w_bottom = max(0, width - 4 - len(footer_left_bottom))
            avail_w_top = max(0, width - 4 - len(footer_left_top)) if height > 5 else 0

            candidate_all = " | ".join(all_badges)
            if all_badges and len(candidate_all) + 2 <= avail_w_bottom:
                badge_str = f" {candidate_all} "
                safe_addstr(
                    stdscr,
                    height - 2,
                    max(2, width - len(badge_str) - 2),
                    badge_str,
                    theme["accent"] | curses.A_BOLD,
                )
            elif all_badges:
                top_badges = []
                remaining_badges = []
                for i, b in enumerate(all_badges):
                    candidate = " | ".join(top_badges + [b])
                    if avail_w_top > 0 and len(candidate) + 2 <= avail_w_top:
                        top_badges.append(b)
                    else:
                        remaining_badges = all_badges[i:]
                        break
                
                bottom_badges = []
                for b in remaining_badges:
                    candidate = " | ".join(bottom_badges + [b])
                    if len(candidate) + 2 <= avail_w_bottom:
                        bottom_badges.append(b)
                    else:
                        break
                
                if top_badges:
                    badge_str = f" {' | '.join(top_badges)} "
                    safe_addstr(
                        stdscr,
                        height - 3,
                        max(2, width - len(badge_str) - 2),
                        badge_str,
                        theme["accent"] | curses.A_BOLD,
                    )
                if bottom_badges:
                    badge_str = f" {' | '.join(bottom_badges)} "
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
                if isinstance(length, str):
                    length = interpolate_placeholders(length, config)
                try:
                    length = int(length)
                except (ValueError, TypeError):
                    length = 40
                char = option.get("char", "-")
                if char:
                    char = interpolate_placeholders(char, config)
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

        elif key == curses.KEY_F1:
            help_path = os.path.join(BASHMENU_DIR, "bashmenu.md")
            stdscr.timeout(-1)
            run_interactive_action(stdscr, f"glow -p '{help_path}'", quiet=True)

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
            except Exception as e:  # noqa: BLE001
                # Broad exception catch is required here because the visual menu editor (menuedit)
                # is a complex interactive curses module that can raise a variety of runtime, key,
                # or formatting exceptions, and we must ensure the main menu gracefully survives.
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
