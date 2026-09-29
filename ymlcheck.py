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

# Permitted option types in bashmenu.mnu
VALID_OPTION_TYPES = {
    "command", "script", "submenu", "config", "toggle", "editor",
    "confirm", "message", "popup", "info", "python", "inject_block",
    "theme_selector", "divider", "back", "exit", "action"
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
                if depth_str in VALID_NON_COLOR_KEYS:
                    errors.extend(validate_indicator_value(keys, f"{theme_name}.{depth_str}"))
                else:
                    errors.extend(validate_depth_section(depth_str, keys, theme_name))
    else:
        for depth_key, keys in data.items():
            depth_str = str(depth_key)
            if depth_str in VALID_NON_COLOR_KEYS:
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

    if "user" in data and not isinstance(data["user"], dict):
        errors.append(f"'user' must be a mapping, got {type(data['user']).__name__}.")

    if errors:
        print(f"\n[ERROR] Found {len(errors)} config validation issue(s):\n")
        for e in errors:
            print(f"  - {e}")
        return False

    print("SUCCESS: Configuration file is valid!")
    return True


def _validate_menu_options(options: list[Any], path: str, errors: list[str]) -> None:
    if not isinstance(options, list):
        errors.append(f"'{path}': Must be a list of menu options.")
        return

    for idx, opt in enumerate(options):
        opt_path = f"{path}[{idx}]"
        if not isinstance(opt, dict):
            errors.append(f"'{opt_path}': Menu option must be a dictionary.")
            continue

        opt_type = opt.get("type", "command")
        if opt_type not in VALID_OPTION_TYPES and "submenu" not in opt:
            errors.append(f"'{opt_path}': Unknown option type '{opt_type}'.")

        if opt_type == "submenu" or "submenu" in opt:
            sub = opt.get("submenu")
            if isinstance(sub, dict):
                sub_opts = sub.get("options", [])
                _validate_menu_options(sub_opts, f"{opt_path}.submenu.options", errors)
            elif sub is not None:
                errors.append(f"'{opt_path}.submenu': Must be a dictionary containing options.")


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
    if "options" not in data:
        errors.append("Root dictionary missing required 'options' list.")
    else:
        _validate_menu_options(data["options"], "options", errors)

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
