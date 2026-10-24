#!/usr/bin/env python3
"""
bashmenu.py - A lightweight TUI menu engine loaded from menu and theme files implemented in Textual.

Loads menu structures from bashmenu.mnu, user settings from bashmenu.yml, and
color palettes from bashmenu.themes.
"""

__version__ = "0.0.1"
__author__ = "HappyAmos"

import codecs
import contextlib
import copy
import curses
import datetime
import functools
import getpass
import importlib
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, ClassVar

import yaml
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.geometry import Region
from textual.screen import Screen
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Static

# Curses compatibility attributes for mocking/tests
if not hasattr(curses, "COLS"):
    curses.COLS = 80
if not hasattr(curses, "LINES"):
    curses.LINES = 24
if not hasattr(curses, "update_lines_cols"):
    curses.update_lines_cols = lambda: None

BASH_BIN = shutil.which("bash") or "/bin/bash"


def string_representer(dumper, data):
    """
    Custom YAML representer for strings to preserve double quotes.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    if "'" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, string_representer)
for d_name in ["Dumper", "SafeDumper", "CDumper", "CSafeDumper"]:
    try:
        cls = getattr(yaml, d_name)
        yaml.add_representer(str, string_representer, Dumper=cls)
    except AttributeError:
        pass

import bashmenu_ui

# Absolute path resolution
BASHMENU_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASHMENU_DIR, "bashmenu.yml")
MENU_FILE = os.path.join(BASHMENU_DIR, "bashmenu.mnu")
THEME_FILE = os.path.join(BASHMENU_DIR, "bashmenu.themes")

if BASHMENU_DIR not in sys.path:
    sys.path.insert(0, BASHMENU_DIR)
SCRIPTS_DIR = os.path.join(BASHMENU_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
NOTEBOOKS_DIR = os.path.join(BASHMENU_DIR, "notebooks")

try:
    import ymlcheck
except ImportError:
    ymlcheck = None


def resolve_notebook_path(raw_path: str | None = None, config: dict | None = None) -> str:
    """Resolve a notebook file path, checking the notebooks/ directory first."""
    if not raw_path:
        nb_default = os.path.join(NOTEBOOKS_DIR, "notes.yml")
        if os.path.exists(nb_default):
            return nb_default
        root_default = os.path.join(BASHMENU_DIR, "notes.yml")
        if os.path.exists(root_default):
            return root_default
        return nb_default

    interpolated = interpolate_placeholders(raw_path, config or {})
    expanded = os.path.expanduser(interpolated)
    if os.path.isabs(expanded):
        return expanded

    nb_candidate = os.path.join(NOTEBOOKS_DIR, expanded)
    if os.path.exists(nb_candidate):
        return nb_candidate
    root_candidate = os.path.join(BASHMENU_DIR, expanded)
    if os.path.exists(root_candidate):
        return root_candidate
    return nb_candidate


def resolve_existing_path(primary: Path, fallback: Path | None = None) -> str:
    """Return primary path if it exists, or fallback if primary does not exist and fallback does."""
    if primary.exists():
        return str(primary)
    if fallback and fallback.exists():
        return str(fallback)
    return str(primary)


@functools.lru_cache(maxsize=1)
def get_powershell_profile_path() -> str:
    """Return platform-appropriate PowerShell profile path."""
    home = Path.home()
    if sys.platform == "win32" or os.name == "nt":
        ps_core = home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        if ps_core.exists():
            return str(ps_core)
        ps_win = home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
        if ps_win.exists():
            return str(ps_win)
        return str(ps_core)
    ps_unix = home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"
    return str(ps_unix)


@functools.lru_cache(maxsize=1)
def get_shell_profile_path() -> str:
    """Resolve active login shell profile path, preferring existing files."""
    home = Path.home()
    for fname in [".bash_profile", ".bash_login", ".profile", ".zprofile", ".zshrc", ".bashrc"]:
        candidate = home / fname
        if candidate.is_file():
            return str(candidate)
    return str(home / (".bash_profile" if sys.platform == "darwin" else ".profile"))


USERNAME = getpass.getuser()
USER_HOME = str(Path.home())
BASHRC_PATH = str(Path.home() / ".bashrc")
VIMRC_PATH = str(Path.home() / ".vimrc")
NANORC_PATH = str(Path.home() / ".nanorc")
BASH_ALIASES_PATH = str(Path.home() / ".bash_aliases")
ZSHRC_PATH = str(Path.home() / ".zshrc")
PROFILE_PATH = str(Path.home() / ".profile")
BASH_PROFILE_PATH = str(Path.home() / ".bash_profile")
ZPROFILE_PATH = str(Path.home() / ".zprofile")
TERMUX_PROPERTIES_PATH = str(Path.home() / ".termux" / "termux.properties")
TERMUX_STORAGE_PATH = str(Path.home() / "storage")
PREFIX_PATH = os.environ.get(
    "PREFIX",
    "/data/data/com.termux/files/usr"
    if ("TERMUX_VERSION" in os.environ or "/com.termux/" in os.environ.get("PREFIX", ""))
    else "/usr",
)
APPDATA_PATH = os.environ.get("APPDATA", "")
USERPROFILE_PATH = os.environ.get("USERPROFILE", USER_HOME)
HOSTNAME = socket.gethostname()

safe_isprintable = bashmenu_ui.safe_isprintable
safe_curs_set = bashmenu_ui.safe_curs_set
safe_addstr = bashmenu_ui.safe_addstr
draw_shadow = bashmenu_ui.draw_shadow
show_popup_message = bashmenu_ui.show_popup_message
show_confirm_box = bashmenu_ui.show_confirm_box
show_toggle_box = bashmenu_ui.show_toggle_box
show_input_box = bashmenu_ui.show_input_box
show_file_picker = bashmenu_ui.show_file_picker


def run_curses_editor(*args, **kwargs):
    import bashedit

    return bashedit.run_curses_editor(*args, **kwargs)


get_visible_len = bashmenu_ui.get_visible_len
get_char_width = bashmenu_ui.get_char_width
get_display_width = bashmenu_ui.get_display_width
get_nerd_font_width = bashmenu_ui.get_nerd_font_width
is_pua_glyph = bashmenu_ui.is_pua_glyph
parse_formatting_to_segments = bashmenu_ui.parse_formatting_to_segments
safe_addstr_segments = bashmenu_ui.safe_addstr_segments
is_formatting_tag = bashmenu_ui.is_formatting_tag


def split_label_brackets(label):
    """
    Identify and split standard [brackets] used for right-aligned text.
    """
    if not isinstance(label, str):
        label = str(label)

    text = label.strip()
    if not text.endswith("]"):
        return label, ""

    n = len(text)
    brace_count = 0
    match_idx = -1

    for idx in range(n - 1, -1, -1):
        char = text[idx]
        if char == "]":
            brace_count += 1
        elif char == "[":
            brace_count -= 1
            if brace_count == 0:
                match_idx = idx
                break

    if match_idx != -1:
        left = text[:match_idx].rstrip()
        right = text[match_idx:]
        content = right[1:-1].strip()
        if is_formatting_tag(content):
            return label, ""
        return left, right

    return label, ""


def split_gutter_badges(gutter_str):
    """
    Split the status gutter string by pipe symbols ('|').
    """
    badges = []
    current_badge = []
    brace_count = 0

    for char in gutter_str:
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count = max(0, brace_count - 1)

        if char == "|" and brace_count == 0:
            badges.append("".join(current_badge).strip())
            current_badge = []
        else:
            current_badge.append(char)

    if current_badge:
        badges.append("".join(current_badge).strip())

    return [b for b in badges if b]


def truncate_to_visible_len(text, max_w, config=None):
    """Truncate text so its display width does not exceed max_w."""
    if not text or max_w <= 0:
        return ""
    if get_visible_len(text, config) <= max_w:
        return text
    low, high = 1, len(text)
    best = 0
    while low <= high:
        mid = (low + high) // 2
        if get_visible_len(text[:mid], config) <= max_w:
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    return text[:best]


def format_spread_gutter_line(line_items: list[str], max_w: int, config: dict | None = None) -> str:
    """Format items onto a single line, spreading them apart evenly across max_w with pipe delimiters."""
    if not line_items:
        return ""
    if len(line_items) == 1:
        return line_items[0]
    num_gaps = len(line_items) - 1
    item_lens = [get_visible_len(it, config) for it in line_items]
    tot_item_len = sum(item_lens)
    min_line_len = tot_item_len + num_gaps * 3
    if min_line_len >= max_w:
        return " | ".join(line_items)

    rem = max_w - min_line_len
    base_extra = rem // num_gaps
    extra = rem % num_gaps

    parts = []
    for i, it in enumerate(line_items):
        parts.append(it)
        if i < num_gaps:
            total_extra = base_extra + (1 if i < extra else 0)
            left_spaces = 1 + (total_extra // 2)
            right_spaces = 1 + (total_extra - (total_extra // 2))
            parts.append(f"{' ' * left_spaces}|{' ' * right_spaces}")
    return "".join(parts)


def wrap_gutter_items(items, max_w, max_lines=2, config=None, bottom_up=False, spread=False):
    """Wrap a list of gutter badge/action items separated by ' | ' into at most max_lines,
    treating each item as an atomic token and ensuring each line does not exceed max_w.

    If bottom_up is True, items are packed starting from the end of the list to fill
    the bottom line first with as many items as fit within max_w. Overflow items
    then fill the line(s) above, preserving left-to-right reading order within each line.

    If spread is True, items on each formatted line are spread apart across max_w
    evenly, with pipe delimiters separating the items.
    """
    if not items:
        return []

    cleaned_items = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned_items:
        return []

    if spread and max_lines == 2 and not bottom_up:
        # Check if all items can fit into 2 balanced lines
        mid = (len(cleaned_items) + 1) // 2
        line1_items = cleaned_items[:mid]
        line2_items = cleaned_items[mid:]
        l1_min = sum(get_visible_len(it, config) for it in line1_items) + max(0, len(line1_items) - 1) * 3
        l2_min = sum(get_visible_len(it, config) for it in line2_items) + max(0, len(line2_items) - 1) * 3
        if l1_min <= max_w and l2_min <= max_w:
            return [
                format_spread_gutter_line(line1_items, max_w, config),
                format_spread_gutter_line(line2_items, max_w, config),
            ]

    if bottom_up:
        reversed_lines = []
        remaining = list(cleaned_items)
        for _ in range(max_lines):
            if not remaining:
                break

            if get_visible_len(remaining[-1], config) > max_w:
                truncated = truncate_to_visible_len(remaining.pop(), max_w, config)
                reversed_lines.append(truncated)
                continue

            line_items = []
            while remaining:
                cand_items = [remaining[-1]] + line_items
                cand_str = " | ".join(cand_items)
                if get_visible_len(cand_str, config) <= max_w:
                    line_items.insert(0, remaining.pop())
                else:
                    break

            if line_items:
                line_str = format_spread_gutter_line(line_items, max_w, config) if spread else " | ".join(line_items)
                reversed_lines.append(line_str)
            else:
                truncated = truncate_to_visible_len(remaining.pop(), max_w, config)
                reversed_lines.append(truncated)

        return list(reversed(reversed_lines))

    lines = []
    current_line = []

    for item_str in cleaned_items:
        if not current_line:
            candidate = item_str
        else:
            candidate = " | ".join(current_line) + " | " + item_str

        cand_len = get_visible_len(candidate, config)
        if cand_len <= max_w:
            current_line.append(item_str)
        else:
            # Overlapping item drops to the next line
            if len(lines) < max_lines - 1:
                if current_line:
                    line_str = format_spread_gutter_line(current_line, max_w, config) if spread else " | ".join(current_line)
                    lines.append(line_str)
                    current_line = []
                if get_visible_len(item_str, config) <= max_w:
                    current_line.append(item_str)
                else:
                    current_line.append(truncate_to_visible_len(item_str, max_w, config))
            else:
                # Already reached maximum allowed lines (max_lines); stop accepting more items
                break

    if current_line and len(lines) < max_lines:
        line_str = format_spread_gutter_line(current_line, max_w, config) if spread else " | ".join(current_line)
        lines.append(line_str)

    return lines[:max_lines]


_primary_ip = None


def get_primary_ip():
    """Retrieve primary outbound IPv4 address with caching."""
    global _primary_ip, PRIMARY_IP
    if _primary_ip is not None:
        return _primary_ip
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.1)
            s.connect(("1.1.1.1", 80))
            _primary_ip = s.getsockname()[0]
    except OSError:
        _primary_ip = "127.0.0.1"
    PRIMARY_IP = _primary_ip
    return _primary_ip


_last_battery_time = 0.0
_cached_battery = "N/A"


def get_battery_info():
    """Retrieve current battery percentage with a 5-second cache."""
    global _last_battery_time, _cached_battery
    now = time.time()
    if now - _last_battery_time < 5.0:
        return _cached_battery

    _last_battery_time = now
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

        # macOS fallback via pmset
        if shutil.which("pmset"):
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=1, check=False)
            if res.returncode == 0 and res.stdout:
                m = re.search(r"(\d+)%", res.stdout)
                if m:
                    _cached_battery = f"{m.group(1)}%"
                    return _cached_battery

        # Termux fallback via termux-battery-status
        if shutil.which("termux-battery-status"):
            res = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=1, check=False)
            if res.returncode == 0 and res.stdout:
                import json

                data = json.loads(res.stdout)
                if "percentage" in data:
                    _cached_battery = f"{data['percentage']}%"
                    return _cached_battery
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        pass

    _cached_battery = "N/A"
    return _cached_battery


_last_battery_stat_time = 0.0
_cached_battery_stat = "N/A"


def get_battery_status():
    """Retrieve current battery charging/discharging status with a 5-second cache."""
    global _last_battery_stat_time, _cached_battery_stat
    now = time.time()
    if now - _last_battery_stat_time < 5.0:
        return _cached_battery_stat

    _last_battery_stat_time = now
    try:
        if os.path.exists("/sys/class/power_supply"):
            for name in os.listdir("/sys/class/power_supply"):
                type_path = os.path.join("/sys/class/power_supply", name, "type")
                is_bat = name.startswith("BAT")
                if not is_bat and os.path.exists(type_path):
                    with open(type_path, "r") as f:
                        if "battery" in f.read().lower():
                            is_bat = True
                if is_bat:
                    status_path = os.path.join("/sys/class/power_supply", name, "status")
                    if os.path.exists(status_path):
                        with open(status_path, "r") as f:
                            stat = f.read().strip()
                            if stat:
                                _cached_battery_stat = stat
                                return _cached_battery_stat

        # macOS fallback via pmset
        if shutil.which("pmset"):
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=1, check=False)
            if res.returncode == 0 and res.stdout:
                stdout_lower = res.stdout.lower()
                if "charging" in stdout_lower:
                    _cached_battery_stat = "Charging"
                elif "discharging" in stdout_lower:
                    _cached_battery_stat = "Discharging"
                elif "finishing charge" in stdout_lower or "charged" in stdout_lower:
                    _cached_battery_stat = "Full"
                return _cached_battery_stat

        # Termux fallback via termux-battery-status
        if shutil.which("termux-battery-status"):
            res = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=1, check=False)
            if res.returncode == 0 and res.stdout:
                import json

                data = json.loads(res.stdout)
                if "status" in data:
                    _cached_battery_stat = str(data["status"]).title()
                    return _cached_battery_stat
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        pass

    _cached_battery_stat = "N/A"
    return _cached_battery_stat


PRIMARY_IP = "127.0.0.1"

DEFAULT_CONFIG = {
    "version": __version__,
    "theme": "dracula",
    "user": {
        "example_boolean": True,
        "example_filepath": "{bashmenu_dir}",
        "example_string": "A string of text",
        "localip": "[b]{localip}[/b]",
        "postal_code": 49079,
    },
    "settings": {
        "cache_dir": "{home}/.cache/bashmenu",
        "check_for_updates": False,
        "plugins": {},
        "templates_dir": "{bashmenu_dir}/templates",
        "scripts_dir": "{bashmenu_dir}/scripts",
        "ping_target": "1.1.1.1",
        "tab_to_spaces": True,
        "tabstop": 8,
        "show_menu_shortcuts": True,
        "use_nerd_fonts": True,
        "nerd_font_width": "auto",
        "status_gutter": "{user} | {battery} | {date_time_24_short} | {user.localip}",
    },
}

BLOCK_AUTOEXEC = """# CODEBLOCK:autoexec.sh:START
if [ -f "$HOME/autoexec.sh" ]; then
    . "$HOME/autoexec.sh"
fi
# CODEBLOCK:autoexec.sh:END"""


def configure_autoexec():
    """Create autoexec.sh in user home and append sourcing logic to ~/.bashrc."""
    autoexec_path = Path.home() / "autoexec.sh"
    bashrc = Path(BASHRC_PATH)
    if not autoexec_path.exists():
        try:
            autoexec_path.touch()
            autoexec_path.chmod(0o755)
        except OSError as e:
            return f"Error creating autoexec.sh: {e}"

    try:
        bashrc_content = bashrc.read_text() if bashrc.exists() else ""
        if "# CODEBLOCK:autoexec.sh:START" not in bashrc_content:
            with bashrc.open("a") as f:
                f.write("\n" + BLOCK_AUTOEXEC + "\n")
        else:
            return "Autoexec sourcing block already present in ~/.bashrc."
    except OSError as e:
        return f"Error updating ~/.bashrc: {e}"

    return "Autoexec configuration completed successfully."


def deep_merge(dict1, dict2):
    """Recursively merge dict2 into dict1."""
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            deep_merge(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


def get_config_value(config, key_path, default=None):
    """Retrieve value from nested dict using dot-notation string.
    Supports optional 'app.' or 'bashmenu.' namespace prefixes.
    """
    if not key_path or not isinstance(key_path, str) or not isinstance(config, dict):
        return default
    keys = key_path.split(".")
    curr = config
    found = True
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            found = False
            break
    if found:
        return curr

    # If not found directly, check for 'app.' or 'bashmenu.' alias prefix
    if len(keys) > 1 and keys[0] in ("app", "bashmenu"):
        sub_curr = config
        for k in keys[1:]:
            if isinstance(sub_curr, dict) and k in sub_curr:
                sub_curr = sub_curr[k]
            else:
                return default
        return sub_curr

    return default


def set_config_value(config, key_path, value):
    """Set value in nested dict using dot-notation string.
    Supports optional 'app.' or 'bashmenu.' namespace prefixes.
    """
    if not key_path or not isinstance(key_path, str) or not isinstance(config, dict):
        return False
    keys = key_path.split(".")
    if len(keys) > 1 and keys[0] in ("app", "bashmenu") and keys[0] not in config:
        keys = keys[1:]
    curr = config
    for k in keys[:-1]:
        if k not in curr or not isinstance(curr[k], dict):
            curr[k] = {}
        curr = curr[k]
    curr[keys[-1]] = value
    return True


def resolve_glyph(glyph_def, config=None):
    """Resolve adaptive icon glyph string format '{nf:[char]:[hex]:[emoji]}'."""
    if not isinstance(glyph_def, str) or not glyph_def.startswith("{nf:"):
        return glyph_def

    inner = glyph_def[4:-1]
    parts = inner.split(":")

    def is_hex_token(t: str) -> bool:
        if not t:
            return False
        clean = t.lstrip("#$").replace("0x", "").strip()
        return bool(clean and all(c in "0123456789abcdefABCDEF" for c in clean))

    char_part = ""
    hex_part = ""
    emoji_part = ""

    if len(parts) >= 3:
        char_part = parts[0]
        hex_part = parts[1]
        emoji_part = ":".join(parts[2:])
    elif len(parts) == 2:
        if parts[0] == "":
            char_part = ""
            hex_part = parts[1]
            emoji_part = ""
        elif is_hex_token(parts[0]):
            char_part = ""
            hex_part = parts[0]
            emoji_part = parts[1]
        else:
            char_part = parts[0]
            hex_part = parts[1]
            emoji_part = ""
    elif len(parts) == 1:
        part = parts[0]
        if is_hex_token(part):
            char_part = ""
            hex_part = part
            emoji_part = ""
        else:
            char_part = part

    if not config:
        config, _ = load_config()
    use_nerd = get_config_value(config, "settings.use_nerd_fonts", False)

    if use_nerd:
        if emoji_part:
            if r"\u" in emoji_part.lower():
                with contextlib.suppress(Exception):
                    emoji_part = codecs.decode(emoji_part, "unicode-escape")
            return emoji_part
        if hex_part and is_hex_token(hex_part):
            try:
                hex_clean = hex_part.lstrip("#$").replace("0x", "").strip()
                if hex_clean:
                    return chr(int(hex_clean, 16))
            except ValueError:
                pass

    return char_part


_cmd_substitution_cache = {}
_CMD_CACHE_TTL = 30.0

COMMAND_PATTERN = re.compile(r"\{command:((?:[^{}]|\{[^{}]*\})+)\}")
ASCII_PATTERN = re.compile(r"\{ascii:\s*(\d+)[a-zA-Z_\-]*\s*\}", re.IGNORECASE)
DOT_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)+)\}")
TOAST_PATTERN = re.compile(
    r"\{toast:\s*(?:(\d+(?:\.\d+)?)\s*:\s*)?(?:\"([^\"]*)\"|'([^']*)'|([^}]+))\s*\}",
    re.IGNORECASE,
)


def trigger_toast(
    message: str,
    timeout: float = 2.0,
    title: str | None = None,
    app_or_screen=None,
) -> None:
    """Display a non-blocking toast message on the active Textual screen or app."""
    target = app_or_screen
    if target is None:
        with contextlib.suppress(Exception):
            from textual._context import active_app

            target = active_app.get()
    if target is not None:
        with contextlib.suppress(Exception):
            target.notify(message, title=title or None, timeout=float(timeout))


