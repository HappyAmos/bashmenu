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
    console = Console()
    grid_text = Text()

    for i in range(256):
        grid_text.append(f"{i:4d}", style=f"color({i})")
        if (i + 1) % 16 == 0:
            grid_text.append("\n")

    console.print(grid_text)


def print_ncurses_colors():
    """Print colors using raw ANSI 256-color escape sequences."""
    for i in range(256):
        sys.stdout.write(f"\033[38;5;{i}m{i:4d}")
        if (i + 1) % 16 == 0:
            sys.stdout.write("\033[0m\n")

    sys.stdout.write("\033[0m")
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
