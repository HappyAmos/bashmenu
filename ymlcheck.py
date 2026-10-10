#!/usr/bin/env python3
"""
ymlcheck.py - Theme and YAML Configuration Validator.

Validates YAML files for HA Bash Menu. By default, checks if the YAML is
well-formed syntax with no schema enforcement. Mode flags (--themes, --config,
--menu) enable dedicated schema and domain validation for specific file types.
"""

import argparse
import os
import sys
from typing import Any

import yaml

__version__ = "0.0.2"
__author__ = "HA Bash Menu Development Team"

VALID_16_COLORS = {
    "COLOR_BLACK", "COLOR_RED", "COLOR_GREEN", "COLOR_YELLOW",
    "COLOR_BLUE", "COLOR_MAGENTA", "COLOR_CYAN", "COLOR_WHITE",
    "COLOR_GREY", "COLOR_GRAY", "COLOR_BRIGHT_BLACK", "COLOR_BRIGHT_RED",
    "COLOR_BRIGHT_GREEN", "COLOR_BRIGHT_YELLOW", "COLOR_BRIGHT_BLUE",
    "COLOR_BRIGHT_MAGENTA", "COLOR_BRIGHT_CYAN", "COLOR_BRIGHT_WHITE",
    "COLOR_ORANGE", "COLOR_PURPLE", "COLOR_PINK", "COLOR_BROWN"
}

# Recognized color depth palette section keys
VALID_DEPTHS = {"256", "16", "8", "truecolor"}

# Non-color structural attributes permitted in theme definitions
VALID_NON_COLOR_KEYS = {"indicator", "prefix"}

# Permitted window border keys in theme window: sections
VALID_WINDOW_BORDER_KEYS = {
    "border_horizontal",
    "border_vertical",
    "border_horizontal_top",
    "border_horizontal_bottom",
    "border_vertical_left",
    "border_vertical_right",
    "border_top",
    "border_bottom",
    "border_left",
    "border_right",
    "border_top_left",
    "border_top_right",
    "border_bottom_left",
    "border_bottom_right",
    "border_tee_top",
    "border_tee_bottom",
    "border_tee_left",
    "border_tee_right",
    "border_cross",
    "left_tee",
    "right_tee",
    "top_tee",
    "bottom_tee",
    "tee_left",
    "tee_right",
    "tee_top",
    "tee_bottom",
    "window_left_tee",
    "window_right_tee",
    "window_top_tee",
    "window_bottom_tee",
    "window_tee_left",
    "window_tee_right",
    "window_tee_top",
    "window_tee_bottom",
    "title_left_cap",
    "title_right_cap",
    "title_cap_left",
    "title_cap_right",
    "shadow_char",
    "window_border_horizontal",
    "window_border_vertical",
    "window_border_horizontal_top",
    "window_border_horizontal_bottom",
    "window_border_vertical_left",
    "window_border_vertical_right",
    "window_border_top",
    "window_border_bottom",
    "window_border_left",
    "window_border_right",
    "window_border_top_left",
    "window_border_top_right",
    "window_border_bottom_left",
    "window_border_bottom_right",
    "window_border_tee_top",
    "window_border_tee_bottom",
    "window_border_tee_left",
    "window_border_tee_right",
    "window_border_cross",
    "window_title_left_cap",
    "window_title_right_cap",
    "window_title_cap_left",
    "window_title_cap_right",
    "window_shadow_char",
}

# Permitted option types in bashmenu.mnu
VALID_OPTION_TYPES = {
    "command", "script", "submenu", "config", "toggle", "editor",
    "confirm", "message", "popup", "info", "python", "inject_block",
    "theme_selector", "{divider}", "back", "exit", "action"
}


def format_yaml_error(error: yaml.YAMLError) -> str:
    """Format PyYAML syntax errors for readable terminal output."""
    if hasattr(error, 'problem_mark'):
        mark = error.problem_mark
        return (
            f"Syntax Error at line {mark.line + 1}, column {mark.column + 1}:\n"
            f"  {error.problem}\n"
            f"  Line snippet: {mark.get_snippet()}"
        )
    return f"YAML Parsing Error: {error}"


