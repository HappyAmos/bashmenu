"""
Cheat CLI - A lightweight terminal-based cheatsheet manager.

This script searches, lists, and displays Markdown cheatsheets based on exact
path matches, frontmatter tags, or full-text content search.

Dependencies:
    - PyYAML: For parsing configuration and YAML frontmatter.
    - rich.sh: Terminal markdown renderer using Python Rich.

Usage:
    python cheat.py [query]
    python cheat.py -l [query]
    python cheat.py -d
"""

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

with contextlib.suppress(ImportError):
    from rich.markdown import Heading

    if hasattr(Heading, "LEVEL_ALIGN"):
        Heading.LEVEL_ALIGN["h1"] = "left"
    else:

        def _custom_h1_console(self, console, options):
            text = self.text
            text.justify = "left"
            if self.tag == "h1":
                from rich import box
                from rich.panel import Panel

                yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
            else:
                if self.tag == "h2":
                    from rich.text import Text

                    yield Text("")
                yield text

        Heading.__rich_console__ = _custom_h1_console


def get_config_path() -> Path:
    """
    Locate or create the `.cheat.yml` configuration file.

    Returns:
        Path: Resolved path to `.cheat.yml` in the script directory.
    """
    # Resolve directory containing this script
    script_dir = Path(__file__).resolve().parent
    config_file = script_dir / ".cheat.yml"

    if config_file.is_file():
        return config_file

    # Create default configuration file if missing
    try:
        config_file.write_text("dir: ~/cheat\n", encoding="utf-8")
        print(f"Created default configuration file at: {config_file}")
        return config_file
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Error: No .cheat.yml found, and failed to create one at {config_file}: {e}")


