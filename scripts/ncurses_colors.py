#!/usr/bin/env python3
"""
ncurses_colors.py - Display and verify 256 terminal colors.

This script outputs the 256 terminal color palette, formatted identically to
the bash scripts 'tput_colors.sh' and 'ncurses_colors.sh'. It supports both
the standard curses/tput color mappings (default, matching bashmenu.py and menuedit.py)
and raw ANSI 256-color sequences.
"""

import argparse
import sys

__version__ = "0.0.1"
__author__ = "HappyAmos"


def print_tput_colors():
    """Print colors using tput/curses compatible escape sequences."""
    try:
        import curses
        curses.setupterm()
        setaf_bytes = curses.tigetstr('setaf')
        sgr0_bytes = curses.tigetstr('sgr0')
        
        def setaf(color_id):
            return curses.tparm(setaf_bytes, color_id).decode('utf-8', errors='ignore')
            
        def sgr0():
            return sgr0_bytes.decode('utf-8', errors='ignore')
            
    except (curses.error, ImportError, TypeError, AttributeError):  # Catch missing curses, library attributes, or initialization errors safely
        # Fallback to hardcoded ANSI sequences that precisely emulate tput setaf/sgr0
        def setaf(color_id):
            if color_id < 8:
                return f"\033[{30 + color_id}m"
            elif color_id < 16:
                return f"\033[{90 + (color_id - 8)}m"
            else:
                return f"\033[38;5;{color_id}m"
                
        def sgr0():
            return "\033(B\033[m"

    for i in range(256):
        sys.stdout.write(setaf(i))
        sys.stdout.write(f"{i:4d}")
        
        if (i + 1) % 16 == 0:
            sys.stdout.write(sgr0())
            sys.stdout.write("\n")
            
    sys.stdout.write(sgr0())
    sys.stdout.flush()


def print_ncurses_colors():
    """Print colors using raw ANSI 256-color escape sequences (identical to ncurses_colors.sh)."""
    for i in range(256):
        sys.stdout.write(f"\033[38;5;{i}m{i:4d}")
        if (i + 1) % 16 == 0:
            sys.stdout.write("\n")
            
    sys.stdout.flush()


def main():
    """
    Parse command-line arguments and run the appropriate color printing mode.
    """
    parser = argparse.ArgumentParser(
        description="Display the 256 terminal color palette used in the menu system."
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["tput", "ncurses", "ansi"],
        default="tput",
        help="Color escape sequence mode. 'tput' (default) matches bashmenu.py, "
             "menuedit.py and tput_colors.sh. 'ncurses' / 'ansi' matches ncurses_colors.sh."
    )
    
    args = parser.parse_args()
    
    if args.mode == "tput":
        print_tput_colors()
    else:
        print_ncurses_colors()


if __name__ == "__main__":
    main()
