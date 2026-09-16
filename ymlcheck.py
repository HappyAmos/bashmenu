#!/usr/bin/env python3
"""
ymlcheck.py - Theme and YAML Configuration Validator.

Validates theme definitions (such as bashconfig.themes) and general YAML
structure against expected schema definitions, color indices, selection
indicators, and standard curses color constant names.
"""

import os
import sys

__version__ = "0.0.1"
__author__ = "HA Bash Menu Development Team"
from typing import Any

import yaml

# Standard 16-color curses constants valid in 16/8 color depth modes
VALID_16_COLORS = {
    "COLOR_BLACK", "COLOR_RED", "COLOR_GREEN", "COLOR_YELLOW",
    "COLOR_BLUE", "COLOR_MAGENTA", "COLOR_CYAN", "COLOR_WHITE"
}

# Recognized color depth palette section keys
VALID_DEPTHS = {"256", "16", "8", "truecolor"}

# Non-color structural attributes permitted in theme definitions
VALID_NON_COLOR_KEYS = {"indicator", "prefix"}


def format_yaml_error(error: yaml.YAMLError) -> str:
    """
    Format PyYAML syntax errors for readable terminal output.

    Extracts line numbers, column numbers, and code snippet context
    from PyYAML exceptions when available.
    """
    if hasattr(error, 'problem_mark'):
        mark = error.problem_mark
        return (
            f"Syntax Error at line {mark.line + 1}, column {mark.column + 1}:\n"
            f"  {error.problem}\n"
            f"  Line snippet: {mark.get_snippet()}"
        )
    return f"YAML Parsing Error: {error}"


def validate_indicator_value(val: Any, path: str) -> list[str]:
    """
    Validate menu cursor selection indicator or prefix symbol.

    Ensures value is a valid string, character, integer, or null.
    """
    if val is None:
        return []
    if isinstance(val, (str, int)):
        return []
    return [
        f"'{path}': Invalid type {type(val).__name__} for indicator. Expected string or character symbol."
    ]


def validate_color_value(val: Any, depth_mode: str, path: str) -> list[str]:
    """
    Validate an individual color value (foreground, background, or standalone).

    Checks integer color bounds (0-255 or -1 for default) for 256/truecolor
    modes, and string constants/IDs for 16/8 color modes.
    """
    errors = []
    if depth_mode in ("256", "truecolor"):
        # 256-color palette index or default background (-1)
        if isinstance(val, int):
            if not (-1 <= val <= 255):
                errors.append(
                    f"'{path}': Integer color ID {val} out of range (-1 to 255)."
                )
        elif isinstance(val, str):
            # String representations of integer IDs or standard curses names
            if not (val in VALID_16_COLORS or val.isdigit() or (val.startswith("-") and val[1:].isdigit())):
                errors.append(
                    f"'{path}': Invalid color string '{val}'. Expected integer ID or valid constant."
                )
        else:
            errors.append(f"'{path}': Expected color ID or string, got {type(val).__name__}.")
    elif depth_mode in ("16", "8"):
        # 16/8 color mode palette constant or -1 integer/string
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
    """
    Validate a [foreground, background] color pair list.

    Ensures pair is a 2-element sequence and validates each element
    according to the specified color depth.
    """
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return [f"'{path}': Must be a 2-element list [fg, bg], got {pair!r}"]

    errors = []
    errors.extend(validate_color_value(pair[0], depth_mode, f"{path}.fg"))
    errors.extend(validate_color_value(pair[1], depth_mode, f"{path}.bg"))
    return errors


def validate_depth_section(depth_str: str, keys: Any, base_path: str) -> list[str]:
    """
    Validate a specific color depth mapping (e.g., '256', '16', '8').

    Checks background property, pair definitions, and indicator settings.
    """
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
    """
    Load and validate a YAML theme file against schema and domain rules.

    Supports both multi-theme dictionaries (e.g., 'dracula:', 'nord:')
    and single-theme depth structures.
    """
    print(f"Validating {filepath}...")

    # Step 1: Read and parse YAML file syntax
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as err:
        print("\n[ERROR] YAML File is Malformed!")
        print(format_yaml_error(err))
        return False
    except OSError as err:
        print(f"\n[ERROR] Could not read file: {err}")
        return False

    if not isinstance(data, dict):
        print("\n[ERROR] Root structure must be a YAML mapping/dict.")
        return False

    errors = []

    # Step 2: Determine if root contains multiple themes or a single theme
    is_multi_theme = any(
        isinstance(v, dict) and any(str(k) in VALID_DEPTHS for k in v)
        for v in data.values()
    )

    if is_multi_theme:
        # Validate multi-theme format (e.g., dracula -> indicator / 256/16/8)
        for theme_name, depth_map in data.items():
            if not isinstance(depth_map, dict):
                errors.append(
                    f"Theme '{theme_name}' must be a mapping of color depths."
                )
                continue

            for depth_key, keys in depth_map.items():
                depth_str = str(depth_key)
                if depth_str in VALID_NON_COLOR_KEYS:
                    errors.extend(
                        validate_indicator_value(
                            keys, f"{theme_name}.{depth_str}"
                        )
                    )
                else:
                    errors.extend(
                        validate_depth_section(
                            depth_str, keys, theme_name
                        )
                    )
    else:
        # Validate single-theme format (depths or indicators at root)
        for depth_key, keys in data.items():
            depth_str = str(depth_key)
            if depth_str in VALID_NON_COLOR_KEYS:
                errors.extend(
                    validate_indicator_value(keys, f"root.{depth_str}")
                )
            else:
                errors.extend(validate_depth_section(depth_str, keys, "root"))

    # Step 3: Output validation results and summary
    if errors:
        print(f"\n[ERROR] Found {len(errors)} validation issue(s):\n")
        for err in errors:
            print(f"  - {err}")
        return False

    print("SUCCESS: Theme file is valid!")
    return True


if __name__ == "__main__":
    script_name = os.path.basename(sys.argv[0])
    if len(sys.argv) < 2:
        print(f"Usage: python {script_name} <path_to_theme.yaml>")
        sys.exit(1)

    success = validate_theme_file(sys.argv[1])
    sys.exit(0 if success else 1)