def load_yaml_raw(filepath: str) -> tuple[Any, str | None]:
    """Load raw YAML and return (data, error_message)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data, None
    except yaml.YAMLError as err:
        return None, format_yaml_error(err)
    except OSError as err:
        return None, f"Could not read file '{filepath}': {err}"


def validate_yaml_syntax(filepath: str) -> bool:
    """Check whether a file is valid, parseable YAML without schema checks."""
    print(f"Checking YAML syntax for {filepath}...")
    _data, err = load_yaml_raw(filepath)
    if err:
        print(f"\n[ERROR] YAML Syntax Error in '{filepath}':")
        print(err)
        return False
    print(f"SUCCESS: '{filepath}' contains valid YAML syntax!")
    return True


def validate_indicator_value(val: Any, path: str) -> list[str]:
    """Validate menu cursor selection indicator or prefix symbol."""
    if val is None:
        return []
    if isinstance(val, (str, int)):
        return []
    return [
        f"'{path}': Invalid type {type(val).__name__} for indicator. Expected string or character symbol."
    ]


def validate_window_section(window_data: Any, path: str) -> list[str]:
    """Validate window border overrides in a theme."""
    if not isinstance(window_data, dict):
        return [f"'{path}': Section must contain key-value pairs."]

    errors = []
    for key, val in window_data.items():
        subpath = f"{path}.{key}"
        if key not in VALID_WINDOW_BORDER_KEYS:
            errors.append(f"'{subpath}': Unknown window border property '{key}'.")
        elif not isinstance(val, (str, int)):
            errors.append(
                f"'{subpath}': Window border character must be a string or integer, got {type(val).__name__}."
            )
    return errors


def validate_divider_section(divider_data: Any, path: str) -> list[str]:
    """Validate divider overrides in a theme."""
    if isinstance(divider_data, (str, int)):
        return []
    if not isinstance(divider_data, dict):
        return [f"'{path}': Section must contain key-value pairs or a character string."]

    errors = []
    for key, val in divider_data.items():
        subpath = f"{path}.{key}"
        if key not in ("char", "length"):
            errors.append(f"'{subpath}': Unknown divider property '{key}'. Expected 'char' or 'length'.")
        elif isinstance(val, dict):
            # Handle inline YAML placeholder like length: {window_width}
            if not any(k in val for k in ("window_width", "screen_width")):
                errors.append(f"'{subpath}': Invalid mapping for divider property.")
        elif not isinstance(val, (str, int)):
            errors.append(
                f"'{subpath}': Divider property must be a string or integer, got {type(val).__name__}."
            )
    return errors


def validate_color_value(val: Any, depth_mode: str, path: str) -> list[str]:
    """Validate an individual color value (foreground, background, or standalone)."""
    errors = []
    if depth_mode in ("256", "truecolor"):
        if isinstance(val, int):
            if not (-1 <= val <= 255):
                errors.append(f"'{path}': Integer color ID {val} out of range (-1 to 255).")
        elif isinstance(val, str):
            if not (val in VALID_16_COLORS or val.isdigit() or (val.startswith("-") and val[1:].isdigit())):
                errors.append(
                    f"'{path}': Invalid color string '{val}'. Expected integer ID or valid constant."
                )
        else:
            errors.append(f"'{path}': Expected color ID or string, got {type(val).__name__}.")
    elif depth_mode in ("16", "8"):
        if isinstance(val, str):
            if val not in VALID_16_COLORS and val != "-1":
                errors.append(
                    f"'{path}': Invalid color constant '{val}'. Must be quoted string like 'COLOR_BLUE'."
                )
        elif isinstance(val, int):
            if not (-1 <= val <= 15):
                errors.append(f"'{path}': Color index {val} out of range for {depth_mode}-color mode.")
        else:
            errors.append(f"'{path}': Invalid type {type(val).__name__} for color specification.")
    return errors


def validate_color_pair(pair: Any, depth_mode: str, path: str) -> list[str]:
    """Validate a [foreground, background] color pair list."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return [f"'{path}': Must be a 2-element list [fg, bg], got {pair!r}"]

    errors = []
    errors.extend(validate_color_value(pair[0], depth_mode, f"{path}.fg"))
    errors.extend(validate_color_value(pair[1], depth_mode, f"{path}.bg"))
    return errors


def validate_depth_section(depth_str: str, keys: Any, base_path: str) -> list[str]:
    """Validate a specific color depth mapping (e.g., '256', '16', '8')."""
    errors = []
    if depth_str not in VALID_DEPTHS:
        return [f"'{base_path}': Unknown color depth section '{depth_str}'."]

    if not isinstance(keys, dict):
        return [f"'{base_path}.{depth_str}': Section must contain key-value pairs."]

    for key, value in keys.items():
        path = f"{base_path}.{depth_str}.{key}"
        if key in VALID_NON_COLOR_KEYS:
            errors.extend(validate_indicator_value(value, path))
        elif key == "background":
            errors.extend(validate_color_value(value, depth_str, path))
        else:
            errors.extend(validate_color_pair(value, depth_str, path))

    return errors