def interpolate_placeholders(text, config, depth=0, extra_vars=None, trigger_toasts=True):
    """Interpolate placeholders like {user}, {battery}, {window_width}, {scripts_dir}."""
    if not text or not isinstance(text, str) or "{" not in text:
        return text if text is not None else ""

    now = None
    if any(t_tok in text for t_tok in ("{date", "{time", "{utc_seconds}")):
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()

    def replace_toast(match):
        sec_str = match.group(1)
        timeout = float(sec_str) if sec_str else 2.0
        msg = (
            match.group(2)
            if match.group(2) is not None
            else (match.group(3) if match.group(3) is not None else match.group(4))
        )
        msg_clean = (msg or "").strip()
        if "{" in msg_clean and depth < 3:
            msg_clean = interpolate_placeholders(
                msg_clean, config, depth=depth + 1, extra_vars=extra_vars, trigger_toasts=False
            )
        if trigger_toasts:
            trigger_toast(msg_clean, timeout=timeout)
        return ""

    res_text = TOAST_PATTERN.sub(replace_toast, text)

    def replace_ascii(match):
        code_str = match.group(1)
        try:
            code = int(code_str)
            return bytes([code % 256]).decode("cp437", errors="replace")
        except (ValueError, OverflowError):
            return match.group(0)

    res_text = ASCII_PATTERN.sub(replace_ascii, res_text)

    # Command substitution: {command:cmd} with TTL caching to eliminate UI thread latency
    def replace_command(match):
        cmd_str = match.group(1).strip()
        now_ts = time.time()
        cached = _cmd_substitution_cache.get(cmd_str)
        if cached and (now_ts - cached[0] < _CMD_CACHE_TTL):
            return cached[1]
        try:
            res = subprocess.run(
                cmd_str,
                shell=True,
                executable=BASH_BIN,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            output = res.stdout.strip() if res and res.stdout else ""
            _cmd_substitution_cache[cmd_str] = (now_ts, output)
            return output
        except Exception:  # noqa: BLE001
            return ""

    res_text = COMMAND_PATTERN.sub(replace_command, res_text)

    if extra_vars and "window_width" in extra_vars:
        win_w = int(extra_vars["window_width"])
    else:
        cols = getattr(curses, "COLS", None)
        if cols is not None and isinstance(cols, int) and cols > 0:
            win_w = max(1, cols - 8)
        else:
            term_size = shutil.get_terminal_size((80, 24))
            win_w = max(1, term_size.columns - 8)

    if extra_vars and "screen_width" in extra_vars:
        scr_w = int(extra_vars["screen_width"])
    else:
        cols = getattr(curses, "COLS", None)
        if cols is not None and isinstance(cols, int) and cols > 0:
            scr_w = max(1, cols - 2)
        else:
            term_size = shutil.get_terminal_size((80, 24))
            scr_w = max(1, term_size.columns - 2)

    if extra_vars and "window_height" in extra_vars:
        win_h = int(extra_vars["window_height"])
    else:
        lines = getattr(curses, "LINES", None)
        if lines is not None and isinstance(lines, int) and lines > 0:
            win_h = max(1, lines - 6)
        else:
            term_size = shutil.get_terminal_size((80, 24))
            win_h = max(1, term_size.lines - 6)

    scripts_dir_setting = get_config_value(config, "settings.scripts_dir", "{bashmenu_dir}/scripts")
    templates_dir_setting = get_config_value(config, "settings.templates_dir", "{bashmenu_dir}/templates")
    cache_dir_setting = get_config_value(config, "settings.cache_dir", "{home}/.cache/bashmenu")

    if cache_dir_setting:
        raw_cache = str(cache_dir_setting)
        if "{home}" in raw_cache:
            raw_cache = raw_cache.replace("{home}", USER_HOME)
        if "{bashmenu_dir}" in raw_cache:
            raw_cache = raw_cache.replace("{bashmenu_dir}", BASHMENU_DIR)
        resolved_cache = os.path.abspath(os.path.expanduser(raw_cache))
        if os.environ.get("CACHE_DIR") != resolved_cache:
            os.environ["CACHE_DIR"] = resolved_cache
        cache_dir_setting = resolved_cache

    cur_profile = (
        resolve_existing_path(Path.home() / ".profile", Path.home() / ".bash_profile")
        if "{profile}" in res_text
        else ""
    )
    cur_bash_profile = (
        resolve_existing_path(Path.home() / ".bash_profile", Path.home() / ".profile")
        if "{bash_profile}" in res_text
        else ""
    )

    placeholders = {
        "{user}": USERNAME,
        "{username}": USERNAME,
        "{host}": HOSTNAME,
        "{hostname}": HOSTNAME,
        "{home}": USER_HOME,
        "{bashmenu_dir}": BASHMENU_DIR,
        "{scripts}": str(scripts_dir_setting),
        "{scripts_dir}": str(scripts_dir_setting),
        "{templates}": str(templates_dir_setting),
        "{templates_dir}": str(templates_dir_setting),
        "{cache}": str(cache_dir_setting),
        "{cache_dir}": str(cache_dir_setting),
        "{notebooks}": NOTEBOOKS_DIR,
        "{notebooks_dir}": NOTEBOOKS_DIR,
        "{bashrc}": BASHRC_PATH,
        "{bash_aliases}": BASH_ALIASES_PATH,
        "{vimrc}": VIMRC_PATH,
        "{nanorc}": NANORC_PATH,
        "{zshrc}": ZSHRC_PATH,
        "{profile}": cur_profile,
        "{bash_profile}": cur_bash_profile,
        "{zprofile}": ZPROFILE_PATH,
        "{shell_profile}": get_shell_profile_path() if "{shell_profile}" in res_text else "",
        "{powershell_profile}": get_powershell_profile_path() if "{powershell_profile}" in res_text else "",
        "{prefix}": PREFIX_PATH,
        "{termux_properties}": TERMUX_PROPERTIES_PATH,
        "{termux_storage}": TERMUX_STORAGE_PATH,
        "{appdata}": APPDATA_PATH,
        "{userprofile}": USERPROFILE_PATH,
        "{battery}": get_battery_info() if "{battery}" in res_text else "",
        "{battery_stat}": get_battery_status() if "{battery_stat}" in res_text or "{battery_status}" in res_text else "",
        "{battery_status}": get_battery_status() if "{battery_stat}" in res_text or "{battery_status}" in res_text else "",
        "{window_width}": str(win_w),
        "{screen_width}": str(scr_w),
        "{window_height}": str(win_h),
        "{date_time_12}": now.strftime("%Y-%m-%d %I:%M:%S %p") if (now and "{date_time_12}" in res_text) else "",
        "{date_time_12_short}": now.strftime("%Y-%m-%d %I:%M %p") if (now and "{date_time_12_short}" in res_text) else "",
        "{date_time_24}": now.strftime("%Y-%m-%d %H:%M:%S") if (now and "{date_time_24}" in res_text) else "",
        "{date_time_24_short}": now.strftime("%Y-%m-%d %H:%M") if (now and "{date_time_24_short}" in res_text) else "",
        "{date}": now.strftime("%Y-%m-%d") if (now and "{date}" in res_text) else "",
        "{time_12}": now.strftime("%I:%M:%S %p") if (now and "{time_12}" in res_text) else "",
        "{time_12_short}": now.strftime("%I:%M %p") if (now and "{time_12_short}" in res_text) else "",
        "{time_24}": now.strftime("%H:%M:%S") if (now and "{time_24}" in res_text) else "",
        "{time_24_short}": now.strftime("%H:%M") if (now and "{time_24_short}" in res_text) else "",
        "{utc_seconds}": str(int(now.timestamp())) if (now and "{utc_seconds}" in res_text) else "",
        "{user-mode}": "Root" if os.geteuid() == 0 else "User",
        "{version}": __version__,
        "{localip}": get_primary_ip() if "{localip}" in res_text else PRIMARY_IP,
        "{theme}": str(get_config_value(config, "theme", "dracula")),
        "{app.theme}": str(get_config_value(config, "theme", "dracula")),
    }

    if isinstance(config, dict):
        for ck, cv in config.items():
            if not isinstance(cv, (dict, list)):
                if f"{{{ck}}}" not in placeholders:
                    placeholders[f"{{{ck}}}"] = str(cv)
                if f"{{app.{ck}}}" not in placeholders:
                    placeholders[f"{{app.{ck}}}"] = str(cv)

    if extra_vars:
        for k, v in extra_vars.items():
            placeholders[f"{{{k}}}"] = str(v)

    if "{divider}" in res_text:
        res_text = res_text.replace("{divider}", resolve_divider_string(config, extra_vars=extra_vars))

    for k, v in placeholders.items():
        if k in res_text:
            res_text = res_text.replace(k, str(v))

    def replace_dot_var(match):
        key_path = match.group(1)
        val = get_config_value(config, key_path)
        if key_path in (
            "user.divider",
            "settings.divider",
            "app.user.divider",
            "app.settings.divider",
        ) or (isinstance(val, dict) and ("char" in val or "length" in val)):
            return resolve_divider_string(config, extra_vars=extra_vars)
        return str(val) if val is not None else match.group(0)

    res_text = DOT_VAR_PATTERN.sub(replace_dot_var, res_text)

    if "{" in res_text and depth < 3:
        res_text = interpolate_placeholders(res_text, config, depth + 1, extra_vars=extra_vars, trigger_toasts=trigger_toasts)

    return res_text


def is_divider(opt) -> bool:
    """Return True if the option represents a visual divider.
    Only strictly recognizes '{divider}' (quoted or unquoted YAML '{divider}'),
    never plain 'divider'.
    """
    if opt == "{divider}":
        return True
    if not isinstance(opt, dict):
        return False
    if "{divider}" in opt:
        return True
    t = opt.get("type")
    return t == "{divider}" or bool(isinstance(t, dict) and "divider" in t)


def get_effective_divider_config(config=None, **kwargs):
    """Resolve effective divider configuration strictly from the active theme in bashmenu.themes.
    Default fallback: char='{ascii:196}', length='{window_width}'
    """
    if not isinstance(config, dict):
        config = {}

    result = {"char": "{ascii:196}", "length": "{window_width}"}

    theme_name = get_config_value(config, "theme", "dracula")
    theme_div = bashmenu_ui.get_theme_divider(theme_name, config=config)
    if isinstance(theme_div, dict):
        for k in ("char", "length"):
            if theme_div.get(k) is not None:
                result[k] = theme_div[k]
    elif isinstance(theme_div, (str, int)):
        result["char"] = str(theme_div)

    return result


def resolve_divider_string(config, target_w=None, extra_vars=None, **kwargs):
    """Generate divider string based on active theme configuration and target width."""
    divider_conf = get_effective_divider_config(config)

    char = divider_conf.get("char")
    if not char:
        char = "{ascii:196}"

    char = interpolate_placeholders(char, config, extra_vars=extra_vars)
    char = resolve_glyph(char, config)
    if not char:
        char = "─"

    if target_w is not None:
        length = target_w
    else:
        length_spec = divider_conf.get("length", "{window_width}")
        if isinstance(length_spec, dict):
            for k in ("screen_width", "window_width"):
                if k in length_spec:
                    length_spec = f"{{{k}}}"
                    break
            else:
                length_spec = "{window_width}"
        length_str = interpolate_placeholders(str(length_spec), config, extra_vars=extra_vars)
        try:
            length = int(length_str)
        except ValueError:
            length = int(extra_vars.get("window_width", 80)) if extra_vars else 80
    raw_div = char * length
    return f"[color=divider]{raw_div}[/color]"


def get_plugin_divider_config(config: dict) -> tuple[bool, bool]:
    """Return (has_divider, is_screen_divider) for the plugin section divider.

    Checks `settings.plugins.divider`, `settings.plugins.top_divider`,
    `settings.plugins.layout.divider`, or `settings.plugins.pretext` (if set to '{divider}').
    If configured, respects explicit 'screen' or 'window' specification,
    or defaults to the theme's effective divider configuration.
    """
    if not isinstance(config, dict):
        return False, False
    plugins = config.get("settings", {}).get("plugins", {})
    if not isinstance(plugins, dict):
        return False, False

    val = plugins.get("divider")
    if val is None:
        val = plugins.get("top_divider")
    if val is None:
        layout = plugins.get("layout")
        if isinstance(layout, dict):
            val = layout.get("divider")
            if val is None:
                val = layout.get("top_divider")
    if val is None:
        p_pre = plugins.get("pretext")
        if isinstance(p_pre, str) and "{divider}" in p_pre:
            val = True
        elif isinstance(p_pre, bool):
            val = p_pre

    if val is None or val is False:
        return False, False

    div_cfg = get_effective_divider_config(config)
    length_val = div_cfg.get("length", "{window_width}")
    if isinstance(length_val, dict):
        theme_is_screen = any("screen_width" in str(k) for k in length_val)
    else:
        theme_is_screen = "screen_width" in str(length_val)

    if isinstance(val, str):
        val_str = val.strip().lower()
        if val_str in ("false", "0", "no", "none", "off", ""):
            return False, False
        if val_str == "screen":
            return True, True
        if val_str == "window":
            return True, False
        return True, theme_is_screen

    if isinstance(val, dict):
        l_spec = val.get("length")
        if l_spec:
            return True, "screen" in str(l_spec)
        return True, theme_is_screen

    return bool(val), theme_is_screen


def load_yaml_file(filename):
    """Load YAML file with error formatting."""
    if not os.path.exists(filename):
        return None, f"File not found: {filename}"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}, None
    except (yaml.YAMLError, OSError) as exc:
        return None, f"Error reading '{filename}': {exc}"


CONFIG_HEADER = """# ==============================================================================
# BashMenu Configuration (bashmenu.yml)
# All keys defined in this file can be referenced via placeholders using the
# '{app.<key>}' namespace (e.g. {app.theme}, {app.settings.tabstop}, {app.user.postal_code}),
# or shorthand shortcuts ({theme}, {user.<key>}, {settings.<key>}).
# ==============================================================================
"""


def save_config(config):
    """Persist current configuration to bashmenu.yml."""
    if _config_has_load_error:
        return
    try:
        content = yaml.dump(config, default_flow_style=False, sort_keys=False)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(CONFIG_HEADER + content)
    except Exception:  # noqa: BLE001, S110
        pass


def load_config():
    """Load configuration settings from bashmenu.yml."""
    global _config_has_load_error
    if not os.path.exists(CONFIG_FILE):
        _config_has_load_error = False
        save_config(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG), None

    data, err = load_yaml_file(CONFIG_FILE)
    if err:
        _config_has_load_error = True
        return copy.deepcopy(DEFAULT_CONFIG), err

    _config_has_load_error = False
    merged = deep_merge(copy.deepcopy(DEFAULT_CONFIG), data)
    return merged, None


def build_dynamic_theme_submenu():
    """
    Construct a menu structure dictionary populated with available color themes.
    """
    themes = bashmenu_ui.load_themes_file()
    items = [
        {
            "type": "{divider}",
        }
    ]
    if themes:
        for theme_key in themes:
            formatted_name = theme_key.replace("_", " ").title()
            items.append({
                "title": formatted_name,
                "label": formatted_name,
                "set_theme": theme_key,
                "icon": "{nf::#f0301:🎨}",
            })
    items.append({
        "type": "{divider}",
    })
    items.append({
        "title": "Back to Options & Settings",
        "label": "Back to Options & Settings",
        "type": "back",
        "icon": "{nf::#f048}",
    })
    return {"title": "Select Color Theme", "items": items, "options": items}


def build_dynamic_notebook_submenu(filepath, notebook_data=None, config=None):
    """Construct a dynamic menu structure dictionary from a notebook YAML file."""
    filepath = resolve_notebook_path(filepath, config=config)
    if notebook_data is None:
        notebook_data = bashmenu_ui.load_notebook(filepath)
    nb_dict = notebook_data.get("notebook", {}) if isinstance(notebook_data, dict) else {}
    nb_title = nb_dict.get("title", "Notebook")
    notes_list = bashmenu_ui.get_notebook_notes(notebook_data)

    items = [
        {
            "type": "{divider}",
        }
    ]
    if notes_list:
        for title, note_props in notes_list:
            custom_icon = None
            if isinstance(note_props, dict):
                custom_icon = note_props.get("icon")
            items.append({
                "title": title,
                "label": title,
                "type": "notebook_note",
                "_notebook_file": filepath,
                "_note_title": title,
                "icon": custom_icon or "{nf:󰎞:#f039e}",
            })
    else:
        items.append({
            "title": "(No notes yet — press [N] to create)",
            "label": "(No notes yet — press [N] to create)",
            "type": "notebook_empty",
            "_notebook_file": filepath,
            "icon": "    ",
        })

    items.append({
        "type": "{divider}",
    })
    items.append({
        "title": "Back",
        "label": "Back",
        "type": "back",
        "icon": "{nf:󰁮:#f048}",
    })
    return {
        "title": nb_title,
        "items": items,
        "options": items,
        "_is_notebook": True,
        "_notebook_file": filepath,
        "_notebook_data": notebook_data,
    }


def inject_dynamic_menus(menu_item):
    """
    Recursively replace 'theme_selector' items with dynamic theme submenus.
    """
    if not isinstance(menu_item, dict):
        return
    items = menu_item.get("items", menu_item.get("options", []))
    for idx, opt in enumerate(items):
        if not isinstance(opt, dict):
            continue
        if opt.get("type") == "theme_selector":
            title = opt.get("title", opt.get("label", "Change Theme"))
            items[idx]["title"] = title
            items[idx]["label"] = title
            items[idx]["submenu"] = build_dynamic_theme_submenu()
        elif "submenu" in opt:
            inject_dynamic_menus(opt["submenu"])


def normalize_menu_items(items):
    """Normalize menu items list from either the new format (list of {label: props} or '{divider}')
    or legacy format (list of {label: ..., type: ...}).
    Returns a canonical list of item dicts with 'label', 'type', etc.
    """
    if not isinstance(items, list):
        return []
    normalized = []
    for raw in items:
        if raw is None:
            continue
        if is_divider(raw):
            normalized.append({"type": "{divider}"})
            continue
        if isinstance(raw, str):
            normalized.append({"label": raw, "type": "command", "action": raw})
            continue
        if not isinstance(raw, dict):
            continue

        if "label" in raw and ("type" in raw or "action" in raw or "submenu" in raw or len(raw) > 1):
            item = dict(raw)
            if "submenu" in item and isinstance(item["submenu"], dict):
                sub = dict(item["submenu"])
                sub_items = normalize_menu_items(sub.get("items", sub.get("options", [])))
                sub["items"] = sub_items
                sub["options"] = sub_items
                item["submenu"] = sub
            normalized.append(item)
            continue

        if len(raw) == 1:
            lbl = next(iter(raw))
            val = raw[lbl]
            if val is None:
                item = {"label": lbl}
            elif isinstance(val, dict):
                item = dict(val)
                item["label"] = lbl
                if "submenu" in item and isinstance(item["submenu"], dict):
                    sub = dict(item["submenu"])
                    sub_items = normalize_menu_items(sub.get("items", sub.get("options", [])))
                    sub["items"] = sub_items
                    sub["options"] = sub_items
                    item["submenu"] = sub
            else:
                item = {"label": lbl, "action": str(val)}
            normalized.append(item)
        else:
            item = dict(raw)
            if "submenu" in item and isinstance(item["submenu"], dict):
                sub = dict(item["submenu"])
                sub_items = normalize_menu_items(sub.get("items", sub.get("options", [])))
                sub["items"] = sub_items
                sub["options"] = sub_items
                item["submenu"] = sub
            normalized.append(item)

    return normalized


def load_menu():
    """Load menu structure definition from bashmenu.mnu."""
    data, err = load_yaml_file(MENU_FILE)
    if err:
        err_items = [
            {"label": f"Error: {err}"},
            {"label": "Exit Utility", "type": "exit"},
        ]
        return {
            "title": "YAML Configuration Error",
            "items": err_items,
            "options": err_items,
        }, err
    if isinstance(data, dict):
        norm_items = normalize_menu_items(data.get("items", data.get("options", [])))
        data["items"] = norm_items
        data["options"] = norm_items
    inject_dynamic_menus(data)
    return data, None


DEFAULT_MENU_PRUNES = {
    "stream": False,
    "masked": False,
    "show_whitespace": False,
    "refresh": False,
    "no_formatting": False,
    "external": False,
    "alt_buffer": False,
}


