#!/usr/bin/env python3
"""
ncurses_colors.py - Display and verify 256 terminal colors using Rich / Textual styling.

This script outputs the 256 terminal color palette using Rich / ANSI 256-color formatting.
"""

import argparse
import sys

from rich.console import Console
from rich.text import Text

__version__ = "0.0.3"
__author__ = "HappyAmos"


def print_rich_colors():
    """Print 256 terminal colors using Rich Console."""
    console = Console(force_terminal=True)
    grid_text = Text()

    for i in range(256):
        grid_text.append(f"{i:4d}", style=f"color({i})")
        if (i + 1) % 16 == 0:
            grid_text.append("\n")

    grid_text.append("\nStandard Color Constants:\n", style="bold underline")
    standard_colors = [
        ("COLOR_BLACK", "bold color(0) on color(255)"),
        ("COLOR_RED", "bold color(196)"),
        ("COLOR_GREEN", "bold color(46)"),
        ("COLOR_YELLOW", "bold color(226)"),
        ("COLOR_BLUE", "bold color(63)"),
        ("COLOR_MAGENTA", "bold color(201)"),
        ("COLOR_CYAN", "bold color(51)"),
        ("COLOR_WHITE", "bold color(231)"),
    ]
    for idx, (name, style_spec) in enumerate(standard_colors, start=1):
        grid_text.append(f"{name:20s} ", style=style_spec)
        if idx % 4 == 0:
            grid_text.append("\n")

    grid_text.append("\nExtended & Bright Color Constants:\n", style="bold underline")
    extended_colors = [
        ("COLOR_GREY", "bold color(244)"),
        ("COLOR_BRIGHT_RED", "bold color(203)"),
        ("COLOR_BRIGHT_GREEN", "bold color(82)"),
        ("COLOR_BRIGHT_YELLOW", "bold color(227)"),
        ("COLOR_BRIGHT_BLUE", "bold color(75)"),
        ("COLOR_BRIGHT_MAGENTA", "bold color(207)"),
        ("COLOR_BRIGHT_CYAN", "bold color(87)"),
        ("COLOR_BRIGHT_WHITE", "bold color(255)"),
        ("COLOR_ORANGE", "bold color(208)"),
        ("COLOR_PURPLE", "bold color(129)"),
        ("COLOR_PINK", "bold color(211)"),
        ("COLOR_BROWN", "bold color(130)"),
    ]
    for idx, (name, style_spec) in enumerate(extended_colors, start=1):
        grid_text.append(f"{name:21s} ", style=style_spec)
        if idx % 3 == 0:
            grid_text.append("\n")
    if len(extended_colors) % 3 != 0:
        grid_text.append("\n")

    console.print(grid_text)


def print_ncurses_colors():
    """Print colors using raw ANSI 256-color escape sequences."""
    for i in range(256):
        sys.stdout.write(f"\033[38;5;{i}m{i:4d}")
        if (i + 1) % 16 == 0:
            sys.stdout.write("\033[0m\n")

    sys.stdout.write("\033[0m\n\n\033[1;4mStandard Color Constants:\033[0m\n")
    sys.stdout.write("\033[38;5;0;48;5;255mCOLOR_BLACK\033[0m         ")
    sys.stdout.write("\033[1;38;5;196mCOLOR_RED\033[0m           ")
    sys.stdout.write("\033[1;38;5;46mCOLOR_GREEN\033[0m         ")
    sys.stdout.write("\033[1;38;5;226mCOLOR_YELLOW\033[0m        \n")
    sys.stdout.write("\033[1;38;5;63mCOLOR_BLUE\033[0m          ")
    sys.stdout.write("\033[1;38;5;201mCOLOR_MAGENTA\033[0m       ")
    sys.stdout.write("\033[1;38;5;51mCOLOR_CYAN\033[0m          ")
    sys.stdout.write("\033[1;38;5;231mCOLOR_WHITE\033[0m         \n")

    sys.stdout.write("\n\033[1;4mExtended & Bright Color Constants:\033[0m\n")
    sys.stdout.write("\033[1;38;5;244mCOLOR_GREY\033[0m          ")
    sys.stdout.write("\033[1;38;5;203mCOLOR_BRIGHT_RED\033[0m    ")
    sys.stdout.write("\033[1;38;5;82mCOLOR_BRIGHT_GREEN\033[0m  \n")
    sys.stdout.write("\033[1;38;5;227mCOLOR_BRIGHT_YELLOW\033[0m ")
    sys.stdout.write("\033[1;38;5;75mCOLOR_BRIGHT_BLUE\033[0m   ")
    sys.stdout.write("\033[1;38;5;207mCOLOR_BRIGHT_MAGENTA\033[0m\n")
    sys.stdout.write("\033[1;38;5;87mCOLOR_BRIGHT_CYAN\033[0m   ")
    sys.stdout.write("\033[1;38;5;255mCOLOR_BRIGHT_WHITE\033[0m  ")
    sys.stdout.write("\033[1;38;5;208mCOLOR_ORANGE\033[0m        \n")
    sys.stdout.write("\033[1;38;5;129mCOLOR_PURPLE\033[0m        ")
    sys.stdout.write("\033[1;38;5;211mCOLOR_PINK\033[0m          ")
    sys.stdout.write("\033[1;38;5;130mCOLOR_BROWN\033[0m         \n")
    sys.stdout.flush()


def main():
    """Parse command-line arguments and display colors."""
    parser = argparse.ArgumentParser(
        description="Display the 256 terminal color palette used in the menu system."
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["tput", "ncurses", "ansi", "rich"],
        default="rich",
        help="Color display mode. 'rich' (default) uses Rich 256-color styles. 'ncurses' / 'ansi' uses raw escape sequences.",
    )

    args = parser.parse_args()

    if args.mode in ["rich", "tput"]:
        print_rich_colors()
    else:
        print_ncurses_colors()


if __name__ == "__main__":
    main()