def get_root_directory(config_path: Path) -> Path:
    """
    Extract and validate target cheatsheets root directory from configuration.

    Args:
        config_path: Path to `.cheat.yml` configuration file.

    Returns:
        Path: Resolved absolute path to target cheatsheets directory.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        dir_path_str = config.get("dir")
        if not dir_path_str:
            sys.exit(f"Error: Missing 'dir' key in {config_path}")

        # Expand user directory (~) and resolve absolute path
        root = Path(dir_path_str).expanduser().resolve()
        if not root.is_dir():
            sys.exit(f"Error: Invalid directory in {config_path}: {root}")

        return root
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Error reading config file {config_path}: {e}")


def display_markdown(file_path: Path) -> None:
    """
    Display Markdown file content using `rich.sh` or print fallback.

    Args:
        file_path: Path to Markdown file to display.
    """
    script_dir = Path(__file__).resolve().parent
    rich_script = script_dir / "rich.sh"

    cmd = None
    if rich_script.is_file():
        if os.access(rich_script, os.X_OK):
            cmd = [str(rich_script), str(file_path)]
        else:
            cmd = ["bash", str(rich_script), str(file_path)]
    elif shutil.which("rich.sh"):
        cmd = ["rich.sh", str(file_path)]

    if cmd:
        try:
            res = subprocess.run(cmd, check=False)
            if res.returncode != 0:
                sys.exit(res.returncode)
            return
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception:  # noqa: BLE001, S110
            pass

    # Fall back to rich or stdout print if rich.sh fails to run
    try:
        from rich.console import Console
        from rich.markdown import Markdown

        console = Console()
        console.print(Markdown(file_path.read_text(encoding="utf-8"), hyperlinks=True))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:  # noqa: BLE001
        try:
            print(file_path.read_text(encoding="utf-8"))
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"Error reading {file_path}: {e}")


def extract_tags_from_frontmatter(file_path: Path) -> list[str]:
    """
    Parse YAML frontmatter from Markdown file and extract tags.

    Args:
        file_path: Target Markdown file path.

    Returns:
        list[str]: Lowercased list of tags extracted from frontmatter.
    """
    try:
        content = file_path.read_text(encoding="utf-8").lstrip()
    except Exception:  # noqa: BLE001
        return []

    # Frontmatter must begin with '---' delimiter
    if not content.startswith("---"):
        return []

    # Split into 3 sections: empty header prefix, YAML block, body
    parts = content.split("---", 2)
    if len(parts) < 3:
        return []

    with contextlib.suppress(Exception):
        frontmatter = yaml.safe_load(parts[1])
        if isinstance(frontmatter, dict):
            tags = frontmatter.get("tags", [])
            # Standard YAML list of tags: tags: [tag1, tag2]
            if isinstance(tags, list):
                return [str(t).strip().lower() for t in tags if t]
            # String of tags: tags: tag1, tag2
            if isinstance(tags, str):
                return [t.strip().lower() for t in tags.split(",") if t.strip()]

    return []


def print_file_list(files: list[Path], root_dir: Path) -> None:
    """
    Print a list of cheatsheet files and their tags in two neatly aligned columns.

    Args:
        files: List of file paths to display.
        root_dir: Root cheatsheets directory for relative path resolution.
    """
    if not files:
        return

    entries: list[tuple[str, str]] = []
    max_len = 0
    for file in files:
        rel_path = str(file.relative_to(root_dir))
        tags = extract_tags_from_frontmatter(file)
        tags_str = f"[{', '.join(tags)}]" if tags else ""
        entries.append((rel_path, tags_str))
        max_len = max(max_len, len(rel_path))

    col_width = max_len + 4

    for rel_path, tags_str in entries:
        if tags_str:
            print(f"{rel_path:<{col_width}}{tags_str}")
        else:
            print(rel_path)


def main():
    """
    Main entry point for CLI argument parsing and query execution.
    """
    parser = argparse.ArgumentParser(description="Query and display cheatsheets.")
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query to display markdown file."
    )
    parser.add_argument(
        "-l", "--list",
        nargs="?",
        const=True,
        default=False,
        help="List all files with tags, or list matching files for an optional search query."
    )
    parser.add_argument(
        "-s", "--search",
        nargs="?",
        const=True,
        default=False,
        help="Search cheatsheets and list matching files with tags."
    )
    parser.add_argument(
        "-d", "--directory",
        action="store_true",
        help="Print the configured cheatsheets directory path."
    )

    args = parser.parse_args()

    # Parse configuration and target cheatsheets root directory
    config_path = get_config_path()
    root_dir = get_root_directory(config_path)

    # -----------------------------------------------------------------
    # DIRECTORY PATH MODE (-d / --directory)
    # -----------------------------------------------------------------
    if args.directory:
        print(root_dir)
        return

    # Recursively find and sort all Markdown files in root directory
    md_files = sorted(
        [p for p in root_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".md"],
        key=lambda p: str(p.relative_to(root_dir)).lower()
    )

    # -----------------------------------------------------------------
    # LIST / SEARCH MODE (-l / --list / -s / --search)
    # -----------------------------------------------------------------
    if args.list is not False or args.search is not False:
        list_query = None
        if isinstance(args.search, str):
            list_query = args.search.lower()
        elif isinstance(args.list, str):
            list_query = args.list.lower()
        elif args.query:
            list_query = args.query.lower()

        # Strip .md extension if provided by user query
        if list_query:
            list_query = list_query.removesuffix(".md")

        # Case 1: Unfiltered list mode -> output all files with tags
        if not list_query:
            if not md_files:
                print(f"No markdown files found under {root_dir}")
                return

            print_file_list(md_files, root_dir)
            return

        # Case 2: Filtered list mode (search) -> output files matching query
        matching_files = []
        for file in md_files:
            rel_path_str = str(file.relative_to(root_dir).with_suffix("")).lower()

            # Priority 1: Filename or relative path match
            if file.stem.lower() == list_query or rel_path_str == list_query:
                matching_files.append(file)
                continue

            # Priority 2: Frontmatter tag match
            tags = extract_tags_from_frontmatter(file)
            if list_query in tags:
                matching_files.append(file)
                continue

            # Priority 3: Full-text content match
            with contextlib.suppress(Exception):
                content = file.read_text(encoding="utf-8")
                if list_query in content.lower():
                    matching_files.append(file)

        if not matching_files:
            sys.exit(f"No markdown file matched '{list_query}' under {root_dir}")

        print_file_list(matching_files, root_dir)
        return

    # -----------------------------------------------------------------
    # NORMAL DISPLAY MODE
    # -----------------------------------------------------------------
    if not args.query:
        parser.print_help()
        sys.exit(1)

    query = args.query.lower().removesuffix(".md")

    # Priority 1a: Fast exact relative path lookup (<root>/<query>.md)
    exact_match = root_dir / f"{query}.md"
    if exact_match.is_file():
        display_markdown(exact_match)
        return

    # Priority 1b: Stem or relative path match
    for file in md_files:
        rel_path_str = str(file.relative_to(root_dir).with_suffix("")).lower()
        if file.stem.lower() == query or rel_path_str == query:
            display_markdown(file)
            return

    # Priority 2: Frontmatter tag match
    for file in md_files:
        tags = extract_tags_from_frontmatter(file)
        if query in tags:
            display_markdown(file)
            return

    # Priority 3: Full-text content match
    for file in md_files:
        with contextlib.suppress(Exception):
            content = file.read_text(encoding="utf-8")
            if query in content.lower():
                display_markdown(file)
                return

    sys.exit(f"No markdown file matched '{query}' under {root_dir}")


if __name__ == "__main__":
    main()