def validate_theme_file(filepath: str) -> bool:
    """Load and validate a YAML theme file against schema and domain rules."""
    print(f"Validating theme file {filepath}...")
    data, err = load_yaml_raw(filepath)
    if err:
        print("\n[ERROR] YAML File is Malformed!")
        print(err)
        return False

    if not isinstance(data, dict):
        print("\n[ERROR] Root structure must be a YAML mapping/dict.")
        return False

    errors = []
    is_multi_theme = any(
        isinstance(v, dict) and any(str(k) in VALID_DEPTHS for k in v)
        for v in data.values()
    )

    if is_multi_theme:
        for theme_name, depth_map in data.items():
            if not isinstance(depth_map, dict):
                errors.append(f"Theme '{theme_name}' must be a mapping of color depths.")
                continue

            for depth_key, keys in depth_map.items():
                depth_str = str(depth_key)
                if depth_str == "window":
                    errors.extend(validate_window_section(keys, f"{theme_name}.window"))
                elif depth_str == "divider":
                    errors.extend(validate_divider_section(keys, f"{theme_name}.divider"))
                elif depth_str in VALID_NON_COLOR_KEYS:
                    errors.extend(validate_indicator_value(keys, f"{theme_name}.{depth_str}"))
                else:
                    errors.extend(validate_depth_section(depth_str, keys, theme_name))
    else:
        for depth_key, keys in data.items():
            depth_str = str(depth_key)
            if depth_str == "window":
                errors.extend(validate_window_section(keys, "root.window"))
            elif depth_str == "divider":
                errors.extend(validate_divider_section(keys, "root.divider"))
            elif depth_str in VALID_NON_COLOR_KEYS:
                errors.extend(validate_indicator_value(keys, f"root.{depth_str}"))
            else:
                errors.extend(validate_depth_section(depth_str, keys, "root"))

    if errors:
        print(f"\n[ERROR] Found {len(errors)} validation issue(s):\n")
        for err in errors:
            print(f"  - {err}")
        return False

    print("SUCCESS: Theme file is valid!")
    return True


def validate_config_file(filepath: str) -> bool:
    """Validate a bashmenu.yml configuration file against expected structure."""
    print(f"Validating configuration file {filepath}...")
    data, err = load_yaml_raw(filepath)
    if err:
        print(f"\n[ERROR] Configuration File is Malformed: {err}")
        return False

    if not isinstance(data, dict):
        print("\n[ERROR] Root structure of config must be a YAML dictionary.")
        return False

    errors = []
    if "theme" in data and not isinstance(data["theme"], str):
        errors.append(f"'theme' must be a string, got {type(data['theme']).__name__}.")

    if "settings" in data and not isinstance(data["settings"], dict):
        errors.append(f"'settings' must be a mapping, got {type(data['settings']).__name__}.")
    elif "settings" in data:
        settings = data["settings"]
        if "plugins" in settings and not isinstance(settings["plugins"], dict):
            errors.append(f"'settings.plugins' must be a mapping, got {type(settings['plugins']).__name__}.")
        if "inactivity_timeout" in settings:
            it = settings["inactivity_timeout"]
            if not isinstance(it, dict):
                errors.append(f"'settings.inactivity_timeout' must be a mapping, got {type(it).__name__}.")
            else:
                if "milliseconds" in it and not isinstance(it["milliseconds"], (int, float)):
                    errors.append(
                        f"'settings.inactivity_timeout.milliseconds' must be a number, got {type(it['milliseconds']).__name__}."
                    )
                if "command" in it and not isinstance(it["command"], str):
                    errors.append(
                        f"'settings.inactivity_timeout.command' must be a string, got {type(it['command']).__name__}."
                    )

    if "user" in data and not isinstance(data["user"], dict):
        errors.append(f"'user' must be a mapping, got {type(data['user']).__name__}.")

    if errors:
        print(f"\n[ERROR] Found {len(errors)} config validation issue(s):\n")
        for e in errors:
            print(f"  - {e}")
        return False

    print("SUCCESS: Configuration file is valid!")
    return True


