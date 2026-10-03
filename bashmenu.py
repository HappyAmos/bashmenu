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
import getpass
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import ClassVar

import yaml
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static

# Curses compatibility attributes for mocking/tests
if not hasattr(curses, "COLS"):
    curses.COLS = 80
if not hasattr(curses, "LINES"):
    curses.LINES = 24
if not hasattr(curses, "update_lines_cols"):
    curses.update_lines_cols = lambda: None


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

import bashedit
import bashmenu_ui
import menuedit

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

try:
    import ymlcheck
except ImportError:
    ymlcheck = None

USERNAME = getpass.getuser()
USER_HOME = str(Path.home())
BASHRC_PATH = str(Path.home() / ".bashrc")
VIMRC_PATH = str(Path.home() / ".vimrc")
BASH_ALIASES_PATH = str(Path.home() / ".bash_aliases")
ZSHRC_PATH = str(Path.home() / ".zshrc")
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
run_curses_editor = bashedit.run_curses_editor
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


def get_primary_ip():
    """Retrieve primary outbound IPv4 address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.1)
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


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


PRIMARY_IP = get_primary_ip()

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
    """Retrieve value from nested dict using dot-notation string."""
    if not key_path or not isinstance(key_path, str):
        return default
    keys = key_path.split(".")
    curr = config
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            return default
    return curr


def set_config_value(config, key_path, value):
    """Set value in nested dict using dot-notation string."""
    if not key_path or not isinstance(key_path, str):
        return False
    keys = key_path.split(".")
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
ASCII_PATTERN = re.compile(r"\{ascii:(\d+)\}")
DOT_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)+)\}")


def interpolate_placeholders(text, config, depth=0, extra_vars=None):
    """Interpolate placeholders like {user}, {battery}, {window_width}, {scripts_dir}."""
    if not text or not isinstance(text, str):
        return text if text is not None else ""

    now = datetime.datetime.now(datetime.timezone.utc)

    def replace_ascii(match):
        code_str = match.group(1)
        try:
            code = int(code_str)
            return bytes([code]).decode("cp437", errors="replace")
        except (ValueError, OverflowError):
            return match.group(0)

    res_text = ASCII_PATTERN.sub(replace_ascii, text)

    # Command substitution: {command:cmd} with TTL caching to eliminate UI thread latency
    def replace_command(match):
        cmd_str = match.group(1).strip()
        now_ts = time.time()
        cached = _cmd_substitution_cache.get(cmd_str)
        if cached and (now_ts - cached[0] < _CMD_CACHE_TTL):
            return cached[1]
        try:
            res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=3, check=False)
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
        os.environ["CACHE_DIR"] = resolved_cache
        cache_dir_setting = resolved_cache

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
        "{bashrc}": BASHRC_PATH,
        "{bash_aliases}": BASH_ALIASES_PATH,
        "{vimrc}": VIMRC_PATH,
        "{zshrc}": ZSHRC_PATH,
        "{battery}": get_battery_info(),
        "{window_width}": str(win_w),
        "{window_height}": str(win_h),
        "{date_time_12}": now.strftime("%Y-%m-%d %I:%M:%S %p"),
        "{date_time_12_short}": now.strftime("%Y-%m-%d %I:%M %p"),
        "{date_time_24}": now.strftime("%Y-%m-%d %H:%M:%S"),
        "{date_time_24_short}": now.strftime("%Y-%m-%d %H:%M"),
        "{date}": now.strftime("%Y-%m-%d"),
        "{time_12}": now.strftime("%I:%M:%S %p"),
        "{time_12_short}": now.strftime("%I:%M %p"),
        "{time_24}": now.strftime("%H:%M:%S"),
        "{time_24_short}": now.strftime("%H:%M"),
        "{utc_seconds}": str(int(now.timestamp())),
        "{user-mode}": "Root" if os.geteuid() == 0 else "User",
        "{version}": __version__,
        "{localip}": PRIMARY_IP,
    }

    if extra_vars:
        for k, v in extra_vars.items():
            placeholders[f"{{{k}}}"] = str(v)

    if "{divider}" in res_text:
        tw = win_w if (extra_vars and "window_width" in extra_vars) else None
        res_text = res_text.replace("{divider}", resolve_divider_string(config, target_w=tw, extra_vars=extra_vars))

    for k, v in placeholders.items():
        if k in res_text:
            res_text = res_text.replace(k, str(v))

    def replace_dot_var(match):
        key_path = match.group(1)
        val = get_config_value(config, key_path)
        if key_path in ("user.divider", "settings.divider") or (isinstance(val, dict) and ("char" in val or "length" in val)):
            tw = win_w if (extra_vars and "window_width" in extra_vars) else None
            return resolve_divider_string(config, target_w=tw, extra_vars=extra_vars)
        return str(val) if val is not None else match.group(0)

    res_text = DOT_VAR_PATTERN.sub(replace_dot_var, res_text)

    if "{" in res_text and depth < 3:
        res_text = interpolate_placeholders(res_text, config, depth + 1, extra_vars=extra_vars)

    return res_text


def resolve_divider_string(config, target_w=None, extra_vars=None):
    """Generate divider string based on configuration and target width."""
    divider_conf = get_config_value(config, "user.divider", None)
    if divider_conf is None or not isinstance(divider_conf, dict):
        divider_conf = get_config_value(config, "settings.divider", {})
    if not isinstance(divider_conf, dict):
        divider_conf = {}

    char = divider_conf.get("char", "{ascii:196}")
    char = interpolate_placeholders(char, config, extra_vars=extra_vars)
    char = resolve_glyph(char, config)
    if not char:
        char = "─"

    if target_w is not None:
        length = target_w
    elif extra_vars and "window_width" in extra_vars:
        length = int(extra_vars["window_width"])
    else:
        length_spec = divider_conf.get("length", "{window_width}")
        length_str = interpolate_placeholders(str(length_spec), config, extra_vars=extra_vars)
        try:
            length = int(length_str)
        except ValueError:
            length = 80
    raw_div = char * length
    return f"[color=divider]{raw_div}[/color]"


def load_yaml_file(filename):
    """Load YAML file with error formatting."""
    if not os.path.exists(filename):
        return None, f"File not found: {filename}"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}, None
    except (yaml.YAMLError, OSError) as exc:
        return None, f"Error reading '{filename}': {exc}"


_config_has_load_error = False


def save_config(config):
    """Persist current configuration to bashmenu.yml."""
    if _config_has_load_error:
        return
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
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
    options = [
        {
            "type": "divider",
            "length": "{window_width}",
            "char": "{ascii:196}",
        }
    ]
    if themes:
        for theme_key in themes:
            formatted_name = theme_key.replace("_", " ").title()
            options.append({
                "title": formatted_name,
                "label": formatted_name,
                "set_theme": theme_key,
                "icon": "{nf::#f0301:🎨}",
            })
    options.append({
        "type": "divider",
        "length": "{window_width}",
        "char": "{ascii:196}",
    })
    options.append({
        "title": "Back to Options & Settings",
        "label": "Back to Options & Settings",
        "type": "back",
        "icon": "{nf::#f048}",
    })
    return {"title": "Select Color Theme", "options": options}


def inject_dynamic_menus(menu_item):
    """
    Recursively replace 'theme_selector' options with dynamic theme submenus.
    """
    if not isinstance(menu_item, dict):
        return
    options = menu_item.get("options", [])
    for idx, opt in enumerate(options):
        if not isinstance(opt, dict):
            continue
        if opt.get("type") == "theme_selector":
            options[idx]["title"] = opt.get("title", opt.get("label", "Change Theme"))
            options[idx]["submenu"] = build_dynamic_theme_submenu()
        elif "submenu" in opt:
            inject_dynamic_menus(opt["submenu"])


def load_menu():
    """Load menu structure definition from bashmenu.mnu."""
    data, err = load_yaml_file(MENU_FILE)
    if err:
        return {
            "title": "YAML Configuration Error",
            "options": [
                {"label": f"Error: {err}"},
                {"label": "Exit Utility", "type": "exit"},
            ],
        }, err
    inject_dynamic_menus(data)
    return data, None


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
_plugin_fetching = set()
_plugin_lock = threading.RLock()


def _fetch_plugin_worker(name, script_cmd, now):
    try:
        if os.path.exists(script_cmd) and os.path.isfile(script_cmd):
            res = subprocess.run(
                [script_cmd],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        else:
            res = subprocess.run(
                script_cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        raw_out = res.stdout.strip() if res and res.stdout else ""
        plugin_lines = [l for l in raw_out.splitlines() if l.strip()]
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
        with contextlib.suppress(Exception):
            if self.screen and self.screen.menu_view and self.screen.menu_view.config:
                cfg = self.screen.menu_view.config

        raw_plugin_lines = get_plugin_outputs(cfg)
        if not raw_plugin_lines:
            return Text()

        theme_styles = bashmenu_ui.init_theme_colors(cfg.get("theme", "dracula"))
        plugin_style = theme_styles.get("plugin", Style(color="cyan"))
        bg_style = theme_styles.get("background", Style())

        buffer_w = max(20, self.size.width or 80)
        max_rows = min(10, len(raw_plugin_lines))
        lines_to_display = raw_plugin_lines[:max_rows]
        extra_vars = {"window_width": buffer_w, "window_height": max_rows}

        out = Text()
        for idx, p_line in enumerate(lines_to_display):
            clean_line = (
                p_line.replace("\x00", "")
                .replace("\t", "    ")
                .replace("\ufe0f", "")
                .replace("\ufe0e", "")
                .rstrip("\r\n")
            )
            p_line_interp = interpolate_placeholders(clean_line, self.config, extra_vars=extra_vars)

            if "\x1b[" in p_line_interp:
                p_content_rich = Text.from_ansi(p_line_interp)
            else:
                p_content_rich = bashmenu_ui.formatting_to_rich_text(
                    p_line_interp, default_style=plugin_style, theme=theme_styles
                )

            if p_content_rich.cell_len > buffer_w:
                p_content_rich.truncate(buffer_w)
            pad_w = max(0, buffer_w - p_content_rich.cell_len)
            if pad_w > 0:
                p_content_rich.append(" " * pad_w, style=bg_style)

            out.append_text(p_content_rich)
            if idx < len(lines_to_display) - 1:
                out.append("\n")

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
        self.menu_data = menu_data or load_menu()[0]
        self.menu_stack = [self.menu_data]
        self.selected_rows = [0]
        self.show_shortcuts = True
        self.can_focus = True

    def current_menu(self) -> dict:
        return self.menu_stack[-1]

    def current_row(self) -> int:
        return self.selected_rows[-1]

    def set_current_row(self, row: int) -> None:
        opts = self.current_menu().get("options", [])
        if opts:
            self.selected_rows[-1] = max(0, min(row, len(opts) - 1))
            self.refresh()

    def get_plugin_lines_and_limits(self, total_content_rows: int) -> tuple[list[str], int, int]:
        """The `get_plugin_lines_and_limits` method returns the capped plugin
        output lines, separator row count, and available menu option rows.
        """
        raw_plugin_lines = get_plugin_outputs(self.config)
        max_plugin_rows = min(10, max(0, total_content_rows - 2))
        if len(raw_plugin_lines) > max_plugin_rows:
            raw_plugin_lines = raw_plugin_lines[:max_plugin_rows] if max_plugin_rows > 0 else []
        separator_rows = 1 if len(raw_plugin_lines) > 0 else 0
        visible_option_rows = max(1, total_content_rows - len(raw_plugin_lines) - separator_rows)
        return raw_plugin_lines, separator_rows, visible_option_rows

    def render(self) -> Text:
        """Render the complete primary menu interface as an isolated textual screen buffer.

        Constructs top/bottom window borders, menu titles, options with fixed 4-column
        icon slots and column 11 label alignment, shortcut badges, divider rules,
        and bottom status/help gutter. Enforces strict boundary padding and truncation
        to prevent terminal border overflow.
        """
        w = max(40, self.size.width or 80)
        h = max(10, self.size.height or 24)
        out = Text()

        curr_menu = self.current_menu()
        curr_row = self.current_row()
        options = curr_menu.get("options", [])

        theme_styles = bashmenu_ui.init_theme_colors(self.config.get("theme", "dracula"))
        self.theme_styles = theme_styles
        with contextlib.suppress(Exception):
            if hasattr(self, "app") and self.app:
                self.app.theme_styles = theme_styles
            if hasattr(self, "screen") and self.screen:
                self.screen.theme_styles = theme_styles
        indicator_symbol = resolve_glyph(theme_styles.get("indicator", ">"), self.config)
        border_style = theme_styles.get("border", Style(color="blue"))
        title_style = theme_styles.get("title", Style(color="magenta", bold=True))
        highlight_style = theme_styles.get("highlight", Style(color="white", bgcolor="magenta", bold=True))
        text_style = theme_styles.get("text", Style(color="white"))
        shortcut_key_style = theme_styles.get("shortcut_key", Style(color="magenta", bold=True))
        gutter_style = theme_styles.get("gutter", Style(color="cyan", bold=True))
        help_text_style = theme_styles.get("help_text", Style(color="cyan"))

        # 1. Printable dimensions (2-character margins on left and right inside border)
        avail_w = max(20, w - 6)
        # Content rows available for menu options & plugins (excludes top border, 2-row top margin, help/status gutter row, and bottom border)
        total_content_rows = max(1, h - 5)

        # 2. Plugin lines and row allocation
        raw_plugin_lines, separator_rows, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)
        extra_vars = {"window_width": avail_w, "window_height": visible_option_rows}

        # 3. Header border line: ┌── Title ──┐
        title_raw = interpolate_placeholders(curr_menu.get("title", "HA Bash Menu"), self.config, extra_vars=extra_vars)
        title_str = f" {title_raw} "
        title_len = get_visible_len(title_str, self.config)

        left_b = max(2, (w - title_len) // 2)
        right_b = max(2, w - left_b - title_len)

        top_bar = Text("┌" + "─" * (left_b - 1), style=border_style)
        top_bar.append_text(bashmenu_ui.formatting_to_rich_text(title_str, default_style=title_style, theme=theme_styles))
        top_bar.append("─" * (right_b - 1) + "┐\n", style=border_style)
        out.append_text(top_bar)

        # Top Margin Rows (2 blank lines below top border per .gemini specification)
        out.append_text(Text("│  " + " " * avail_w + "  │\n", style=border_style))
        out.append_text(Text("│  " + " " * avail_w + "  │\n", style=border_style))

        # 4. Scroll position calculation
        scroll_start = 0
        if curr_row >= visible_option_rows:
            scroll_start = curr_row - visible_option_rows + 1

        shortcut_chars = "123456789abcdefghijklmnopqrstuvwxyz"
        shortcut_map = {}
        sc_idx = 0
        for idx, opt in enumerate(options):
            if opt.get("type") != "divider" and sc_idx < len(shortcut_chars):
                shortcut_map[idx] = shortcut_chars[sc_idx]
                sc_idx += 1

        rendered_content_rows = 0

        # 5. Render visible menu options
        for i in range(visible_option_rows):
            idx = scroll_start + i
            if idx >= len(options):
                break

            opt = options[idx]
            is_selected = (idx == curr_row)
            item_style = highlight_style if is_selected else text_style

            line_rich = Text("│  ", style=border_style)

            if opt.get("type") == "divider":
                div_str = resolve_divider_string(self.config, target_w=avail_w)
                div_rich = bashmenu_ui.formatting_to_rich_text(div_str, theme=theme_styles)
                line_rich.append_text(div_rich)

                used_w = get_visible_len(div_str, self.config)
                fill_w = max(0, avail_w - used_w)
                line_rich.append(" " * fill_w)
                line_rich.append("  │\n", style=border_style)
                out.append_text(line_rich)
                rendered_content_rows += 1
                continue

            ind_str = f"{indicator_symbol} " if is_selected else "  "
            ind_w = get_display_width(ind_str, self.config)

            sc_char = shortcut_map.get(idx, "")
            sc_str = f"[{sc_char}] " if (self.show_shortcuts and sc_char) else "    "
            sc_w = get_display_width(sc_str, self.config)

            icon_raw = opt.get("icon") or opt.get("glyph") or ""
            icon_resolved = resolve_glyph(interpolate_placeholders(icon_raw, self.config, extra_vars=extra_vars), self.config) if icon_raw else ""
            if icon_resolved:
                clean_icon = icon_resolved.replace("\ufe0f", "").replace("\ufe0e", "")
                vis_w = get_display_width(clean_icon, self.config)
                pad_w = max(1, 4 - vis_w)
                icon_str = f"{clean_icon}{' ' * pad_w}"
                icon_w = vis_w + pad_w
            else:
                icon_str = "    "
                icon_w = 4

            raw_label = interpolate_placeholders(opt.get("label") or opt.get("title") or "", self.config, extra_vars=extra_vars)
            if opt.get("set_theme") == self.config.get("theme"):
                raw_label += " (Active)"

            left_label, right_bracket = split_label_brackets(raw_label)

            prefix_w = ind_w + sc_w + icon_w
            right_w = get_visible_len(right_bracket, self.config) if right_bracket else 0
            label_avail_w = max(5, avail_w - prefix_w - (right_w + 1 if right_w else 0))

            row_content = Text(ind_str, style=item_style)
            if self.show_shortcuts and sc_char:
                row_content.append(f"[{sc_char}] ", style=shortcut_key_style if not is_selected else item_style)
            else:
                row_content.append("    ", style=item_style)

            row_content.append(icon_str, style=item_style)

            lbl_truncated = left_label
            if get_visible_len(left_label, self.config) > label_avail_w:
                low, high = 1, len(left_label)
                best = 1
                while low <= high:
                    mid = (low + high) // 2
                    if get_visible_len(left_label[:mid], self.config) <= label_avail_w:
                        best = mid
                        low = mid + 1
                    else:
                        high = mid - 1
                lbl_truncated = left_label[:best]

            lbl_rich = bashmenu_ui.formatting_to_rich_text(lbl_truncated, default_style=item_style, theme=theme_styles)
            row_content.append_text(lbl_rich)

            rendered_lbl_w = get_visible_len(lbl_truncated, self.config)
            spaces_w = max(0, avail_w - prefix_w - rendered_lbl_w - right_w)
            row_content.append(" " * spaces_w, style=item_style)

            if right_bracket:
                rb_rich = bashmenu_ui.formatting_to_rich_text(right_bracket, default_style=item_style, theme=theme_styles)
                row_content.append_text(rb_rich)

            if row_content.cell_len > avail_w:
                row_content.truncate(avail_w)
            pad_w = max(0, avail_w - row_content.cell_len)
            if pad_w > 0:
                row_content.append(" " * pad_w, style=item_style)

            line_rich.append_text(row_content)
            line_rich.append("  │\n", style=border_style)
            out.append_text(line_rich)
            rendered_content_rows += 1

        # 6. Pad blank rows between menu options and plugins
        target_blank_rows = total_content_rows - len(raw_plugin_lines) - separator_rows
        while rendered_content_rows < target_blank_rows:
            out.append_text(Text("│  " + " " * avail_w + "  │\n", style=border_style))
            rendered_content_rows += 1

        # 7. Rows reserved for the PluginBuffer widget overlay
        for _ in raw_plugin_lines:
            out.append_text(Text("│  " + " " * avail_w + "  │\n", style=border_style))
            rendered_content_rows += 1

        # 8. Blank separation row above Help Keys & Status Gutter (when plugins are active)
        if separator_rows > 0:
            out.append_text(Text("│  " + " " * avail_w + "  │\n", style=border_style))
            rendered_content_rows += 1

        # 9. Help Keys & Status Gutter Row (h - 2)
        help_variants = [
            "[UP/DN]: Nav | [0-9/a-z]: Direct | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back",
            "[UP/DN]: Nav | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back",
            "[UP/DN]: Nav | [F1]: Help | [ESC]: Back",
            "[F1]: Help",
            "",
        ] if self.show_shortcuts else [
            "[UP/DN]: Nav | [ENTER]: Select | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back",
            "[UP/DN]: Nav | [F1]: Help | [F5]: Keys | [F4]: Edit | [ESC]: Back",
            "[UP/DN]: Nav | [F1]: Help | [ESC]: Back",
            "[F1]: Help",
            "",
        ]

        status_gutter_raw = get_config_value(self.config, "settings.status_gutter", "{user} | {battery} | {date_time_24}")
        raw_badges = split_gutter_badges(status_gutter_raw)
        all_badges = [interpolate_placeholders(b, self.config, extra_vars=extra_vars) for b in raw_badges if b.strip()]
        gutter_str = f"{' | '.join(all_badges)}" if all_badges else ""

        gutter_w = get_visible_len(gutter_str, self.config)

        chosen_help = ""
        for hv in help_variants:
            hv_w = get_visible_len(hv, self.config)
            if hv_w + (gutter_w + 2 if gutter_w else 0) <= avail_w:
                chosen_help = hv
                break

        if not chosen_help and help_variants:
            chosen_help = help_variants[-2]
            ch_w = get_visible_len(chosen_help, self.config)
            avail_gutter_w = max(0, avail_w - ch_w - 2)
            while all_badges and get_visible_len(f"{' | '.join(all_badges)}", self.config) > avail_gutter_w:
                all_badges.pop()
            gutter_str = f"{' | '.join(all_badges)}" if all_badges else ""
            gutter_w = get_visible_len(gutter_str, self.config)

        help_w = get_visible_len(chosen_help, self.config)
        footer_spaces = max(0, avail_w - help_w - gutter_w)

        hg_content = Text()
        if chosen_help:
            hg_content.append_text(bashmenu_ui.formatting_to_rich_text(chosen_help, default_style=help_text_style, theme=theme_styles))
        if footer_spaces > 0:
            hg_content.append(" " * footer_spaces, style=border_style)
        if gutter_str:
            hg_content.append_text(bashmenu_ui.formatting_to_rich_text(gutter_str, default_style=gutter_style, theme=theme_styles))

        if hg_content.cell_len > avail_w:
            hg_content.truncate(avail_w)
        hg_pad_w = max(0, avail_w - hg_content.cell_len)
        if hg_pad_w > 0:
            hg_content.append(" " * hg_pad_w, style=border_style)

        hg_line = Text("│  ", style=border_style)
        hg_line.append_text(hg_content)
        hg_line.append("  │\n", style=border_style)
        out.append_text(hg_line)

        # 9. Bottom Border Row (h - 1): └────────...────────┘
        bot_bar = Text("└" + "─" * (w - 2) + "┘", style=border_style)
        out.append_text(bot_bar)

        return out

    def on_click(self, event) -> None:
        rendered_row = event.y - 3
        curr_menu = self.current_menu()
        options = curr_menu.get("options", [])
        if not options:
            return

        total_content_rows = max(1, (self.size.height or 24) - 5)
        _, _, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)

        scroll_start = 0
        curr_row = self.current_row()
        if curr_row >= visible_option_rows:
            scroll_start = curr_row - visible_option_rows + 1

        if 0 <= rendered_row < visible_option_rows:
            target_idx = scroll_start + rendered_row
            if 0 <= target_idx < len(options):
                opt = options[target_idx]
                if opt.get("type") != "divider":
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

    def on_mouse_move(self, event) -> None:
        rendered_row = event.y - 3
        curr_menu = self.current_menu()
        options = curr_menu.get("options", [])
        if not options:
            return

        total_content_rows = max(1, (self.size.height or 24) - 5)
        _, _, visible_option_rows = self.get_plugin_lines_and_limits(total_content_rows)

        scroll_start = 0
        curr_row = self.current_row()
        if curr_row >= visible_option_rows:
            scroll_start = curr_row - visible_option_rows + 1

        if 0 <= rendered_row < visible_option_rows:
            target_idx = scroll_start + rendered_row
            if 0 <= target_idx < len(options):
                opt = options[target_idx]
                if opt.get("type") != "divider" and self.current_row() != target_idx:
                    self.set_current_row(target_idx)


def _get_active_title_chain(screen) -> list[str]:
    chain = []
    with contextlib.suppress(Exception):
        mv = getattr(screen, "menu_view", None)
        if mv:
            for m, r in zip(mv.menu_stack, mv.selected_rows):
                opts = m.get("options", [])
                if 0 <= r < len(opts):
                    opt = opts[r]
                    t = opt.get("title") or opt.get("label")
                    if t:
                        chain.append(str(t))
    return chain


def process_item_action(screen, item, config):
    """Execute menu entry action based on option dictionary definition type."""
    item_type = item.get("type", "command")

    if item_type == "exit":
        screen.app.exit()

    elif item_type == "back":
        screen.action_go_back()

    elif "submenu" in item:
        sub_menu = item["submenu"]
        screen.menu_view.menu_stack.append(sub_menu)
        sub_options = sub_menu.get("options", [])
        start_idx = 0
        while start_idx < len(sub_options) and sub_options[start_idx].get("type") == "divider":
            start_idx += 1
        screen.menu_view.selected_rows.append(min(start_idx, max(0, len(sub_options) - 1)))
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

    elif item_type == "theme_selector":
        item["submenu"] = build_dynamic_theme_submenu()
        sub_menu = item["submenu"]
        screen.menu_view.menu_stack.append(sub_menu)
        sub_options = sub_menu.get("options", [])
        start_idx = 0
        while start_idx < len(sub_options) and sub_options[start_idx].get("type") == "divider":
            start_idx += 1
        screen.menu_view.selected_rows.append(min(start_idx, max(0, len(sub_options) - 1)))
        screen.menu_view.refresh()

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

    elif item_type == "config":
        key_path = item.get("key", "")
        if key_path:
            title = item.get("title", item.get("label", "Edit Setting"))
            picker_mode = item.get("picker")

            if picker_mode in ["file", "dir"]:
                start_dir = interpolate_placeholders(item.get("start_dir", "~"), config)

                def picker_cb(chosen_path):
                    if chosen_path is not None:
                        set_config_value(config, key_path, chosen_path)
                        save_config(config)
                        screen.menu_view.config = config
                        screen.menu_view.refresh()

                screen.app.push_screen(
                    bashmenu_ui.FilePickerModalScreen(title, start_dir=start_dir, mode=picker_mode),
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

        if resolved_file and ("{file_picker}" in resolved_file or "{file_picker_new}" in resolved_file or "{file_picker:new}" in resolved_file):
            start_dir = interpolate_placeholders(item.get("start_dir", "~"), config)

            def fp_cb(chosen_file):
                if chosen_file:
                    launch_editor(chosen_file)

            screen.app.push_screen(bashmenu_ui.FilePickerModalScreen("Select File to Edit", start_dir=start_dir, mode="file"), fp_cb)
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
            if "{file_picker}" in curr_action or "{file_picker_new}" in curr_action or "{file_picker:new}" in curr_action:
                title = item.get("title", "Select File")
                start_dir = interpolate_placeholders(item.get("start_dir", "~"), config)

                def f_cb(fpath):
                    if fpath is not None:
                        res = (
                            curr_action.replace("{file_picker}", fpath)
                            .replace("{file_picker_new}", fpath)
                            .replace("{file_picker:new}", fpath)
                        )
                        resolve_and_run(res)

                screen.app.push_screen(bashmenu_ui.FilePickerModalScreen(title, start_dir=start_dir, mode="file"), f_cb)
                return

            # 3. Resolve interactive directory picker macro ({dir_picker})
            if "{dir_picker}" in curr_action or "{dir_picker_new}" in curr_action or "{dir_picker:new}" in curr_action:
                title = item.get("title", "Select Directory")
                start_dir = interpolate_placeholders(item.get("start_dir", "~"), config)

                def d_cb(dpath):
                    if dpath is not None:
                        res = (
                            curr_action.replace("{dir_picker}", dpath)
                            .replace("{dir_picker_new}", dpath)
                            .replace("{dir_picker:new}", dpath)
                        )
                        resolve_and_run(res)

                screen.app.push_screen(bashmenu_ui.FilePickerModalScreen(title, start_dir=start_dir, mode="dir"), d_cb)
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
                        subprocess.run(curr_action, shell=True, check=False)
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
        Binding("f4", "edit_menu", "Edit Menu"),
        Binding("f5", "toggle_shortcuts", "Keys"),
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

    def on_mount(self) -> None:
        self._update_plugin_buffer_geometry()
        self.set_interval(1.0, self._periodic_refresh)

    def _update_plugin_buffer_geometry(self) -> None:
        """The `_update_plugin_buffer_geometry` method positions and bounds
        the PluginBuffer widget directly above the help/status gutter.
        """
        with contextlib.suppress(Exception):
            w = max(40, self.size.width or 80)
            h = max(10, self.size.height or 24)
            avail_w = max(20, w - 6)
            total_content_rows = max(1, h - 5)
            raw_plugin_lines, separator_rows, _ = self.menu_view.get_plugin_lines_and_limits(total_content_rows)
            plugin_count = len(raw_plugin_lines)

            pb = self.plugin_buffer
            pb.config = self.menu_view.config

            theme_styles = bashmenu_ui.init_theme_colors(self.menu_view.config.get("theme", "dracula"))
            bg_style = theme_styles.get("background")
            bg_hex = get_hex_from_style(bg_style, "#000000")
            pb.styles.background = bg_hex
            self.menu_view.styles.background = bg_hex

            if plugin_count == 0:
                pb.styles.display = "none"
            else:
                pb.styles.display = "block"
                plugin_start_row = 3 + total_content_rows - plugin_count - separator_rows
                pb.styles.offset = (3, plugin_start_row)
                pb.styles.width = avail_w
                pb.styles.height = plugin_count
                pb.refresh()

    def _periodic_refresh(self) -> None:
        """The `_periodic_refresh` method refreshes the menu view periodically."""
        with contextlib.suppress(Exception):
            self.menu_view.refresh()
            self._update_plugin_buffer_geometry()

    def on_resize(self, event) -> None:
        """The `on_resize` method updates plugin buffer bounds upon window resize."""
        self._update_plugin_buffer_geometry()

    def on_key(self, event: Key) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        shortcut_chars = "123456789abcdefghijklmnopqrstuvwxyz"

        shortcut_map = {}
        sc_idx = 0
        for idx, opt in enumerate(opts):
            if opt.get("type") != "divider" and sc_idx < len(shortcut_chars):
                shortcut_map[shortcut_chars[sc_idx]] = idx
                sc_idx += 1

        if mv.show_shortcuts and event.character in shortcut_map:
            target_idx = shortcut_map[event.character]
            mv.set_current_row(target_idx)
            item = opts[target_idx]
            process_item_action(self, item, mv.config)

    def on_mouse_scroll_down(self, event) -> None:
        self.action_move_down()

    def on_mouse_scroll_up(self, event) -> None:
        self.action_move_up()

    def action_move_up(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        if not opts:
            return
        orig = mv.current_row()
        idx = (orig - 1) % len(opts)
        while idx != orig and opts[idx].get("type") == "divider":
            idx = (idx - 1) % len(opts)
        mv.set_current_row(idx)

    def action_move_down(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        if not opts:
            return
        orig = mv.current_row()
        idx = (orig + 1) % len(opts)
        while idx != orig and opts[idx].get("type") == "divider":
            idx = (idx + 1) % len(opts)
        mv.set_current_row(idx)

    def action_move_home(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        idx = 0
        while idx < len(opts) and opts[idx].get("type") == "divider":
            idx += 1
        mv.set_current_row(idx)

    def action_move_end(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        idx = len(opts) - 1
        while idx >= 0 and opts[idx].get("type") == "divider":
            idx -= 1
        mv.set_current_row(idx)

    def action_select_option(self) -> None:
        mv = self.menu_view
        opts = mv.current_menu().get("options", [])
        curr_row = mv.current_row()
        if 0 <= curr_row < len(opts):
            item = opts[curr_row]
            process_item_action(self, item, mv.config)

    def action_go_back(self) -> None:
        mv = self.menu_view
        if len(mv.menu_stack) > 1:
            mv.menu_stack.pop()
            mv.selected_rows.pop()
            mv.refresh()
        else:
            self.app.exit()

    def action_edit_menu(self) -> None:
        curr_row = self.menu_view.current_row()
        curr_opts = self.menu_view.current_menu().get("options", [])
        sel_item = curr_opts[curr_row] if (0 <= curr_row < len(curr_opts)) else None
        title_chain = _get_active_title_chain(self)

        self.app.push_screen(
            menuedit.MenuEditScreen(
                menu_file_path=MENU_FILE,
                selected_item=sel_item,
                title_chain=title_chain,
                theme=getattr(self.app, "theme_styles", None),
            ),
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

        self.app.push_screen(
            bashmenu_ui.ThemePickerModalScreen(
                current_theme=current_theme,
                theme=getattr(self.app, "theme_styles", None),
            ),
            theme_cb,
        )

    def action_toggle_shortcuts(self) -> None:
        mv = self.menu_view
        mv.show_shortcuts = not mv.show_shortcuts
        set_config_value(mv.config, "settings.show_menu_shortcuts", mv.show_shortcuts)
        save_config(mv.config)
        mv.refresh()

    def refresh_environment(self) -> None:
        mv = self.menu_view
        mv.config, _ = load_config()
        mv.menu_data, _ = load_menu()
        mv.menu_stack = [mv.menu_data]
        mv.selected_rows = [0]
        mv.refresh()
        self._update_plugin_buffer_geometry()


class BashMenuApp(App):
    """Main Textual Application for HA Bash Menu."""

    ENABLE_COMMAND_PALETTE = False

    def on_mount(self) -> None:
        self.push_screen(BashMenuScreen())


def main():
    app = BashMenuApp()
    app.run()


if __name__ == "__main__":
    main()