class IndentedDumper(yaml.SafeDumper):
    """YAML safe dumper that indents sequences under mapping keys."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow=False, indentless=False)


def _represent_none(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


IndentedDumper.add_representer(type(None), _represent_none)


def serialize_menu_item_for_save(item):
    """Serialize a normalized item dictionary into clean label-as-key mapping."""
    if not isinstance(item, dict):
        if item == "{divider}":
            return {"{divider}": None}
        return item

    if item.get("type") == "{divider}" or "{divider}" in item:
        return {"{divider}": None}

    label = item.get("label") or item.get("title") or "Unnamed"
    props = {}
    item_type = item.get("type", "command")

    for k, v in item.items():
        if k in ("label", "title") and k == ("label" if "label" in item else "title"):
            continue
        if k in DEFAULT_MENU_PRUNES and v == DEFAULT_MENU_PRUNES[k]:
            continue
        if k == "tabstop" and item_type != "editor":
            continue
        if k == "command" and v == item.get("action"):
            continue
        if k == "submenu" and isinstance(v, dict):
            sub = {"title": v.get("title", label)}
            sub_items = v.get("items", v.get("options", []))
            sub["items"] = [serialize_menu_item_for_save(x) for x in sub_items]
            props["submenu"] = sub
        else:
            props[k] = v

    if not props:
        return {label: None}
    return {label: props}


def serialize_menu_data(menu_data):
    """Serialize menu data dictionary into clean items schema."""
    if not isinstance(menu_data, dict):
        return menu_data
    items = menu_data.get("items", menu_data.get("options", []))
    res = {
        "version": menu_data.get("version", "0.0.1"),
        "title": menu_data.get("title", "Bash Menu"),
        "items": [serialize_menu_item_for_save(x) for x in items],
    }
    for k, v in menu_data.items():
        if k not in ("version", "title", "items", "options"):
            res[k] = v
    return res


def dump_menu_yaml(menu_data) -> str:
    """Dump menu data dictionary into YAML string formatted per clean items schema."""
    clean = serialize_menu_data(menu_data)
    return yaml.dump(clean, Dumper=IndentedDumper, sort_keys=False, default_flow_style=False, allow_unicode=True)


ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[([0-9;]*)m|"
    r"\x1b\([a-zA-Z0-9]|"
    r"\x1b\)[a-zA-Z0-9]|"
    r"\x1b\[[0-9;]*[a-zA-Z]"
)


def parse_ansi_line(line, default_theme_attr=0):
    """Parse a line containing ANSI color escape sequences into a list of (text, attr) segments."""
    if not line:
        return []

    segments = []
    pos = 0
    for match in ANSI_ESCAPE_RE.finditer(line):
        text_before = line[pos : match.start()]
        if text_before:
            segments.append((text_before, default_theme_attr))
        pos = match.end()

    if pos < len(line):
        segments.append((line[pos:], default_theme_attr))

    return segments if segments else [("", default_theme_attr)]


def process_line_to_segments(line, default_theme_attr=0):
    """Process tabs and ANSI codes into segments for testing."""
    if not line:
        return [("", default_theme_attr)]
    sanitized = line.replace("\x00", "").replace("\t", "    ")
    return parse_ansi_line(sanitized, default_theme_attr)


_plugin_output_cache = {}
_plugin_display_cache = {}
_plugin_fetching = set()
_plugin_lock = threading.RLock()


def _fetch_plugin_worker(name, script_cmd, now):
    try:
        env = dict(os.environ)
        if "COLUMNS" not in env or not env["COLUMNS"]:
            try:
                term_w = shutil.get_terminal_size((80, 24)).columns
                env["COLUMNS"] = str(max(20, term_w - 6))
            except (OSError, ValueError):
                env["COLUMNS"] = "74"

        if os.path.exists(script_cmd) and os.path.isfile(script_cmd):
            res = subprocess.run(
                [script_cmd],
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        else:
            res = subprocess.run(
                script_cmd,
                env=env,
                shell=True,
                executable=BASH_BIN,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        raw_out = res.stdout.strip() if res and res.stdout else ""
        plugin_lines = [line for line in raw_out.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001
        plugin_lines = []

    with _plugin_lock:
        _plugin_output_cache[name] = {"time": now, "lines": plugin_lines}
        _plugin_fetching.discard(name)


def get_plugin_outputs(config):
    """
    Execute configured plugin scripts and return formatted output lines.
    Caches outputs according to the plugin's 'sleep' interval.
    Asynchronously fetches updates in background threads to avoid UI freezes.
    """
    lines = []
    if not isinstance(config, dict):
        return lines

    settings = config.get("settings", {})
    plugins = settings.get("plugins", {})
    if not isinstance(plugins, dict):
        return lines

    scripts_dir = interpolate_placeholders(
        settings.get("scripts_dir", "{bashmenu_dir}/scripts"), config
    )

    now = time.time()
    for name, plugin in plugins.items():
        if not isinstance(plugin, dict):
            continue
        script_raw = plugin.get("script")
        if not script_raw:
            continue

        script = interpolate_placeholders(str(script_raw), config)
        sleep_time = plugin.get("sleep", 300)

        with _plugin_lock:
            cache_entry = _plugin_output_cache.get(name)

        if cache_entry and (now - cache_entry["time"] < sleep_time) and sleep_time > 0:
            plugin_lines = cache_entry["lines"]
        else:
            if os.path.isabs(script):
                script_path = script
            else:
                candidate = os.path.join(scripts_dir, script)
                script_path = candidate if os.path.exists(candidate) else script

            is_test_env = (
                "unittest" in sys.modules
                or hasattr(subprocess.run, "assert_called")
                or type(subprocess.run).__name__ in ("MagicMock", "Mock")
            )
            if is_test_env:
                _fetch_plugin_worker(name, script_path, now)
            else:
                with _plugin_lock:
                    if name not in _plugin_fetching:
                        _plugin_fetching.add(name)
                        t = threading.Thread(
                            target=_fetch_plugin_worker,
                            args=(name, script_path, now),
                            daemon=True,
                        )
                        t.start()

            with _plugin_lock:
                cache_entry = _plugin_output_cache.get(name)
            plugin_lines = cache_entry["lines"] if cache_entry else []

        pretext = plugin.get("pretext")
        posttext = plugin.get("posttext")

        if plugin_lines:
            if pretext:
                lines.append(pretext)
            lines.extend(plugin_lines)
            if posttext:
                lines.append(posttext)

    return lines


# ==============================================================================
# TEXTUAL MENU CANVAS WIDGET & APPLICATION
# ==============================================================================


def get_hex_from_style(style: Style | None, fallback: str = "#000000") -> str:
    """The `get_hex_from_style` function converts a Rich Style bgcolor to a
    valid hex color string accepted by Textual CSS styles.
    """
    if not style or not style.bgcolor:
        return fallback
    try:
        trip = style.bgcolor.get_truecolor()
        return f"#{trip.red:02x}{trip.green:02x}{trip.blue:02x}"
    except (AttributeError, ValueError):
        return fallback


def get_plugin_display_items(
    config: dict,
    avail_w: int = 74,
    screen_div_w: int = 78,
    has_screen_divider: bool = False,
    extra_vars: dict | None = None,
    theme_styles: dict | None = None,
    plugin_style: Style | None = None,
    bg_style: Style | None = None,
) -> list[tuple[str, bool, Text]]:
    """Return structured plugin rows (raw_text, is_divider, rendered_rich_text)
    accounting for table layouts, standalone plugins, and screen/window margins.
    """
    raw_plugin_lines = get_plugin_outputs(config)
    cache_ver = tuple(raw_plugin_lines)
    theme_name = config.get("theme", "dracula") if isinstance(config, dict) else "dracula"
    cache_key = (avail_w, screen_div_w, has_screen_divider, theme_name, cache_ver)
    cached_items = _plugin_display_cache.get(cache_key)
    if cached_items is not None:
        return [(r_str, is_d, rt.copy()) for r_str, is_d, rt in cached_items]

    plugins_dict = config.get("settings", {}).get("plugins", {}) if isinstance(config, dict) else {}
    if not isinstance(plugins_dict, dict):
        plugins_dict = {}

    layout = plugins_dict.get("layout") if isinstance(plugins_dict, dict) else None
    if (
        not (isinstance(layout, dict) and layout.get("type") == "table")
        and isinstance(plugins_dict, dict)
        and plugins_dict.get("type") == "table"
    ):
        layout = plugins_dict
    is_table_layout = isinstance(layout, dict) and layout.get("type") == "table"

    if theme_styles is None:
        theme_styles = bashmenu_ui.init_theme_colors(
            config.get("theme", "dracula") if isinstance(config, dict) else "dracula"
        )
    if plugin_style is None:
        plugin_style = theme_styles.get("plugin", Style(color="cyan"))
    if bg_style is None:
        bg_style = theme_styles.get("background", Style())
    if extra_vars is None:
        extra_vars = {"window_width": avail_w, "screen_width": screen_div_w, "window_height": 10}

    plugin_bg_color = plugin_style.bgcolor if plugin_style else None
    plugin_bg_style = Style(bgcolor=plugin_bg_color) if plugin_bg_color else Style()

    with _plugin_lock:
        has_cached_data = any(
            isinstance(p_name, str) and p_name in _plugin_output_cache
            for p_name in plugins_dict
        )

    def _render_row(content: str | Text, is_div: bool, raw_str: str) -> tuple[str, bool, Text]:
        if is_div:
            target_w = screen_div_w if has_screen_divider else avail_w
            div_vars = dict(extra_vars)
            div_vars["window_width"] = target_w
            div_vars["screen_width"] = target_w
            if any(tok in str(content) for tok in ("{divider}", "{user.divider}", "{settings.divider}")):
                div_str = interpolate_placeholders(str(content), config, extra_vars=div_vars)
            else:
                div_str = resolve_divider_string(config, target_w=target_w, extra_vars=div_vars)
            div_theme = theme_styles
            if plugin_bg_color and theme_styles and "divider" in theme_styles:
                orig_div = theme_styles["divider"]
                div_theme = dict(theme_styles)
                div_theme["divider"] = Style(color=orig_div.color, bgcolor=plugin_bg_color)
            div_rt = bashmenu_ui.formatting_to_rich_text(
                div_str, default_style=plugin_bg_style, theme=div_theme, avail_width=target_w
            )
            if div_rt.cell_len > target_w:
                div_rt.truncate(target_w)
            pad_w = max(0, target_w - div_rt.cell_len)
            if pad_w > 0:
                div_rt.append(" " * pad_w, style=plugin_bg_style)
            return (raw_str, True, div_rt)

        if isinstance(content, Text):
            c_rt = content.copy()
            c_style = Style.parse(c_rt.style) if isinstance(c_rt.style, str) else c_rt.style
            if plugin_bg_color and (not c_style or not c_style.bgcolor):
                c_rt.style = plugin_bg_style + (c_style or Style())
        else:
            c_interp = interpolate_placeholders(str(content), config, extra_vars=extra_vars)
            if "\x1b[" in c_interp:
                c_rt = Text.from_ansi(c_interp)
                c_style = Style.parse(c_rt.style) if isinstance(c_rt.style, str) else c_rt.style
                if plugin_bg_color and (not c_style or not c_style.bgcolor):
                    c_rt.style = plugin_bg_style + (c_style or Style())
            else:
                c_rt = bashmenu_ui.formatting_to_rich_text(
                    c_interp, default_style=plugin_style, theme=theme_styles, avail_width=avail_w
                )

        if has_screen_divider:
            if c_rt.cell_len > avail_w:
                c_rt.truncate(avail_w)
            row_rt = Text("  ", style=plugin_bg_style)
            row_rt.append_text(c_rt)
            pad_w = max(0, screen_div_w - row_rt.cell_len)
            if pad_w > 0:
                row_rt.append(" " * pad_w, style=plugin_bg_style)
            return (raw_str, False, row_rt)
        else:
            buffer_w = avail_w
            if c_rt.cell_len > buffer_w:
                c_rt.truncate(buffer_w)
            pad_w = max(0, buffer_w - c_rt.cell_len)
            if pad_w > 0:
                c_rt.append(" " * pad_w, style=plugin_bg_style)
            return (raw_str, False, c_rt)

    items: list[tuple[str, bool, Text]] = []
    if is_table_layout and has_cached_data:
        width_spec = layout.get("width", "100%")
        raw_headers = layout.get("headers", [])
        headers = list(raw_headers) if isinstance(raw_headers, (list, tuple)) else []
        max_entries = layout.get("entries") or layout.get("columns") or 2
        try:
            max_entries = max(1, int(max_entries))
        except (ValueError, TypeError):
            max_entries = 2

        raw_rows = layout.get("rows")
        if raw_rows and isinstance(raw_rows, list):
            rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in raw_rows]
        else:
            rows = []
            cur_row = []
            for p_name, p_val in plugins_dict.items():
                if (
                    p_name in ("layout", "_layout", "type", "width", "entries", "columns", "headers", "rows", "divider", "top_divider", "pretext", "posttext")
                    or not isinstance(p_val, dict)
                ):
                    continue
                is_standalone = p_val.get("standalone") or (p_val.get("span") in ("full", 1))
                if is_standalone:
                    if cur_row:
                        rows.append(cur_row)
                        cur_row = []
                    rows.append([p_name])
                else:
                    cur_row.append(p_name)
                    if len(cur_row) >= max_entries:
                        rows.append(cur_row)
                        cur_row = []
            if cur_row:
                rows.append(cur_row)

        has_any_content = False
        for r in rows:
            if not r or len(items) >= 10:
                continue

            if len(r) == 1:
                p_name = r[0]
                p_cfg = plugins_dict.get(p_name, {}) if isinstance(plugins_dict, dict) else {}
                is_standalone = p_cfg.get("standalone") or (p_cfg.get("span") in ("full", 1))
                if is_standalone:
                    with _plugin_lock:
                        cache_entry = _plugin_output_cache.get(p_name)
                    raw_lines = cache_entry["lines"] if cache_entry else []
                    lines = [
                        line.replace("\x00", "").replace("\t", "    ").replace("\ufe0f", "").replace("\ufe0e", "").rstrip("\r\n")
                        for line in raw_lines
                    ]
                    pre = p_cfg.get("pretext")
                    post = p_cfg.get("posttext")
                    if lines:
                        has_any_content = True
                        full_lines = ([pre] if pre else []) + list(lines) + ([post] if post else [])
                    elif pre or post:
                        full_lines = ([pre] if pre else []) + ([post] if post else [])
                    else:
                        full_lines = []

                    for fl in full_lines:
                        if len(items) >= 10:
                            break
                        for sub in str(fl).split("\n"):
                            if len(items) >= 10:
                                break
                            is_div = any(tok in sub for tok in ("{divider}", "{user.divider}", "{settings.divider}"))
                            items.append(_render_row(sub, is_div, sub))
                    continue

            # Multi-cell or non-standalone table row
            row_has_data = False
            row_cells = []
            for p_name in r:
                with _plugin_lock:
                    cache_entry = _plugin_output_cache.get(p_name)
                raw_lines = cache_entry["lines"] if cache_entry else []
                lines = [
                    line.replace("\x00", "").replace("\t", "    ").replace("\ufe0f", "").replace("\ufe0e", "").rstrip("\r\n")
                    for line in raw_lines
                ]
                p_cfg = plugins_dict.get(p_name, {}) if isinstance(plugins_dict, dict) else {}
                pre = p_cfg.get("pretext")
                post = p_cfg.get("posttext")
                if lines:
                    row_has_data = True
                    has_any_content = True
                    full_lines = ([pre] if pre else []) + list(lines) + ([post] if post else [])
                elif pre or post:
                    full_lines = ([pre] if pre else []) + ([post] if post else [])
                else:
                    full_lines = []
                cell_text = "\n".join(full_lines)
                row_cells.append(f"[td]{cell_text}[/td]")

            if row_has_data or headers:
                table_parts = [f"[table width={width_spec}]"]
                if headers and len(headers) == len(r):
                    table_parts.append("[tr]" + "".join(f"[th]{h}[/th]" for h in headers) + "[/tr]")
                table_parts.append("[tr]" + "".join(row_cells) + "[/tr]")
                table_parts.append("[/table]")
                table_bb = "".join(table_parts)
                table_interp = interpolate_placeholders(table_bb, config, extra_vars=extra_vars)
                table_rt = bashmenu_ui.formatting_to_rich_text(
                    table_interp, default_style=plugin_style, theme=theme_styles, avail_width=avail_w
                )
                for t_line in table_rt.split("\n"):
                    if len(items) >= 10:
                        break
                    raw_t = t_line.plain if hasattr(t_line, "plain") else str(t_line)
                    items.append(_render_row(t_line, False, raw_t))

        if not has_any_content and not headers:
            items = []
    else:
        for p_line in raw_plugin_lines[:10]:
            clean_line = (
                p_line.replace("\x00", "")
                .replace("\t", "    ")
                .replace("\ufe0f", "")
                .replace("\ufe0e", "")
                .rstrip("\r\n")
            )
            is_div_line = any(tok in clean_line for tok in ("{divider}", "{user.divider}", "{settings.divider}"))
            items.append(_render_row(clean_line, is_div_line, clean_line))

    if len(_plugin_display_cache) < 64:
        _plugin_display_cache[cache_key] = items
    return [(r_str, is_d, rt.copy()) for r_str, is_d, rt in items]


def get_plugin_display_lines(config: dict, width: int | None = None) -> list[str]:
    """Return the list of display lines for active plugins, accounting for table layouts."""
    w = width or 74
    items = get_plugin_display_items(config, avail_w=w, screen_div_w=w + 4, has_screen_divider=False)
    return [it[0] for it in items]


class PluginBuffer(Static):
    """The `PluginBuffer` widget displays active plugin lines in an isolated buffer."""

    DEFAULT_CSS = """
    PluginBuffer {
        layer: top;
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
        overflow-x: hidden;
        overflow-y: hidden;
    }
    """

    def __init__(self, config=None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or {}

    def render(self) -> Text:
        """Render cached extension script and plugin outputs into an isolated Textual buffer.

        Applies active theme background and plugin colors, limits display to a maximum
        of 10 rows, and normalizes tabs, null bytes, and Unicode variation selectors.
        """
        cfg = self.config
        scr = None
        with contextlib.suppress(Exception):
            scr = getattr(self, "_screen", None)
            if scr is None and hasattr(self, "screen"):
                scr = self.screen

        with contextlib.suppress(Exception):
            if scr and scr.menu_view and scr.menu_view.config:
                cfg = scr.menu_view.config

        theme_styles = bashmenu_ui.init_theme_colors(cfg.get("theme", "dracula"))
        plugin_style = theme_styles.get("plugin", Style(color="cyan"))
        bg_style = theme_styles.get("background", Style())

        div_cfg = get_effective_divider_config(cfg)
        length_val = div_cfg.get("length", "{window_width}")
        if isinstance(length_val, dict):
            is_screen = any("screen_width" in str(k) for k in length_val)
        else:
            is_screen = "screen_width" in str(length_val)

        screen_w = 0
        with contextlib.suppress(Exception):
            if self.screen and self.screen.size.width:
                screen_w = self.screen.size.width
        if not screen_w:
            screen_w = max(40, self.size.width or 80)
            avail_w = max(20, self.size.width or 80)
            screen_div_w = max(20, screen_w - 2)
        else:
            screen_w = max(40, screen_w)
            screen_div_w = max(20, screen_w - 2)
            avail_w = max(20, screen_w - 6)

        raw_plugin_lines = get_plugin_outputs(cfg)
        if not raw_plugin_lines:
            return Text()

        has_screen_divider = is_screen and any(
            any(tok in line for tok in ("{divider}", "{user.divider}", "{settings.divider}"))
            for line in raw_plugin_lines
        )

        if has_screen_divider:
            avail_w = max(20, screen_div_w - 4)

        grid = None
        theme_default_bg = None
        x_offset = 0
        y_offset = 0

        mv = None
        with contextlib.suppress(Exception):
            if scr and hasattr(scr, "menu_view"):
                mv = scr.menu_view

        if mv is not None:
            canvas = getattr(mv, "_canvas", None)
            if canvas is not None and getattr(canvas, "grid", None):
                grid = canvas.grid
                theme_default_bg = getattr(canvas, "theme_default_bg", None)

            with contextlib.suppress(Exception):
                off = getattr(self.styles, "offset", None)
                if off:
                    ox = getattr(off, "x", None)
                    oy = getattr(off, "y", None)
                    if ox is not None:
                        x_offset = int(getattr(ox, "value", ox))
                    if oy is not None:
                        y_offset = int(getattr(oy, "value", oy))

            if y_offset == 0 and grid:
                with contextlib.suppress(Exception):
                    h = max(10, mv.size.height or 24)
                    t_rows = getattr(mv, "total_content_rows", None)
                    total_content_rows = t_rows if isinstance(t_rows, int) else max(1, h - 5)
                    raw_p_lines, sep_rows, _ = mv.get_plugin_lines_and_limits(total_content_rows)
                    y_offset = 3 + total_content_rows - len(raw_p_lines) - sep_rows
                    x_offset = 1 if has_screen_divider else 3

        theme_name = cfg.get("theme", "dracula")
        cache_key = (
            id(grid),
            x_offset,
            y_offset,
            theme_name,
            avail_w,
            screen_div_w,
            has_screen_divider,
            tuple(raw_plugin_lines),
        )
        if getattr(self, "_cached_render_key", None) == cache_key and getattr(self, "_cached_render_text", None) is not None:
            return self._cached_render_text.copy()

        max_rows = min(10, len(raw_plugin_lines))
        extra_vars = {"window_width": avail_w, "screen_width": screen_div_w, "window_height": max_rows}

        items = get_plugin_display_items(
            cfg,
            avail_w=avail_w,
            screen_div_w=screen_div_w,
            has_screen_divider=has_screen_divider,
            extra_vars=extra_vars,
            theme_styles=theme_styles,
            plugin_style=plugin_style,
            bg_style=bg_style,
        )

        if not items:
            return Text()

        out = Text()
        num_items = min(10, len(items))
        for idx in range(num_items):
            line_rt = items[idx][2].copy()
            if grid:
                row_y = y_offset + idx
                if 0 <= row_y < len(grid):
                    full_row = grid[row_y]
                    row_cache = full_row[x_offset : x_offset + line_rt.cell_len]
                    line_rt = bashmenu_ui.composite_single_row(
                        line_rt, row_cache, theme_default_bg=theme_default_bg
                    )
            out.append_text(line_rt)
            if idx < num_items - 1:
                out.append("\n")

        self._cached_render_key = cache_key
        self._cached_render_text = out.copy()
        return out


class MainMenuView(Widget):
    """Custom canvas rendering the main menu interface with border, margins, brackets alignment, and status gutter."""

    DEFAULT_CSS = """
    MainMenuView {
        layer: base;
        width: 100%;
        height: 1fr;
        background: $surface;
    }
    """

    def __init__(self, config=None, menu_data=None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or load_config()[0]
        if menu_data and isinstance(menu_data, dict):
            norm_items = normalize_menu_items(menu_data.get("items", menu_data.get("options", [])))
            menu_data["items"] = norm_items
            menu_data["options"] = norm_items
        self.menu_data = menu_data or load_menu()[0]
        self.menu_stack = [self.menu_data]
        self.selected_rows = [0]
        self.scroll_offsets = [0]
        self.show_shortcuts = True
        self.can_focus = True
        self._canvas = bashmenu_ui.PrebakedWallpaperCanvas()
        self._marquee_tracker = bashmenu_ui.MarqueeTracker(pause_ticks=4)
        self._shortcut_map: dict[int, str] = {}
        self._marquee_timer = None

    def on_mount(self) -> None:
        self._marquee_timer = self.set_interval(0.25, self._tick_marquee)

    def _tick_marquee(self) -> None:
        with contextlib.suppress(Exception):
            scr = getattr(self, "screen", None)
            if scr and hasattr(scr, "_is_covered") and scr._is_covered():
                return
            app = getattr(self, "app", None)
            if app and (len(getattr(app, "screen_stack", [])) > 1 or getattr(app, "screen", None) is not scr):
                return
        opts = self.current_menu().get("items", self.current_menu().get("options", []))
        if not opts:
            return
        curr_row = self.current_row()
        if curr_row < 0 or curr_row >= len(opts):
            return
        if self._marquee_tracker.tick():
            w = max(40, self.size.width or 80)
            visible_rows = getattr(self, "visible_option_rows", None)
            scroll_start = self.current_scroll_offset()
            if visible_rows and visible_rows > 0:
                y = 3 + (curr_row - scroll_start)
                if 3 <= y < 3 + visible_rows:
                    self.refresh(Region(0, y, w, 1))

    def current_menu(self) -> dict:
        return self.menu_stack[-1]

    def current_row(self) -> int:
        return self.selected_rows[-1]

    def current_scroll_offset(self) -> int:
        if not hasattr(self, "scroll_offsets") or not self.scroll_offsets:
            self.scroll_offsets = [0]
        return self.scroll_offsets[-1]

    def set_current_row(self, row: int) -> None:
        opts = self.current_menu().get("items", self.current_menu().get("options", []))
        if not opts:
            return
        old_row = self.selected_rows[-1]
        new_row = max(0, min(row, len(opts) - 1))

        visible_rows = getattr(self, "visible_option_rows", None)
        w = max(40, self.size.width or 80)
        h = max(10, self.size.height or 24)

        if not hasattr(self, "scroll_offsets") or not self.scroll_offsets:
            self.scroll_offsets = [0]
        old_scroll = self.scroll_offsets[-1]
        max_scroll = max(0, len(opts) - visible_rows) if visible_rows and visible_rows > 0 else 0

        if visible_rows and visible_rows > 0:
            if new_row < old_scroll:
                new_scroll = new_row
            elif new_row >= old_scroll + visible_rows:
                new_scroll = new_row - visible_rows + 1
            else:
                new_scroll = old_scroll
            new_scroll = max(0, min(new_scroll, max_scroll))
        else:
            new_scroll = 0

        self.scroll_offsets[-1] = new_scroll

        if old_row == new_row and old_scroll == new_scroll:
            return

        self._marquee_tracker.reset(new_id=new_row)
        self.selected_rows[-1] = new_row

        if visible_rows and visible_rows > 0 and old_scroll == new_scroll:
            # Menu option indices map directly to terminal line rows:
            # Row 0: Top frame border, Rows 1-2: Top margins, Row 3+: Options
            y_old = 3 + (old_row - old_scroll)
            y_new = 3 + (new_row - new_scroll)
            if 0 <= y_old < h and 0 <= y_new < h:
                r_old = Region(0, y_old, w, 1)
                r_new = Region(0, y_new, w, 1)
                self.refresh(r_old, r_new)
                return

        self.refresh()

    def scroll_down(self, step: int = 1) -> None:
        opts = self.current_menu().get("items", self.current_menu().get("options", []))
        if not opts:
            return
        visible_rows = getattr(self, "visible_option_rows", None)
        if not visible_rows or visible_rows <= 0:
            return
        max_scroll = max(0, len(opts) - visible_rows)
        curr_scroll = self.current_scroll_offset()
        if max_scroll == 0:
            orig = self.current_row()
            idx = orig + 1
            while idx < len(opts) and is_divider(opts[idx]):
                idx += 1
            if idx < len(opts):
                self.set_current_row(idx)
            return

        new_scroll = min(max_scroll, curr_scroll + step)
        if new_scroll != curr_scroll:
            self.scroll_offsets[-1] = new_scroll
            curr_row = self.current_row()
            if curr_row < new_scroll:
                target = new_scroll
                while target < len(opts) and is_divider(opts[target]):
                    target += 1
                if target < len(opts):
                    self._marquee_tracker.reset(new_id=target)
                    self.selected_rows[-1] = target
            elif curr_row >= new_scroll + visible_rows:
                target = new_scroll + visible_rows - 1
                while target >= new_scroll and is_divider(opts[target]):
                    target -= 1
                if target >= 0:
                    self._marquee_tracker.reset(new_id=target)
                    self.selected_rows[-1] = target
            self.refresh()
        else:
            orig = self.current_row()
            idx = orig + 1
            while idx < len(opts) and is_divider(opts[idx]):
                idx += 1
            if idx < len(opts):
                self.set_current_row(idx)

    def scroll_up(self, step: int = 1) -> None:
        opts = self.current_menu().get("items", self.current_menu().get("options", []))
        if not opts:
            return
        visible_rows = getattr(self, "visible_option_rows", None)
        if not visible_rows or visible_rows <= 0:
            return
        max_scroll = max(0, len(opts) - visible_rows)
        curr_scroll = self.current_scroll_offset()
        if max_scroll == 0:
            orig = self.current_row()
            idx = orig - 1
            while idx >= 0 and is_divider(opts[idx]):
                idx -= 1
            if idx >= 0:
                self.set_current_row(idx)
            return

        new_scroll = max(0, curr_scroll - step)
        if new_scroll != curr_scroll:
            self.scroll_offsets[-1] = new_scroll
            curr_row = self.current_row()
            if curr_row >= new_scroll + visible_rows:
                target = new_scroll + visible_rows - 1
                while target >= new_scroll and is_divider(opts[target]):
                    target -= 1
                if target >= 0:
                    self._marquee_tracker.reset(new_id=target)
                    self.selected_rows[-1] = target
            elif curr_row < new_scroll:
                target = new_scroll
                while target < len(opts) and is_divider(opts[target]):
                    target += 1
                if target < len(opts):
                    self._marquee_tracker.reset(new_id=target)
                    self.selected_rows[-1] = target
            self.refresh()
        else:
            orig = self.current_row()
            idx = orig - 1
            while idx >= 0 and is_divider(opts[idx]):
                idx -= 1
            if idx >= 0:
                self.set_current_row(idx)

    def on_mouse_scroll_down(self, event) -> None:
        self.scroll_down(step=1)
        event.prevent_default()
        event.stop()

    def on_mouse_scroll_up(self, event) -> None:
        self.scroll_up(step=1)
        event.prevent_default()
        event.stop()

    def get_plugin_lines_and_limits(self, total_content_rows: int) -> tuple[list[str], int, int]:
        """The `get_plugin_lines_and_limits` method returns the capped plugin
        output lines, separator row count, and available menu option rows.
        """
        w = max(40, self.size.width or 80)
        avail_w = max(20, w - 6)
        raw_plugin_lines = get_plugin_display_lines(self.config, width=avail_w)
        has_top_div, _ = get_plugin_divider_config(self.config)
        top_div_rows = 1 if (has_top_div and len(raw_plugin_lines) > 0) else 0
        max_plugin_rows = min(10, max(0, total_content_rows - 2 - top_div_rows))
        if len(raw_plugin_lines) > max_plugin_rows:
            raw_plugin_lines = raw_plugin_lines[:max_plugin_rows] if max_plugin_rows > 0 else []
        separator_rows = 1 if len(raw_plugin_lines) > 0 else 0
        visible_option_rows = max(1, total_content_rows - len(raw_plugin_lines) - separator_rows - top_div_rows)
        return raw_plugin_lines, separator_rows, visible_option_rows

    def render(self) -> Text:
        """Render the complete primary menu interface as an isolated textual screen buffer."""
        watchdog = None
        with contextlib.suppress(Exception):
            if hasattr(self, "app") and self.app:
                watchdog = getattr(self.app, "watchdog", None)
        if watchdog is None:
            watchdog = getattr(self, "watchdog", None)

        if watchdog is not None:
            with watchdog.measure("MainMenuView.render"):
                return self._render_menu_buffer()
        return self._render_menu_buffer()

    def _render_menu_buffer(self, assemble: bool = True) -> Text:
        """Constructs top/bottom window borders, menu titles, options with fixed 4-column
        icon slots and column 11 label alignment, shortcut badges, divider rules,
        and bottom status/help gutter using an in-memory pre-baked canvas for sub-millisecond assembly.
        """
        w = max(40, self.size.width or 80)
        h = max(10, self.size.height or 24)

        curr_menu = self.current_menu()
        curr_row = self.current_row()
        options = curr_menu.get("items", curr_menu.get("options", []))

        theme_name = self.config.get("theme", "dracula")
        theme_styles = bashmenu_ui.init_theme_colors(theme_name)
        self.theme_styles = theme_styles
        with contextlib.suppress(Exception):
            if hasattr(self, "app") and self.app:
                self.app.theme_styles = theme_styles
            if hasattr(self, "screen") and self.screen:
                self.screen.theme_styles = theme_styles

        # 1. Resolve wallpaper background configuration
        bg_cfg = get_config_value(self.config, "settings.background", None)
        user_bg = bg_cfg if isinstance(bg_cfg, dict) else {}
        theme_bg_raw = theme_styles.get("theme_background") or theme_styles.get("wallpaper")
        theme_bg_dict = {}
        if isinstance(theme_bg_raw, dict):
            theme_bg_dict = theme_bg_raw
        elif isinstance(theme_bg_raw, str):
            theme_bg_dict = {"image": theme_bg_raw}

        user_has_bg = user_bg.get("enabled", False) or bool(user_bg.get("image"))
        theme_has_bg = bool(theme_bg_dict.get("image"))
        user_disabled = user_bg.get("enabled") is False

        img_spec = None
        opacity = 0.35
        scaling = "cover"
        clustering = 0
        quantization = 1
        has_bg = False

        if not user_disabled and (user_has_bg or theme_has_bg):
            img_spec = user_bg.get("image") or theme_bg_dict.get("image")
            if img_spec:
                opacity = user_bg.get("opacity") if "opacity" in user_bg else theme_bg_dict.get("opacity", 0.35)
                scaling = user_bg.get("scaling") or theme_bg_dict.get("scaling", "cover")
                clustering = user_bg.get("clustering") if "clustering" in user_bg else theme_bg_dict.get("clustering", 0)
                quantization = user_bg.get("quantization") if "quantization" in user_bg else theme_bg_dict.get("quantization", 1)
                has_bg = True

        img_path = interpolate_placeholders(str(img_spec).strip(), self.config) if (img_spec and has_bg) else ""
        if has_bg and not img_path:
            has_bg = False

        # Status and help gutters wrapping (cached per second/width to avoid re-evaluating during rapid navigation)
        avail_w = max(20, w - 6)
        screen_div_w = max(20, w - 2)
        avail_both = max(4, w - 11)
        left_gutter_w = avail_both // 2
        right_gutter_w = avail_both - left_gutter_w

        now_sec = int(time.time())
        is_nb = bool(self.current_menu().get("_is_notebook"))
        gutter_key = (now_sec, left_gutter_w, right_gutter_w, avail_w, self.show_shortcuts, is_nb)
        cached_gutters = getattr(self, "_cached_gutters", None)
        if cached_gutters and cached_gutters[0] == gutter_key:
            help_lines, status_lines = cached_gutters[1], cached_gutters[2]
        else:
            if is_nb:
                full_help_str = (
                    "[N]: New Note | [ENTER]: Read | [M]: Rename | [D]: Delete | "
                    "[UP/DN]: Nav | [F1]: Help | [F2]: Themes | [F7]: Gutter | [F8]: ThemeEdit | [ESC]: Back"
                )
            elif self.show_shortcuts:
                full_help_str = "[UP/DN]: Nav | [0-9/a-z]: Direct | [F1]: Help | [F2]: Themes | [F3]: Editor | [F4]: Edit | [F5]: Refresh | [F6]: Keys | [F7]: Gutter | [F8]: ThemeEdit | [ESC]: Back"
            else:
                full_help_str = "[UP/DN]: Nav | [ENTER]: Select | [F1]: Help | [F2]: Themes | [F3]: Editor | [F4]: Edit | [F5]: Refresh | [F6]: Keys | [F7]: Gutter | [F8]: ThemeEdit | [ESC]: Back"
            raw_help_items = [item.strip() for item in full_help_str.split("|") if item.strip()]
            help_lines = wrap_gutter_items(raw_help_items, left_gutter_w, max_lines=2, config=self.config, spread=True)

            status_gutter_raw = get_config_value(self.config, "settings.status_gutter", "{user} | {battery} | {date_time_24}")
            raw_badges = split_gutter_badges(status_gutter_raw)
            init_extra_vars = {"window_width": right_gutter_w, "screen_width": screen_div_w}
            all_badges = [interpolate_placeholders(b, self.config, extra_vars=init_extra_vars, trigger_toasts=False).strip() for b in raw_badges if b.strip()]
            all_badges = [b for b in all_badges if b]
            status_lines = wrap_gutter_items(all_badges, right_gutter_w, max_lines=2, config=self.config, bottom_up=True)
            self._cached_gutters = (gutter_key, help_lines, status_lines)

        gutter_rows = min(2, max(1, max(len(help_lines), len(status_lines))))
        gutter_y_start = h - 1 - gutter_rows

        total_content_rows = max(1, h - 5 - gutter_rows)
        self.total_content_rows = total_content_rows
        raw_plugin_lines, separator_rows, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)
        self.visible_option_rows = visible_option_rows

        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            canvas = bashmenu_ui.PrebakedWallpaperCanvas()
            self._canvas = canvas

        canvas_key = (
            w,
            h,
            id(curr_menu),
            len(options),
            theme_name,
            self.show_shortcuts,
            has_bg,
            img_path,
            round(opacity, 3),
            scaling,
            clustering,
            quantization,
            tuple(raw_plugin_lines),
            separator_rows,
            gutter_rows,
        )

        if not canvas.is_valid(canvas_key):
            self._build_canvas(
                canvas,
                canvas_key,
                w,
                h,
                curr_menu,
                options,
                theme_name,
                theme_styles,
                has_bg,
                img_path,
                opacity,
                scaling,
                clustering,
                avail_w,
                screen_div_w,
                visible_option_rows,
                total_content_rows,
                raw_plugin_lines,
                separator_rows,
                gutter_rows,
                quantization=quantization,
            )

        scroll_start = self.current_scroll_offset()
        max_scroll = max(0, len(options) - visible_option_rows)
        if curr_row < scroll_start:
            scroll_start = curr_row
        elif curr_row >= scroll_start + visible_option_rows:
            scroll_start = curr_row - visible_option_rows + 1
        scroll_start = max(0, min(scroll_start, max_scroll))
        if hasattr(self, "scroll_offsets") and self.scroll_offsets:
            self.scroll_offsets[-1] = scroll_start

        cached_hg = getattr(self, "_cached_raw_hg_lines", None)
        if cached_hg and cached_hg[0] == gutter_key:
            raw_hg_lines = cached_hg[1]
        else:
            raw_hg_lines = self._render_raw_gutter_lines(
                help_lines, status_lines, gutter_rows, avail_w, theme_styles, w=w
            )
            self._cached_raw_hg_lines = (gutter_key, raw_hg_lines)

        gutter_lines = canvas.get_gutter_lines(
            (gutter_key, id(theme_styles)),
            gutter_y_start,
            raw_hg_lines,
        )

        active_opt_line = None
        active_opt_strip = None
        if 0 <= curr_row < len(options) and not is_divider(options[curr_row]):
            active_y = 3 + (curr_row - scroll_start)
            if self._marquee_tracker.offset != 0:
                sc_char = getattr(self, "_shortcut_map", {}).get(curr_row, "")
                borders = bashmenu_ui.get_theme_window_borders(theme_name, config=self.config)
                div_cfg = get_effective_divider_config(self.config)
                length_val = div_cfg.get("length", "{window_width}")
                is_screen = any("screen_width" in str(k) for k in length_val) if isinstance(length_val, dict) else "screen_width" in str(length_val)
                indicator_symbol = resolve_glyph(interpolate_placeholders(theme_styles.get("indicator", ">"), self.config, trigger_toasts=False), self.config)
                extra_vars = {"window_width": avail_w, "screen_width": screen_div_w, "window_height": visible_option_rows}

                raw_active = self._render_raw_option_line(
                    curr_row,
                    options[curr_row],
                    True,
                    sc_char,
                    avail_w,
                    screen_div_w,
                    extra_vars,
                    theme_styles,
                    borders,
                    div_cfg,
                    is_screen,
                    indicator_symbol,
                    marquee_offset=self._marquee_tracker.offset,
                )
                active_opt_line = canvas.composite_dynamic_line(active_y, raw_active)
                active_opt_strip = bashmenu_ui.text_to_strip(active_opt_line)
            else:
                active_opt_line = canvas.get_option_line(active_y, curr_row, True)
                active_opt_strip = canvas.get_option_strip(active_y, curr_row, True)

        self._has_wallpaper = has_bg
        self._wallpaper_frame_state = {
            "h": h,
            "scroll_start": scroll_start,
            "curr_row": curr_row,
            "visible_option_rows": visible_option_rows,
            "num_options": len(options),
            "gutter_y_start": gutter_y_start,
            "num_gutter_lines": len(gutter_lines),
            "active_option_strip": active_opt_strip,
        }

        if not assemble:
            return Text()

        return canvas.assemble_frame(
            h,
            scroll_start,
            curr_row,
            visible_option_rows,
            len(options),
            gutter_y_start,
            gutter_lines,
            active_option_line=active_opt_line,
        )

    def _render_content(self) -> None:
        """Render all lines, bypassing full Text->Content->Strip overhead when wallpaper canvas is active."""
        self._render_menu_buffer(assemble=False)
        if getattr(self, "_has_wallpaper", False):
            self._dirty_regions.clear()
            return
        super()._render_content()

    def render_line(self, y: int) -> Strip:
        """Render a single line of content directly from pre-baked Strips."""
        if self.BLANK:
            return Strip.blank(self.size.width, self.visual_style.rich_style)

        if self._dirty_regions or getattr(self, "_wallpaper_frame_state", None) is None:
            self._render_content()

        if not getattr(self, "_has_wallpaper", False):
            try:
                return self._render_cache.lines[y]
            except (AttributeError, IndexError):
                return Strip.blank(self.size.width, self.visual_style.rich_style)

        state = getattr(self, "_wallpaper_frame_state", None)
        canvas = getattr(self, "_canvas", None)
        if not state or not canvas:
            return Strip.blank(self.size.width, self.visual_style.rich_style)

        return canvas.get_line_strip(
            y,
            scroll_start=state["scroll_start"],
            curr_row=state["curr_row"],
            visible_option_rows=state["visible_option_rows"],
            num_options=state["num_options"],
            gutter_y_start=state["gutter_y_start"],
            num_gutter_lines=state["num_gutter_lines"],
            active_option_strip=state.get("active_option_strip"),
        )

    def _build_canvas(
        self,
        canvas: bashmenu_ui.PrebakedWallpaperCanvas,
        canvas_key: tuple,
        w: int,
        h: int,
        curr_menu: dict,
        options: list,
        theme_name: str,
        theme_styles: dict,
        has_bg: bool,
        img_path: str,
        opacity: float,
        scaling: str,
        clustering: int,
        avail_w: int,
        screen_div_w: int,
        visible_option_rows: int,
        total_content_rows: int,
        raw_plugin_lines: list,
        separator_rows: int,
        gutter_rows: int = 1,
        quantization: int = 1,
    ) -> None:
        """Pre-bake static frame borders, margins, options, and plugin rows onto the canvas."""
        grid = None
        if has_bg and img_path:
            compositor = getattr(self, "_wallpaper_compositor", None)
            if compositor is None or getattr(compositor, "image_path", None) != img_path:
                compositor = bashmenu_ui.WallpaperCompositor(
                    img_path,
                    opacity=opacity,
                    scaling=scaling,
                    base_dir=BASHMENU_DIR,
                    clustering=clustering,
                    quantization=quantization,
                )
                self._wallpaper_compositor = compositor
            else:
                compositor.opacity = opacity
                compositor.scaling = scaling
                compositor.clustering = clustering
                compositor.quantization = quantization

            theme_bg_rgb = bashmenu_ui.get_theme_bg_rgb(theme_styles)
            grid = compositor.get_grid(w, h, theme_bg_rgb)

        theme_bg_style = theme_styles.get("background")
        theme_default_bg = theme_bg_style.bgcolor if theme_bg_style else None
        canvas.invalidate()
        canvas.set_grid(grid, theme_default_bg=theme_default_bg)

        borders = bashmenu_ui.get_theme_window_borders(theme_name, config=self.config)
        border_style = theme_styles.get("border", Style(color="blue"))
        title_style = theme_styles.get("title", Style(color="magenta", bold=True))
        cap_style = theme_styles.get("title_cap") or theme_styles.get("title") or title_style
        b_tl = borders.get("border_top_left", "┌")
        b_tr = borders.get("border_top_right", "┐")
        b_bl = borders.get("border_bottom_left", "└")
        b_br = borders.get("border_bottom_right", "┘")
        b_h_top = borders.get("border_horizontal_top", borders.get("border_horizontal", "─"))
        b_h_bot = borders.get("border_horizontal_bottom", borders.get("border_horizontal", "─"))
        b_v_left = borders.get("border_vertical_left", borders.get("border_vertical", "│"))
        b_v_right = borders.get("border_vertical_right", borders.get("border_vertical", "│"))
        b_tee_l = borders.get("left_tee") or borders.get("border_tee_left") or b_v_left
        b_tee_r = borders.get("right_tee") or borders.get("border_tee_right") or b_v_right
        b_gt_border = borders.get("gutter_border") or b_h_bot
        b_gt_l_tee = borders.get("gutter_left_tee") or b_tee_l
        b_gt_r_tee = borders.get("gutter_right_tee") or b_tee_r
        b_gt_top_tee = borders.get("gutter_top_tee") or borders.get("top_tee", "┬")
        b_gt_bot_tee = borders.get("gutter_bottom_tee") or borders.get("bottom_tee", "┴")
        title_l_cap = borders.get("title_left_cap", " ") or " "
        title_r_cap = borders.get("title_right_cap", " ") or " "

        extra_vars = {"window_width": avail_w, "screen_width": screen_div_w, "window_height": visible_option_rows}

        # 1. Header border line: ┌──[ Title ]──┐
        title_raw = interpolate_placeholders(curr_menu.get("title", "HA Bash Menu"), self.config, extra_vars=extra_vars, trigger_toasts=False)
        title_body = f" {title_raw} "
        title_full = f"{title_l_cap}{title_body}{title_r_cap}"
        title_len = get_visible_len(title_full, self.config)
        left_b = max(2, (w - title_len) // 2)
        right_b = max(2, w - left_b - title_len)

        top_bar = Text(b_tl + b_h_top * max(0, left_b - 1), style=border_style)
        top_bar.append(title_l_cap, style=cap_style)
        top_bar.append_text(bashmenu_ui.formatting_to_rich_text(title_body, default_style=title_style, theme=theme_styles))
        top_bar.append(title_r_cap, style=cap_style)
        top_bar.append(b_h_top * max(0, right_b - 1) + b_tr, style=border_style)
        canvas.set_static_line(0, top_bar)

        # 2. Margins (Lines 1, 2)
        canvas.set_static_line(1, Text(f"{b_v_left}  " + " " * avail_w + f"  {b_v_right}", style=border_style))
        canvas.set_static_line(2, Text(f"{b_v_left}  " + " " * avail_w + f"  {b_v_right}", style=border_style))

        # 3. Static lines between options and plugins
        has_top_div, top_div_is_screen = get_plugin_divider_config(self.config)
        top_div_rows = 1 if (has_top_div and len(raw_plugin_lines) > 0) else 0
        target_blank_rows = total_content_rows - len(raw_plugin_lines) - separator_rows - top_div_rows

        div_cfg = get_effective_divider_config(self.config)
        length_val = div_cfg.get("length", "{window_width}")
        is_screen = any("screen_width" in str(k) for k in length_val) if isinstance(length_val, dict) else "screen_width" in str(length_val)

        for y in range(3, 3 + target_blank_rows):
            canvas.set_static_line(y, Text(f"{b_v_left}  " + " " * avail_w + f"  {b_v_right}", style=border_style))

        curr_y = 3 + target_blank_rows
        if top_div_rows > 0:
            plugin_style = theme_styles.get("plugin", Style(color="cyan"))
            plugin_bg_color = plugin_style.bgcolor if plugin_style else None
            plugin_bg_style = Style(bgcolor=plugin_bg_color) if plugin_bg_color else None

            top_div_theme = theme_styles
            if plugin_bg_color and theme_styles and "divider" in theme_styles:
                orig_div = theme_styles["divider"]
                top_div_theme = dict(theme_styles)
                top_div_theme["divider"] = Style(color=orig_div.color, bgcolor=plugin_bg_color)

            if top_div_is_screen:
                div_str = resolve_divider_string(self.config, target_w=screen_div_w, extra_vars=extra_vars)
                div_rich = bashmenu_ui.formatting_to_rich_text(
                    div_str, default_style=plugin_bg_style, theme=top_div_theme, avail_width=screen_div_w
                )
                line_rich = Text(f"{b_tee_l}", style=border_style)
                line_rich.append_text(div_rich)
                used_w = get_visible_len(div_str, self.config)
                fill_w = max(0, screen_div_w - used_w)
                if fill_w > 0:
                    line_rich.append(" " * fill_w, style=plugin_bg_style or Style())
                line_rich.append(f"{b_tee_r}", style=border_style)
                canvas.set_static_line(curr_y, line_rich)
            else:
                target_div_w = avail_w
                if str(length_val).isdigit():
                    target_div_w = min(avail_w, int(length_val))
                div_str = resolve_divider_string(self.config, target_w=target_div_w, extra_vars=extra_vars)
                div_rich = bashmenu_ui.formatting_to_rich_text(
                    div_str, default_style=plugin_bg_style, theme=top_div_theme, avail_width=target_div_w
                )
                line_rich = Text(f"{b_v_left}  ", style=border_style)
                line_rich.append_text(div_rich)
                used_w = get_visible_len(div_str, self.config)
                fill_w = max(0, avail_w - used_w)
                if fill_w > 0:
                    line_rich.append(" " * fill_w, style=plugin_bg_style or Style())
                line_rich.append(f"  {b_v_right}", style=border_style)
                canvas.set_static_line(curr_y, line_rich)
            curr_y += 1

        for p_line in raw_plugin_lines:
            clean_line = (
                p_line.replace("\x00", "")
                .replace("\ufe0f", "")
                .replace("\ufe0e", "")
                .rstrip("\r\n")
            )
            is_div_line = any(tok in clean_line for tok in ("{divider}", "{user.divider}", "{settings.divider}"))
            if is_screen and is_div_line:
                canvas.set_static_line(curr_y, Text(f"{b_tee_l}" + " " * screen_div_w + f"{b_tee_r}", style=border_style))
            else:
                canvas.set_static_line(curr_y, Text(f"{b_v_left}  " + " " * avail_w + f"  {b_v_right}", style=border_style))
            curr_y += 1

        if separator_rows > 0:
            canvas.set_static_line(curr_y, Text(f"{b_v_left}  " + " " * avail_w + f"  {b_v_right}", style=border_style))
            curr_y += 1

        # Gutter top border & window bottom border
        avail_both = max(4, w - 11)
        left_gutter_w = avail_both // 2
        sep_x = left_gutter_w + 5
        left_seg_len = max(0, sep_x - 1)
        right_seg_len = max(0, w - 2 - sep_x)

        gutter_border_y = h - 2 - gutter_rows
        gt_bar = Text(
            b_gt_l_tee + b_gt_border * left_seg_len + b_gt_top_tee + b_gt_border * right_seg_len + b_gt_r_tee,
            style=border_style,
        )
        canvas.set_static_line(gutter_border_y, gt_bar)

        # Bottom border at h - 1 with bottom tee connecting the vertical separator
        bot_bar = Text(
            b_bl + b_h_bot * left_seg_len + b_gt_bot_tee + b_h_bot * right_seg_len + b_br,
            style=border_style,
        )
        canvas.set_static_line(h - 1, bot_bar)

        # 4. Pre-bake options
        shortcut_chars = "123456789abcdefghijklmnopqrstuvwxyz"
        shortcut_map = {}
        sc_idx = 0
        for idx, opt in enumerate(options):
            if not is_divider(opt) and sc_idx < len(shortcut_chars):
                shortcut_map[idx] = shortcut_chars[sc_idx]
                sc_idx += 1
        self._shortcut_map = shortcut_map

        indicator_symbol = resolve_glyph(interpolate_placeholders(theme_styles.get("indicator", ">"), self.config, trigger_toasts=False), self.config)
        for idx, opt in enumerate(options):
            sc_char = shortcut_map.get(idx, "")
            line_unsel = self._render_raw_option_line(
                idx, opt, False, sc_char, avail_w, screen_div_w, extra_vars, theme_styles, borders, div_cfg, is_screen, indicator_symbol
            )
            canvas.set_raw_option_line(idx, False, line_unsel)
            line_sel = self._render_raw_option_line(
                idx, opt, True, sc_char, avail_w, screen_div_w, extra_vars, theme_styles, borders, div_cfg, is_screen, indicator_symbol
            )
            canvas.set_raw_option_line(idx, True, line_sel)

        # 5. Pre-warm visible slots
        for i in range(min(visible_option_rows, len(options))):
            y = 3 + i
            canvas.prebake_option(y, i, False)
            canvas.prebake_option(y, i, True)

        canvas._canvas_key = canvas_key

    def _render_raw_gutter_lines(
        self,
        help_lines: list[str],
        status_lines: list[str],
        gutter_rows: int,
        avail_w: int,
        theme_styles: dict,
        w: int | None = None,
    ) -> list[Text]:
        theme_name = self.config.get("theme", "dracula")
        borders = bashmenu_ui.get_theme_window_borders(theme_name, config=self.config)
        b_v_left = borders.get("border_vertical_left", borders.get("border_vertical", "│"))
        b_v_right = borders.get("border_vertical_right", borders.get("border_vertical", "│"))
        b_gt_sep = borders.get("gutter_separator") or borders.get("border_vertical", "│")
        border_style = theme_styles.get("border", Style(color="blue"))
        gutter_style = theme_styles.get("gutter", Style(color="cyan", bold=True))
        help_text_style = theme_styles.get("help_text", Style(color="cyan"))

        if w is None:
            w = avail_w + 6

        avail_both = max(4, w - 11)
        left_gutter_w = avail_both // 2
        right_gutter_w = avail_both - left_gutter_w

        status_offset = gutter_rows - len(status_lines)
        raw_lines = []
        for r in range(gutter_rows):
            h_text = help_lines[r] if r < len(help_lines) else ""
            s_idx = r - status_offset
            s_text = status_lines[s_idx] if 0 <= s_idx < len(status_lines) else ""

            h_rich = (
                bashmenu_ui.formatting_to_rich_text(h_text, default_style=help_text_style, theme=theme_styles)
                if h_text
                else Text()
            )
            if h_rich.cell_len > left_gutter_w:
                h_rich.truncate(left_gutter_w)
            h_pad = max(0, left_gutter_w - h_rich.cell_len)
            if h_pad > 0:
                h_rich.append(" " * h_pad)

            s_rich = (
                bashmenu_ui.formatting_to_rich_text(s_text, default_style=gutter_style, theme=theme_styles)
                if s_text
                else Text()
            )
            if s_rich.cell_len > right_gutter_w:
                s_rich.truncate(right_gutter_w)
            s_pad = max(0, right_gutter_w - s_rich.cell_len)
            status_cell = Text(" " * s_pad)
            status_cell.append_text(s_rich)

            hg_line = Text(f"{b_v_left}  ", style=border_style)
            hg_line.append_text(h_rich)
            hg_line.append("  ", style=border_style)
            hg_line.append(b_gt_sep, style=border_style)
            hg_line.append("  ", style=border_style)
            hg_line.append_text(status_cell)
            hg_line.append(f"  {b_v_right}", style=border_style)
            raw_lines.append(hg_line)
        return raw_lines

    def _render_raw_option_line(
        self,
        idx: int,
        opt: dict,
        is_selected: bool,
        shortcut_char: str,
        avail_w: int,
        screen_div_w: int,
        extra_vars: dict,
        theme_styles: dict,
        borders: dict,
        div_cfg: dict,
        is_screen: bool,
        indicator_symbol: str,
        marquee_offset: int = 0,
    ) -> Text:
        border_style = theme_styles.get("border", Style(color="blue"))
        highlight_style = theme_styles.get("highlight", Style(color="white", bgcolor="magenta", bold=True))
        text_style = theme_styles.get("text", Style(color="white"))
        shortcut_key_style = theme_styles.get("shortcut_key", Style(color="magenta", bold=True))

        b_v_left = borders.get("border_vertical_left", borders.get("border_vertical", "│"))
        b_v_right = borders.get("border_vertical_right", borders.get("border_vertical", "│"))
        b_tee_l = borders.get("left_tee") or borders.get("border_tee_left") or b_v_left
        b_tee_r = borders.get("right_tee") or borders.get("border_tee_right") or b_v_right

        item_style = highlight_style if is_selected else text_style

        if is_divider(opt):
            item_div_conf = get_effective_divider_config(self.config)
            length_val = item_div_conf.get("length", "{window_width}")
            item_is_screen = any("screen_width" in str(k) for k in length_val) if isinstance(length_val, dict) else "screen_width" in str(length_val)

            if item_is_screen:
                div_str = resolve_divider_string(self.config, target_w=screen_div_w, extra_vars=extra_vars)
                div_rich = bashmenu_ui.formatting_to_rich_text(div_str, theme=theme_styles)
                line_rich = Text(f"{b_tee_l}", style=border_style)
                line_rich.append_text(div_rich)
                used_w = get_visible_len(div_str, self.config)
                fill_w = max(0, screen_div_w - used_w)
                if fill_w > 0:
                    line_rich.append(" " * fill_w)
                line_rich.append(f"{b_tee_r}", style=border_style)
            else:
                target_div_w = avail_w
                if str(length_val).isdigit():
                    target_div_w = min(avail_w, int(length_val))
                div_str = resolve_divider_string(self.config, target_w=target_div_w, extra_vars=extra_vars)
                div_rich = bashmenu_ui.formatting_to_rich_text(div_str, theme=theme_styles)
                line_rich = Text(f"{b_v_left}  ", style=border_style)
                line_rich.append_text(div_rich)
                used_w = get_visible_len(div_str, self.config)
                fill_w = max(0, avail_w - used_w)
                if fill_w > 0:
                    line_rich.append(" " * fill_w)
                line_rich.append(f"  {b_v_right}", style=border_style)
            return line_rich

        line_rich = Text(f"{b_v_left}  ", style=border_style)
        ind_str = f"{indicator_symbol} " if is_selected else "  "
        ind_w = get_display_width(ind_str, self.config)

        sc_char = shortcut_char
        sc_str = f"[{sc_char}] " if (self.show_shortcuts and sc_char) else "    "
        sc_w = get_display_width(sc_str, self.config)

        theme_key = (self.config.get("theme"), self.config.get("settings.use_nerd_fonts", True))
        cached_opt = opt.get("_parsed_cache")
        if cached_opt and cached_opt[0] == theme_key:
            icon_str, icon_w, left_label, right_bracket = cached_opt[1:]
        else:
            icon_raw = opt.get("icon") or opt.get("glyph") or ""
            icon_resolved = resolve_glyph(interpolate_placeholders(icon_raw, self.config, extra_vars=extra_vars, trigger_toasts=False), self.config) if icon_raw else ""
            if icon_resolved:
                clean_icon = icon_resolved.replace("\ufe0f", "").replace("\ufe0e", "")
                vis_w = get_display_width(clean_icon, self.config)
                pad_w = max(1, 4 - vis_w)
                icon_str = f"{clean_icon}{' ' * pad_w}"
                icon_w = vis_w + pad_w
            else:
                icon_str = "    "
                icon_w = 4

            raw_label = interpolate_placeholders(opt.get("label") or opt.get("title") or "", self.config, extra_vars=extra_vars, trigger_toasts=False)
            if opt.get("set_theme") == self.config.get("theme"):
                raw_label += " (Active)"

            left_label, right_bracket = split_label_brackets(raw_label)
            if "{" not in str(icon_raw) and "{" not in str(opt.get("label") or opt.get("title") or ""):
                opt["_parsed_cache"] = (theme_key, icon_str, icon_w, left_label, right_bracket)

        prefix_w = ind_w + sc_w + icon_w

        mq_cfg = bashmenu_ui.get_theme_marquee_config(theme_styles)
        mq_char = mq_cfg.get("char", "•")
        mq_gap = mq_cfg.get("gap", 5)

        def _truncate_ellipsis(s: str, max_w: int) -> str:
            if not s or max_w <= 0:
                return ""
            if get_visible_len(s, self.config) <= max_w:
                return s
            if max_w <= 1:
                return "…"[:max_w]
            target_w = max_w - 1
            low, high = 1, len(s)
            best = 0
            while low <= high:
                mid = (low + high) // 2
                if get_visible_len(s[:mid], self.config) <= target_w:
                    best = mid
                    low = mid + 1
                else:
                    high = mid - 1
            return f"{s[:best]}…"

        row_content = Text(ind_str, style=item_style)
        if self.show_shortcuts and sc_char:
            row_content.append(f"[{sc_char}] ", style=shortcut_key_style if not is_selected else item_style)
        else:
            row_content.append("    ", style=item_style)
        row_content.append(icon_str, style=item_style)

        if right_bracket:
            center = avail_w // 2
            left_part_w = max(prefix_w + 1, center - 2)
            left_label_avail_w = max(1, left_part_w - prefix_w)
            right_part_w = max(3, avail_w - (center + 2))

            if is_selected:
                if get_visible_len(left_label, self.config) > left_label_avail_w:
                    lbl_text = bashmenu_ui.get_marquee_slice(
                        left_label, left_label_avail_w, marquee_offset, char=mq_char, gap=mq_gap
                    )
                else:
                    lbl_text = left_label

                if get_visible_len(right_bracket, self.config) > right_part_w:
                    rb_text = bashmenu_ui.get_marquee_slice(
                        right_bracket, right_part_w, marquee_offset, char=mq_char, gap=mq_gap
                    )
                else:
                    rb_text = right_bracket
            else:
                lbl_text = _truncate_ellipsis(left_label, left_label_avail_w)
                rb_text = _truncate_ellipsis(right_bracket, right_part_w)

            lbl_rich = bashmenu_ui.formatting_to_rich_text(lbl_text, default_style=item_style, theme=theme_styles)
            row_content.append_text(lbl_rich)

            used_left = row_content.cell_len
            pad_left = max(0, left_part_w - used_left)
            if pad_left > 0:
                row_content.append(" " * pad_left, style=item_style)

            gap_w = max(0, (center + 2) - row_content.cell_len)
            if gap_w > 0:
                row_content.append(" " * gap_w, style=item_style)

            rb_rich = bashmenu_ui.formatting_to_rich_text(rb_text, default_style=item_style, theme=theme_styles)
            rb_w = rb_rich.cell_len
            pad_right = max(0, right_part_w - rb_w)
            if pad_right > 0:
                row_content.append(" " * pad_right, style=item_style)
            row_content.append_text(rb_rich)
        else:
            label_avail_w = max(5, avail_w - prefix_w)
            if is_selected:
                if get_visible_len(left_label, self.config) > label_avail_w:
                    lbl_text = bashmenu_ui.get_marquee_slice(
                        left_label, label_avail_w, marquee_offset, char=mq_char, gap=mq_gap
                    )
                else:
                    lbl_text = left_label
            else:
                lbl_text = _truncate_ellipsis(left_label, label_avail_w)

            lbl_rich = bashmenu_ui.formatting_to_rich_text(lbl_text, default_style=item_style, theme=theme_styles)
            row_content.append_text(lbl_rich)

        if row_content.cell_len > avail_w:
            row_content.truncate(avail_w)
        pad_end = max(0, avail_w - row_content.cell_len)
        if pad_end > 0:
            row_content.append(" " * pad_end, style=item_style)

        line_rich.append_text(row_content)
        line_rich.append(f"  {b_v_right}", style=border_style)
        return line_rich

    def _apply_wallpaper_background(
        self, text: Text, width: int, height: int, theme_styles: dict, bg_cfg: dict | None
    ) -> Text:
        """Apply half-block background wallpaper compositing to rendered menu interface."""
        user_bg = bg_cfg if isinstance(bg_cfg, dict) else {}

        # If user explicitly disabled background in settings, respect that
        if user_bg.get("enabled") is False:
            return text

        # Check theme-level background specification
        theme_bg_raw = theme_styles.get("theme_background") or theme_styles.get("wallpaper")
        theme_bg_dict = {}
        if isinstance(theme_bg_raw, dict):
            theme_bg_dict = theme_bg_raw
        elif isinstance(theme_bg_raw, str):
            theme_bg_dict = {"image": theme_bg_raw}

        # If background is not enabled in settings and no background is specified in theme, nothing to render
        user_has_bg = user_bg.get("enabled", False) or bool(user_bg.get("image"))
        theme_has_bg = bool(theme_bg_dict.get("image"))
        if not user_has_bg and not theme_has_bg:
            return text

        # Hierarchy: user settings override theme defaults
        img_spec = user_bg.get("image") or theme_bg_dict.get("image")
        if not img_spec:
            return text

        opacity = user_bg.get("opacity") if "opacity" in user_bg else theme_bg_dict.get("opacity", 0.35)
        scaling = user_bg.get("scaling") or theme_bg_dict.get("scaling", "cover")
        clustering = user_bg.get("clustering") if "clustering" in user_bg else theme_bg_dict.get("clustering", 0)
        quantization = user_bg.get("quantization") if "quantization" in user_bg else theme_bg_dict.get("quantization", 1)

        img_path = interpolate_placeholders(str(img_spec).strip(), self.config)

        compositor = getattr(self, "_wallpaper_compositor", None)
        if compositor is None or getattr(compositor, "image_path", None) != img_path:
            compositor = bashmenu_ui.WallpaperCompositor(
                img_path,
                opacity=opacity,
                scaling=scaling,
                base_dir=BASHMENU_DIR,
                clustering=clustering,
                quantization=quantization,
            )
            self._wallpaper_compositor = compositor
        else:
            compositor.opacity = opacity
            compositor.scaling = scaling
            compositor.clustering = clustering
            compositor.quantization = quantization

        theme_bg_rgb = bashmenu_ui.get_theme_bg_rgb(theme_styles)
        grid = compositor.get_grid(width, height, theme_bg_rgb)
        if not grid:
            return text

        console = getattr(self, "_compositor_console", None)
        if console is None:
            from rich.console import Console

            console = Console(width=width, height=height)
            self._compositor_console = console

        theme_bg_style = theme_styles.get("background")
        theme_default_bg = theme_bg_style.bgcolor if theme_bg_style else None

        return bashmenu_ui.composite_menu_text(
            text, grid, width, height, console=console, theme_default_bg=theme_default_bg
        )

    def on_click(self, event) -> None:
        rendered_row = event.y - 3
        curr_menu = self.current_menu()
        options = curr_menu.get("items", curr_menu.get("options", []))

        visible_option_rows = getattr(self, "visible_option_rows", None)
        if visible_option_rows is None:
            total_content_rows = max(1, (self.size.height or 24) - 5)
            _, _, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)

        scroll_start = self.current_scroll_offset()

        if 0 <= rendered_row < visible_option_rows:
            if options:
                target_idx = scroll_start + rendered_row
                if 0 <= target_idx < len(options):
                    opt = options[target_idx]
                    if not is_divider(opt):
                        self.set_current_row(target_idx)
                        scr = None
                        with contextlib.suppress(Exception):
                            scr = self.screen
                        if not scr:
                            scr = getattr(self, "_screen", None)

                        if event.button == 3 and scr and hasattr(scr, "action_edit_menu"):
                            scr.action_edit_menu()
                        elif event.button == 1 and scr and hasattr(scr, "action_select_option"):
                            scr.action_select_option()
            return

        # Handle clicks on the interactive help gutter and status gutter
        h = max(10, self.size.height or 24)
        cached_gutters = getattr(self, "_cached_gutters", None)
        if cached_gutters:
            help_lines, status_lines = cached_gutters[1], cached_gutters[2]
            gutter_rows = min(2, max(1, max(len(help_lines), len(status_lines))))
            gutter_y_start = h - 1 - gutter_rows
            if gutter_y_start <= event.y < h - 1:
                r_idx = event.y - gutter_y_start
                avail_both = max(4, (self.size.width or 80) - 11)
                left_gutter_w = avail_both // 2
                sep_x = left_gutter_w + 5
                if event.x >= sep_x:
                    scr = None
                    with contextlib.suppress(Exception):
                        scr = self.screen
                    if not scr:
                        scr = getattr(self, "_screen", None)
                    if scr and hasattr(scr, "action_edit_status_gutter"):
                        scr.action_edit_status_gutter()
                elif 0 <= r_idx < len(help_lines):
                    self._handle_gutter_click(event.x, help_lines[r_idx])

    def _handle_gutter_click(self, click_x: int, line_str: str) -> None:
        scr = None
        with contextlib.suppress(Exception):
            scr = self.screen
        if not scr:
            scr = getattr(self, "_screen", None)
        if not scr:
            return

        x_cursor = 2
        for raw_item in line_str.split("|"):
            item = raw_item.strip()
            item_len = len(raw_item)
            if x_cursor <= click_x <= x_cursor + item_len + 1:
                item_lower = item.lower()
                if ("help" in item_lower or "f1" in item_lower) and hasattr(scr, "action_help"):
                    scr.action_help()
                elif (("theme" in item_lower and "edit" in item_lower) or "f8" in item_lower or "themeedit" in item_lower) and hasattr(scr, "action_theme_editor"):
                    scr.action_theme_editor()
                elif ("theme" in item_lower or "f2" in item_lower) and hasattr(scr, "action_themes"):
                    scr.action_themes()
                elif ("editor" in item_lower or "f3" in item_lower) and (hasattr(scr, "action_launch_editor") or hasattr(scr, "action_editor")):
                    if hasattr(scr, "action_launch_editor"):
                        scr.action_launch_editor()
                    else:
                        scr.action_editor()
                elif ("edit" in item_lower or "f4" in item_lower) and hasattr(scr, "action_edit_menu"):
                    scr.action_edit_menu()
                elif ("refresh" in item_lower or "f5" in item_lower) and (hasattr(scr, "action_refresh_menu") or hasattr(scr, "action_refresh")):
                    if hasattr(scr, "action_refresh_menu"):
                        scr.action_refresh_menu()
                    else:
                        scr.action_refresh()
                elif ("keys" in item_lower or "f6" in item_lower) and hasattr(scr, "action_toggle_shortcuts"):
                    scr.action_toggle_shortcuts()
                elif ("gutter" in item_lower or "f7" in item_lower) and hasattr(scr, "action_edit_status_gutter"):
                    scr.action_edit_status_gutter()
                elif ("back" in item_lower or "esc" in item_lower) and (hasattr(scr, "action_go_back") or hasattr(scr, "action_quit")):
                    if hasattr(scr, "action_go_back"):
                        scr.action_go_back()
                    else:
                        scr.action_quit()
                elif ("new note" in item_lower or item_lower.startswith("[n]") or item_lower == "n") and hasattr(scr, "action_new_note"):
                    scr.action_new_note()
                elif ("rename" in item_lower or item_lower.startswith("[m]") or item_lower == "m") and hasattr(scr, "action_rename_note"):
                    scr.action_rename_note()
                elif ("delete" in item_lower or item_lower.startswith("[d]") or item_lower == "d") and hasattr(scr, "action_delete_note"):
                    scr.action_delete_note()
                elif ("select" in item_lower or "read" in item_lower or "enter" in item_lower) and hasattr(scr, "action_select_option"):
                    scr.action_select_option()
                return
            x_cursor += item_len + 1

    def on_mouse_move(self, event) -> None:
        rendered_row = event.y - 3
        if rendered_row == getattr(self, "_last_mouse_row", None):
            return
        self._last_mouse_row = rendered_row

        curr_menu = self.current_menu()
        options = curr_menu.get("items", curr_menu.get("options", []))
        if not options:
            return

        visible_option_rows = getattr(self, "visible_option_rows", None)
        if visible_option_rows is None:
            total_content_rows = max(1, (self.size.height or 24) - 5)
            _, _, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)

        scroll_start = self.current_scroll_offset()

        if 0 <= rendered_row < visible_option_rows:
            target_idx = scroll_start + rendered_row
            if 0 <= target_idx < len(options):
                opt = options[target_idx]
                if not is_divider(opt) and self.current_row() != target_idx:
                    self.set_current_row(target_idx)


def _get_active_title_chain(screen) -> list[str]:
    chain = []
    with contextlib.suppress(Exception):
        mv = getattr(screen, "menu_view", None)
        if mv:
            for m, r in zip(mv.menu_stack, mv.selected_rows):
                opts = m.get("items", m.get("options", []))
                if 0 <= r < len(opts):
                    opt = opts[r]
                    t = opt.get("title") or opt.get("label")
                    if t:
                        chain.append(str(t))
    return chain


FILE_PICKER_MACRO_RE = re.compile(
    r"\{(file_picker(?:_new)?)(?::((?:[^{}]|\{[^{}]*\})+))?\}"
)
DIR_PICKER_MACRO_RE = re.compile(
    r"\{(dir_picker(?:_new)?)(?::((?:[^{}]|\{[^{}]*\})+))?\}"
)
PICKER_MACRO_RE = re.compile(
    r"\{(file_picker(?:_new)?|dir_picker(?:_new)?)(?::((?:[^{}]|\{[^{}]*\})+))?\}"
)


def parse_picker_macro(macro_type: str, spec: str | None, config: dict | None = None) -> dict[str, Any]:
    """Parse macro type and colon-delimited spec into structured parameters."""
    is_new = macro_type.endswith("_new")
    modifier = None
    start_dir = None

    if spec:
        # Interpolate nested variables if present and config supplied
        if config and "{" in spec:
            spec = interpolate_placeholders(spec, config)

        tokens = spec.split(":")
        if "new" in tokens:
            is_new = True
            tokens.remove("new")

        if tokens and tokens[-1] in ("stem", "name", "base", "dir", "ext", "parent"):
            modifier = tokens.pop()

        if tokens:
            if tokens[0] == "path":
                tokens.pop(0)
            if tokens:
                start_dir = ":".join(tokens)

    return {
        "macro_type": macro_type,
        "is_new": is_new,
        "modifier": modifier,
        "start_dir": start_dir,
    }


def _extract_picker_spec(
    action_str: str,
    config: dict | None = None,
    default_start_dir: str | None = None,
    target_macro: str | None = None,
) -> dict[str, Any]:
    """Extract start_dir, is_new flag, and macro type from action string."""
    regex = (
        FILE_PICKER_MACRO_RE
        if target_macro in ("file", "file_picker")
        else DIR_PICKER_MACRO_RE
        if target_macro in ("dir", "dir_picker")
        else PICKER_MACRO_RE
    )
    m = regex.search(action_str)
    if not m:
        start_dir = default_start_dir or "~"
        if config and "{" in start_dir:
            start_dir = interpolate_placeholders(start_dir, config)
        return {
            "macro_type": "file_picker" if target_macro in ("file", "file_picker", None) else "dir_picker",
            "is_new": False,
            "modifier": None,
            "start_dir": os.path.expanduser(start_dir),
        }

    macro_type = m.group(1)
    spec_str = m.group(2)
    parsed = parse_picker_macro(macro_type, spec_str, config=config)

    start_dir = parsed.get("start_dir")
    if start_dir:
        if config and "{" in start_dir:
            start_dir = interpolate_placeholders(start_dir, config)
    else:
        # Check if preceding path exists before placeholder, e.g. "/path/to/folder/{file_picker}"
        preceding = action_str[: m.start()]
        if config and "{" in preceding:
            preceding = interpolate_placeholders(preceding, config)
        match_dir = re.search(r'["\'`]([^"\'`]+)/$', preceding)
        if not match_dir:
            match_dir = re.search(r'(?:^|[\s=])(\S+)/$', preceding)
        if match_dir:
            cand = match_dir.group(1)
            cand_expanded = os.path.expanduser(cand)
            if os.path.isdir(cand_expanded) or not default_start_dir:
                start_dir = cand

    if not start_dir:
        start_dir = default_start_dir or "~"
        if config and "{" in start_dir:
            start_dir = interpolate_placeholders(start_dir, config)

    parsed["start_dir"] = os.path.expanduser(start_dir)
    return parsed


def _apply_file_picker_macros(template_str: str, fpath: str, config: dict | None = None) -> str:
    """Substitute {file_picker} and its path modifiers (:stem, :name, :base, :dir, :ext, :path:)."""
    p = Path(fpath)
    p_stem = str(p.parent / p.stem) if str(p.parent) != "." else p.stem
    p_name = p.name
    p_base = p.stem
    p_dir = str(p.parent)
    p_ext = p.suffix

    def _replace_macro(match: re.Match) -> str:
        macro_type = match.group(1)
        if not macro_type.startswith("file_picker"):
            return match.group(0)
        spec_str = match.group(2)
        parsed = parse_picker_macro(macro_type, spec_str, config=config)
        mod = parsed["modifier"]
        if mod == "stem":
            return p_stem
        if mod == "name":
            return p_name
        if mod == "base":
            return p_base
        if mod == "dir":
            return p_dir
        if mod == "ext":
            return p_ext
        return fpath

    res = template_str

    # Handle preceding directory prefix avoidance if macro had no modifier
    for m in list(FILE_PICKER_MACRO_RE.finditer(res)):
        macro_type = m.group(1)
        parsed = parse_picker_macro(macro_type, m.group(2), config=config)
        if parsed["modifier"] is None:
            preceding = res[: m.start()]
            match_dir = re.search(r'["\'`]([^"\'`]+)/$', preceding)
            if not match_dir:
                match_dir = re.search(r'(?:^|[\s=])(\S+)/$', preceding)
            if match_dir:
                cand = match_dir.group(1)
                cand_resolved = cand
                if config and "{" in cand_resolved:
                    cand_resolved = interpolate_placeholders(cand_resolved, config)
                cand_norm = os.path.normpath(os.path.expanduser(cand_resolved))
                parent_norm = os.path.normpath(str(p.parent))
                if cand_norm == parent_norm or os.path.isdir(cand_norm):
                    res = res[: match_dir.start(1)] + fpath + res[m.end() :]
                    break

    return FILE_PICKER_MACRO_RE.sub(_replace_macro, res)


def _apply_dir_picker_macros(template_str: str, dpath: str, config: dict | None = None) -> str:
    """Substitute {dir_picker} and its path modifiers (:name, :dir, :parent, :path:)."""
    p = Path(dpath)
    p_name = p.name
    p_dir = str(p.parent)

    def _replace_macro(match: re.Match) -> str:
        macro_type = match.group(1)
        if not macro_type.startswith("dir_picker"):
            return match.group(0)
        spec_str = match.group(2)
        parsed = parse_picker_macro(macro_type, spec_str, config=config)
        mod = parsed["modifier"]
        if mod == "name":
            return p_name
        if mod in ("dir", "parent"):
            return p_dir
        return dpath

    res = template_str

    # Preceding directory prefix avoidance
    for m in list(DIR_PICKER_MACRO_RE.finditer(res)):
        macro_type = m.group(1)
        parsed = parse_picker_macro(macro_type, m.group(2), config=config)
        if parsed["modifier"] is None:
            preceding = res[: m.start()]
            match_dir = re.search(r'["\'`]([^"\'`]+)/$', preceding)
            if not match_dir:
                match_dir = re.search(r'(?:^|[\s=])(\S+)/$', preceding)
            if match_dir:
                cand = match_dir.group(1)
                cand_resolved = cand
                if config and "{" in cand_resolved:
                    cand_resolved = interpolate_placeholders(cand_resolved, config)
                cand_norm = os.path.normpath(os.path.expanduser(cand_resolved))
                parent_norm = os.path.normpath(str(p.parent))
                if cand_norm == parent_norm or os.path.isdir(cand_norm):
                    res = res[: match_dir.start(1)] + dpath + res[m.end() :]
                    break

    return DIR_PICKER_MACRO_RE.sub(_replace_macro, res)


def process_item_action(screen, item, config):
    """Execute menu entry action based on option dictionary definition type."""
    item_type = item.get("type", "command")

    if item_type == "exit":
        screen.app.exit()

    elif item_type == "back":
        screen.action_go_back()

    elif item_type == "notebook":
        filepath = resolve_notebook_path(item.get("file"), config=config)
        try:
            sub_menu = build_dynamic_notebook_submenu(filepath, config=config)
            item["submenu"] = sub_menu
            screen.menu_view.menu_stack.append(sub_menu)
            sub_options = sub_menu.get("items", sub_menu.get("options", []))
            start_idx = 0
            while start_idx < len(sub_options) and is_divider(sub_options[start_idx]):
                start_idx += 1
            screen.menu_view.selected_rows.append(min(start_idx, max(0, len(sub_options) - 1)))
            if hasattr(screen.menu_view, "scroll_offsets"):
                screen.menu_view.scroll_offsets.append(0)
            screen.menu_view.refresh()
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as e:
            theme = getattr(screen.app, "theme_styles", getattr(screen, "theme_styles", None))
            screen.app.push_screen(bashmenu_ui.MessageModalScreen("Notebook Error", f"Failed to load notebook:\n{e}", theme=theme))

    elif item_type == "theme_selector":
        item["submenu"] = build_dynamic_theme_submenu()
        sub_menu = item["submenu"]
        screen.menu_view.menu_stack.append(sub_menu)
        sub_options = sub_menu.get("items", sub_menu.get("options", []))
        start_idx = 0
        while start_idx < len(sub_options) and is_divider(sub_options[start_idx]):
            start_idx += 1
        screen.menu_view.selected_rows.append(min(start_idx, max(0, len(sub_options) - 1)))
        if hasattr(screen.menu_view, "scroll_offsets"):
            screen.menu_view.scroll_offsets.append(0)
        screen.menu_view.refresh()

    elif item_type == "notebook_note":
        filepath = item.get("_notebook_file", "")
        note_title = item.get("_note_title", "")
        if filepath and note_title and hasattr(screen, "open_note_viewer"):
            screen.open_note_viewer(filepath, note_title)

    elif item_type == "notebook_empty":
        if hasattr(screen, "action_new_note"):
            screen.action_new_note()

    elif "submenu" in item:
        sub_menu = item["submenu"]
        screen.menu_view.menu_stack.append(sub_menu)
        sub_options = sub_menu.get("items", sub_menu.get("options", []))
        start_idx = 0
        while start_idx < len(sub_options) and is_divider(sub_options[start_idx]):
            start_idx += 1
        screen.menu_view.selected_rows.append(min(start_idx, max(0, len(sub_options) - 1)))
        if hasattr(screen.menu_view, "scroll_offsets"):
            screen.menu_view.scroll_offsets.append(0)
        screen.menu_view.refresh()

    elif "set_theme" in item:
        new_theme = item["set_theme"]
        set_config_value(config, "theme", new_theme)
        save_config(config)
        screen.menu_view.config = config
        new_styles = bashmenu_ui.init_theme_colors(new_theme)
        screen.theme_styles = new_styles
        screen.menu_view.theme_styles = new_styles
        if hasattr(screen, "app") and screen.app:
            screen.app.theme_styles = new_styles
        screen.menu_view.refresh()
        if hasattr(screen, "_update_plugin_buffer_geometry"):
            screen._update_plugin_buffer_geometry()

    elif item_type == "toast":
        raw_msg = item.get("message", item.get("text", item.get("prompt", item.get("action", ""))))
        sec = item.get("seconds") or item.get("timeout") or item.get("duration") or 2.0
        title = item.get("title", item.get("label", ""))
        title_interp = interpolate_placeholders(title, config, trigger_toasts=False) if title else None
        target = screen.app if hasattr(screen, "app") and screen.app else screen
        if TOAST_PATTERN.search(str(raw_msg)):
            interpolate_placeholders(str(raw_msg), config, trigger_toasts=True)
        else:
            msg = interpolate_placeholders(str(raw_msg), config, trigger_toasts=False)
            if msg:
                trigger_toast(msg, timeout=float(sec), title=title_interp, app_or_screen=target)

    elif item_type in ["message", "popup", "info"]:
        msg_title = interpolate_placeholders(item.get("title", item.get("label", "Notice")), config)
        msg_text = interpolate_placeholders(item.get("message", item.get("text", "")), config)
        screen.app.push_screen(bashmenu_ui.MessageModalScreen(msg_title, msg_text))

    elif item_type == "confirm":
        conf_title = interpolate_placeholders(item.get("title", item.get("label", "Confirm")), config)
        conf_msg = interpolate_placeholders(item.get("message", item.get("prompt", "Are you sure?")), config)

        def confirm_cb(res):
            if res == "yes" and "on_yes" in item:
                process_item_action(screen, item["on_yes"], config)
            elif res == "no" and "on_no" in item:
                process_item_action(screen, item["on_no"], config)

        screen.app.push_screen(bashmenu_ui.ConfirmModalScreen(conf_title, conf_msg), confirm_cb)

    elif item_type in ["toggle", "config_toggle"]:
        key_path = item.get("key", "")
        if key_path:
            title = item.get("title", item.get("label", "Toggle Setting"))
            msg = interpolate_placeholders(item.get("message", item.get("prompt", f"Configure option {key_path}:")), config)

            def toggle_cb(res):
                if res in ["true", "false"]:
                    set_config_value(config, key_path, res == "true")
                    save_config(config)
                    screen.menu_view.config = config
                    screen.menu_view.refresh()

            screen.app.push_screen(bashmenu_ui.ToggleModalScreen(title, msg), toggle_cb)

    elif item_type in ["choice", "config_choice"]:
        key_path = item.get("key", "")
        if key_path:
            title = item.get("title", item.get("label", "Choose Setting"))
            msg = interpolate_placeholders(item.get("message", item.get("prompt", f"Configure option {key_path}:")), config)
            raw_choices = item.get("options", [
                {"value": "default", "label": "Default ($EDITOR)"},
                {"value": "builtin", "label": "Built-in (BashEdit)"},
            ])
            choices_list = []
            for c in raw_choices:
                if isinstance(c, dict):
                    choices_list.append((str(c.get("value", "")), str(c.get("label", c.get("value", "")))))
                elif isinstance(c, (list, tuple)) and len(c) >= 2:
                    choices_list.append((str(c[0]), str(c[1])))
                else:
                    choices_list.append((str(c), str(c)))

            def choice_cb(res):
                if res is not None:
                    set_config_value(config, key_path, res)
                    save_config(config)
                    screen.menu_view.config = config
                    screen.menu_view.refresh()

            theme = getattr(screen.app, "theme_styles", getattr(screen, "theme_styles", None))
            screen.app.push_screen(bashmenu_ui.ChoiceModalScreen(title, msg, choices=choices_list, theme=theme), choice_cb)

    elif item_type == "config":
        key_path = item.get("key", "")
        if key_path:
            title = item.get("title", item.get("label", "Edit Setting"))
            picker_mode = item.get("picker")

            if picker_mode in ["file", "dir"]:
                start_dir = interpolate_placeholders(item.get("start_dir", "~"), config)
                allow_new = item.get("allow_new", False)

                def picker_cb(chosen_path):
                    if chosen_path is not None:
                        set_config_value(config, key_path, chosen_path)
                        save_config(config)
                        screen.menu_view.config = config
                        screen.menu_view.refresh()

                screen.app.push_screen(
                    bashmenu_ui.FilePickerModalScreen(
                        title,
                        start_dir=start_dir,
                        mode=picker_mode,
                        allow_new=allow_new,
                        theme=getattr(screen.app, "theme_styles", None),
                    ),
                    picker_cb,
                )
            else:
                prompt = item.get("prompt", "Enter new value:")
                masked = item.get("masked", False)
                current_val = str(get_config_value(config, key_path, ""))

                def input_cb(new_val):
                    if new_val is not None:
                        parsed = new_val.strip()
                        if parsed.lower() in ["true", "false"]:
                            parsed = parsed.lower() == "true"
                        elif parsed.isdigit():
                            parsed = int(parsed)
                        set_config_value(config, key_path, parsed)
                        save_config(config)
                        screen.menu_view.config = config
                        screen.menu_view.refresh()

                screen.app.push_screen(
                    bashmenu_ui.InputModalScreen(title, prompt, default_text=current_val, masked=masked),
                    input_cb,
                )

    elif item_type == "editor":
        target_file = item.get("file") or item.get("action")
        resolved_file = interpolate_placeholders(target_file, config) if target_file else None

        show_whitespace = item.get("show_whitespace", False)
        tabstop = item.get("tabstop", 8)
        tab_to_spaces = config.get("settings", {}).get("tab_to_spaces", True)
        display_colors = item.get("display_theme_colors", False) or "--display-theme-colors" in str(item.get("action", ""))

        def launch_editor(fpath):
            import bashedit

            screen.app.push_screen(
                bashedit.BashEditScreen(
                    file_path=fpath,
                    theme=getattr(screen.app, "theme_styles", None),
                    show_whitespace=show_whitespace,
                    tabstop=tabstop,
                    tab_to_spaces=tab_to_spaces,
                    display_theme_colors=display_colors,
                ),
                lambda res: screen.menu_view.refresh(),
            )

        if resolved_file and "{file_picker" in resolved_file:
            picker_spec = _extract_picker_spec(
                resolved_file,
                config=config,
                default_start_dir=item.get("start_dir"),
                target_macro="file_picker",
            )
            is_new = picker_spec["is_new"]
            start_dir = picker_spec["start_dir"]

            def fp_cb(chosen_file):
                if chosen_file:
                    launch_editor(_apply_file_picker_macros(resolved_file, chosen_file, config=config))

            screen.app.push_screen(
                bashmenu_ui.FilePickerModalScreen(
                    "Select File to Edit",
                    start_dir=start_dir,
                    mode="file",
                    allow_new=is_new,
                    theme=getattr(screen.app, "theme_styles", None),
                ),
                fp_cb,
            )
        else:
            launch_editor(resolved_file)

    elif item_type == "python":
        action_name = item.get("action")
        if action_name == "configure_autoexec":
            msg = configure_autoexec()
            screen.app.push_screen(bashmenu_ui.MessageModalScreen("Autoexec Configuration", msg))
        elif "gorillas" in str(action_name):
            import gorillas
            screen.app.push_screen(gorillas.GorillasScreen(), lambda res: screen.menu_view.refresh())
        elif action_name in ("theme_editor", "action_theme_editor") or "themeedit" in str(action_name):
            import themeedit
            cfg = getattr(screen, "config", None)
            if not cfg:
                with contextlib.suppress(Exception):
                    cfg = screen.menu_view.config
            if not cfg:
                cfg = getattr(screen.app, "config", None) or {}
            active_theme = get_config_value(cfg, "theme") or getattr(screen.app, "theme_name", None) or "dracula"
            screen.app.push_screen(
                themeedit.ThemeEditScreen(initial_theme=active_theme),
                lambda res: screen.refresh_environment(),
            )

    elif item_type in ("theme_editor", "theme_edit"):
        import themeedit
        cfg = getattr(screen, "config", None)
        if not cfg:
            with contextlib.suppress(Exception):
                cfg = screen.menu_view.config
        if not cfg:
            cfg = getattr(screen.app, "config", None) or {}
        active_theme = get_config_value(cfg, "theme") or getattr(screen.app, "theme_name", None) or "dracula"
        screen.app.push_screen(
            themeedit.ThemeEditScreen(initial_theme=active_theme),
            lambda res: screen.refresh_environment(),
        )

    elif item_type == "inject_block":
        target_path_str = interpolate_placeholders(item.get("target", ""), config)
        template_path_str = interpolate_placeholders(item.get("template", ""), config)
        block_id = interpolate_placeholders(item.get("block_id", "default"), config)

        if not target_path_str or not template_path_str:
            screen.app.push_screen(
                bashmenu_ui.MessageModalScreen("Configuration Error", "Both 'target' and 'template' paths must be specified.")
            )
            return

        target_path = Path(os.path.abspath(os.path.expanduser(target_path_str)))
        template_path = Path(template_path_str) if os.path.isabs(template_path_str) else Path(BASHMENU_DIR) / template_path_str

        if not template_path.exists():
            screen.app.push_screen(bashmenu_ui.MessageModalScreen("Template Error", f"Template file not found:\n{template_path}"))
            return

        try:
            template_content = template_path.read_text()
            interpolated_content = interpolate_placeholders(template_content, config)
        except (OSError, ValueError) as e:
            screen.app.push_screen(bashmenu_ui.MessageModalScreen("Read Error", f"Failed to read template:\n{e}"))
            return

        start_marker = f"# CODEBLOCK:{block_id}:START"
        end_marker = f"# CODEBLOCK:{block_id}:END"
        block_to_inject = f"\n{start_marker}\n{interpolated_content.strip()}\n{end_marker}\n"

        target_exists = target_path.exists()
        target_content = target_path.read_text() if target_exists else ""
        block_present = start_marker in target_content and end_marker in target_content

        def block_action_cb(choice):
            if choice == "yes":
                if block_present:
                    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)
                    new_content = pattern.sub(block_to_inject.strip(), target_content)
                else:
                    new_content = target_content + ("\n" if target_content and not target_content.endswith("\n") else "") + block_to_inject

                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(new_content)
                    if target_path.name.endswith(".sh") or "autoexec.sh" in target_path_str:
                        target_path.chmod(0o755)
                    screen.app.push_screen(bashmenu_ui.MessageModalScreen("Success", f"Code block '{block_id}' installed in:\n{target_path}"))
                except (OSError, ValueError) as e:
                    screen.app.push_screen(bashmenu_ui.MessageModalScreen("Write Error", f"Failed to write target file:\n{e}"))
            elif choice == "no" and block_present:
                pattern = re.compile(rf"\n?{re.escape(start_marker)}.*?{re.escape(end_marker)}\n?", re.DOTALL)
                new_content = pattern.sub("", target_content)
                try:
                    target_path.write_text(new_content)
                    screen.app.push_screen(bashmenu_ui.MessageModalScreen("Success", f"Code block '{block_id}' removed from:\n{target_path}"))
                except (OSError, ValueError) as e:
                    screen.app.push_screen(bashmenu_ui.MessageModalScreen("Write Error", f"Failed to write target file:\n{e}"))

        if block_present:
            msg = f"Code block '{block_id}' is already present in:\n{target_path}\n\n- Press YES to reinstall/update.\n- Press NO to uninstall/remove.\n- Press [C / ESC] Cancel to abort."
            screen.app.push_screen(bashmenu_ui.ConfirmModalScreen("Update or Uninstall Block", msg), block_action_cb)
        else:
            msg = f"Would you like to inject code block '{block_id}' into:\n{target_path}?"
            screen.app.push_screen(bashmenu_ui.ConfirmModalScreen("Install Code Block", msg), block_action_cb)

    elif item_type in ["command", "script", "action"] or "command" in item or "script" in item or "action" in item:
        user_mode = item.get("user_mode")
        if user_mode == "root" and os.geteuid() != 0:
            screen.app.push_screen(
                bashmenu_ui.MessageModalScreen("Permission Denied", "This operation requires root permissions (run with sudo).")
            )
            return

        action_str = interpolate_placeholders(
            item.get("action") or item.get("command") or item.get("script") or "", config
        )

        def resolve_and_run(curr_action):
            """Recursively resolve interactive macros ({param}, {file_picker}, {dir_picker}) then execute action."""
            if not curr_action:
                return

            # 1. Resolve interactive parameter input ({param})
            if "{param}" in curr_action:
                title = item.get("title", "Parameter Input")
                prompt = item.get("prompt", "Enter parameter:")
                masked = item.get("masked", False)

                def p_cb(val):
                    if val is not None:
                        resolve_and_run(curr_action.replace("{param}", val))

                screen.app.push_screen(bashmenu_ui.InputModalScreen(title, prompt, masked=masked), p_cb)
                return

            # 2. Resolve interactive file picker macro ({file_picker})
            if "{file_picker" in curr_action:
                picker_spec = _extract_picker_spec(
                    curr_action,
                    config=config,
                    default_start_dir=item.get("start_dir"),
                    target_macro="file_picker",
                )
                is_new = picker_spec["is_new"]
                title = item.get("title", "Select File" if not is_new else "Select or Create File")
                start_dir = picker_spec["start_dir"]

                def f_cb(fpath):
                    if fpath is not None:
                        res = _apply_file_picker_macros(curr_action, fpath, config=config)
                        resolve_and_run(res)

                screen.app.push_screen(
                    bashmenu_ui.FilePickerModalScreen(
                        title,
                        start_dir=start_dir,
                        mode="file",
                        allow_new=is_new,
                        theme=getattr(screen.app, "theme_styles", None),
                    ),
                    f_cb,
                )
                return

            # 3. Resolve interactive directory picker macro ({dir_picker})
            if "{dir_picker" in curr_action:
                picker_spec = _extract_picker_spec(
                    curr_action,
                    config=config,
                    default_start_dir=item.get("start_dir"),
                    target_macro="dir_picker",
                )
                is_new = picker_spec["is_new"]
                title = item.get("title", "Select Directory" if not is_new else "Select or Create Directory")
                start_dir = picker_spec["start_dir"]

                def d_cb(dpath):
                    if dpath is not None:
                        res = _apply_dir_picker_macros(curr_action, dpath, config=config)
                        resolve_and_run(res)

                screen.app.push_screen(
                    bashmenu_ui.FilePickerModalScreen(
                        title,
                        start_dir=start_dir,
                        mode="dir",
                        allow_new=is_new,
                        theme=getattr(screen.app, "theme_styles", None),
                    ),
                    d_cb,
                )
                return

            if "menuedit.py" in curr_action:
                import menuedit

                def menu_cb(res):
                    if item.get("refresh", False):
                        screen.refresh_environment()
                    screen.menu_view.refresh()

                curr_row = screen.menu_view.current_row()
                curr_opts = screen.menu_view.current_menu().get("options", [])
                sel_item = curr_opts[curr_row] if (0 <= curr_row < len(curr_opts)) else item
                title_chain = _get_active_title_chain(screen)

                screen.app.push_screen(
                    menuedit.MenuEditScreen(
                        menu_file_path=MENU_FILE,
                        selected_item=sel_item,
                        title_chain=title_chain,
                        theme=getattr(screen.app, "theme_styles", None),
                    ),
                    menu_cb,
                )
                return

            if "bashedit.py" in curr_action:
                import bashedit

                display_colors = "--display-theme-colors" in curr_action
                target_file = None
                parts = curr_action.split()
                for p in parts:
                    if p != "bashedit.py" and not p.startswith("--") and not p.endswith("python") and not p.endswith("python3"):
                        target_file = p
                        break

                screen.app.push_screen(
                    bashedit.BashEditScreen(
                        file_path=target_file,
                        theme=getattr(screen.app, "theme_styles", None),
                        display_theme_colors=display_colors,
                    ),
                    lambda res: screen.menu_view.refresh(),
                )
                return

            raw_stream = item.get("stream", False)
            is_stream = bool(raw_stream) if isinstance(raw_stream, bool) else str(raw_stream).lower() in ["true", "1", "yes"]
            no_formatting = bool(item.get("no_formatting", False))
            is_quiet = bool(item.get("quiet", False))

            if is_stream:
                title = item.get("title", item.get("label", "Stream Output"))

                def stream_cb(res):
                    if item.get("refresh", False):
                        screen.refresh_environment()
                    screen.menu_view.refresh()

                screen.app.push_screen(
                    bashmenu_ui.StreamOutputModalScreen(title, curr_action, no_formatting=no_formatting),
                    stream_cb,
                )
            else:
                use_alt_buffer = bool(item.get("alt_buffer", True))
                with screen.app.suspend():
                    if use_alt_buffer:
                        sys.stdout.write("\x1b[?1049h")
                        sys.stdout.flush()
                    try:
                        if not is_quiet:
                            print(f"\n--- Running Command: {curr_action} ---\n")
                        subprocess.run(curr_action, shell=True, executable=BASH_BIN, check=False)
                        if not is_quiet:
                            print("\n--------------------------------------------------")
                            input("Execution complete. Press [ENTER] to return...")
                    finally:
                        if use_alt_buffer:
                            sys.stdout.write("\x1b[?1049l")
                            sys.stdout.flush()

                if item.get("refresh", False):
                    screen.refresh_environment()
                screen.menu_view.refresh()

        resolve_and_run(action_str)


class BashMenuScreen(Screen):
    """Main Screen containing MainMenuView widget and keybindings."""

    DEFAULT_CSS = """
    BashMenuScreen {
        layers: base top;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("pageup", "move_home", "Home", show=False),
        Binding("pagedown", "move_end", "End", show=False),
        Binding("enter", "select_option", "Select", show=False),
        Binding("f1", "help", "Help"),
        Binding("f2", "themes", "Themes"),
        Binding("f3", "launch_editor", "Text Editor"),
        Binding("f4", "edit_menu", "Edit Menu"),
        Binding("f5", "refresh_menu", "Refresh"),
        Binding("f6", "toggle_shortcuts", "Keys"),
        Binding("f7", "edit_status_gutter", "Gutter"),
        Binding("f8", "theme_editor", "Theme Editor"),
        Binding("escape", "go_back", "Back/Exit"),
    ]

    def __init__(self, config=None, menu_data=None, **kwargs):
        super().__init__(**kwargs)
        self.initial_config = config
        self.initial_menu_data = menu_data

    def compose(self) -> ComposeResult:
        yield MainMenuView(config=self.initial_config, menu_data=self.initial_menu_data, id="menu_view")
        yield PluginBuffer(config=self.initial_config, id="plugin_buffer")

    @property
    def menu_view(self) -> MainMenuView:
        return self.query_one("#menu_view", MainMenuView)

    @property
    def plugin_buffer(self) -> PluginBuffer:
        return self.query_one("#plugin_buffer", PluginBuffer)

    def _determine_refresh_interval(self) -> float:
        """Return optimal periodic refresh interval based on user settings or status gutter clock granularity."""
        cfg = None
        with contextlib.suppress(Exception):
            cfg = getattr(self.menu_view, "config", None)
        if not cfg:
            cfg = self.initial_config or {}

        # 1. Explicit user override in settings.refresh_interval / settings.status_refresh_rate
        for key in (
            "settings.refresh_interval",
            "settings.status_refresh_rate",
            "settings.status_refresh_interval",
            "settings.status_refresh",
        ):
            custom_interval = get_config_value(cfg, key, None)
            if custom_interval is not None:
                try:
                    val = float(custom_interval)
                    # Support both milliseconds (e.g. >= 50 like plugin intervals) and seconds (e.g. 1.0 or 2)
                    if val >= 50:
                        val = val / 1000.0
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass

        # 2. Dynamic clock granularity based on status_gutter placeholders
        gutter = str(get_config_value(cfg, "settings.status_gutter", ""))
        second_tokens = (
            "{date_time_24}",
            "{date_time_12}",
            "{time_24}",
            "{time_12}",
            "{seconds}",
            "%S",
        )
        if any(tok in gutter for tok in second_tokens):
            return 1.0
        return 5.0

    def on_mount(self) -> None:
        self._update_plugin_buffer_geometry()
        interval = self._determine_refresh_interval()
        self._refresh_timer = self.set_interval(interval, self._periodic_refresh)
        app_obj = None
        with contextlib.suppress(Exception):
            app_obj = getattr(self, "_app", None) or getattr(self, "app", None)
        if app_obj and hasattr(app_obj, "setup_inactivity_timer"):
            app_obj.setup_inactivity_timer()

    def _update_plugin_buffer_geometry(self) -> None:
        """The `_update_plugin_buffer_geometry` method positions and bounds
        the PluginBuffer widget directly above the help/status gutter.
        """
        with contextlib.suppress(Exception):
            screen_w = 0
            with contextlib.suppress(Exception):
                if self.screen and self.screen.size.width:
                    screen_w = self.screen.size.width
            if not screen_w:
                screen_w = self.size.width or 80
            w = max(40, screen_w)
            h = max(10, self.size.height or 24)
            avail_w = max(20, w - 6)
            screen_div_w = max(20, w - 2)
            t_rows = getattr(self.menu_view, "total_content_rows", None)
            total_content_rows = t_rows if isinstance(t_rows, int) else max(1, h - 5)
            raw_plugin_lines, separator_rows, _ = self.menu_view.get_plugin_lines_and_limits(total_content_rows)
            plugin_count = len(raw_plugin_lines)

            pb = self.plugin_buffer
            pb.config = self.menu_view.config

            theme_styles = bashmenu_ui.init_theme_colors(self.menu_view.config.get("theme", "dracula"))
            plugin_style = theme_styles.get("plugin", Style(color="cyan"))
            bg_style = theme_styles.get("background")
            bg_hex = get_hex_from_style(bg_style, "#000000")
            if plugin_style and plugin_style.bgcolor:
                plugin_bg_hex = get_hex_from_style(plugin_style, bg_hex)
                pb.styles.background = plugin_bg_hex
            else:
                pb.styles.background = None
            self.menu_view.styles.background = bg_hex

            if plugin_count == 0:
                pb.styles.display = "none"
            else:
                pb.styles.display = "block"
                div_cfg = get_effective_divider_config(self.menu_view.config)
                length_val = div_cfg.get("length", "{window_width}")
                if isinstance(length_val, dict):
                    is_screen = any("screen_width" in str(k) for k in length_val)
                else:
                    is_screen = "screen_width" in str(length_val)

                has_screen_divider = is_screen and any(
                    any(tok in line for tok in ("{divider}", "{user.divider}", "{settings.divider}"))
                    for line in raw_plugin_lines
                )

                pb_offset_x = 1 if has_screen_divider else 3
                pb_width = screen_div_w if has_screen_divider else avail_w
                plugin_start_row = 3 + total_content_rows - plugin_count - separator_rows
                pb.styles.offset = (pb_offset_x, plugin_start_row)
                pb.styles.width = pb_width
                pb.styles.height = plugin_count
                pb.refresh()

    def _is_covered(self) -> bool:
        """Return True if any modal, popup, or overlay window is currently over this screen."""
        with contextlib.suppress(Exception):
            app = getattr(self, "app", None) or getattr(self, "_app", None)
            if not app:
                return False
            if getattr(app, "screen", None) is not self:
                return True
            screen_stack = getattr(app, "screen_stack", None)
            if screen_stack and self in screen_stack and screen_stack[-1] is not self:
                return True
        return False

    def on_screen_suspend(self) -> None:
        """Pause all background timers and ticks when another screen/modal covers MenuScreen."""
        with contextlib.suppress(Exception):
            if hasattr(self, "_refresh_timer") and self._refresh_timer:
                self._refresh_timer.pause()
        with contextlib.suppress(Exception):
            mv = getattr(self, "menu_view", None)
            if mv and getattr(mv, "_marquee_timer", None):
                mv._marquee_timer.pause()
        with contextlib.suppress(Exception):
            for mq in self.query(bashmenu_ui.MarqueeLabel):
                if getattr(mq, "_timer", None):
                    mq._timer.pause()

    def on_screen_resume(self) -> None:
        """Resume background timers and trigger a refresh when returning to MenuScreen."""
        with contextlib.suppress(Exception):
            if hasattr(self, "_refresh_timer") and self._refresh_timer:
                self._refresh_timer.resume()
        with contextlib.suppress(Exception):
            mv = getattr(self, "menu_view", None)
            if mv and getattr(mv, "_marquee_timer", None):
                mv._marquee_timer.resume()
        with contextlib.suppress(Exception):
            for mq in self.query(bashmenu_ui.MarqueeLabel):
                if getattr(mq, "_timer", None):
                    mq._timer.resume()
        with contextlib.suppress(Exception):
            self._periodic_refresh()

    def _periodic_refresh(self) -> None:
        """The `_periodic_refresh` method refreshes the menu view periodically.
        When only the clock/gutter or plugins update, it limits refreshes to the
        affected regions to decouple background wallpaper from timer ticks.
        """
        if self._is_covered():
            return
        with contextlib.suppress(Exception):
            mv = self.menu_view
            h = max(10, mv.size.height or 24)
            w = max(40, mv.size.width or 80)
            # The help keys & status gutter occupy up to 2 rows directly above the bottom border (h - 3, h - 2)
            gutter_region = Region(0, max(0, h - 3), w, 2)
            mv.refresh(gutter_region)
            self._update_plugin_buffer_geometry()

    def on_resize(self, event) -> None:
        """The `on_resize` method updates plugin buffer bounds upon window resize."""
        self._update_plugin_buffer_geometry()

    def on_key(self, event: Key) -> None:
        mv = self.menu_view
        curr_m = mv.current_menu()
        if curr_m.get("_is_notebook"):
            if event.key in ("n", "N") or getattr(event, "character", None) in ("n", "N"):
                self.action_new_note()
                event.stop()
                event.prevent_default()
                return
            if event.key in ("m", "M") or getattr(event, "character", None) in ("m", "M"):
                self.action_rename_note()
                event.stop()
                event.prevent_default()
                return
            if event.key in ("d", "D") or getattr(event, "character", None) in ("d", "D"):
                self.action_delete_note()
                event.stop()
                event.prevent_default()
                return

        opts = curr_m.get("items", curr_m.get("options", []))
        shortcut_chars = "123456789abcdefghijklmnopqrstuvwxyz"

        shortcut_map = {}
        sc_idx = 0
        for idx, opt in enumerate(opts):
            if not is_divider(opt) and sc_idx < len(shortcut_chars):
                shortcut_map[shortcut_chars[sc_idx]] = idx
                sc_idx += 1

        if mv.show_shortcuts and event.character in shortcut_map:
            target_idx = shortcut_map[event.character]
            mv.set_current_row(target_idx)
            item = opts[target_idx]
            process_item_action(self, item, mv.config)

    def on_mouse_scroll_down(self, event) -> None:
        mv = getattr(self, "menu_view", None)
        if mv:
            mv.scroll_down(step=1)
        event.prevent_default()
        event.stop()

    def on_mouse_scroll_up(self, event) -> None:
        mv = getattr(self, "menu_view", None)
        if mv:
            mv.scroll_up(step=1)
        event.prevent_default()
        event.stop()

    def action_move_up(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("items", mv.current_menu().get("options", []))
        if not opts:
            return
        orig = mv.current_row()
        idx = (orig - 1) % len(opts)
        while idx != orig and is_divider(opts[idx]):
            idx = (idx - 1) % len(opts)
        mv.set_current_row(idx)

    def action_move_down(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("items", mv.current_menu().get("options", []))
        if not opts:
            return
        orig = mv.current_row()
        idx = (orig + 1) % len(opts)
        while idx != orig and is_divider(opts[idx]):
            idx = (idx + 1) % len(opts)
        mv.set_current_row(idx)

    def action_move_home(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("items", mv.current_menu().get("options", []))
        idx = 0
        while idx < len(opts) and is_divider(opts[idx]):
            idx += 1
        mv.set_current_row(idx)

    def action_move_end(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("items", mv.current_menu().get("options", []))
        idx = len(opts) - 1
        while idx >= 0 and is_divider(opts[idx]):
            idx -= 1
        mv.set_current_row(idx)

    def action_select_option(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("items", mv.current_menu().get("options", []))
        curr_row = mv.current_row()
        if 0 <= curr_row < len(opts):
            item = opts[curr_row]
            process_item_action(self, item, mv.config)

    def action_go_back(self) -> None:
        mv = self.menu_view
        if len(mv.menu_stack) > 1:
            mv.menu_stack.pop()
            mv.selected_rows.pop()
            if hasattr(mv, "scroll_offsets") and len(mv.scroll_offsets) > 1:
                mv.scroll_offsets.pop()
            mv.refresh()
        else:
            self.app.exit()

    def action_launch_editor(self) -> None:
        import bashedit

        self.app.push_screen(
            bashedit.BashEditScreen(
                theme=getattr(self.app, "theme_styles", None),
            ),
            lambda res: self.refresh_environment(),
        )

    def action_edit_menu(self) -> None:
        curr_row = self.menu_view.current_row()
        curr_opts = self.menu_view.current_menu().get("options", [])
        sel_item = curr_opts[curr_row] if (0 <= curr_row < len(curr_opts)) else None
        title_chain = _get_active_title_chain(self)

        import menuedit

        self.app.push_screen(
            menuedit.MenuEditScreen(
                menu_file_path=MENU_FILE,
                selected_item=sel_item,
                title_chain=title_chain,
                theme=getattr(self.app, "theme_styles", None),
            ),
            lambda res: self.refresh_environment(),
        )

    def action_theme_editor(self) -> None:
        """Launch the interactive Visual Theme Editor."""
        app_obj = getattr(self, "_app", None)
        if not app_obj:
            with contextlib.suppress(Exception):
                app_obj = self.app
        cfg = getattr(self, "config", None)
        if not cfg:
            with contextlib.suppress(Exception):
                cfg = self.menu_view.config
        if not cfg:
            cfg = getattr(app_obj, "config", None) or {}
        active_theme = get_config_value(cfg, "theme") or getattr(app_obj, "theme_name", None) or "dracula"
        import themeedit

        if app_obj:
            app_obj.push_screen(
                themeedit.ThemeEditScreen(initial_theme=active_theme),
                lambda res: self.refresh_environment(),
            )

    def action_help(self) -> None:
        help_path = os.path.join(BASHMENU_DIR, "bashmenu.md")
        help_text = "Help manual file not found."
        if os.path.exists(help_path):
            with open(help_path, "r", encoding="utf-8") as f:
                help_text = f.read()
        self.app.push_screen(
            bashmenu_ui.MessageModalScreen(
                "HA Bash Menu Manual",
                help_text,
                theme=getattr(self.app, "theme_styles", None),
                is_help=True,
                is_markdown=True,
            )
        )

    def action_themes(self) -> None:
        current_theme = self.menu_view.config.get("theme", "dracula")

        def theme_cb(choice):
            if choice:
                set_config_value(self.menu_view.config, "theme", choice)
                save_config(self.menu_view.config)
                new_styles = bashmenu_ui.init_theme_colors(choice)
                self.theme_styles = new_styles
                self.menu_view.theme_styles = new_styles
                if hasattr(self, "app") and self.app:
                    self.app.theme_styles = new_styles
                self.menu_view.refresh()
                self._update_plugin_buffer_geometry()
            else:
                self.refresh_environment()

        self.app.push_screen(
            bashmenu_ui.ThemePickerModalScreen(
                current_theme=current_theme,
                theme=getattr(self.app, "theme_styles", None),
            ),
            theme_cb,
        )

    def action_refresh_menu(self) -> None:
        """Reload configurations, themes, menus, caches, and source files (F5 hot-reload)."""
        self.refresh_environment(clear_plugins=True, reload_modules=True)

    def action_toggle_shortcuts(self) -> None:
        mv = self.menu_view
        mv.show_shortcuts = not mv.show_shortcuts
        set_config_value(mv.config, "settings.show_menu_shortcuts", mv.show_shortcuts)
        save_config(mv.config)
        mv.refresh()

    def action_edit_status_gutter(self) -> None:
        """Launch the status gutter format configuration modal (F7)."""
        current_val = str(get_config_value(self.menu_view.config, "settings.status_gutter", "{user} | {battery} | {date_time_24}"))
        prompt = (
            "Enter status gutter format. Available options: {user}, {battery}, "
            "{date}, {date_time_24}, {date_time_24_short}, {date_time_12}, "
            "{date_time_12_short}, {host}, {user-mode}, {version}, {utc_seconds}"
        )
        app_obj = getattr(self, "_app", None)
        if not app_obj:
            with contextlib.suppress(Exception):
                app_obj = self.app
        theme = getattr(app_obj, "theme_styles", getattr(self, "theme_styles", None))

        def input_cb(new_val: str | None) -> None:
            if new_val is not None:
                set_config_value(self.menu_view.config, "settings.status_gutter", new_val.strip())
                save_config(self.menu_view.config)
                self.menu_view.refresh()

        modal = bashmenu_ui.InputModalScreen("Configure Status Gutter", prompt, default_text=current_val, theme=theme)
        if app_obj:
            app_obj.push_screen(modal, input_cb)

    def action_new_note(self) -> None:
        """Prompt for a new note title and launch the note editor."""
        curr_m = self.menu_view.current_menu()
        if not curr_m.get("_is_notebook"):
            return
        filepath = curr_m.get("_notebook_file")
        if not filepath:
            return

        theme = getattr(self.app, "theme_styles", getattr(self, "theme_styles", None))

        def on_title_entered(title: str | None) -> None:
            if not title or not title.strip():
                return
            clean_title = title.strip()
            self.open_note_editor(filepath, clean_title, initial_content="", is_new=True)

        self.app.push_screen(
            bashmenu_ui.InputModalScreen("New Note", "Enter note title:", theme=theme),
            on_title_entered,
        )

    def action_rename_note(self, specific_title: str | None = None, from_viewer: bool = False) -> None:
        """Prompt to rename the currently selected (or specified) notebook note."""
        curr_m = self.menu_view.current_menu()
        if not curr_m.get("_is_notebook"):
            return
        filepath = curr_m.get("_notebook_file")
        if not filepath:
            return

        note_title = specific_title
        if not note_title:
            opts = curr_m.get("items", curr_m.get("options", []))
            curr_row = self.menu_view.current_row()
            if 0 <= curr_row < len(opts):
                item = opts[curr_row]
                if item.get("type") == "notebook_note":
                    note_title = item.get("_note_title") or item.get("title")

        if not note_title:
            return

        theme = getattr(self.app, "theme_styles", getattr(self, "theme_styles", None))

        def on_rename_entered(new_title: str | None) -> None:
            if not new_title or not new_title.strip():
                if from_viewer:
                    self.open_note_viewer(filepath, note_title)
                return
            clean_new_title = new_title.strip()
            if clean_new_title == note_title:
                if from_viewer:
                    self.open_note_viewer(filepath, note_title)
                return
            nb_data = bashmenu_ui.load_notebook(filepath)
            if bashmenu_ui.rename_note(nb_data, note_title, clean_new_title):
                bashmenu_ui.save_notebook(filepath, nb_data)
                self.refresh_current_notebook(filepath, select_title=clean_new_title)
                if from_viewer:
                    self.open_note_viewer(filepath, clean_new_title)
            elif from_viewer:
                self.open_note_viewer(filepath, note_title)

        self.app.push_screen(
            bashmenu_ui.InputModalScreen("Rename Note", "Enter new note title:", default_text=note_title, theme=theme),
            on_rename_entered,
        )

    def action_delete_note(self) -> None:
        """Prompts to delete the currently selected notebook note."""
        curr_m = self.menu_view.current_menu()
        if not curr_m.get("_is_notebook"):
            return
        filepath = curr_m.get("_notebook_file")
        if not filepath:
            return

        opts = curr_m.get("items", curr_m.get("options", []))
        curr_row = self.menu_view.current_row()
        if 0 <= curr_row < len(opts):
            item = opts[curr_row]
            if item.get("type") == "notebook_note":
                note_title = item.get("_note_title") or item.get("title")
                if note_title:
                    self.confirm_delete_note(filepath, note_title)

    def open_note_viewer(self, filepath: str, note_title: str) -> None:
        """Open the formatted note viewer modal for an existing note."""
        nb_data = bashmenu_ui.load_notebook(filepath)
        note_dict = bashmenu_ui.get_note_by_title(nb_data, note_title)
        if not note_dict:
            return
        content = note_dict.get("content", "")
        note_format = note_dict.get("format", "markdown")
        theme = getattr(self.app, "theme_styles", getattr(self, "theme_styles", None))

        def on_viewer_dismissed(action: str | None) -> None:
            if action == "edit":
                reloaded_nb = bashmenu_ui.load_notebook(filepath)
                reloaded_note = bashmenu_ui.get_note_by_title(reloaded_nb, note_title)
                curr_content = reloaded_note.get("content", content) if reloaded_note else content
                self.open_note_editor(filepath, note_title, initial_content=curr_content, is_new=False)
            elif action == "rename":
                self.action_rename_note(specific_title=note_title, from_viewer=True)
            elif action == "delete":
                self.confirm_delete_note(filepath, note_title)

        self.app.push_screen(
            bashmenu_ui.NoteViewerModalScreen(
                title=note_title,
                content=content,
                note_format=note_format,
                theme=theme,
                filepath=filepath,
                note_title=note_title,
            ),
            on_viewer_dismissed,
        )

    def open_note_editor(self, filepath: str, note_title: str, initial_content: str = "", is_new: bool = False) -> None:
        """Open the raw note editor modal with Textual TextArea."""
        theme = getattr(self.app, "theme_styles", getattr(self, "theme_styles", None))

        def on_editor_saved(saved_content: str | None) -> None:
            if saved_content is not None:
                nb_data = bashmenu_ui.load_notebook(filepath)
                bashmenu_ui.add_or_update_note(nb_data, note_title, saved_content)
                bashmenu_ui.save_notebook(filepath, nb_data)
                self.refresh_current_notebook(filepath, select_title=note_title)
                self.open_note_viewer(filepath, note_title)
            elif not is_new:
                self.open_note_viewer(filepath, note_title)

        auto_format = True
        with contextlib.suppress(Exception):
            cfg = getattr(self.menu_view, "config", getattr(self, "config", {}))
            auto_format = get_config_value(cfg, "settings.notebook_auto_format", True)

        self.app.push_screen(
            bashmenu_ui.NoteEditorModalScreen(
                title=f"Editing: {note_title}",
                content=initial_content,
                theme=theme,
                auto_format=auto_format,
            ),
            on_editor_saved,
        )

    def confirm_delete_note(self, filepath: str, note_title: str) -> None:
        """Prompt confirmation before deleting a note."""
        theme = getattr(self.app, "theme_styles", getattr(self, "theme_styles", None))

        def on_confirm_delete(res: str | None) -> None:
            if res == "yes":
                nb_data = bashmenu_ui.load_notebook(filepath)
                bashmenu_ui.delete_note(nb_data, note_title)
                bashmenu_ui.save_notebook(filepath, nb_data)
                self.refresh_current_notebook(filepath)

        self.app.push_screen(
            bashmenu_ui.ConfirmModalScreen(
                "Delete Note",
                f"Are you sure you want to delete note '{note_title}'?",
                theme=theme,
            ),
            on_confirm_delete,
        )

    def refresh_current_notebook(self, filepath: str, select_title: str | None = None) -> None:
        """Reload and rebuild current notebook menu items."""
        nb_data = bashmenu_ui.load_notebook(filepath)
        updated_sub = build_dynamic_notebook_submenu(filepath, notebook_data=nb_data, config=self.menu_view.config)
        self.menu_view.menu_stack[-1] = updated_sub
        opts = updated_sub.get("items", [])
        target_idx = 0
        if select_title:
            for idx, opt in enumerate(opts):
                if opt.get("_note_title") == select_title:
                    target_idx = idx
                    break
        else:
            while target_idx < len(opts) and is_divider(opts[target_idx]):
                target_idx += 1
        self.menu_view.selected_rows[-1] = min(target_idx, max(0, len(opts) - 1))
        if len(self.menu_view.menu_stack) >= 2:
            parent_menu = self.menu_view.menu_stack[-2]
            p_items = parent_menu.get("items", parent_menu.get("options", []))
            for p_item in p_items:
                if isinstance(p_item, dict) and p_item.get("type") == "notebook":
                    p_file = resolve_notebook_path(p_item.get("file"), self.menu_view.config)
                    if os.path.abspath(os.path.expanduser(p_file)) == os.path.abspath(os.path.expanduser(filepath)):
                        p_item["submenu"] = updated_sub
        self.menu_view.refresh()

    def refresh_environment(self, clear_plugins: bool = True, reload_modules: bool = False) -> None:
        # 1. Hot-reload source modules if requested (skips pytest runner to avoid wiping active mocks)
        if reload_modules and "pytest" not in sys.modules:
            for mod_name in ("ymlcheck", "bashmenu_ui", "bashedit", "menuedit", "themeedit"):
                if mod_name in sys.modules and sys.modules[mod_name] is not None:
                    with contextlib.suppress(Exception):
                        importlib.reload(sys.modules[mod_name])
            if (
                "bashmenu" in sys.modules
                and sys.modules["bashmenu"] is not None
                and getattr(sys.modules["bashmenu"], "__name__", "") != "__main__"
            ):
                with contextlib.suppress(Exception):
                    importlib.reload(sys.modules["bashmenu"])

        # 2. Invalidate theme file caches and border cache
        with contextlib.suppress(Exception):
            bashmenu_ui._themes_file_cache.clear()
            bashmenu_ui._themes_last_stat_check.clear()
            bashmenu_ui._theme_styles_cache.clear()
            bashmenu_ui._last_applied_theme_borders = None

        # 3. Clear plugin output and display caches
        if clear_plugins:
            with _plugin_lock:
                _plugin_output_cache.clear()
                _plugin_display_cache.clear()
                _plugin_fetching.clear()

        # 4. Clear command output, battery, and profile path caches
        global _last_battery_time, _last_battery_stat_time
        _cmd_substitution_cache.clear()
        _last_battery_time = 0.0
        _last_battery_stat_time = 0.0
        with contextlib.suppress(Exception):
            get_powershell_profile_path.cache_clear()
            get_shell_profile_path.cache_clear()

        # 5. Reload configuration (bashmenu.yml) and menu data (bashmenu.mnu)
        mv = self.menu_view
        mv.config, _ = load_config()
        mv.menu_data, _ = load_menu()
        mv.menu_stack = [mv.menu_data]
        mv.selected_rows = [0]
        mv.scroll_offsets = [0]
        mv.show_shortcuts = get_config_value(mv.config, "settings.show_menu_shortcuts", True)

        # 6. Re-read and apply active theme styles, borders, and background
        theme_name = mv.config.get("theme", "dracula")
        new_styles = bashmenu_ui.init_theme_colors(theme_name)
        self.theme_styles = new_styles
        mv.theme_styles = new_styles
        app_obj = None
        with contextlib.suppress(Exception):
            app_obj = getattr(self, "_app", None) or getattr(self, "app", None)
        if app_obj:
            app_obj.theme_styles = new_styles
            app_obj.theme_name = theme_name
        bashmenu_ui.apply_theme_to_textual_borders(theme_name)

        bg_style = new_styles.get("background")
        bg_hex = get_hex_from_style(bg_style, "#000000")
        if hasattr(self, "styles"):
            with contextlib.suppress(Exception):
                self.styles.background = bg_hex
        if hasattr(self, "plugin_buffer") and hasattr(self.plugin_buffer, "styles"):
            with contextlib.suppress(Exception):
                p_style = new_styles.get("plugin")
                if p_style and p_style.bgcolor:
                    p_hex = get_hex_from_style(p_style, bg_hex)
                    self.plugin_buffer.styles.background = p_hex
                else:
                    self.plugin_buffer.styles.background = None
        if hasattr(mv, "styles"):
            with contextlib.suppress(Exception):
                mv.styles.background = bg_hex

        # 7. Invalidate pre-baked wallpaper canvas and compositor grid cache
        canvas = getattr(mv, "_canvas", None)
        if canvas and hasattr(canvas, "invalidate"):
            canvas.invalidate()
            if getattr(canvas, "compositor", None):
                canvas.compositor._cached_key = None
                canvas.compositor._cached_grid = None

        # 8. Update plugin buffer geometry and trigger UI widget refresh
        if hasattr(self, "plugin_buffer"):
            self.plugin_buffer.config = mv.config
        get_plugin_outputs(mv.config)
        self._update_plugin_buffer_geometry()
        mv.refresh()
        if hasattr(self, "plugin_buffer"):
            self.plugin_buffer.refresh()

        # 9. Re-arm periodic refresh timer and inactivity timeout
        if hasattr(self, "_refresh_timer") and self._refresh_timer:
            with contextlib.suppress(Exception):
                new_interval = self._determine_refresh_interval()
                if getattr(self._refresh_timer, "interval", None) != new_interval:
                    self._refresh_timer.pause()
                    self._refresh_timer = self.set_interval(new_interval, self._periodic_refresh)
        app_obj = None
        with contextlib.suppress(Exception):
            app_obj = getattr(self, "_app", None) or getattr(self, "app", None)
        if app_obj and hasattr(app_obj, "setup_inactivity_timer"):
            app_obj.setup_inactivity_timer()


class ResponsivenessWatchdog:
    """Monitors UI thread execution times and reports excessive blocking behavior."""

    def __init__(self, threshold_ms: float = 35.0, warning_callback=None):
        self.threshold_ms = threshold_ms
        self.warning_callback = warning_callback or self._default_warn
        self.max_frame_ms = 0.0
        self.total_frames = 0
        self.slow_frames = 0
        self.history: list[tuple[str, float]] = []

    def _default_warn(self, source: str, duration_ms: float):
        import logging

        logger = logging.getLogger("bashmenu")
        logger.warning(
            f"[Watchdog] Excessive blocking in {source}: {duration_ms:.2f}ms (threshold: {self.threshold_ms:.1f}ms)"
        )

    @contextlib.contextmanager
    def measure(self, source: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = (time.perf_counter() - t0) * 1000.0
            self.total_frames += 1
            self.max_frame_ms = max(self.max_frame_ms, dt)
            if len(self.history) < 200:
                self.history.append((source, dt))
            if dt > self.threshold_ms:
                self.slow_frames += 1
                self.warning_callback(source, dt)


class BashMenuApp(App):
    """Main Textual Application for HA Bash Menu."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, config=None, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.theme_name = get_config_value(config or {}, "theme", "dracula")
        self._inactivity_timer = None
        self._is_screensaver_active = False
        self.watchdog = ResponsivenessWatchdog(threshold_ms=35.0)

    def on_mount(self) -> None:
        self.push_screen(BashMenuScreen(config=self.config))
        self.setup_inactivity_timer()

    def on_ready(self) -> None:
        """Arm or reset inactivity timer when application is fully mounted and ready for input."""
        self.reset_inactivity_timer()

    def get_inactivity_config(self) -> tuple[float, str]:
        """The `get_inactivity_config` method retrieves the inactivity timeout
        duration in seconds and the command to execute from configuration.
        """
        cfg = getattr(self, "config", None)
        if cfg is None:
            with contextlib.suppress(Exception):
                if getattr(self, "_screen_stack", None) and hasattr(self.screen, "menu_view"):
                    cfg = getattr(self.screen.menu_view, "config", None)
        if cfg is None:
            cfg, _ = load_config()

        timeout_cfg = get_config_value(cfg, "settings.inactivity_timeout", None)
        if not isinstance(timeout_cfg, dict):
            return 0.0, ""

        ms = timeout_cfg.get("milliseconds", 0)
        cmd = timeout_cfg.get("command", "")
        if not isinstance(cmd, str) or not cmd.strip():
            return 0.0, ""

        try:
            ms_val = float(ms)
        except (ValueError, TypeError):
            return 0.0, ""

        if ms_val <= 0:
            return 0.0, ""

        seconds = ms_val / 1000.0
        interpolated_cmd = interpolate_placeholders(cmd.strip(), cfg)
        return seconds, interpolated_cmd

    def setup_inactivity_timer(self) -> None:
        """The `setup_inactivity_timer` method configures or arms the
        inactivity timer countdown.
        """
        if self._inactivity_timer is not None:
            with contextlib.suppress(Exception):
                self._inactivity_timer.stop()
            self._inactivity_timer = None

        seconds, cmd = self.get_inactivity_config()
        if seconds > 0 and cmd:
            self._inactivity_timer = self.set_timer(
                seconds,
                self._trigger_inactivity_timeout,
                name="inactivity_timeout",
            )

    def reset_inactivity_timer(self) -> None:
        """The `reset_inactivity_timer` method resets the inactivity countdown."""
        if self._is_screensaver_active:
            return
        if self._inactivity_timer is not None:
            task = getattr(self._inactivity_timer, "_task", None)
            if task is not None and not task.done():
                self._inactivity_timer.reset()
                return
            self.setup_inactivity_timer()

    def _trigger_inactivity_timeout(self) -> None:
        """The `_trigger_inactivity_timeout` method executes the screensaver
        command in an alternate screen buffer, suspending Textual.
        """
        if self._is_screensaver_active:
            return
        _, cmd = self.get_inactivity_config()
        if not cmd:
            return

        self._is_screensaver_active = True
        try:
            driver = getattr(self, "_driver", None)
            can_suspend = driver is not None and getattr(driver, "can_suspend", False)

            if can_suspend:
                with self.suspend():
                    sys.stdout.write("\x1b[?1049h\x1b[H\x1b[2J")
                    sys.stdout.flush()
                    try:
                        with contextlib.suppress(KeyboardInterrupt, Exception):
                            subprocess.run(
                                cmd,
                                shell=True,
                                executable=BASH_BIN,
                                check=False,
                            )
                    finally:
                        sys.stdout.write("\x1b[?1049l")
                        sys.stdout.flush()
                with contextlib.suppress(Exception):
                    if getattr(self, "_screen_stack", None):
                        self.screen.refresh()
                self.refresh(layout=True)
            else:
                with contextlib.suppress(KeyboardInterrupt, Exception):
                    subprocess.run(
                        cmd,
                        shell=True,
                        executable=BASH_BIN,
                        check=False,
                    )
        finally:
            self._is_screensaver_active = False
            self.setup_inactivity_timer()

    async def on_event(self, event: events.Event) -> None:
        """The `on_event` method intercepts keyboard and mouse events to reset
        the inactivity timer countdown.
        """
        if isinstance(event, (events.Key, events.MouseEvent)):
            self.reset_inactivity_timer()
        await super().on_event(event)


def main():
    app = BashMenuApp()
    app.run()


if __name__ == "__main__":
    main()