def _validate_menu_items(items: list[Any], path: str, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"'{path}': Must be a list of menu items.")
        return

    for idx, raw in enumerate(items):
        item_path = f"{path}[{idx}]"
        if raw == "{divider}":
            continue
        if not isinstance(raw, dict):
            errors.append(f"'{item_path}': Menu item must be a dictionary or '{{divider}}'.")
            continue

        if "{divider}" in raw:
            continue

        if len(raw) == 1 and "label" not in raw:
            label = next(iter(raw))
            props = raw[label]
            if props is None:
                continue
            if not isinstance(props, dict):
                errors.append(f"'{item_path}.{label}': Item properties must be a dictionary.")
                continue

            item_type = props.get("type", "command")
            is_div = item_type == "{divider}" or (isinstance(item_type, dict) and "divider" in item_type)
            if not is_div and item_type not in VALID_OPTION_TYPES and "submenu" not in props:
                errors.append(f"'{item_path}.{label}': Unknown item type '{item_type}'.")

            if item_type == "submenu" or "submenu" in props:
                sub = props.get("submenu")
                if isinstance(sub, dict):
                    sub_items = sub.get("items", sub.get("options", []))
                    _validate_menu_items(sub_items, f"{item_path}.{label}.submenu.items", errors)
                elif sub is not None:
                    errors.append(f"'{item_path}.{label}.submenu': Must be a dictionary containing items.")
        else:
            opt_type = raw.get("type", "command")
            is_div = opt_type == "{divider}" or (isinstance(opt_type, dict) and "divider" in opt_type)
            if not is_div and opt_type not in VALID_OPTION_TYPES and "submenu" not in raw:
                errors.append(f"'{item_path}': Unknown option type '{opt_type}'.")

            if opt_type == "submenu" or "submenu" in raw:
                sub = raw.get("submenu")
                if isinstance(sub, dict):
                    sub_items = sub.get("items", sub.get("options", []))
                    _validate_menu_items(sub_items, f"{item_path}.submenu.items", errors)
                elif sub is not None:
                    errors.append(f"'{item_path}.submenu': Must be a dictionary containing items.")


def validate_menu_file(filepath: str) -> bool:
    """Validate a bashmenu.mnu menu layout file against expected structure."""
    print(f"Validating menu file {filepath}...")
    data, err = load_yaml_raw(filepath)
    if err:
        print(f"\n[ERROR] Menu File is Malformed: {err}")
        return False

    if not isinstance(data, dict):
        print("\n[ERROR] Root structure of menu file must be a YAML dictionary.")
        return False

    errors = []
    if "items" not in data and "options" not in data:
        errors.append("Root dictionary missing required 'items' list.")
    else:
        items = data.get("items", data.get("options"))
        _validate_menu_items(items, "items", errors)

    if errors:
        print(f"\n[ERROR] Found {len(errors)} menu validation issue(s):\n")
        for e in errors:
            print(f"  - {e}")
        return False

    print("SUCCESS: Menu file is valid!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate YAML files for syntax or specific schema rules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 ymlcheck.py bashmenu.yml                # Check YAML syntax only (default)
  python3 ymlcheck.py --themes bashmenu.themes   # Validate theme structure
  python3 ymlcheck.py --config bashmenu.yml      # Validate config structure
  python3 ymlcheck.py --menu bashmenu.mnu        # Validate menu structure
""",
    )
    parser.add_argument("files", nargs="+", help="Path to one or more YAML files to validate.")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-t", "--themes", "--theme",
        dest="mode",
        action="store_const",
        const="theme",
        help="Validate as a theme palette file (bashmenu.themes).",
    )
    mode_group.add_argument(
        "-c", "--config",
        dest="mode",
        action="store_const",
        const="config",
        help="Validate as a settings configuration file (bashmenu.yml).",
    )
    mode_group.add_argument(
        "-m", "--menu",
        dest="mode",
        action="store_const",
        const="menu",
        help="Validate as a menu structure file (bashmenu.mnu).",
    )
    mode_group.add_argument(
        "-y", "--yaml",
        dest="mode",
        action="store_const",
        const="yaml",
        help="Validate YAML syntax only with no schema enforcement (default).",
    )

    args = parser.parse_args()
    mode = args.mode or "yaml"

    all_passed = True
    for fpath in args.files:
        if not os.path.exists(fpath):
            print(f"[ERROR] File not found: '{fpath}'")
            all_passed = False
            continue

        if mode == "theme":
            passed = validate_theme_file(fpath)
        elif mode == "config":
            passed = validate_config_file(fpath)
        elif mode == "menu":
            passed = validate_menu_file(fpath)
        else:
            passed = validate_yaml_syntax(fpath)

        if not passed:
            all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
