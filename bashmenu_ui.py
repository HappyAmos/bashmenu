"""
bashmenu_ui.py - Reusable Textual TUI primitives, modal screens, text formatting and theme utilities.
"""

import contextlib
import ctypes
import os
import re
import subprocess
import textwrap
import threading
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from rich._palettes import EIGHT_BIT_PALETTE
from rich.cells import cell_len
from rich.markdown import Heading, Markdown
from rich.style import Style

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

if hasattr(Heading, "LEVEL_ALIGN"):
    Heading.LEVEL_ALIGN["h1"] = "left"
import yaml
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    OptionList,
    RichLog,
    Static,
    TextArea,
)
from textual.widgets import Markdown as TextualMarkdown
from textual.widgets.option_list import Option
from textual.widgets.text_area import Edit, EditResult


def safe_curs_set(visibility: int) -> None:
    """
    Compatibility function for setting cursor visibility (no-op in Textual).
    """


def safe_isprintable(s: str) -> bool:
    """
    Returns True if the string contains only valid printable characters,
    specifically preserving Nerd Font / PUA glyphs.
    """
    for char in s:
        category = unicodedata.category(char)
        if category == "Co":
            continue
        if category.startswith("C") or category == "Zl" or category == "Zp":
            return False
    return True


def is_formatting_tag(content: str) -> bool:
    """
    Helper to check if bracketed content is a console formatting tag.
    """
    if not isinstance(content, str):
        return False
    content_clean = content.strip().lower()
    if content_clean in [
        "b",
        "/b",
        "u",
        "/u",
        "dim",
        "/dim",
        "reverse",
        "/reverse",
        "/color",
        "table",
        "/table",
        "tr",
        "/tr",
        "th",
        "/th",
        "td",
        "/td",
        "list",
        "list=1",
        "/list",
        "*",
        "/*",
    ]:
        return True
    if content_clean.startswith(("color=", "list=", "table")) and "]" not in content_clean:
        return True
    content_clean = content_clean.removeprefix("/")
    if len(content_clean) <= 1:
        return False
    with contextlib.suppress(Exception):
        Style.parse(content_clean)
        return True
    return False


PLACEHOLDER_SECTIONS = [
    (
        "Interactive Input Directives",
        [
            ("{param}", "Prompts for text input modal (masked=true supported)"),
            ("{file_picker}", "Launches visual file chooser dialog"),
            ("{file_picker:path:<dir>}", "File chooser opening in specified default directory"),
            ("{file_picker:stem}", "Path without file extension (/path/to/img)"),
            ("{file_picker:name}", "Filename with extension (img.png)"),
            ("{file_picker:base}", "Filename without extension (img)"),
            ("{file_picker:dir}", "Parent directory path (/path/to)"),
            ("{file_picker:ext}", "File extension with leading dot (.png)"),
            ("{file_picker_new}", "File chooser allowing creation of new files ('n')"),
            ("{dir_picker}", "Launches visual directory chooser dialog"),
            ("{dir_picker:path:<dir>}", "Directory chooser opening in specified default directory"),
            ("{dir_picker:name}", "Folder name without parent path"),
            ("{dir_picker:dir}", "Parent directory path of chosen folder"),
            ("{dir_picker_new}", "Directory chooser allowing creation of new folders ('n')"),
        ],
    ),
    (
        "System & Path Placeholders",
        [
            ("{user}", "Current logged-in username"),
            ("{username}", "Alias for {user}"),
            ("{host}", "System hostname"),
            ("{hostname}", "Alias for {host}"),
            ("{home}", "User home directory path (~ / /home/username)"),
            ("{bashmenu_dir}", "Application root directory"),
            ("{scripts_dir}", "Scripts directory path"),
            ("{scripts}", "Alias for {scripts_dir}"),
            ("{templates_dir}", "Templates directory path"),
            ("{templates}", "Alias for {templates_dir}"),
            ("{cache_dir}", "Cache directory path"),
            ("{cache}", "Alias for {cache_dir}"),
            ("{notebooks_dir}", "Notebooks directory path"),
            ("{notebooks}", "Alias for {notebooks_dir}"),
            ("{bashrc}", "Path to ~/.bashrc profile file"),
            ("{bash_aliases}", "Path to ~/.bash_aliases file"),
            ("{zshrc}", "Path to ~/.zshrc configuration file"),
            ("{profile}", "Path to ~/.profile (or existing profile)"),
            ("{bash_profile}", "Path to ~/.bash_profile (or existing profile)"),
            ("{zprofile}", "Path to ~/.zprofile configuration file"),
            ("{shell_profile}", "Path to active shell login profile"),
            ("{vimrc}", "Path to ~/.vimrc configuration file"),
            ("{nanorc}", "Path to ~/.nanorc configuration file"),
        ],
    ),
    (
        "Cross-Platform Environment",
        [
            ("{prefix}", "Termux / system prefix path ($PREFIX / /usr)"),
            ("{termux_properties}", "Termux properties file path"),
            ("{termux_storage}", "Termux Android storage directory (~/storage)"),
            ("{powershell_profile}", "PowerShell profile script path"),
            ("{appdata}", "Windows AppData roaming directory path"),
            ("{userprofile}", "Windows user profile directory path"),
        ],
    ),
    (
        "System Status & Network",
        [
            ("{battery}", "Current battery capacity percentage"),
            ("{battery_stat}", "Current battery charging status (Charging, Discharging, Full)"),
            ("{battery_status}", "Alias for {battery_stat}"),
            ("{localip}", "Primary outbound IPv4 address"),
            ("{user-mode}", "Privilege level (User or Root)"),
            ("{version}", "BashMenu application version"),
            ("{theme}", "Active color theme name (or {app.theme})"),
        ],
    ),
    (
        "Date & Time Placeholders",
        [
            ("{date_time_12}", "Timestamp 12-hr format (YYYY-MM-DD HH:MM:SS AM/PM)"),
            ("{date_time_12_short}", "Timestamp 12-hr short format (YYYY-MM-DD HH:MM AM/PM)"),
            ("{date_time_24}", "Timestamp 24-hr format (YYYY-MM-DD HH:MM:SS)"),
            ("{date_time_24_short}", "Timestamp 24-hr short format (YYYY-MM-DD HH:MM)"),
            ("{date}", "Current date (YYYY-MM-DD)"),
            ("{time_12}", "Current time 12-hr format"),
            ("{time_12_short}", "Current time 12-hr short format"),
            ("{time_24}", "Current time 24-hr format"),
            ("{time_24_short}", "Current time 24-hr short format"),
            ("{utc_seconds}", "UTC Unix epoch timestamp in seconds"),
        ],
    ),
    (
        "Terminal Layout Directives",
        [
            ("{window_width}", "Inner terminal window column width"),
            ("{window_height}", "Inner terminal window line height"),
            ("{screen_width}", "Full terminal screen column width"),
            ("{divider}", "Themed horizontal divider bar ({ascii:196})"),
        ],
    ),
    (
        "Special Encodings & Dynamic Macros",
        [
            ("{ascii:<code_num>}", "CP437 ASCII character byte (e.g. {ascii:196} -> ─)"),
            ("{command:<cmd>}", "Executes shell command and inserts output"),
            ('{toast:SECONDS:"MESSAGE"}', "Displays non-blocking popup toast message"),
            ("{nf:<char>:<hex>:<emoji>}", "Adaptive Nerd Font / Unicode / Emoji glyph"),
            ("{app.<key.path>}", "Configuration key in bashmenu.yml (e.g. {app.theme})"),
            ("{<key.path>}", "Refers to nested key in bashmenu.yml (e.g. {user.postal_code})"),
        ],
    ),
]


def format_placeholder_help_text(col1_width: int = 28) -> str:
    """Format placeholder help entries into two aligned columns."""
    lines = []
    for title, items in PLACEHOLDER_SECTIONS:
        if lines:
            lines.append("")
        lines.append(f"[bold magenta]── {title} ──[/bold magenta]")
        for ph, desc in items:
            padded_ph = f"{ph:<{col1_width}}"
            lines.append(f"[bold white]{padded_ph}[/bold white] │ {desc}")
    return "\n".join(lines)


PLACEHOLDER_HELP_TEXT = format_placeholder_help_text(28)


RICH_REFERENCE_SECTIONS = [
    (
        "Text Styling & Font Weight Tags",
        [
            (r"\[b\]text\[/b\]", "Renders text in bold font weight", "[b]Bold text preview[/b]"),
            (r"\[u\]text\[/u\]", "Renders text with an underline", "[u]Underlined text preview[/u]"),
            (r"\[dim\]text\[/dim\]", "Renders text with reduced/dimmed contrast", "[dim]Dimmed text preview[/dim]"),
            (r"\[reverse\]text\[/reverse\]", "Inverts foreground and background colors", "[reverse] Inverted video preview [/reverse]"),
        ],
    ),
    (
        "Theme Color Tags (Adaptive)",
        [
            (r"\[color=accent\]...\[/color\]", "Active theme accent / badge highlight color", "[color=accent]Accent status indicator[/color]"),
            (r"\[color=title\]...\[/color\]", "Active theme window title and header color", "[color=title]Title header element[/color]"),
            (r"\[color=highlight\]...\[/color\]", "Active theme selection highlight color", "[color=highlight]Selected item highlight[/color]"),
            (r"\[color=shortcut_key\]...\[/color\]", "Direct action keyboard shortcut badge color", "[color=shortcut_key]Shortcut badge [1][/color]"),
            (r"\[color=help_text\]...\[/color\]", "Help prompt and footer guidance text color", "[color=help_text]Footer help text[/color]"),
            (r"\[color=plugin\]...\[/color\]", "Plugin output buffer text color", "[color=plugin]Plugin feed data[/color]"),
            (r"\[color=border\]...\[/color\]", "Outer window border frame color", "[color=border]Window border style[/color]"),
            (r"\[color=divider\]...\[/color\]", "Horizontal rule and separator divider color", "[color=divider]Divider line[/color]"),
            (r"\[color=text\]...\[/color\]", "Default foreground text body color", "[color=text]Default body copy[/color]"),
            (r"\[color=footer\]...\[/color\]", "Bottom status bar and footer color", "[color=footer]Footer status gutter[/color]"),
        ],
    ),
    (
        "Standard Named & Hex Colors",
        [
            (r"\[color=red\]...\[/color\]", "Standard red foreground color", "[color=red]Alert / Red text[/color]"),
            (r"\[color=green\]...\[/color\]", "Standard green foreground color", "[color=green]Success / Green text[/color]"),
            (r"\[color=yellow\]...\[/color\]", "Standard yellow foreground color", "[color=yellow]Warning / Yellow text[/color]"),
            (r"\[color=blue\]...\[/color\]", "Standard blue foreground color", "[color=blue]Notice / Blue text[/color]"),
            (r"\[color=magenta\]...\[/color\]", "Standard magenta foreground color", "[color=magenta]Magenta text[/color]"),
            (r"\[color=cyan\]...\[/color\]", "Standard cyan foreground color", "[color=cyan]Cyan text[/color]"),
            (r"\[color=white\]...\[/color\]", "Standard white foreground color", "[color=white]White text[/color]"),
            (r"\[color=#rrggbb\]...\[/color\]", "24-bit TrueColor hex color (Rich style)", "e.g. [color=cyan]#50fa7b[/color]"),
        ],
    ),
    (
        "Structural Layout Tags",
        [
            (r"\[table width=100%\]...\[/table\]", "Auto-aligned Unicode box-drawing table", "Encloses [tr], [th], and [td] cells"),
            (r"\[tr\]...\[/tr\]", "Table row container element", "Groups header and data cells"),
            (r"\[th\]...\[/th\]", "Table header cell (automatically bolded)", "Column header label cell"),
            (r"\[td\]...\[/td\]", "Table data cell with text wrapping", "Standard table data cell"),
            (r"\[list\]...\[/list\]", "Unordered bulleted list (`•`)", "Encloses [*] item bullet entries"),
            (r"\[list=1\]...\[/list\]", "Ordered numbered list (`1.`, `2.`)", "Encloses [*] numbered step entries"),
            (r"\[list=a\]...\[/list\]", "Ordered alphabetic list (`a.`, `b.`)", "Encloses [*] alphabetic entries"),
            (r"\[*\]item", "List item entry delimiter", "Prefix for items inside [list]"),
        ],
    ),
    (
        "Parser Directives & Escaping",
        [
            (r"\[tag]", "Backslash escaping to render literal tags", r"Renders literal \[b] without styling"),
            ("`[tag]` / ```[tag]```", "Inline and fenced code block suppression", "Suppresses tag styling inside code"),
            ("no_formatting=True", "Screen/conversion parameter to bypass parser", "Displays raw unformatted source text"),
        ],
    ),
]


def format_rich_reference_help_text(col1_width: int = 34) -> str:
    """Format Rich Text and BBCode tags reference into aligned help documentation."""
    lines = []
    for title, items in RICH_REFERENCE_SECTIONS:
        if lines:
            lines.append("")
        lines.append(f"[bold magenta]── {title} ──[/bold magenta]")
        for tag_syntax, desc, example in items:
            padded_tag = f"{tag_syntax:<{col1_width}}"
            lines.append(f"[bold white]{padded_tag}[/bold white] │ {desc}")
            if example:
                lines.append(f"  [dim]Example:[/dim] {example}")
    return "\n".join(lines)


RICH_REFERENCE_HELP_TEXT = format_rich_reference_help_text(34)


MARKDOWN_REFERENCE_TEXT = """# Markdown Syntax Reference

| Syntax | Output / Action |
| :--- | :--- |
| `# Heading 1` | Top-level section heading |
| `## Heading 2` | Secondary section heading |
| `### Heading 3` | Subsection heading |
| `**Bold**` or `__Bold__` | Bold weighted text |
| `*Italic*` or `_Italic_` | Italic emphasized text |
| `~~Strikethrough~~` | Strikethrough text |
| `` `code` `` | Inline monospace code snippet |
| `> Blockquote` | Quoted callout block |
| `- Item` or `* Item` | Unordered bulleted list item |
| `1. Item` | Ordered numbered list item |
| `- [ ] Todo` / `- [x] Done` | Task list checkboxes |
| `[Title](url)` | Hyperlink anchor reference |
| `![Alt](path/to/img)` | Image embed reference |
| `---` or `***` | Horizontal divider rule |
| ```` ```bash ```` | Fenced code block with syntax highlight |
"""


def is_pua_glyph(c: str) -> bool:
    """
    Check if a character falls within Unicode Private Use Area ranges
    where Nerd Font glyphs reside.
    """
    if not c or not isinstance(c, str):
        return False
    cp = ord(c[0])
    return (
        (0xE000 <= cp <= 0xF8FF)
        or (0xF0000 <= cp <= 0xFFFFF)
        or (0x100000 <= cp <= 0x10FFFD)
    )


def get_nerd_font_width(config=None) -> int:
    """
    Determine the display width for Nerd Font / PUA glyphs.
    """
    mode = "auto"
    if isinstance(config, dict):
        settings = config.get("settings", {})
        if isinstance(settings, dict) and "nerd_font_width" in settings:
            mode = settings.get("nerd_font_width")

    if mode is not None:
        mode_str = str(mode).lower().strip()
        if mode_str in ("2", "double", "wide", "two"):
            return 2
        elif mode_str in ("1", "single", "narrow", "one"):
            return 1

    return 1


def is_emoji_char(c: str) -> bool:
    """
    Check if a character is a standard Unicode emoji symbol.
    """
    if not c:
        return False
    cp = ord(c[0])
    return (
        (0x1F300 <= cp <= 0x1F9FF)
        or (0x1FA00 <= cp <= 0x1FAFF)
        or (0x2600 <= cp <= 0x27BF)
        or (0x2300 <= cp <= 0x23FF)
        or (0x2B50 <= cp <= 0x2B59)
        or (0x1F000 <= cp <= 0x1F02F)
        or (0x1F0A0 <= cp <= 0x1F0FF)
        or (0x1F1E6 <= cp <= 0x1F1FF)
        or (0x2100 <= cp <= 0x214F)
        or (0x2000 <= cp <= 0x206F)
        or (0x2900 <= cp <= 0x297F)
        or (0x2B00 <= cp <= 0x2BFF)
    )


try:
    _libc = ctypes.CDLL(None)
    _c_wcwidth = _libc.wcwidth
    _c_wcwidth.argtypes = [ctypes.c_wchar]
    _c_wcwidth.restype = ctypes.c_int
except Exception:  # noqa: BLE001
    _c_wcwidth = None


def get_char_width(c: str, config=None) -> int:
    """
    Get the display width of a single character in terminal columns.
    """
    if not c:
        return 0
    cp = ord(c[0])
    if 0xFE00 <= cp <= 0xFE0F:
        return 0
    if is_pua_glyph(c[0]):
        return get_nerd_font_width(config)
    if 0x2500 <= cp <= 0x259F:
        return 1
    if is_emoji_char(c[0]) or unicodedata.east_asian_width(c[0]) in ("W", "F"):
        return 2
    if _c_wcwidth is not None:
        w = _c_wcwidth(c[0])
        if w >= 0:
            return w
    return 1


def get_display_width(s: str, config=None) -> int:
    """
    Calculate the visual display width of a string on screen in terminal columns.
    """
    if not s:
        return 0
    if not isinstance(s, str):
        s = str(s)
    clean_s = s.replace("\ufe0f", "").replace("\ufe0e", "")
    if not clean_s:
        return 0

    try:
        from rich.cells import cell_len
        return cell_len(clean_s)
    except ImportError:
        pass

    total = 0
    i = 0
    n = len(clean_s)
    while i < n:
        c = clean_s[i]
        cp = ord(c)

        if 0xFE00 <= cp <= 0xFE0F:
            i += 1
            continue

        if is_pua_glyph(c):
            total += get_nerd_font_width(config)
            i += 1
            continue

        if 0x2500 <= cp <= 0x259F:
            total += 1
            i += 1
            continue

        if (0x1F300 <= cp <= 0x1F9FF) or (0x1FA00 <= cp <= 0x1FAFF) or unicodedata.east_asian_width(c) in ("W", "F"):
            total += 2
            i += 1
            continue

        if unicodedata.category(c).startswith("M"):
            i += 1
            continue

        if _c_wcwidth is not None:
            w = _c_wcwidth(c)
            if w >= 0:
                total += w
                i += 1
                continue
        i += 1

    return total


TAG_PATTERN = re.compile(r"\[(/?[a-zA-Z_0-9=\*\s%]+)\]")


def wrap_cell_content(c_text: str, max_w: int, config=None) -> list[str]:
    """
    Split cell text into lines and wrap any line exceeding max_w into multiple lines,
    preserving BBCode tags and word boundaries.
    """
    if max_w <= 0:
        return [""]
    raw_lines = c_text.split("\n")
    final_lines = []
    for line in raw_lines:
        line_vis = get_visible_len(line, config)
        if line_vis <= max_w:
            final_lines.append(line)
            continue

        words = line.split(" ")
        cur_line = []
        cur_len = 0
        for w in words:
            w_vis = get_visible_len(w, config)
            if w_vis > max_w:
                if cur_line:
                    final_lines.append(" ".join(cur_line))
                    cur_line = []
                    cur_len = 0
                chunk = w
                while get_visible_len(chunk, config) > max_w:
                    sub = chunk[:max_w]
                    final_lines.append(sub)
                    chunk = chunk[max_w:]
                if chunk:
                    cur_line.append(chunk)
                    cur_len = get_visible_len(chunk, config)
                continue

            if not cur_line:
                cur_line.append(w)
                cur_len = w_vis
            elif cur_len + 1 + w_vis <= max_w:
                cur_line.append(w)
                cur_len += 1 + w_vis
            else:
                final_lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = w_vis

        if cur_line:
            final_lines.append(" ".join(cur_line))

    return final_lines or [""]


def process_bbcode_structural_tags(
    text: str, config=None, theme=None, no_formatting: bool = False, avail_width: int | None = None
) -> str:
    """
    Preprocess structural BBCode tags ([table]...[/table], [list]...[/list]) into
    aligned ASCII/Unicode table borders and bullet/numbered lists before inline styling.
    Suppresses processing inside backtick code spans/blocks and respects backslash escaping.
    """
    if not isinstance(text, str) or no_formatting:
        return text if text is not None else ""

    text_lower = text.lower()
    if "[table" not in text_lower and "[list" not in text_lower:
        return text

    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]

    def is_inside_code(start: int, end: int) -> bool:
        return any(r_start <= start and end <= r_end for r_start, r_end in code_ranges)

    def replace_list(match):
        start, end = match.span()
        if is_inside_code(start, end):
            return match.group(0)
        if start > 0 and text[start - 1] == "\\":
            return match.group(0)

        list_type = match.group(1) or ""
        content = match.group(2)
        raw_items = re.split(r"\[\*\]", content)
        items = []
        for it in raw_items:
            it = re.sub(r"\[/\*\]\s*$", "", it).strip()
            if it:
                items.append(it)

        lt = list_type.strip().lower()
        lines = []
        for idx, it in enumerate(items, 1):
            if lt == "1":
                prefix = f"  {idx}. "
            elif lt == "a":
                prefix = f"  {chr(ord('a') + (idx - 1) % 26)}. "
            elif list_type.strip() == "A":
                prefix = f"  {chr(ord('A') + (idx - 1) % 26)}. "
            else:
                prefix = "  • "

            indent = " " * len(prefix)
            sublines = it.split("\n")
            lines.append(f"{prefix}{sublines[0].strip()}")
            for sl in sublines[1:]:
                lines.append(f"{indent}{sl.strip()}")
        return "\n".join(lines)

    text = re.sub(r"\[list(?:=([0-9a-zA-Z]+))?\](.*?)\[/list\]", replace_list, text, flags=re.DOTALL | re.IGNORECASE)

    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]

    def replace_table(match):
        start, end = match.span()
        if is_inside_code(start, end):
            return match.group(0)
        if start > 0 and text[start - 1] == "\\":
            return match.group(0)

        eff_avail_w = avail_width
        if eff_avail_w is None and isinstance(config, dict):
            eff_avail_w = config.get("avail_width") or config.get("window_width")
        if not eff_avail_w:
            with contextlib.suppress(Exception):
                import shutil
                eff_avail_w = max(20, shutil.get_terminal_size((80, 24)).columns - 6)
        if not eff_avail_w:
            eff_avail_w = 74

        attrs = match.group(1) or ""
        table_content = match.group(2)
        tr_matches = re.findall(r"\[tr(?:\s+[^\]]*)?\](.*?)\[/tr\]", table_content, flags=re.DOTALL | re.IGNORECASE)
        if not tr_matches:
            return ""

        rows = []
        for tr in tr_matches:
            cells = []
            for cell_match in re.finditer(r"\[(th|td)(?:\s+[^\]]*)?\](.*?)\[/\1\]", tr, flags=re.DOTALL | re.IGNORECASE):
                tag = cell_match.group(1).lower()
                c_text = cell_match.group(2).strip()
                if tag == "th":
                    c_text = f"[b]{c_text}[/b]"
                cells.append((tag, c_text))
            if cells:
                rows.append(cells)

        if not rows:
            return ""

        num_cols = max(len(r) for r in rows)
        overhead = 3 * num_cols + 1

        # Check for width attribute on [table width=...]
        target_w = None
        w_match = re.search(r"width\s*=\s*['\"]?([0-9]+%?|full)['\"]?", attrs, re.IGNORECASE)
        if w_match:
            w_val = w_match.group(1).lower()
            if w_val in ("100%", "full"):
                target_w = eff_avail_w
            elif w_val.endswith("%"):
                with contextlib.suppress(ValueError):
                    pct = int(w_val[:-1])
                    target_w = max(10, int(eff_avail_w * (pct / 100.0)))
            else:
                with contextlib.suppress(ValueError):
                    target_w = int(w_val)

        if target_w is not None:
            # Distribute width equally across columns (e.g. 50/50, 33/33/33, 25/25/25/25)
            avail_content = max(num_cols, target_w - overhead)
            base_col_w = avail_content // num_cols
            remainder = avail_content % num_cols
            col_widths = [base_col_w + (1 if c_idx < remainder else 0) for c_idx in range(num_cols)]
        else:
            # Auto-fit based on longest string in each column
            col_widths = [0] * num_cols
            for r in rows:
                for c_idx in range(len(r)):
                    _, c_text = r[c_idx]
                    vis_len = get_visible_len(c_text, config)
                    col_widths[c_idx] = max(col_widths[c_idx], vis_len)
            col_widths = [max(1, w) for w in col_widths]

            # If unconstrained table exceeds eff_avail_w, constrain and wrap text
            if overhead + sum(col_widths) > eff_avail_w:
                avail_content = max(num_cols, eff_avail_w - overhead)
                base_col_w = avail_content // num_cols
                remainder = avail_content % num_cols
                col_widths = [base_col_w + (1 if c_idx < remainder else 0) for c_idx in range(num_cols)]

        top_border = "┌─" + "─┬─".join("─" * w for w in col_widths) + "─┐"
        sep_border = "├─" + "─┼─".join("─" * w for w in col_widths) + "─┤"
        bot_border = "└─" + "─┴─".join("─" * w for w in col_widths) + "─┘"

        table_lines = [top_border]
        for r_idx, r in enumerate(rows):
            cell_lines_per_col = []
            for c_idx in range(num_cols):
                if c_idx < len(r):
                    _, c_text = r[c_idx]
                    clines = wrap_cell_content(c_text, col_widths[c_idx], config)
                else:
                    clines = [""]
                cell_lines_per_col.append(clines)

            row_height = max(len(clines) for clines in cell_lines_per_col)
            for h in range(row_height):
                padded_cells = []
                for c_idx in range(num_cols):
                    clines = cell_lines_per_col[c_idx]
                    line_text = clines[h] if h < len(clines) else ""
                    vis_len = get_visible_len(line_text, config)
                    pad = " " * max(0, col_widths[c_idx] - vis_len)
                    padded_cells.append(line_text + pad)
                table_lines.append("│ " + " │ ".join(padded_cells) + " │")

            is_current_th = any(tag == "th" for tag, _ in r)
            is_next_td = (r_idx + 1 < len(rows)) and any(tag == "td" for tag, _ in rows[r_idx + 1])
            if is_current_th and is_next_td:
                table_lines.append(sep_border)

        table_lines.append(bot_border)
        return "\n".join(table_lines)

    text = re.sub(r"\[table(?:\s+([^\]]*))?\](.*?)\[/table\]", replace_table, text, flags=re.DOTALL | re.IGNORECASE)
    return text


def get_visible_len(text, config=None, avail_width: int | None = None) -> int:
    """
    Return the visible length of a string by stripping formatting tags [tag].
    For multi-line strings, returns the maximum line width.
    """
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)

    clean_text = strip_formatting_tags(text, avail_width=avail_width)
    if "\n" in clean_text:
        return max((get_display_width(line, config) for line in clean_text.split("\n")), default=0)
    return get_display_width(clean_text, config)


def parse_formatting_to_segments(
    text, base_attr=0, theme=None, no_formatting: bool = False, avail_width: int | None = None
):
    """
    Parse console bracket formatting tags [b], [u], [dim], [reverse], [color=...] and
    return a list of (text, attr) segments for backward compatibility.
    """
    if not isinstance(text, str):
        text = str(text)

    if no_formatting:
        return [(text, base_attr)]

    text = process_bbcode_structural_tags(text, no_formatting=no_formatting, avail_width=avail_width)
    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=\*\s%]+)\]")
    segments = []
    current_attr = base_attr
    attr_stack = [current_attr]
    last_idx = 0

    for match in tag_pattern.finditer(text):
        tag = match.group(1)
        if not is_formatting_tag(tag):
            continue

        start, end = match.span()
        if any(r_start <= start and end <= r_end for r_start, r_end in code_ranges):
            continue

        if start > 0 and text[start - 1] == "\\":
            if start - 1 > last_idx:
                segments.append((text[last_idx : start - 1], current_attr))
            segments.append((text[start:end], current_attr))
            last_idx = end
            continue

        if start > last_idx:
            segments.append((text[last_idx:start], current_attr))

        if tag.startswith("/"):
            if len(attr_stack) > 1:
                attr_stack.pop()
                current_attr = attr_stack[-1]
        else:
            new_attr = current_attr
            tag_clean = tag.strip().lower()
            if tag_clean == "b":
                new_attr |= 1  # BOLD flag representation
            elif tag_clean == "u":
                new_attr |= 2  # UNDERLINE flag representation
            elif tag_clean == "dim":
                new_attr |= 4  # DIM flag representation
            elif tag_clean == "reverse":
                new_attr |= 8  # REVERSE flag representation
            attr_stack.append(new_attr)
            current_attr = new_attr

        last_idx = end

    if last_idx < len(text):
        segments.append((text[last_idx:], current_attr))

    return segments


def formatting_to_rich_text(
    text: str,
    default_style: Style | None = None,
    theme: dict | None = None,
    no_formatting: bool = False,
    avail_width: int | None = None,
) -> Text:
    """
    Convert custom bracket formatting ([b], [u], [dim], [color=name]) into a Rich Text object.
    Supports backslash escaping (\\\\[tag]) and suppresses formatting inside backtick code spans/blocks.
    """
    if not isinstance(text, str):
        text = str(text)

    if no_formatting:
        return Text(text, style=default_style or Style())

    text = process_bbcode_structural_tags(text, theme=theme, no_formatting=no_formatting, avail_width=avail_width)
    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=\*\s%]+)\]")
    rich_text = Text()

    if isinstance(default_style, str):
        try:
            current_style = Style.parse(default_style)
        except Exception:  # noqa: BLE001
            current_style = Style()
    elif isinstance(default_style, Style):
        current_style = default_style
    else:
        current_style = Style()
    style_stack = [current_style]
    last_idx = 0

    for match in tag_pattern.finditer(text):
        tag = match.group(1)
        if not is_formatting_tag(tag):
            continue

        start, end = match.span()
        if any(r_start <= start and end <= r_end for r_start, r_end in code_ranges):
            continue

        if start > 0 and text[start - 1] == "\\":
            if start - 1 > last_idx:
                rich_text.append(text[last_idx : start - 1], style=current_style)
            rich_text.append(text[start:end], style=current_style)
            last_idx = end
            continue

        if start > last_idx:
            rich_text.append(text[last_idx:start], style=current_style)

        if tag.startswith("/"):
            if len(style_stack) > 1:
                style_stack.pop()
                current_style = style_stack[-1]
        else:
            tag_clean = tag.strip().lower()
            new_style = current_style
            if tag_clean in ("b", "bold"):
                new_style = new_style + Style(bold=True)
            elif tag_clean in ("u", "underline"):
                new_style = new_style + Style(underline=True)
            elif tag_clean == "dim":
                new_style = new_style + Style(dim=True)
            elif tag_clean == "reverse":
                new_style = new_style + Style(reverse=True)
            elif tag_clean.startswith("color="):
                color_name = tag.split("=", 1)[1].strip()
                if theme and color_name in theme:
                    t_style = theme[color_name]
                    if isinstance(t_style, Style):
                        new_style = new_style + t_style
                elif color_name in COLOR_MAP:
                    new_style = new_style + Style(color=COLOR_MAP[color_name])
                else:
                    try:
                        new_style = new_style + Style(color=color_name)
                    except Exception:  # noqa: BLE001, S110
                        pass
            else:
                with contextlib.suppress(Exception):
                    new_style = new_style + Style.parse(tag_clean)

            style_stack.append(new_style)
            current_style = new_style

        last_idx = end

    if last_idx < len(text):
        rich_text.append(text[last_idx:], style=current_style)

    return rich_text


def strip_formatting_tags(text: str, no_formatting: bool = False, avail_width: int | None = None) -> str:
    """
    Strip all bracketed formatting tags [b], [color=...], etc.
    """
    if not isinstance(text, str):
        text = str(text)
    if no_formatting:
        return text

    text = process_bbcode_structural_tags(text, no_formatting=no_formatting, avail_width=avail_width)
    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=\*\s%]+)\]")
    result = []
    last_idx = 0

    for match in tag_pattern.finditer(text):
        tag = match.group(1)
        if not is_formatting_tag(tag):
            continue

        start, end = match.span()
        if any(r_start <= start and end <= r_end for r_start, r_end in code_ranges):
            continue

        if start > 0 and text[start - 1] == "\\":
            result.append(text[last_idx : start - 1])
            result.append(text[start:end])
            last_idx = end
        else:
            result.append(text[last_idx:start])
            last_idx = end

    result.append(text[last_idx:])
    return "".join(result)


def safe_addstr_segments(win, y, x=None, segments=None, config=None):
    """Compatibility shim."""


def safe_addstr(win, y_or_text, x_or_attr=None, text_or_none=None, attr=0):
    """Compatibility shim."""


def draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme=None):
    """Draw a classic drop shadow behind a popup modal window on stdscr."""
    with contextlib.suppress(Exception):
        max_y, max_x = stdscr.getmaxyx()
        shadow_char = "░"
        if isinstance(theme, dict) and "window_borders" in theme:
            shadow_char = theme["window_borders"].get("shadow_char", "░")

        for y in range(start_y + 1, min(max_y, start_y + box_h + 1)):
            for x in range(start_x + box_w, min(max_x, start_x + box_w + 2)):
                with contextlib.suppress(Exception):
                    stdscr.addstr(y, x, shadow_char)
        for x in range(start_x + 2, min(max_x, start_x + box_w + 2)):
            y = start_y + box_h
            if y < max_y:
                with contextlib.suppress(Exception):
                    stdscr.addstr(y, x, shadow_char)


# ==============================================================================
# THEME PARSING AND CONVERSION
# ==============================================================================

COLOR_MAP = {
    "COLOR_BLACK": "#000000",
    "COLOR_RED": "#ff0000",
    "COLOR_GREEN": "#00ff00",
    "COLOR_YELLOW": "#ffff00",
    "COLOR_BLUE": "#5f87ff",
    "COLOR_MAGENTA": "#ff00ff",
    "COLOR_CYAN": "#00ffff",
    "COLOR_WHITE": "#ffffff",
    "COLOR_GREY": "#808080",
    "COLOR_GRAY": "#808080",
    "COLOR_BRIGHT_BLACK": "#808080",
    "COLOR_BRIGHT_RED": "#ff5555",
    "COLOR_BRIGHT_GREEN": "#55ff55",
    "COLOR_BRIGHT_YELLOW": "#ffff55",
    "COLOR_BRIGHT_BLUE": "#5555ff",
    "COLOR_BRIGHT_MAGENTA": "#ff55ff",
    "COLOR_BRIGHT_CYAN": "#55ffff",
    "COLOR_BRIGHT_WHITE": "#ffffff",
    "COLOR_ORANGE": "#ff8700",
    "COLOR_PURPLE": "#af00ff",
    "COLOR_PINK": "#ff87af",
    "COLOR_BROWN": "#af5f00",
}


def parse_color_val(val):
    """Parse color spec into Rich color string or None."""
    if val is None or val == -1 or val == "-1":
        return None
    if isinstance(val, str) and val in COLOR_MAP:
        return COLOR_MAP[val]
    if isinstance(val, int):
        return f"color({val})"
    if isinstance(val, str):
        if val.isdigit():
            return f"color({val})"
        try:
            from rich.color import Color
            Color.parse(val)
            return val
        except Exception:  # noqa: BLE001
            return None
    return None


_themes_file_cache = {}
_themes_last_stat_check: dict[str, float] = {}
_default_themes_filepath: str | None = None
_theme_styles_cache = {}

DEFAULT_WINDOW_BORDER = {
    "border_horizontal": "─",
    "border_vertical": "│",
    "border_horizontal_top": "─",
    "border_horizontal_bottom": "─",
    "border_vertical_left": "│",
    "border_vertical_right": "│",
    "border_top_left": "┌",
    "border_top_right": "┐",
    "border_bottom_left": "└",
    "border_bottom_right": "┘",
    "border_tee_top": "┬",
    "border_tee_bottom": "┴",
    "border_tee_left": "├",
    "border_tee_right": "┤",
    "left_tee": "├",
    "right_tee": "┤",
    "top_tee": "┬",
    "bottom_tee": "┴",
    "border_cross": "┼",
    "title_left_cap": "[",
    "title_right_cap": "]",
    "shadow_char": "░",
    "gutter_border": "─",
    "gutter_separator": "│",
    "gutter_left_tee": "├",
    "gutter_right_tee": "┤",
    "gutter_top_tee": "┬",
    "gutter_bottom_tee": "┴",
}


def get_theme_window_borders(
    theme_name: str | dict = "dracula",
    config: dict | None = None,
    raw_theme_data: dict | None = None,
) -> dict[str, str]:
    """Retrieve and interpolate window border characters for the specified theme.

    Returns a dictionary containing border_horizontal, border_vertical,
    border_horizontal_top, border_horizontal_bottom, border_vertical_left,
    border_vertical_right, border_top_left, border_top_right,
    border_bottom_left, border_bottom_right, border_tee_top, border_tee_bottom,
    border_tee_left, border_tee_right, border_cross, title_left_cap,
    title_right_cap, and shadow_char.
    Falls back to standard box drawing characters for any undefined keys.
    """
    window_def = None
    if isinstance(theme_name, dict):
        if "window_borders" in theme_name and isinstance(theme_name["window_borders"], dict):
            return dict(theme_name["window_borders"])
        if "window" in theme_name and isinstance(theme_name["window"], dict):
            window_def = theme_name["window"]
            theme_def = theme_name
        else:
            theme_name = theme_name.get("theme_name", "dracula")

    if not raw_theme_data:
        raw_theme_data = load_themes_file()

    if window_def is None:
        theme_def = raw_theme_data.get(theme_name, {}) if isinstance(theme_name, str) else {}
        if not theme_def and raw_theme_data:
            theme_def = next(iter(raw_theme_data.values()), {})

        window_def = theme_def.get("window", {}) if isinstance(theme_def, dict) else {}
        if not isinstance(window_def, dict):
            window_def = {}

    if isinstance(config, dict):
        cfg_win = config.get("window") or config.get("settings", {}).get("window") or config.get("user", {}).get("window")
        if isinstance(cfg_win, dict):
            merged_win = dict(window_def)
            merged_win.update(cfg_win)
            window_def = merged_win

    borders = dict(DEFAULT_WINDOW_BORDER)
    if not window_def:
        return borders

    import bashmenu

    # Helper to resolve raw value from window_def
    def _resolve_val(val_raw):
        if val_raw is None:
            return None
        val_str = str(val_raw)
        if "{" in val_str:
            val_str = bashmenu.interpolate_placeholders(val_str, config or {})
            val_str = bashmenu.resolve_glyph(val_str, config or {})
        val_clean = val_str.replace("\ufe0f", "").replace("\ufe0e", "")
        return val_clean if val_clean else None

    # Base horizontal & vertical fallbacks
    h_base = _resolve_val(window_def.get("border_horizontal") or window_def.get("window_border_horizontal"))
    v_base = _resolve_val(window_def.get("border_vertical") or window_def.get("window_border_vertical"))
    if h_base:
        borders["border_horizontal"] = h_base
        borders["border_horizontal_top"] = h_base
        borders["border_horizontal_bottom"] = h_base
    if v_base:
        borders["border_vertical"] = v_base
        borders["border_vertical_left"] = v_base
        borders["border_vertical_right"] = v_base

    # Specific edge, corner, T-junction, title cap, and shadow overrides
    aliases = {
        "border_horizontal_top": ["border_horizontal_top", "border_top", "window_border_horizontal_top", "window_border_top"],
        "border_horizontal_bottom": ["border_horizontal_bottom", "border_bottom", "window_border_horizontal_bottom", "window_border_bottom"],
        "border_vertical_left": ["border_vertical_left", "border_left", "window_border_vertical_left", "window_border_left"],
        "border_vertical_right": ["border_vertical_right", "border_right", "window_border_vertical_right", "window_border_right"],
        "border_top_left": ["border_top_left", "window_border_top_left"],
        "border_top_right": ["border_top_right", "window_border_top_right"],
        "border_bottom_left": ["border_bottom_left", "window_border_bottom_left"],
        "border_bottom_right": ["border_bottom_right", "window_border_bottom_right"],
        "border_tee_top": ["border_tee_top", "top_tee", "tee_top", "window_border_tee_top", "window_top_tee", "window_tee_top"],
        "border_tee_bottom": ["border_tee_bottom", "bottom_tee", "tee_bottom", "window_border_tee_bottom", "window_bottom_tee", "window_tee_bottom"],
        "border_tee_left": ["border_tee_left", "left_tee", "tee_left", "window_border_tee_left", "window_left_tee", "window_tee_left"],
        "border_tee_right": ["border_tee_right", "right_tee", "tee_right", "window_border_tee_right", "window_right_tee", "window_tee_right"],
        "border_cross": ["border_cross", "window_border_cross"],
        "title_left_cap": ["title_left_cap", "title_cap_left", "window_title_left_cap", "window_title_cap_left"],
        "title_right_cap": ["title_right_cap", "title_cap_right", "window_title_right_cap", "window_title_cap_right"],
        "shadow_char": ["shadow_char", "window_shadow_char"],
        "gutter_border": ["gutter_border", "window_gutter_border"],
        "gutter_separator": ["gutter_separator", "window_gutter_separator"],
        "gutter_left_tee": ["gutter_left_tee", "gutter_tee_left", "window_gutter_left_tee"],
        "gutter_right_tee": ["gutter_right_tee", "gutter_tee_right", "window_gutter_right_tee"],
        "gutter_top_tee": ["gutter_top_tee", "gutter_tee_top", "window_gutter_top_tee"],
        "gutter_bottom_tee": ["gutter_bottom_tee", "gutter_tee_bottom", "window_gutter_bottom_tee"],
    }

    cfg_win_dict = cfg_win if (isinstance(config, dict) and isinstance(cfg_win, dict)) else {}
    for target_key, candidate_keys in aliases.items():
        found = False
        for ck in candidate_keys:
            if ck in cfg_win_dict:
                res = _resolve_val(cfg_win_dict[ck])
                if res:
                    borders[target_key] = res
                    found = True
                    break
        if found:
            continue

        for ck in candidate_keys:
            if ck in window_def:
                res = _resolve_val(window_def[ck])
                if res:
                    borders[target_key] = res
                    break

    # Provide direct convenient aliases in the returned border dictionary
    borders["left_tee"] = borders["border_tee_left"]
    borders["right_tee"] = borders["border_tee_right"]
    borders["top_tee"] = borders["border_tee_top"]
    borders["bottom_tee"] = borders["border_tee_bottom"]

    if "gutter_border" not in borders or not borders["gutter_border"]:
        borders["gutter_border"] = borders.get("border_horizontal_bottom", borders.get("border_horizontal", "─"))
    if "gutter_separator" not in borders or not borders["gutter_separator"]:
        borders["gutter_separator"] = borders.get("border_vertical", "│")
    if "gutter_left_tee" not in borders or not borders["gutter_left_tee"]:
        borders["gutter_left_tee"] = borders.get("left_tee", "├")
    if "gutter_right_tee" not in borders or not borders["gutter_right_tee"]:
        borders["gutter_right_tee"] = borders.get("right_tee", "┤")
    if "gutter_top_tee" not in borders or not borders["gutter_top_tee"]:
        borders["gutter_top_tee"] = borders.get("top_tee", "┬")
    if "gutter_bottom_tee" not in borders or not borders["gutter_bottom_tee"]:
        borders["gutter_bottom_tee"] = borders.get("bottom_tee", "┴")

    return borders


def get_theme_divider(
    theme_name: str | dict = "dracula",
    config: dict | None = None,
    raw_theme_data: dict | None = None,
) -> dict | None:
    """Retrieve explicit divider configuration from bashmenu.themes for the given theme, if defined."""
    if isinstance(theme_name, dict):
        if "divider" in theme_name:
            div = theme_name["divider"]
            if isinstance(div, dict):
                return dict(div)
            if isinstance(div, (str, int)):
                return {"char": str(div)}
        theme_name = theme_name.get("theme_name", "dracula")

    if not raw_theme_data:
        raw_theme_data = load_themes_file()

    theme_def = raw_theme_data.get(theme_name, {}) if isinstance(theme_name, str) and raw_theme_data else {}
    if isinstance(theme_def, dict) and "divider" in theme_def:
        div = theme_def["divider"]
        if isinstance(div, dict):
            return dict(div)
        if isinstance(div, (str, int)):
            return {"char": str(div)}
    return None


_last_applied_theme_borders = None


def apply_theme_to_textual_borders(
    theme_name: str | dict = "dracula",
    config: dict | None = None,
    raw_theme_data: dict | None = None,
) -> None:
    """Synchronize Textual's global border rendering characters with the active theme borders."""
    global _last_applied_theme_borders
    with contextlib.suppress(Exception):
        import textual._border as tb

        borders = get_theme_window_borders(theme_name, config=config, raw_theme_data=raw_theme_data)
        b_h_top = borders.get("border_horizontal_top", borders.get("border_horizontal", "─"))
        b_h_bot = borders.get("border_horizontal_bottom", borders.get("border_horizontal", "─"))
        b_v_left = borders.get("border_vertical_left", borders.get("border_vertical", "│"))
        b_v_right = borders.get("border_vertical_right", borders.get("border_vertical", "│"))
        b_tl = borders.get("border_top_left", "┌")
        b_tr = borders.get("border_top_right", "┐")
        b_bl = borders.get("border_bottom_left", "└")
        b_br = borders.get("border_bottom_right", "┘")
        new_box = (
            (b_tl, b_h_top, b_tr),
            (b_v_left, " ", b_v_right),
            (b_bl, b_h_bot, b_br),
        )
        if _last_applied_theme_borders == new_box:
            return
        _last_applied_theme_borders = new_box
        tb.BORDER_CHARS["thick"] = new_box
        tb.BORDER_CHARS["solid"] = new_box
        if hasattr(tb.get_box, "cache_clear"):
            tb.get_box.cache_clear()


def get_theme_marquee_config(
    theme_name: str | dict | None = "dracula",
    raw_theme_data: dict | None = None,
) -> dict[str, Any]:
    """Retrieve marquee configuration (char and gap) for the specified theme.

    Falls back to 5 bullets (char: '•', gap: 5) if not defined.
    """
    import bashmenu

    def _resolve_marquee_char(raw_val: Any) -> str:
        s = str(raw_val) if raw_val is not None else "•"
        if "{" in s:
            s = bashmenu.interpolate_placeholders(s, {})
            s = bashmenu.resolve_glyph(s, {})
        return s.replace("\ufe0f", "").replace("\ufe0e", "")

    if isinstance(theme_name, dict):
        if "marquee" in theme_name and isinstance(theme_name["marquee"], dict):
            m_def = theme_name["marquee"]
            return {
                "char": _resolve_marquee_char(m_def.get("char", "•")),
                "gap": int(m_def.get("gap", 5)),
            }
        if "theme_name" in theme_name and isinstance(theme_name["theme_name"], str):
            theme_name = theme_name["theme_name"]
        else:
            return {"char": "•", "gap": 5}

    if not raw_theme_data:
        raw_theme_data = load_themes_file()

    theme_def = raw_theme_data.get(theme_name, {}) if isinstance(theme_name, str) else {}
    if not theme_def:
        return {"char": "•", "gap": 5}

    m_def = theme_def.get("marquee", {}) if isinstance(theme_def, dict) else {}
    if isinstance(m_def, dict):
        return {
            "char": _resolve_marquee_char(m_def.get("char", "•")),
            "gap": int(m_def.get("gap", 5)),
        }
    return {"char": "•", "gap": 5}


def format_marquee_spacer(char: str = "•", gap: int = 5) -> str:
    """Format the spacer between repeated cycles of marquee scrolling text.

    Repeats the marquee character `gap` times (e.g. char '~' with gap 6 becomes '~~~~~~').
    If char is empty or None, defaults to bullet ('•') repeated `gap` times.
    """
    g = max(0, gap)
    fill_char = char if (char is not None and len(char) > 0) else "•"
    return fill_char * g


def get_marquee_slice(
    text: str,
    avail_w: int,
    offset: int,
    char: str = "•",
    gap: int = 5,
) -> str:
    """Calculate and return a scrolling slice of text for width avail_w at offset."""
    if not text or avail_w <= 0:
        return ""
    if cell_len(text) <= avail_w:
        return text

    spacer = format_marquee_spacer(char=char, gap=gap)
    loop_unit = text + spacer
    unit_cells = cell_len(loop_unit)
    if unit_cells == 0:
        return ""

    eff_offset = offset % unit_cells
    stream = loop_unit * ((eff_offset + avail_w) // len(loop_unit) + 3)

    curr_cells = 0
    start_idx = 0
    for i, c in enumerate(stream):
        if curr_cells >= eff_offset:
            start_idx = i
            break
        curr_cells += cell_len(c)

    collected: list[str] = []
    collected_cells = 0
    for c in stream[start_idx:]:
        c_w = cell_len(c)
        if collected_cells + c_w > avail_w:
            break
        collected.append(c)
        collected_cells += c_w

    res = "".join(collected)
    pad = avail_w - collected_cells
    if pad > 0:
        res += " " * pad
    return res


class MarqueeTracker:
    """State tracker for pause delays and ticking offsets of marquee text elements."""

    def __init__(self, pause_ticks: int = 4):
        self.pause_ticks = pause_ticks
        self.ticks_remaining = pause_ticks
        self.offset = 0
        self.active_id: Any = None

    def reset(self, new_id: Any = None) -> None:
        self.offset = 0
        self.ticks_remaining = self.pause_ticks
        self.active_id = new_id

    def tick(self) -> bool:
        """Advance marquee ticker. Returns True if offset advanced and redraw is needed."""
        if self.ticks_remaining > 0:
            self.ticks_remaining -= 1
            return False
        self.offset += 1
        return True


class MarqueeLabel(Label):
    """Textual Label widget that automatically marquees its text if it overflows available width."""

    def __init__(
        self,
        text: str = "",
        theme_styles: dict | None = None,
        pause_ticks: int = 4,
        tick_interval: float = 0.25,
        **kwargs,
    ):
        super().__init__(text, **kwargs)
        self.raw_text = text
        self.theme_styles = theme_styles or {}
        self.tracker = MarqueeTracker(pause_ticks=pause_ticks)
        self.tick_interval = tick_interval
        self._timer = None

    def on_mount(self) -> None:
        self._check_timer()

    def on_resize(self, event: events.Resize) -> None:
        self._check_timer()

    def set_text(self, text: str) -> None:
        if self.raw_text != text:
            self.raw_text = text
            self.tracker.reset()
            self._check_timer()
            self.refresh()

    def update(self, text: str) -> None:
        self.set_text(str(text))

    def _check_timer(self) -> None:
        w = max(0, self.size.width)
        if w > 0 and cell_len(self.raw_text) > w:
            if self._timer is None:
                self._timer = self.set_interval(self.tick_interval, self._on_tick)
        elif self._timer is not None:
            with contextlib.suppress(Exception):
                self._timer.stop()
            self._timer = None
            self.tracker.reset()
            self.refresh()

    def _on_tick(self) -> None:
        with contextlib.suppress(Exception):
            app = getattr(self, "app", None)
            scr = getattr(self, "screen", None)
            if app and (len(getattr(app, "screen_stack", [])) > 1 or (scr and getattr(app, "screen", None) is not scr)):
                return
        if self.tracker.tick():
            self.refresh()

    def render(self) -> Text:
        w = max(0, self.size.width)
        if w <= 0:
            return Text()
        mq_cfg = get_theme_marquee_config(self.theme_styles)
        if cell_len(self.raw_text) > w:
            slice_str = get_marquee_slice(
                self.raw_text,
                w,
                self.tracker.offset,
                char=mq_cfg["char"],
                gap=mq_cfg["gap"],
            )
        else:
            slice_str = self.raw_text
        return formatting_to_rich_text(slice_str, theme=self.theme_styles)


def init_theme_colors(theme_name: str = "dracula", raw_theme_data: dict | None = None) -> dict:
    """
    Initialize theme data and construct Rich Style mapping for elements.
    """
    borders = get_theme_window_borders(theme_name, raw_theme_data=raw_theme_data)
    apply_theme_to_textual_borders(theme_name, raw_theme_data=raw_theme_data)

    use_cache = raw_theme_data is None
    if not raw_theme_data:
        raw_theme_data = load_themes_file()

    cache_key = (theme_name, id(raw_theme_data))
    if use_cache and cache_key in _theme_styles_cache:
        cached = _theme_styles_cache[cache_key]
        cached["theme_name"] = theme_name
        cached["window_borders"] = borders
        cached["marquee"] = get_theme_marquee_config(theme_name, raw_theme_data=raw_theme_data)
        return cached

    theme_def = raw_theme_data.get(theme_name, {})
    if not theme_def and raw_theme_data:
        theme_def = next(iter(raw_theme_data.values()), {})

    palette = (
        theme_def.get(256)
        or theme_def.get("256")
        or theme_def.get(16)
        or theme_def.get("16")
        or theme_def.get(8)
        or theme_def.get("8")
        or (theme_def if any(k in theme_def for k in ("background", "title", "border", "text")) else {})
    )
    raw_ind = theme_def.get("indicator", ">")
    if isinstance(raw_ind, str) and "{" in raw_ind:
        import bashmenu
        indicator = bashmenu.resolve_glyph(bashmenu.interpolate_placeholders(raw_ind, {}), {})
        indicator = indicator.replace("\ufe0f", "").replace("\ufe0e", "")
    else:
        indicator = raw_ind

    bg_spec = palette.get("background")
    bg_color = None
    if isinstance(bg_spec, list) and len(bg_spec) >= 2:
        bg_color = parse_color_val(bg_spec[1]) or parse_color_val(bg_spec[0])
    elif bg_spec is not None:
        bg_color = parse_color_val(bg_spec)

    styles = {}
    styles["background"] = Style(bgcolor=bg_color) if bg_color else Style()

    for key, spec in palette.items():
        if key == "background":
            continue
        try:
            if isinstance(spec, dict):
                sub_styles = {}
                sub_bg_spec = spec.get("background")
                sub_bg = parse_color_val(sub_bg_spec) if sub_bg_spec is not None else bg_color
                sub_styles["background"] = Style(bgcolor=sub_bg) if sub_bg else styles["background"]
                for s_k, s_v in spec.items():
                    if s_k == "background":
                        continue
                    if isinstance(s_v, list) and len(s_v) >= 2:
                        s_fg = parse_color_val(s_v[0])
                        s_bg = parse_color_val(s_v[1]) if s_v[1] != -1 and str(s_v[1]).strip() not in ("-1", "None", "transparent") else None
                        sub_styles[s_k] = Style(color=s_fg, bgcolor=s_bg)
                    elif isinstance(s_v, (str, int)):
                        if s_k in ("tab_bar", "background") or s_k.endswith(("_background", "_tab_bar")):
                            sub_styles[s_k] = Style(bgcolor=parse_color_val(s_v))
                        else:
                            sub_styles[s_k] = Style(color=parse_color_val(s_v), bgcolor=None)
                styles[key] = sub_styles
            elif isinstance(spec, list) and len(spec) >= 2:
                fg = parse_color_val(spec[0])
                if spec[1] == -1 or str(spec[1]).strip() in ("-1", "inherit", "transparent", "None"):
                    bg = None
                else:
                    bg = parse_color_val(spec[1])
                styles[key] = Style(color=fg, bgcolor=bg)
            elif isinstance(spec, (str, int)):
                bg = None if key == "plugin" else bg_color
                styles[key] = Style(color=parse_color_val(spec), bgcolor=bg)
            else:
                styles[key] = Style(bgcolor=bg_color)
        except Exception:  # noqa: BLE001
            styles[key] = Style(bgcolor=bg_color)

    # Provide fallback styles if keys are missing
    default_text = styles.get("text", Style(color="white", bgcolor=bg_color))
    styles.setdefault("title", Style(color="magenta", bold=True, bgcolor=bg_color))
    styles.setdefault("border", Style(color="blue", bgcolor=bg_color))
    styles.setdefault("text", default_text)
    styles.setdefault("highlight", Style(color="white", bgcolor="magenta", bold=True))
    styles.setdefault("accent", Style(color="cyan", bgcolor=bg_color))
    styles.setdefault("footer", Style(color="blue", bgcolor=bg_color))
    styles.setdefault("shadow", Style(color="black", dim=True, bgcolor=bg_color))
    styles.setdefault("gutter", Style(color="blue", bgcolor=bg_color))
    styles.setdefault("selection", Style(color="white", bgcolor="blue"))
    styles.setdefault("shortcut_key", Style(color="magenta", bold=True, bgcolor=bg_color))
    styles.setdefault("divider", Style(color="blue", bgcolor=bg_color))
    styles.setdefault("button_primary", Style(color="white", bgcolor="blue"))
    styles.setdefault("button_error", Style(color="white", bgcolor="red"))
    styles.setdefault("button_cancel", Style(color="white", bgcolor="grey37"))
    styles.setdefault("button_success", Style(color="white", bgcolor="green"))
    styles.setdefault("help_text", Style(color="cyan", bgcolor=bg_color))
    styles.setdefault("plugin", Style(color="cyan"))
    styles.setdefault("window_close_button", Style(color="red", bold=True, bgcolor=bg_color))
    styles.setdefault("scrollbar", Style(color="cyan", bgcolor=bg_color or "grey19"))
    default_ws = (
        styles.get("whitespace")
        or styles.get("whitespace_color")
        or Style(color="white", dim=True, bgcolor=bg_color)
    )
    styles.setdefault("whitespace", default_ws)
    styles.setdefault("whitespace_color", default_ws)
    styles["indicator"] = indicator
    raw_bg = theme_def.get("background")
    raw_wp = theme_def.get("wallpaper")
    if isinstance(raw_bg, dict):
        styles["theme_background"] = raw_bg
        styles["wallpaper"] = raw_bg.get("image")
    elif isinstance(raw_bg, str):
        styles["theme_background"] = {"image": raw_bg}
        styles["wallpaper"] = raw_bg
    elif isinstance(raw_wp, str):
        styles["theme_background"] = {"image": raw_wp}
        styles["wallpaper"] = raw_wp
    else:
        styles["theme_background"] = None
        styles["wallpaper"] = None
    styles["theme_name"] = theme_name
    styles["window_borders"] = borders
    styles["marquee"] = get_theme_marquee_config(theme_name, raw_theme_data=raw_theme_data)

    # Populate sub-palette dictionaries with inheritance fallbacks
    ed_styles = styles.setdefault("editor", {})
    if not isinstance(ed_styles, dict):
        ed_styles = {}
        styles["editor"] = ed_styles
    ed_bg = ed_styles.get("background") or styles.get("background")
    ed_styles.setdefault("background", ed_bg)
    ed_styles.setdefault("header", styles.get("header") or styles.get("title"))
    ed_styles.setdefault("tab_bar", ed_bg)
    ed_styles.setdefault("tab_active", styles.get("selection") or styles.get("highlight"))
    ed_styles.setdefault("tab_inactive", styles.get("text"))
    ed_styles.setdefault("tab_close", styles.get("window_close_button") or styles.get("button_error"))
    ed_styles.setdefault("tab_add", styles.get("accent") or styles.get("button_primary"))
    ed_styles.setdefault("line_number", styles.get("gutter"))
    ed_styles.setdefault("gutter", styles.get("gutter"))
    ed_styles.setdefault("eof_tilde", styles.get("gutter"))
    ed_styles.setdefault("text", styles.get("text"))
    ed_styles.setdefault("selection", styles.get("selection"))
    ed_styles.setdefault("whitespace", styles.get("whitespace"))
    ed_styles.setdefault("status", ed_styles.get("header") or styles.get("footer"))
    ed_styles.setdefault("footer", styles.get("footer"))
    ed_styles.setdefault("border", styles.get("border"))

    me_styles = styles.setdefault("menu_editor", {})
    if not isinstance(me_styles, dict):
        me_styles = {}
        styles["menu_editor"] = me_styles
    me_bg = me_styles.get("background") or styles.get("background")
    me_styles.setdefault("background", me_bg)
    me_styles.setdefault("header", styles.get("header") or styles.get("title"))
    me_styles.setdefault("border", styles.get("border"))
    me_styles.setdefault("text", styles.get("text"))
    me_styles.setdefault("selection", styles.get("highlight") or styles.get("selection"))
    me_styles.setdefault("tree_guide", styles.get("gutter") or styles.get("border"))
    me_styles.setdefault("label", styles.get("accent") or styles.get("help_text"))
    me_styles.setdefault("input", styles.get("text"))
    me_styles.setdefault("button_save", styles.get("button_primary") or styles.get("button_success"))
    me_styles.setdefault("button_delete", styles.get("button_error"))
    me_styles.setdefault("footer", styles.get("footer"))

    mod_styles = styles.setdefault("modals", {})
    if not isinstance(mod_styles, dict):
        mod_styles = {}
        styles["modals"] = mod_styles
    mod_bg = mod_styles.get("background") or styles.get("background")
    mod_styles.setdefault("backdrop", styles.get("shadow"))
    mod_styles.setdefault("background", mod_bg)
    mod_styles.setdefault("border", styles.get("border") or styles.get("accent"))
    mod_styles.setdefault("title", styles.get("title") or styles.get("accent"))
    mod_styles.setdefault("text", styles.get("text"))
    mod_styles.setdefault("input", styles.get("text"))
    mod_styles.setdefault("button_confirm", styles.get("button_success") or styles.get("button_primary"))
    mod_styles.setdefault("button_cancel", styles.get("button_cancel"))
    mod_styles.setdefault("button_danger", styles.get("button_error"))
    mod_styles.setdefault("scrollbar", styles.get("scrollbar"))
    mod_styles.setdefault("footer", styles.get("footer"))

    if use_cache:
        _theme_styles_cache[cache_key] = styles
    return styles


def format_close_button_label(theme_dict: dict | None = None) -> Text:
    """
    Format close button label as [X] where brackets match the window border style
    and 'X' uses the theme's window_close_button style.
    """
    if not isinstance(theme_dict, dict):
        theme_dict = {}
    border_style = theme_dict.get("border") or theme_dict.get("accent") or Style(color="blue")
    close_style = theme_dict.get("window_close_button") or Style(color="red", bold=True)

    label = Text()
    label.append("[", style=border_style)
    label.append("X", style=close_style)
    label.append("]", style=border_style)
    return label


def parse_css_color(val) -> str | None:
    """Parse color spec (int 0..255, COLOR_*, color(N), or string) into a valid CSS color string or None."""
    if val is None or val == -1 or val == "-1":
        return None
    if isinstance(val, int):
        if 0 <= val < 256:
            return EIGHT_BIT_PALETTE[val].hex
        return None
    if isinstance(val, str):
        val_clean = val.strip()
        if val_clean.startswith("color(") and val_clean.endswith(")"):
            inner = val_clean[6:-1].strip()
            if inner.isdigit():
                idx = int(inner)
                if 0 <= idx < 256:
                    return EIGHT_BIT_PALETTE[idx].hex
        if val_clean.isdigit():
            idx = int(val_clean)
            if 0 <= idx < 256:
                return EIGHT_BIT_PALETTE[idx].hex
            return None
        if val_clean in COLOR_MAP:
            return COLOR_MAP[val_clean]
        return val_clean
    return None


def rgb_to_ansi256(r: int, g: int, b: int) -> int:
    """Find the nearest ANSI 256 color code for given RGB values."""
    from rich.color_triplet import ColorTriplet

    return EIGHT_BIT_PALETTE.match(
        ColorTriplet(max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))
    )


def ansi256_to_hex(code: int) -> str:
    """Return hex string '#rrggbb' for an ANSI 256 color code."""
    if isinstance(code, int) and 0 <= code < 256:
        trip = EIGHT_BIT_PALETTE[code]
        return f"#{trip.red:02x}{trip.green:02x}{trip.blue:02x}"
    return ""


def resolve_theme_dict(theme_val=None, app=None) -> dict:
    """Resolve theme value (dict, string name, or app attribute) into a complete theme dictionary."""
    if isinstance(theme_val, dict) and theme_val:
        return theme_val
    if isinstance(theme_val, str):
        return init_theme_colors(theme_val)

    if app:
        app_theme = getattr(app, "theme_styles", None)
        if isinstance(app_theme, dict) and app_theme:
            return app_theme
        if isinstance(app_theme, str):
            return init_theme_colors(app_theme)

        app_theme_str = getattr(app, "theme", None)
        if isinstance(app_theme_str, dict) and app_theme_str:
            return app_theme_str
        if isinstance(app_theme_str, str):
            return init_theme_colors(app_theme_str)

        with contextlib.suppress(Exception):
            screen = getattr(app, "screen", None)
            if screen:
                scr_theme = getattr(screen, "theme_styles", None) or getattr(screen, "theme", None)
                if isinstance(scr_theme, dict) and scr_theme:
                    return scr_theme
                if isinstance(scr_theme, str):
                    return init_theme_colors(scr_theme)

                mv = getattr(screen, "menu_view", None)
                if mv:
                    mv_theme = getattr(mv, "theme_styles", None) or getattr(mv, "theme", None)
                    if isinstance(mv_theme, dict) and mv_theme:
                        return mv_theme
                    if isinstance(mv_theme, str):
                        return init_theme_colors(mv_theme)

    try:
        import bashmenu
        cfg_res = bashmenu.load_config() if hasattr(bashmenu, "load_config") else {}
        config = cfg_res[0] if isinstance(cfg_res, tuple) else cfg_res
        if isinstance(config, dict) and "theme" in config:
            active_name = config.get("theme", "dracula")
            return init_theme_colors(active_name)
    except Exception:  # noqa: BLE001, S110
        pass

    return init_theme_colors("dracula")


def get_theme_bg_rgb(theme_styles: dict | None) -> tuple[int, int, int]:
    """Extract RGB triplet (r, g, b) for theme background color."""
    if not isinstance(theme_styles, dict):
        return (15, 20, 32)
    bg_style = theme_styles.get("background")
    if bg_style and bg_style.bgcolor:
        bg_col = bg_style.bgcolor
        if hasattr(bg_col, "triplet") and bg_col.triplet:
            return (bg_col.triplet.red, bg_col.triplet.green, bg_col.triplet.blue)
        if hasattr(bg_col, "number") and bg_col.number is not None and 0 <= bg_col.number < 256:
            trip = EIGHT_BIT_PALETTE[bg_col.number]
            return (trip.red, trip.green, trip.blue)
    return (15, 20, 32)


_wallpaper_image_cache: dict[tuple[str, float], Any] = {}
_wallpaper_grid_cache: dict[tuple, list[list[tuple[Style, str]]]] = {}


class WallpaperCompositor:
    """Manages loading, downsampling, caching, and half-block compositing of background wallpaper."""

    def __init__(
        self,
        image_path: str,
        opacity: float = 0.35,
        scaling: str = "cover",
        base_dir: str | None = None,
        clustering: int = 0,
        quantization: int = 1,
    ) -> None:
        self.image_path = str(image_path).strip() if image_path else ""
        self.opacity = max(0.0, min(1.0, float(opacity)))
        self.scaling = scaling or "cover"
        self.base_dir = base_dir or os.getcwd()
        self.clustering = max(0, int(clustering))
        self.quantization = max(1, int(quantization))
        self._raw_image = None
        self._cached_key = None
        self._cached_grid = None
        self._load_image()

    def _load_image(self) -> None:
        if not PIL_AVAILABLE or not self.image_path:
            self._raw_image = None
            return
        try:
            expanded = os.path.expanduser(self.image_path)
            if not os.path.isabs(expanded):
                cand1 = os.path.join(self.base_dir, expanded)
                cand2 = os.path.join(os.getcwd(), expanded)
                if os.path.exists(cand1):
                    expanded = cand1
                elif os.path.exists(cand2):
                    expanded = cand2
            if os.path.exists(expanded) and os.path.isfile(expanded):
                can_path = os.path.realpath(expanded)
                mtime = os.path.getmtime(can_path)
                cached = _wallpaper_image_cache.get((can_path, mtime))
                if cached is not None:
                    self._raw_image = cached
                    return
                img = Image.open(can_path).convert("RGB")
                # Downscale excessively large images (e.g. 4K/8K) to 1920x1080 bounding box
                # using BILINEAR for fast loading while retaining photographic fidelity.
                max_w, max_h = 1920, 1080
                if img.width > max_w or img.height > max_h:
                    img.thumbnail((max_w, max_h), Image.Resampling.BILINEAR)
                if len(_wallpaper_image_cache) > 16:
                    _wallpaper_image_cache.clear()
                _wallpaper_image_cache[(can_path, mtime)] = img
                self._raw_image = img
            else:
                self._raw_image = None
        except Exception:  # noqa: BLE001
            self._raw_image = None

    def get_grid(
        self, width: int, height: int, theme_bg_rgb: tuple[int, int, int] = (15, 20, 32)
    ) -> list[list[tuple[Style, str]]] | None:
        """Return 2D grid of (half_block_style, cell_bg_color_str) for given dimensions."""
        if not self._raw_image or width <= 0 or height <= 0:
            return None

        cache_key = (
            self.image_path,
            width,
            height,
            theme_bg_rgb,
            round(self.opacity, 3),
            self.scaling,
            self.clustering,
            self.quantization,
        )
        if self._cached_key == cache_key and self._cached_grid is not None:
            return self._cached_grid
        if cache_key in _wallpaper_grid_cache:
            self._cached_key = cache_key
            self._cached_grid = _wallpaper_grid_cache[cache_key]
            return self._cached_grid

        pixel_w = width
        pixel_h = height * 2

        img = self._raw_image
        if self.scaling == "cover":
            img_ratio = img.width / max(1, img.height)
            target_ratio = pixel_w / max(1, pixel_h)
            if img_ratio > target_ratio:
                new_w = max(1, int(img.height * target_ratio))
                left = (img.width - new_w) // 2
                cropped = img.crop((left, 0, left + new_w, img.height))
            else:
                new_h = max(1, int(img.width / target_ratio))
                top = (img.height - new_h) // 2
                cropped = img.crop((0, top, img.width, top + new_h))
            resized = cropped.resize((pixel_w, pixel_h), Image.Resampling.BOX)
        elif self.scaling == "fit":
            img_ratio = img.width / max(1, img.height)
            target_ratio = pixel_w / max(1, pixel_h)
            if img_ratio > target_ratio:
                fitted_w = pixel_w
                fitted_h = max(1, int(pixel_w / img_ratio))
            else:
                fitted_h = pixel_h
                fitted_w = max(1, int(pixel_h * img_ratio))
            scaled = img.resize((fitted_w, fitted_h), Image.Resampling.BOX)
            canvas = Image.new("RGB", (pixel_w, pixel_h), color=theme_bg_rgb)
            canvas.paste(scaled, ((pixel_w - fitted_w) // 2, (pixel_h - fitted_h) // 2))
            resized = canvas
        elif self.scaling == "center":
            canvas = Image.new("RGB", (pixel_w, pixel_h), color=theme_bg_rgb)
            crop_l = max(0, (img.width - pixel_w) // 2)
            crop_t = max(0, (img.height - pixel_h) // 2)
            crop_r = crop_l + min(img.width, pixel_w)
            crop_b = crop_t + min(img.height, pixel_h)
            cropped_c = img.crop((crop_l, crop_t, crop_r, crop_b))
            paste_x = max(0, (pixel_w - cropped_c.width) // 2)
            paste_y = max(0, (pixel_h - cropped_c.height) // 2)
            canvas.paste(cropped_c, (paste_x, paste_y))
            resized = canvas
        elif self.scaling == "tile":
            canvas = Image.new("RGB", (pixel_w, pixel_h), color=theme_bg_rgb)
            w_step = max(1, img.width)
            h_step = max(1, img.height)
            for x in range(0, pixel_w, w_step):
                for y in range(0, pixel_h, h_step):
                    canvas.paste(img, (x, y))
            resized = canvas
        else:  # "stretch" (default / fallback)
            resized = img.resize((pixel_w, pixel_h), Image.Resampling.BOX)

        pixels = resized.load()
        grid = []
        op = self.opacity
        inv_op = 1.0 - op
        t_r, t_g, t_b = theme_bg_rgb
        style_cache: dict[tuple[int, int, int, int, int, int], tuple[Style, str]] = {}
        quant = self.quantization

        delta_threshold = self.clustering

        for r in range(height):
            row_cache = []
            anchor_cell = None
            anchor_k = None
            cluster_run = 0
            for c in range(width):
                orig_r1, orig_g1, orig_b1 = pixels[c, r * 2][:3]
                orig_r2, orig_g2, orig_b2 = pixels[c, r * 2 + 1][:3]

                blended_r1 = int(orig_r1 * op + t_r * inv_op)
                blended_g1 = int(orig_g1 * op + t_g * inv_op)
                blended_b1 = int(orig_b1 * op + t_b * inv_op)
                blended_r2 = int(orig_r2 * op + t_r * inv_op)
                blended_g2 = int(orig_g2 * op + t_g * inv_op)
                blended_b2 = int(orig_b2 * op + t_b * inv_op)

                if quant > 1:
                    r1 = (blended_r1 // quant) * quant
                    g1 = (blended_g1 // quant) * quant
                    b1 = (blended_b1 // quant) * quant
                    r2 = (blended_r2 // quant) * quant
                    g2 = (blended_g2 // quant) * quant
                    b2 = (blended_b2 // quant) * quant
                else:
                    r1, g1, b1 = blended_r1, blended_g1, blended_b1
                    r2, g2, b2 = blended_r2, blended_g2, blended_b2

                k = (r1, g1, b1, r2, g2, b2)

                # If clustering is enabled (> 0), merge near-identical adjacent cells,
                # but cap the run length (max 4 cells) to prevent horizontal streaking.
                if delta_threshold > 0 and anchor_k is not None and cluster_run < 4:
                    delta = (
                        abs(k[0] - anchor_k[0])
                        + abs(k[1] - anchor_k[1])
                        + abs(k[2] - anchor_k[2])
                        + abs(k[3] - anchor_k[3])
                        + abs(k[4] - anchor_k[4])
                        + abs(k[5] - anchor_k[5])
                    )
                    if delta <= delta_threshold:
                        cluster_run += 1
                        row_cache.append(anchor_cell)
                        continue

                cluster_run = 0
                cached = style_cache.get(k)
                if cached is None:
                    avg_r = (r1 + r2) // 2
                    avg_g = (g1 + g2) // 2
                    avg_b = (b1 + b2) // 2
                    half_style = Style(color=f"rgb({r1},{g1},{b1})", bgcolor=f"rgb({r2},{g2},{b2})")
                    bg_color_str = f"rgb({avg_r},{avg_g},{avg_b})"
                    cached = (half_style, bg_color_str)
                    style_cache[k] = cached

                anchor_cell = cached
                anchor_k = k
                row_cache.append(cached)
            grid.append(row_cache)

        if len(_wallpaper_grid_cache) > 64:
            _wallpaper_grid_cache.clear()
        _wallpaper_grid_cache[cache_key] = grid
        self._cached_key = cache_key
        self._cached_grid = grid
        return grid


_style_combine_cache: dict[tuple[int, str], Style] = {}


def get_combined_style(style: Style | None, bg_color_str: str) -> Style:
    """Get or create cached Style combining foreground style with wallpaper cell background color."""
    key = (id(style), bg_color_str)
    cached = _style_combine_cache.get(key)
    if cached is not None:
        return cached
    new_style = Style(
        color=style.color if style and style.color else "white",
        bgcolor=bg_color_str,
        bold=style.bold if style else False,
        italic=style.italic if style else False,
        underline=style.underline if style else False,
        reverse=style.reverse if style else False,
    )
    _style_combine_cache[key] = new_style
    return new_style


_row_composite_cache: dict[tuple, Text] = {}
_cached_grid_id: int | None = None
_compositor_console = None


def get_compositor_console(width: int = 250, height: int = 100):
    """Return a shared Rich Console for compositing text lines to avoid re-creation overhead."""
    global _compositor_console
    if _compositor_console is None or _compositor_console.width < width or _compositor_console.height < height:
        from rich.console import Console

        _compositor_console = Console(
            width=max(250, width),
            height=max(100, height),
            color_system="truecolor",
            legacy_windows=False,
        )
    return _compositor_console


def composite_single_row(
    line: Text,
    row_cache: list[tuple[Style, str]] | None,
    console=None,
    theme_default_bg=None,
) -> Text:
    """Composite half-block background and text cell background colors onto a single rendered line."""
    if not row_cache:
        return line

    if console is None:
        console = get_compositor_console(len(row_cache), 1)

    row_out = Text()
    col_idx = 0
    char_idx = 0

    plain = line.plain
    is_padding = set()
    for m in re.finditer(r" {2,}", plain):
        is_padding.update(range(m.start(), m.end()))
    if plain.startswith(" "):
        is_padding.add(0)
    if plain.endswith(" "):
        is_padding.add(len(plain) - 1)

    curr_chars: list[str] = []
    curr_style: Style | None = None
    base_line_style = console.get_style(line.style) if line.style else None

    for seg in line.render(console):
        text = seg.text
        style = seg.style or base_line_style
        is_highlight_bg = False
        if style is not None and style.bgcolor is not None:
            if theme_default_bg is None:
                is_highlight_bg = True
            elif style.bgcolor == theme_default_bg:
                is_highlight_bg = False
            elif isinstance(theme_default_bg, tuple):
                if hasattr(style.bgcolor, "triplet") and style.bgcolor.triplet == theme_default_bg:
                    is_highlight_bg = False
                elif hasattr(style.bgcolor, "number") and style.bgcolor.number is not None and 0 <= style.bgcolor.number < 256:
                    trip = EIGHT_BIT_PALETTE[style.bgcolor.number]
                    is_highlight_bg = ((trip.red, trip.green, trip.blue) != theme_default_bg)
                else:
                    is_highlight_bg = True
            else:
                is_highlight_bg = True

        for ch in text:
            w_ch = 1 if ord(ch) < 128 else cell_len(ch)
            if col_idx < len(row_cache):
                half_style, bg_color_str = row_cache[col_idx]
                if ch == " " and char_idx in is_padding and not is_highlight_bg:
                    target_ch = "▀"
                    target_style = half_style
                elif is_highlight_bg:
                    target_ch = ch
                    target_style = style
                else:
                    target_ch = ch
                    target_style = get_combined_style(style, bg_color_str)
            else:
                target_ch = ch
                target_style = style

            col_idx += max(1, w_ch) if w_ch > 0 else 0
            char_idx += 1

            if target_style is curr_style:
                curr_chars.append(target_ch)
            else:
                if curr_chars:
                    row_out.append("".join(curr_chars), style=curr_style)
                curr_chars = [target_ch]
                curr_style = target_style

    if curr_chars:
        row_out.append("".join(curr_chars), style=curr_style)

    return row_out


def composite_menu_text(
    rendered_text: Text,
    grid: list[list[tuple[Style, str]]] | None,
    width: int,
    height: int,
    console=None,
    theme_default_bg=None,
) -> Text:
    """Composite half-block background and text cell background colors onto rendered menu lines."""
    global _cached_grid_id
    if not grid:
        return rendered_text

    grid_id = id(grid)
    if _cached_grid_id != grid_id:
        _row_composite_cache.clear()
        _cached_grid_id = grid_id

    if console is None:
        console = get_compositor_console(width, height)

    lines = rendered_text.split("\n")
    out = Text()
    num_lines = len(lines)

    for row_idx, line in enumerate(lines):
        row_cache = grid[row_idx] if row_idx < len(grid) else None
        if not row_cache:
            out.append_text(line)
            if row_idx < num_lines - 1:
                out.append("\n")
            continue

        spans_key = tuple((s.start, s.end, s.style) for s in line._spans)
        row_key = (row_idx, line.plain, spans_key, theme_default_bg)
        cached_row = _row_composite_cache.get(row_key)
        if cached_row is not None:
            out.append_text(cached_row)
            if row_idx < num_lines - 1:
                out.append("\n")
            continue

        row_out = composite_single_row(
            line, row_cache, console=console, theme_default_bg=theme_default_bg
        )

        if len(_row_composite_cache) < 512:
            _row_composite_cache[row_key] = row_out

        out.append_text(row_out)
        if row_idx < num_lines - 1:
            out.append("\n")

    return out


def text_to_strip(text: Text, console=None) -> Strip:
    """Convert a Rich Text object to a Textual Strip without trailing newlines."""
    c = console or get_compositor_console()
    return Strip([s for s in c.render(text) if s.text != "\n"])


class PrebakedWallpaperCanvas:
    """In-memory pre-baked canvas that pre-renders and caches wallpaper rows,
    static window borders/margins, and menu option rows.

    Eliminates runtime compositing, regex parsing, string formatting, and Rich->Strip
    conversions during keyboard navigation, achieving sub-millisecond frame assembly.
    """

    def __init__(
        self,
        compositor: WallpaperCompositor | None = None,
    ) -> None:
        self.compositor = compositor
        self.grid: list[list[tuple[Style, str]]] | None = None
        self.theme_default_bg = None
        self.console = None

        self._canvas_key: tuple | None = None
        self._static_lines: dict[int, Text] = {}
        self._static_strips: dict[int, Strip] = {}
        self._raw_option_lines: dict[tuple[int, bool], Text] = {}
        self._option_line_cache: dict[tuple[int, int, bool], Text] = {}
        self._option_strip_cache: dict[tuple[int, int, bool], Strip] = {}
        self._cached_gutter_key: tuple | None = None
        self._cached_gutter_lines: list[Text] = []
        self._cached_gutter_strips: list[Strip] = []

    def is_valid(self, canvas_key: tuple) -> bool:
        """Check if the cached canvas matches the current state key."""
        return self._canvas_key == canvas_key and self._canvas_key is not None

    def invalidate(self) -> None:
        """Clear all pre-baked lines, strips, and cached states."""
        self._canvas_key = None
        self._static_lines.clear()
        self._static_strips.clear()
        self._raw_option_lines.clear()
        self._option_line_cache.clear()
        self._option_strip_cache.clear()
        self._cached_gutter_key = None
        self._cached_gutter_lines.clear()
        self._cached_gutter_strips.clear()

    def set_grid(
        self,
        grid: list[list[tuple[Style, str]]] | None,
        theme_default_bg=None,
        console=None,
    ) -> None:
        """Set the active wallpaper grid and console for compositing."""
        self.grid = grid
        self.theme_default_bg = theme_default_bg
        self.console = console or get_compositor_console()

    def set_static_line(self, y: int, raw_line: Text) -> None:
        """Pre-bake and store a static frame line and Strip at screen row y."""
        clean_line = raw_line.copy()
        if clean_line.plain.endswith("\n"):
            clean_line.rstrip()
        row_cache = self.grid[y] if (self.grid and y < len(self.grid)) else None
        if row_cache:
            composited = composite_single_row(
                clean_line,
                row_cache,
                console=self.console,
                theme_default_bg=self.theme_default_bg,
            )
        else:
            composited = clean_line
        self._static_lines[y] = composited
        self._static_strips[y] = text_to_strip(composited, self.console)

    def set_raw_option_line(self, opt_idx: int, is_selected: bool, raw_line: Text) -> None:
        """Store the uncomposited formatted line for an option."""
        clean_line = raw_line.copy()
        if clean_line.plain.endswith("\n"):
            clean_line.rstrip()
        self._raw_option_lines[(opt_idx, is_selected)] = clean_line

    def prebake_option(self, y: int, opt_idx: int, is_selected: bool) -> Text:
        """Composite and cache an option row and Strip at screen row y."""
        cached = self._option_line_cache.get((y, opt_idx, is_selected))
        if cached is not None:
            return cached

        raw_line = self._raw_option_lines.get((opt_idx, is_selected))
        if raw_line is None:
            return Text()

        row_cache = self.grid[y] if (self.grid and y < len(self.grid)) else None
        if row_cache:
            composited = composite_single_row(
                raw_line,
                row_cache,
                console=self.console,
                theme_default_bg=self.theme_default_bg,
            )
        else:
            composited = raw_line

        self._option_line_cache[(y, opt_idx, is_selected)] = composited
        self._option_strip_cache[(y, opt_idx, is_selected)] = text_to_strip(composited, self.console)
        return composited

    def get_option_line(self, y: int, opt_idx: int, is_selected: bool) -> Text:
        """Retrieve pre-baked option line from cache, or pre-bake if not cached."""
        cached = self._option_line_cache.get((y, opt_idx, is_selected))
        if cached is not None:
            return cached
        return self.prebake_option(y, opt_idx, is_selected)

    def get_option_strip(self, y: int, opt_idx: int, is_selected: bool) -> Strip:
        """Retrieve pre-baked option Strip from cache, or pre-bake if not cached."""
        cached = self._option_strip_cache.get((y, opt_idx, is_selected))
        if cached is not None:
            return cached
        self.prebake_option(y, opt_idx, is_selected)
        return self._option_strip_cache.get((y, opt_idx, is_selected)) or Strip.blank(0)

    def get_static_strip(self, y: int) -> Strip:
        """Retrieve pre-baked static Strip from cache."""
        cached = self._static_strips.get(y)
        if cached is not None:
            return cached
        line = self._static_lines.get(y)
        if line is not None:
            st = text_to_strip(line, self.console)
            self._static_strips[y] = st
            return st
        return Strip.blank(0)

    def get_gutter_lines(
        self,
        gutter_key: tuple,
        gutter_y_start: int,
        raw_gutter_lines: list[Text],
    ) -> list[Text]:
        """Retrieve or composite gutter lines and Strips (help text and status badges)."""
        if self._cached_gutter_key == gutter_key and self._cached_gutter_lines:
            return self._cached_gutter_lines

        composited_gutters: list[Text] = []
        for r, line in enumerate(raw_gutter_lines):
            y = gutter_y_start + r
            clean_line = line.copy()
            if clean_line.plain.endswith("\n"):
                clean_line.rstrip()
            row_cache = self.grid[y] if (self.grid and y < len(self.grid)) else None
            if row_cache:
                c_line = composite_single_row(
                    clean_line,
                    row_cache,
                    console=self.console,
                    theme_default_bg=self.theme_default_bg,
                )
            else:
                c_line = clean_line
            composited_gutters.append(c_line)

        self._cached_gutter_key = gutter_key
        self._cached_gutter_lines = composited_gutters
        self._cached_gutter_strips = [text_to_strip(line, self.console) for line in composited_gutters]
        return composited_gutters

    def get_gutter_strip(self, g_idx: int) -> Strip:
        """Retrieve pre-baked gutter Strip by index."""
        if 0 <= g_idx < len(self._cached_gutter_strips):
            return self._cached_gutter_strips[g_idx]
        if 0 <= g_idx < len(self._cached_gutter_lines):
            return text_to_strip(self._cached_gutter_lines[g_idx], self.console)
        return Strip.blank(0)

    def get_line_strip(
        self,
        y: int,
        scroll_start: int,
        curr_row: int,
        visible_option_rows: int,
        num_options: int,
        gutter_y_start: int,
        num_gutter_lines: int,
        active_option_strip: Strip | None = None,
    ) -> Strip:
        """Retrieve pre-baked Strip for screen row y with zero concatenation or compositing overhead."""
        if y < 3:
            return self.get_static_strip(y)
        if 3 <= y < 3 + visible_option_rows:
            opt_offset = y - 3
            opt_idx = scroll_start + opt_offset
            if opt_idx < num_options:
                if opt_idx == curr_row and active_option_strip is not None:
                    return active_option_strip
                return self.get_option_strip(y, opt_idx, opt_idx == curr_row)
            return self.get_static_strip(y)
        if gutter_y_start <= y < gutter_y_start + num_gutter_lines:
            g_idx = y - gutter_y_start
            return self.get_gutter_strip(g_idx)
        return self.get_static_strip(y)

    def composite_dynamic_line(self, y: int, raw_line: Text) -> Text:
        """Composite a dynamic/marqueeing raw option line at screen row y without caching."""
        clean_line = raw_line.copy()
        if clean_line.plain.endswith("\n"):
            clean_line.rstrip()
        row_cache = self.grid[y] if (self.grid and y < len(self.grid)) else None
        if row_cache:
            return composite_single_row(
                clean_line,
                row_cache,
                console=self.console,
                theme_default_bg=self.theme_default_bg,
            )
        return clean_line

    def assemble_frame(
        self,
        height: int,
        scroll_start: int,
        curr_row: int,
        visible_option_rows: int,
        num_options: int,
        gutter_y_start: int,
        gutter_lines: list[Text],
        active_option_line: Text | None = None,
    ) -> Text:
        """Assemble full screen Text buffer from pre-baked lines."""
        out = Text()
        last_y = height - 1

        for y in range(height):
            if y < 3:
                line = self._static_lines.get(y)
            elif 3 <= y < 3 + visible_option_rows:
                opt_offset = y - 3
                opt_idx = scroll_start + opt_offset
                if opt_idx < num_options:
                    if opt_idx == curr_row and active_option_line is not None:
                        line = active_option_line
                    else:
                        line = self.get_option_line(y, opt_idx, opt_idx == curr_row)
                else:
                    line = self._static_lines.get(y)
            elif gutter_y_start <= y < gutter_y_start + len(gutter_lines):
                g_idx = y - gutter_y_start
                line = gutter_lines[g_idx]
            else:
                line = self._static_lines.get(y)

            if line is not None:
                out.append_text(line)
            if y < last_y:
                out.append("\n")

        return out


def apply_modal_theme(screen: ModalScreen, theme=None) -> None:
    """Apply theme border, background, title, message, prompt, and footer colors to a modal screen."""
    app = None
    with contextlib.suppress(Exception):
        app = getattr(screen, "app", None)
    theme_dict = resolve_theme_dict(theme, app)
    if not theme_dict:
        return
    t_name = theme_dict.get("theme_name") if isinstance(theme_dict, dict) else theme
    if t_name:
        apply_theme_to_textual_borders(t_name)
    with contextlib.suppress(Exception):
        shadow_style = theme_dict.get("shadow")
        if shadow_style and shadow_style.bgcolor and shadow_style.bgcolor.name:
            css_shadow = parse_css_color(shadow_style.bgcolor.name)
            if css_shadow and hasattr(screen, "styles"):
                screen.styles.background = f"{css_shadow} 60%"

    with contextlib.suppress(Exception):
        borders = theme_dict.get("window_borders") or get_theme_window_borders(
            theme_dict.get("theme_name", "dracula")
        )
        shadow_char = borders.get("shadow_char", "░")
        shadow_style = theme_dict.get("shadow")
        css_shadow_fg = None
        css_shadow_bg = None
        if shadow_style:
            if shadow_style.color and shadow_style.color.name:
                css_shadow_fg = parse_css_color(shadow_style.color.name)
            if shadow_style.bgcolor and shadow_style.bgcolor.name:
                css_shadow_bg = parse_css_color(shadow_style.bgcolor.name)

        for s_id in ["#shadow_right", "#shadow_bottom"]:
            for sw in screen.query(s_id):
                if hasattr(sw, "update_char"):
                    sw.update_char(shadow_char)
                if css_shadow_fg:
                    sw.styles.color = css_shadow_fg
                if css_shadow_bg:
                    sw.styles.background = css_shadow_bg
        mf = screen.query_one("#modal_frame")
        if hasattr(mf, "sync_shadows"):
            mf.sync_shadows()
    mod_styles = theme_dict.get("modals", {}) if isinstance(theme_dict.get("modals"), dict) else {}

    with contextlib.suppress(Exception):
        dialog = screen.query_one("#dialog")
        border_style = mod_styles.get("border") or theme_dict.get("border") or theme_dict.get("accent")
        if border_style and border_style.color and border_style.color.name:
            css_border = parse_css_color(border_style.color.name)
            if css_border:
                dialog.styles.border = ("thick", css_border)
        bg_style = mod_styles.get("background") or theme_dict.get("background")
        if bg_style and bg_style.bgcolor and bg_style.bgcolor.name:
            css_bg = parse_css_color(bg_style.bgcolor.name)
            if css_bg:
                dialog.styles.background = css_bg
        text_style = mod_styles.get("text") or theme_dict.get("text")
        if text_style and text_style.color and text_style.color.name:
            css_text = parse_css_color(text_style.color.name)
            if css_text:
                dialog.styles.color = css_text

    with contextlib.suppress(Exception):
        title = screen.query_one("#title", Label)
        title_style = mod_styles.get("title") or theme_dict.get("title") or theme_dict.get("accent")
        if title_style and title_style.color and title_style.color.name:
            css_title = parse_css_color(title_style.color.name)
            if css_title:
                title.styles.color = css_title
                title.styles.auto_color = False
        borders = theme_dict.get("window_borders") or get_theme_window_borders(theme_dict.get("theme_name", "dracula"))
        l_cap = borders.get("title_left_cap", "[").strip() or "["
        r_cap = borders.get("title_right_cap", "]").strip() or "]"
        raw_text = str(title.renderable) if hasattr(title, "renderable") else str(getattr(screen, "modal_title", ""))
        if raw_text and not raw_text.startswith(l_cap):
            title.update(f"{l_cap} {raw_text.strip()} {r_cap}")

    with contextlib.suppress(Exception):
        msg_style = mod_styles.get("text") or theme_dict.get("text")
        if msg_style and msg_style.color and msg_style.color.name:
            css_msg = parse_css_color(msg_style.color.name)
            if css_msg:
                for target in screen.query("#message, .markdown_block, Checkbox, .markdown_checkbox"):
                    target.styles.color = css_msg
                    target.styles.auto_color = False

    with contextlib.suppress(Exception):
        prompt = screen.query_one("#prompt", Static)
        prompt_style = mod_styles.get("text") or theme_dict.get("text") or theme_dict.get("accent")
        if prompt_style and prompt_style.color and prompt_style.color.name:
            css_prompt = parse_css_color(prompt_style.color.name)
            if css_prompt:
                prompt.styles.color = css_prompt
                prompt.styles.auto_color = False

    with contextlib.suppress(Exception):
        footer_style = mod_styles.get("footer") or theme_dict.get("footer") or theme_dict.get("help_text") or theme_dict.get("text")
        if footer_style and footer_style.color and footer_style.color.name:
            css_footer = parse_css_color(footer_style.color.name)
            if css_footer:
                for ft in screen.query("#footer"):
                    ft.styles.color = css_footer
                    ft.styles.auto_color = False
                for fi in screen.query(".footer_item"):
                    fi.styles.color = css_footer
                    fi.styles.auto_color = False

        sep_style = mod_styles.get("border") or theme_dict.get("border") or theme_dict.get("divider")
        if sep_style and sep_style.color and sep_style.color.name:
            css_sep = parse_css_color(sep_style.color.name)
            if css_sep:
                for fs in screen.query(".footer_sep"):
                    fs.styles.color = css_sep
                    fs.styles.auto_color = False

    with contextlib.suppress(Exception):
        inp_style = mod_styles.get("input") or mod_styles.get("text") or theme_dict.get("text")
        if inp_style:
            css_inp_fg = parse_css_color(inp_style.color.name) if inp_style.color and inp_style.color.name else None
            css_inp_bg = parse_css_color(inp_style.bgcolor.name) if inp_style.bgcolor and inp_style.bgcolor.name else None
            for inp in screen.query(Input):
                if css_inp_fg:
                    inp.styles.color = css_inp_fg
                if css_inp_bg:
                    inp.styles.background = css_inp_bg

    with contextlib.suppress(Exception):
        path_lbl = screen.query_one("#path_label", Label)
        path_style = theme_dict.get("accent") or theme_dict.get("text")
        if path_style and path_style.color and path_style.color.name:
            css_path = parse_css_color(path_style.color.name)
            if css_path:
                path_lbl.styles.color = css_path
                path_lbl.styles.auto_color = False

    for opt_id in ["#options_list", "#option_list"]:
        with contextlib.suppress(Exception):
            opt_list = screen.query_one(opt_id, OptionList)
            border_style = mod_styles.get("border") or theme_dict.get("border") or theme_dict.get("accent")
            if border_style and border_style.color and border_style.color.name:
                css_b = parse_css_color(border_style.color.name)
                if css_b:
                    opt_list.styles.border = ("solid", css_b)

    with contextlib.suppress(Exception):
        for fl in screen.query(".field_label"):
            fl_style = theme_dict.get("accent") or theme_dict.get("text")
            if fl_style and fl_style.color and fl_style.color.name:
                css_fl = parse_css_color(fl_style.color.name)
                if css_fl:
                    fl.styles.color = css_fl
                    fl.styles.auto_color = False

    with contextlib.suppress(Exception):
        btn_close = screen.query_one(".btn_close_x", Label)
        btn_close.update(format_close_button_label(theme_dict))

    with contextlib.suppress(Exception):
        sb_style = mod_styles.get("scrollbar") or theme_dict.get("scrollbar") or theme_dict.get("border")
        if sb_style:
            css_sb_fg = parse_css_color(sb_style.color.name) if sb_style.color and sb_style.color.name else None
            css_sb_bg = parse_css_color(sb_style.bgcolor.name) if sb_style.bgcolor and sb_style.bgcolor.name else None
            for w in [screen, *list(screen.walk_children())]:
                if css_sb_fg:
                    w.styles.scrollbar_color = css_sb_fg
                    w.styles.scrollbar_color_hover = css_sb_fg
                if css_sb_bg:
                    w.styles.scrollbar_background = css_sb_bg
                    w.styles.scrollbar_background_hover = css_sb_bg


def apply_button_theme(button: Button, theme=None, button_type: str = "button_primary") -> None:
    """Apply foreground and background colors to a Textual Button based on theme dictionary."""
    app = None
    with contextlib.suppress(Exception):
        app = getattr(button, "app", None)
    theme_dict = resolve_theme_dict(theme, app)
    if not theme_dict:
        return
    mod_styles = theme_dict.get("modals", {}) if isinstance(theme_dict.get("modals"), dict) else {}
    style = mod_styles.get(button_type) or theme_dict.get(button_type)
    if not style:
        if button_type in ("button_confirm", "button_save"):
            style = mod_styles.get("button_confirm") or theme_dict.get("button_success") or theme_dict.get("button_primary")
        elif button_type in ("button_danger", "button_error", "button_delete"):
            style = mod_styles.get("button_danger") or theme_dict.get("button_error") or theme_dict.get("button_danger")
        elif button_type in ("button_default", "button_cancel"):
            style = mod_styles.get("button_cancel") or theme_dict.get("button_cancel") or theme_dict.get("button_default")
        elif button_type == "button_success":
            style = theme_dict.get("button_success")
    if not style:
        style = theme_dict.get("button_primary")
    if isinstance(style, Style):
        if style.color and style.color.name:
            css_fg = parse_css_color(style.color.name)
            if css_fg:
                button.styles.color = css_fg
        if style.bgcolor and style.bgcolor.name:
            css_bg = parse_css_color(style.bgcolor.name)
            if css_bg:
                button.styles.background = css_bg


def load_themes_file(filepath: str | None = None) -> dict:
    """
    Load bashmenu.themes file and parse YAML.
    """
    global _default_themes_filepath
    import yaml

    target_path = filepath
    if not target_path:
        if _default_themes_filepath and os.path.exists(_default_themes_filepath):
            target_path = _default_themes_filepath
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            c1 = os.path.join(base_dir, "bashmenu.themes")
            c2 = os.path.join(os.getcwd(), "bashmenu.themes")
            if os.path.exists(c1):
                target_path = c1
            elif os.path.exists(c2):
                target_path = c2
            else:
                target_path = c1
            _default_themes_filepath = target_path

    if not target_path or not os.path.exists(target_path):
        return {}

    now = time.time()
    last_stat = _themes_last_stat_check.get(target_path, 0.0)
    cached = _themes_file_cache.get(target_path)
    if cached is not None and (now - last_stat < 1.0):
        return cached[1]

    try:
        _themes_last_stat_check[target_path] = now
        mtime = os.path.getmtime(target_path)
        if cached and cached[0] == mtime:
            return cached[1]

        with open(target_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            _themes_file_cache[target_path] = (mtime, data)
            return data
    except (yaml.YAMLError, OSError):
        return cached[1] if cached else {}


# ==============================================================================
# TEXTUAL MODAL SCREENS
# ==============================================================================


class ShadowWidget(Static):
    """Widget rendering drop shadow with shadow character and theme colors."""

    def __init__(self, shadow_char: str = "░", **kwargs):
        super().__init__(**kwargs)
        self.shadow_char = shadow_char

    def update_char(self, char: str) -> None:
        self.shadow_char = char or "░"
        self.refresh()

    def render(self) -> str:
        w = self.size.width
        h = self.size.height
        if w <= 0 or h <= 0:
            return ""
        line = self.shadow_char * w
        return "\n".join([line] * h)


class ModalFrame(Vertical):
    """Container holding a modal dialog and its classic drop shadows."""

    DEFAULT_CSS = """
    ModalFrame {
        width: auto;
        height: auto;
    }
    #dialog_hrow {
        width: auto;
        height: auto;
    }
    #shadow_right {
        width: 2;
        height: 1;
        margin-top: 1;
    }
    #shadow_bottom {
        width: 100%;
        height: 1;
        margin-left: 2;
    }
    """

    def on_mount(self) -> None:
        self.call_after_refresh(self.sync_shadows)
        with contextlib.suppress(Exception):
            d = self.query_one("#dialog")
            self.watch(d, "size", self._on_dialog_size, init=False)

    def _on_dialog_size(self, old_val, new_val) -> None:
        self.sync_shadows()

    def on_resize(self, event) -> None:
        self.sync_shadows()

    def sync_shadows(self) -> None:
        with contextlib.suppress(Exception):
            d = self.query_one("#dialog")
            h = d.outer_size.height
            w = d.outer_size.width
            if h > 0 and w > 0:
                with contextlib.suppress(Exception):
                    sr = self.query_one("#shadow_right")
                    sr.styles.height = max(1, h - 1)
                with contextlib.suppress(Exception):
                    sb = self.query_one("#shadow_bottom")
                    sb.styles.width = w


class MessageModalScreen(ModalScreen[None]):
    """Modal screen to display popup messages."""

    DEFAULT_CSS = """
    MessageModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #modal_frame {
        max-height: 90%;
    }
    #dialog {
        width: 70;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    MessageModalScreen.help_modal #modal_frame {
        width: 95%;
        height: 95%;
        max-width: 100%;
        max-height: 100%;
    }
    MessageModalScreen.help_modal #dialog_hrow {
        width: 1fr;
        height: 1fr;
    }
    MessageModalScreen.help_modal #dialog {
        width: 1fr;
        height: 100%;
        max-width: 100%;
        max-height: 100%;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    #scroll_container {
        height: auto;
        max-height: 15;
    }
    MessageModalScreen.help_modal #scroll_container {
        height: 1fr;
        max-height: 100%;
    }
    #message {
        width: 100%;
        margin-right: 1;
    }
    #footer {
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close_modal", "Close"),
        Binding("enter", "confirm_or_follow_link", "Close/Open Link"),
        Binding("tab", "next_link", "Next Link", show=False),
        Binding("shift+tab", "prev_link", "Previous Link", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str | Text | Markdown,
        theme: dict | None = None,
        is_help: bool = False,
        no_formatting: bool = False,
        is_markdown: bool = False,
    ):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.theme = theme or {}
        self.is_help = is_help
        self.no_formatting = no_formatting
        self.is_markdown = is_markdown
        self._cached_anchor_lines: dict[str, int] | None = None
        self._cached_links: list[dict[str, Any]] | None = None
        self.active_link_idx: int = -1
        if is_help:
            self.add_class("help_modal")

    def compose(self) -> ComposeResult:
        def _render_dialog():
            with Horizontal(id="title_bar"):
                yield Label(self.modal_title or "", id="title")
                yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
            with VerticalScroll(id="scroll_container"):
                if isinstance(self.message, Text):
                    yield Static(self.message, id="message")
                elif self.is_markdown or isinstance(self.message, (Markdown, TextualMarkdown)):
                    md_text = self.message.markup if isinstance(self.message, Markdown) else str(self.message)
                    yield Static(Markdown(md_text, hyperlinks=True), id="message")
                else:
                    content = formatting_to_rich_text(
                        str(self.message), theme=self.theme, no_formatting=self.no_formatting
                    )
                    yield Static(content, id="message")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="btn_ok")
            if self.is_markdown or isinstance(self.message, (Markdown, TextualMarkdown)):
                yield Label("[ENTER/ESC] Close | [TAB] Links", id="footer", markup=False)
            else:
                yield Label("[ENTER/ESC] Close", id="footer", markup=False)

        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    yield from _render_dialog()
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    @staticmethod
    def _norm_slug(s: str) -> str:
        s = s.lower()
        s = re.sub(r"[^\w\s-]", "", s)
        return re.sub(r"[\s-]+", "-", s).strip("-")

    @staticmethod
    def _extract_slug_variants(raw_title: str) -> set[str]:
        clean_raw = re.sub(r"[`*]", "", raw_title).strip()
        s_gfm = re.sub(r"[^\w\s-]", "", clean_raw.lower()).strip()
        slug_exact = re.sub(r"\s", "-", s_gfm).strip("-")
        slug_collapsed = re.sub(r"[\s-]+", "-", s_gfm).strip("-")
        slug_no_num1 = re.sub(r"^[0-9]+-", "", slug_exact)
        slug_no_num2 = re.sub(r"^[0-9]+-", "", slug_collapsed)
        slug_no_und1 = slug_exact.replace("_", "")
        slug_no_und2 = slug_collapsed.replace("_", "")
        slug_no_num_und = slug_no_num2.replace("_", "")
        return {x for x in (slug_exact, slug_collapsed, slug_no_num1, slug_no_num2, slug_no_und1, slug_no_und2, slug_no_num_und) if x}

    @staticmethod
    def _add_or_merge_link(links: list[dict[str, Any]], text: str, url: str, y: int) -> None:
        if not url or not text:
            return
        if links and links[-1]["url"] == url and links[-1]["y"] == y - 1:
            links[-1]["text"] = f"{links[-1]['text']} {text}".strip()
        else:
            links.append({"text": text, "url": url, "y": y})

    def on_resize(self, event=None) -> None:
        self._cached_anchor_lines = None
        self._cached_links = None

    def _ensure_anchors_and_links(self) -> None:
        if self._cached_anchor_lines is None or self._cached_links is None:
            self._cached_anchor_lines, self._cached_links = self._compute_anchors_and_links()

    def _compute_anchor_lines(self) -> dict[str, int]:
        self._ensure_anchors_and_links()
        return self._cached_anchor_lines or {}

    def _compute_anchors_and_links(self) -> tuple[dict[str, int], list[dict[str, Any]]]:
        anchors: dict[str, int] = {}
        links: list[dict[str, Any]] = []
        with contextlib.suppress(Exception):
            text_str = self.message.markup if isinstance(self.message, Markdown) else str(self.message)
            lines = None
            with contextlib.suppress(Exception):
                msg = self.query_one("#message", Static)
                if not getattr(msg, "_render_cache", None) or not getattr(msg._render_cache, "lines", None):
                    msg._render_content()
                if getattr(msg, "_render_cache", None) and getattr(msg._render_cache, "lines", None):
                    lines = msg._render_cache.lines

            if lines is None:
                from rich.console import Console

                width = 100
                with contextlib.suppress(Exception):
                    scroller = self.query_one("#scroll_container", VerticalScroll)
                    if scroller.size.width > 20:
                        width = scroller.size.width
                c = Console(width=width)
                lines = c.render_lines(Markdown(text_str, hyperlinks=True))

            heading_items = []
            for line in text_str.splitlines():
                m = re.match(r"^(#{1,6})\s+(.*)$", line)
                if m:
                    clean_title = re.sub(r"[`*]", "", m.group(2)).strip()
                    heading_items.append((clean_title, self._extract_slug_variants(clean_title)))

            for clean_title, slugs in heading_items:
                search_prefix = clean_title[:25].lower()
                for y, line in enumerate(lines):
                    line_text = (line.text if hasattr(line, "text") else "".join(s.text for s in line)).strip().lower()
                    if not line_text.startswith(("•", "*", "-")) and search_prefix in line_text:
                        for slug in slugs:
                            if slug not in anchors:
                                anchors[slug] = y
                        break

            for y, line in enumerate(lines):
                cur_url = None
                cur_text: list[str] = []
                segments = line if hasattr(line, "__iter__") else []
                for seg in segments:
                    url = seg.style.link if getattr(seg, "style", None) else None
                    if url:
                        if url == cur_url:
                            cur_text.append(seg.text)
                        else:
                            if cur_url:
                                self._add_or_merge_link(links, "".join(cur_text).strip(), cur_url, y)
                            cur_url = url
                            cur_text = [seg.text]
                    else:
                        if cur_url:
                            self._add_or_merge_link(links, "".join(cur_text).strip(), cur_url, y)
                            cur_url = None
                            cur_text = []
                if cur_url:
                    self._add_or_merge_link(links, "".join(cur_text).strip(), cur_url, y)
        return anchors, links

    def handle_link(self, href: str) -> None:
        if not href:
            return
        if href.startswith("#"):
            self.goto_anchor(href.lstrip("#"))
        elif href.startswith(("http://", "https://")):
            script_path = os.path.join(os.path.dirname(__file__), "scripts", "webopen.sh")
            if os.path.exists(script_path) and os.access(script_path, os.X_OK):
                subprocess.Popen([script_path, href], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    self.app.open_url(href)
                except Exception:  # noqa: BLE001
                    import webbrowser

                    webbrowser.open(href)
        else:
            clean_path = href.removeprefix("file://")
            base_dir = os.path.dirname(__file__)
            target_path = clean_path if os.path.isabs(clean_path) else os.path.join(base_dir, clean_path)
            if os.path.exists(target_path) and target_path.endswith((".md", ".markdown")):
                with contextlib.suppress(Exception):
                    with open(target_path, "r", encoding="utf-8") as f:
                        new_text = f.read()
                    self.message = new_text
                    self.modal_title = os.path.basename(target_path)
                    with contextlib.suppress(Exception):
                        self.query_one("#title", Label).update(self.modal_title)
                    msg_widget = self.query_one("#message", Static)
                    msg_widget.update(Markdown(new_text, hyperlinks=True))
                    self._cached_anchor_lines = None
                    self._cached_links = None
                    self.active_link_idx = -1
                    scroller = self.query_one("#scroll_container", VerticalScroll)
                    scroller.scroll_to(y=0, animate=False)
                    self._ensure_anchors_and_links()
                    self._update_footer()

    def goto_anchor(self, anchor: str) -> None:
        if not anchor:
            return
        with contextlib.suppress(Exception):
            md = self.query_one("#message", TextualMarkdown)
            md.goto_anchor(anchor)
            return

        self._ensure_anchors_and_links()

        clean_target = anchor.lower().strip("-")
        norm_target = self._norm_slug(anchor)
        target_y = None
        if self._cached_anchor_lines:
            target_y = self._cached_anchor_lines.get(clean_target)
            if target_y is None:
                target_y = self._cached_anchor_lines.get(norm_target)
            if target_y is None:
                no_num = re.sub(r"^[0-9]+-", "", norm_target)
                target_y = self._cached_anchor_lines.get(no_num)
            if target_y is None:
                no_und = norm_target.replace("_", "")
                target_y = self._cached_anchor_lines.get(no_und)
            if target_y is None:
                for k, y in self._cached_anchor_lines.items():
                    if k.startswith(norm_target) or norm_target.startswith(k):
                        target_y = y
                        break
            if target_y is None:
                tw = norm_target.split("-")
                if len(tw) >= 2:
                    for k, y in self._cached_anchor_lines.items():
                        kw = k.split("-")
                        if len(kw) >= 2 and kw[:2] == tw[:2]:
                            target_y = y
                            break

        if target_y is not None:
            self.active_link_idx = -1
            self._update_footer()
            with contextlib.suppress(Exception):
                scroller = self.query_one("#scroll_container", VerticalScroll)
                scroller.scroll_to(y=max(0, target_y), animate=False)

    @on(TextualMarkdown.LinkClicked)
    def on_markdown_link_clicked(self, event: TextualMarkdown.LinkClicked) -> None:
        event.stop()
        event.prevent_default()
        self.handle_link(event.href)

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_ok", Button), theme=self.theme, button_type="button_primary")
        self._update_footer()

    def _jump_to_active_link(self) -> None:
        if self._cached_links and 0 <= self.active_link_idx < len(self._cached_links):
            target = self._cached_links[self.active_link_idx]
            target_y = target["y"]
            with contextlib.suppress(Exception):
                scroller = self.query_one("#scroll_container", VerticalScroll)
                scroller.scroll_to(y=max(0, target_y - 2), animate=False)
            self._update_footer()

    def _update_footer(self) -> None:
        with contextlib.suppress(Exception):
            footer = self.query_one("#footer", Label)
            if self._cached_links and 0 <= self.active_link_idx < len(self._cached_links):
                target = self._cached_links[self.active_link_idx]
                label_text = target["text"]
                if len(label_text) > 34:
                    label_text = label_text[:31] + "..."
                idx_str = f"{self.active_link_idx + 1}/{len(self._cached_links)}"
                footer.update(f"[ESC] Close | [TAB/Shift+TAB] ({idx_str}) | [ENTER] -> {label_text}")
            elif self._cached_links or self.is_markdown or isinstance(self.message, (Markdown, TextualMarkdown)):
                footer.update("[ENTER/ESC] Close | [TAB] Links")
            else:
                footer.update("[ENTER/ESC] Close")

    def action_next_link(self) -> None:
        self._ensure_anchors_and_links()
        if not self._cached_links:
            self.app.action_focus_next()
            return
        if self.active_link_idx == -1:
            scroll_y = 0
            with contextlib.suppress(Exception):
                scroll_y = self.query_one("#scroll_container", VerticalScroll).scroll_y
            idx = 0
            for i, link in enumerate(self._cached_links):
                if link["y"] >= scroll_y:
                    idx = i
                    break
            self.active_link_idx = idx
        else:
            self.active_link_idx = (self.active_link_idx + 1) % len(self._cached_links)
        self._jump_to_active_link()

    def action_prev_link(self) -> None:
        self._ensure_anchors_and_links()
        if not self._cached_links:
            self.app.action_focus_previous()
            return
        if self.active_link_idx == -1:
            scroll_y = 0
            with contextlib.suppress(Exception):
                scroll_y = self.query_one("#scroll_container", VerticalScroll).scroll_y
            idx = len(self._cached_links) - 1
            for i in reversed(range(len(self._cached_links))):
                if self._cached_links[i]["y"] <= scroll_y:
                    idx = i
                    break
            self.active_link_idx = idx
        elif self.active_link_idx <= 0:
            self.active_link_idx = len(self._cached_links) - 1
        else:
            self.active_link_idx -= 1
        self._jump_to_active_link()

    def action_confirm_or_follow_link(self) -> None:
        if self._cached_links and 0 <= self.active_link_idx < len(self._cached_links):
            target = self._cached_links[self.active_link_idx]
            href = target["url"]
            self.active_link_idx = -1
            self._update_footer()
            self.handle_link(href)
        else:
            self.dismiss(None)

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)
            return

        link = None
        style = getattr(event, "style", None)
        if style and getattr(style, "link", None):
            link = style.link

        if not link and hasattr(self, "screen"):
            sx = getattr(event, "screen_x", None)
            sy = getattr(event, "screen_y", None)
            if sx is not None and sy is not None:
                with contextlib.suppress(Exception):
                    st = self.screen.get_style_at(sx, sy)
                    if getattr(st, "link", None):
                        link = st.link

        if not link and widget and hasattr(widget, "get_style_at"):
            with contextlib.suppress(Exception):
                sx = getattr(event, "screen_x", event.x)
                sy = getattr(event, "screen_y", event.y)
                if hasattr(widget, "region"):
                    local_x = sx - widget.region.x
                    local_y = sy - widget.region.y
                    st = widget.get_style_at(local_x, local_y)
                    if getattr(st, "link", None):
                        link = st.link

        if link:
            self.handle_link(link)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn_ok", "btn_close_x"):
            self.dismiss(None)

    def action_close_modal(self) -> None:
        self.dismiss(None)


class ConfirmModalScreen(ModalScreen[str]):
    """Modal screen for Yes/No/Cancel confirmation."""

    DEFAULT_CSS = """
    ConfirmModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "select_yes", "Yes"),
        Binding("n", "select_no", "No"),
        Binding("c", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, theme: dict | None = None):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(self.modal_title or "", id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    content = (
                        self.message
                        if isinstance(self.message, Text)
                        else formatting_to_rich_text(str(self.message), theme=self.theme)
                    )
                    yield Static(content, id="message")
                    with Horizontal(id="buttons"):
                        yield Button("Yes", variant="primary", id="btn_yes")
                        yield Button("No", variant="default", id="btn_no")
                        yield Button("Cancel", variant="default", id="btn_cancel")
                    yield Label("[Y] Yes | [N] No | [C / ESC] Cancel", id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_yes", Button), self.theme, "button_primary")
            apply_button_theme(self.query_one("#btn_no", Button), self.theme, "button_error")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_yes":
            self.dismiss("yes")
        elif event.button.id == "btn_no":
            self.dismiss("no")
        else:
            self.dismiss(None)

    def action_select_yes(self) -> None:
        self.dismiss("yes")

    def action_select_no(self) -> None:
        self.dismiss("no")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ToggleModalScreen(ModalScreen[str]):
    """Modal screen for True/False/Cancel toggle selection."""

    DEFAULT_CSS = """
    ToggleModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("t", "select_true", "True"),
        Binding("f", "select_false", "False"),
        Binding("c", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, theme: dict | None = None):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(self.modal_title or "", id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    content = (
                        self.message
                        if isinstance(self.message, Text)
                        else formatting_to_rich_text(str(self.message), theme=self.theme)
                    )
                    yield Static(content, id="message")
                    with Horizontal(id="buttons"):
                        yield Button("True", variant="success", id="btn_true")
                        yield Button("False", variant="error", id="btn_false")
                        yield Button("Cancel", variant="default", id="btn_cancel")
                    yield Label("[T] True | [F] False | [C / ESC] Cancel", id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_true", Button), self.theme, "button_success")
            apply_button_theme(self.query_one("#btn_false", Button), self.theme, "button_error")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_true":
            self.dismiss("true")
        elif event.button.id == "btn_false":
            self.dismiss("false")
        else:
            self.dismiss(None)

    def action_select_true(self) -> None:
        self.dismiss("true")

    def action_select_false(self) -> None:
        self.dismiss("false")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChoiceModalScreen(ModalScreen[str | None]):
    """Modal screen for binary or multiple option selection."""

    DEFAULT_CSS = """
    ChoiceModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 68;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover, .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "cancel", "Cancel", show=False),
        Binding("1", "select_opt_0", "Option 1", show=False),
        Binding("2", "select_opt_1", "Option 2", show=False),
        Binding("3", "select_opt_2", "Option 3", show=False),
        Binding("d", "select_default", "Default", show=False),
        Binding("b", "select_builtin", "Built-in", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        choices: list[tuple[str, str]] | None = None,
        theme: dict | None = None,
    ):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.choices = choices or [("default", "Default ($EDITOR)"), ("builtin", "Built-in (BashEdit)")]
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(self.modal_title or "", id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    content = (
                        self.message
                        if isinstance(self.message, Text)
                        else formatting_to_rich_text(str(self.message), theme=self.theme)
                    )
                    yield Static(content, id="message")
                    with Horizontal(id="buttons"):
                        for idx, (val, lbl) in enumerate(self.choices):
                            variant = "primary" if idx == 0 else ("success" if idx == 1 else "default")
                            yield Button(f"[{idx+1}] {lbl}", variant=variant, id=f"btn_choice_{idx}")
                        yield Button("Cancel [ESC]", variant="default", id="btn_cancel")
                    footer_items = [f"[{idx+1}] {lbl}" for idx, (_, lbl) in enumerate(self.choices)]
                    footer_items.append("[ESC] Cancel")
                    yield Label(" | ".join(footer_items), id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            for idx in range(len(self.choices)):
                b_type = "button_primary" if idx == 0 else ("button_success" if idx == 1 else "button_default")
                apply_button_theme(self.query_one(f"#btn_choice_{idx}", Button), self.theme, b_type)
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("btn_choice_"):
            try:
                idx = int(btn_id.split("_")[-1])
                if 0 <= idx < len(self.choices):
                    self.dismiss(self.choices[idx][0])
                    return
            except (ValueError, IndexError):
                pass
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_select_opt_0(self) -> None:
        if len(self.choices) > 0:
            self.dismiss(self.choices[0][0])

    def action_select_opt_1(self) -> None:
        if len(self.choices) > 1:
            self.dismiss(self.choices[1][0])

    def action_select_opt_2(self) -> None:
        if len(self.choices) > 2:
            self.dismiss(self.choices[2][0])

    def action_select_default(self) -> None:
        for val, _ in self.choices:
            if val == "default":
                self.dismiss("default")
                return

    def action_select_builtin(self) -> None:
        for val, _ in self.choices:
            if val in ("builtin", "bm", "bashedit"):
                self.dismiss(val)
                return


class InputModalScreen(ModalScreen[str]):
    """Modal screen for single-line text input."""

    DEFAULT_CSS = """
    InputModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 65;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #prompt {
        margin-bottom: 1;
    }
    #input {
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        title: str,
        prompt: str,
        default_text: str = "",
        theme: dict | None = None,
        masked: bool = False,
    ):
        super().__init__()
        self.modal_title = title
        self.prompt = prompt
        self.default_text = default_text
        self.theme = theme or {}
        self.masked = masked

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(self.modal_title or "", id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    if self.prompt:
                        content = (
                            self.prompt
                            if isinstance(self.prompt, Text)
                            else formatting_to_rich_text(str(self.prompt), theme=self.theme)
                        )
                        yield Static(content, id="prompt")
                    yield Input(
                        value=self.default_text,
                        password=self.masked,
                        id="input",
                    )
                    with Horizontal(id="buttons"):
                        yield Button("OK", variant="primary", id="btn_ok")
                        yield Button("Cancel", variant="default", id="btn_cancel")
                    yield Label("[ENTER] OK | [ESC] Cancel", id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_ok", Button), self.theme, "button_primary")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_ok":
            val = self.query_one("#input", Input).value
            self.dismiss(val)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class FilePickerModalScreen(ModalScreen[str]):
    """Modal screen for interactive file/directory chooser."""

    DEFAULT_CSS = """
    FilePickerModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 76;
        height: 25;
        max-width: 95%;
        max-height: 95%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    FilePickerModalScreen.save_modal #dialog {
        height: 27;
    }
    FilePickerModalScreen.save_modal #options_list {
        height: 10;
    }
    #title_bar {
        height: 1;
        width: 100%;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #path_label {
        margin-bottom: 1;
    }
    #options_list {
        height: 11;
        border: solid $accent;
    }
    #save_filename_container {
        margin-top: 1;
        height: auto;
    }
    #save_filename_label {
        color: $accent;
    }
    #save_buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        margin-top: 1;
        color: $text;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+h", "toggle_hidden", "Toggle Hidden"),
        Binding("ctrl+shift+h", "toggle_hidden", "Toggle Hidden", show=False),
        Binding("backspace", "toggle_hidden", "Toggle Hidden", show=False),
        Binding("h", "toggle_hidden", "Toggle Hidden", show=False),
        Binding("H", "toggle_hidden", "Toggle Hidden", show=False),
        Binding("space", "select_dir", "Select Folder"),
        Binding("n", "new_item", "New", show=False),
        Binding("N", "new_item", "New", show=False),
    ]

    def __init__(
        self,
        title: str,
        start_dir: str = "~",
        mode: str = "file",
        default_val: str | None = None,
        theme: dict | None = None,
        show_hidden: bool = False,
        allow_new: bool = False,
    ):
        super().__init__()
        self.modal_title = title
        self.mode = mode
        self.default_val = default_val
        self.show_hidden_state = show_hidden
        self.allow_new = allow_new
        self.theme = theme or {}

        resolved_start = os.path.abspath(os.path.expanduser(start_dir))
        if not os.path.exists(resolved_start) or not os.path.isdir(resolved_start):
            resolved_start = str(Path.home())
        self.current_path = resolved_start
        self.entries = []

    def _get_footer_text(self) -> str:
        h_status = "Hidden*" if self.show_hidden_state else "Hidden"
        if self.mode == "save":
            return f"[ENTER] Save/Nav | [Ctrl+H] {h_status} | [ESC] Cancel"
        if self.mode == "dir":
            if self.allow_new:
                return f"[ENTER] Open | [SPACE] Pick | [Ctrl+H] {h_status} | [N] New | [ESC] Cancel"
            return f"[ENTER] Open | [SPACE] Select | [Ctrl+H] {h_status} | [ESC] Cancel"
        if self.allow_new:
            return f"[ENTER] Open | [Ctrl+H] {h_status} | [N] New File | [ESC] Cancel"
        return f"[ENTER] Open/Select | [Ctrl+H] {h_status} | [ESC] Cancel"

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        title_str = self.modal_title or ("Save File As" if self.mode == "save" else "File Picker")
                        yield Label(title_str, id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    yield MarqueeLabel(f"Path: {self.current_path}", id="path_label", theme_styles=self.theme)
                    yield OptionList(id="options_list")
                    if self.mode == "save":
                        with Vertical(id="save_filename_container"):
                            yield Label("File Name:", id="save_filename_label")
                            yield Input(value=self.default_val or "", placeholder="Enter file name...", id="filename_input")
                        with Horizontal(id="save_buttons"):
                            yield Button("Save", variant="primary", id="btn_save")
                            yield Button("Cancel", variant="default", id="btn_cancel")
                    else:
                        with Horizontal(id="save_buttons"):
                            ok_label = "Continue" if self.mode == "dir" else "OK"
                            yield Button(ok_label, variant="primary", id="btn_ok")
                            if self.allow_new:
                                new_lbl = "New Folder" if self.mode == "dir" else "New File"
                                yield Button(new_lbl, variant="default", id="btn_new")
                            yield Button("Cancel", variant="default", id="btn_cancel")
                    yield Label(self._get_footer_text(), id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        if self.mode == "save":
            self.add_class("save_modal")
        self.load_directory()
        apply_modal_theme(self, self.theme)
        if self.mode == "save":
            with contextlib.suppress(Exception):
                apply_button_theme(self.query_one("#btn_save", Button), self.theme, "button_primary")
                apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")
        else:
            with contextlib.suppress(Exception):
                apply_button_theme(self.query_one("#btn_ok", Button), self.theme, "button_primary")
                if self.allow_new:
                    apply_button_theme(self.query_one("#btn_new", Button), self.theme, "button_cancel")
                apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def _submit_save(self) -> None:
        filename = ""
        try:
            filename = self.query_one("#filename_input", Input).value.strip()
        except Exception:  # noqa: BLE001
            filename = (self.default_val or "").strip()
        if filename:
            self.dismiss(os.path.join(self.current_path, filename))
        else:
            self.dismiss(None)

    def _submit_selection(self) -> None:
        with contextlib.suppress(Exception):
            options_list = self.query_one("#options_list", OptionList)
            idx = options_list.highlighted
            if idx is not None and 0 <= idx < len(self.entries):
                selected = self.entries[idx]
                if selected.get("is_new"):
                    self.action_new_item()
                    return
                if selected.get("is_self"):
                    self.dismiss(selected["path"])
                    return
                if selected.get("is_dir"):
                    self.current_path = selected["path"]
                    self.load_directory()
                    return
                self.dismiss(selected["path"])
                return
        if self.mode == "dir":
            self.dismiss(self.current_path)

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn_close_x", "btn_cancel"):
            self.dismiss(None)
        elif event.button.id in ("btn_ok", "btn_continue"):
            if self.mode == "dir":
                self.dismiss(self.current_path)
            elif self.mode == "save":
                self._submit_save()
            else:
                self._submit_selection()
        elif event.button.id == "btn_save":
            self._submit_save()
        elif event.button.id in ("btn_new", "btn_new_dir"):
            self.action_new_item()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.mode == "save" and getattr(event.input, "id", None) == "filename_input":
            self._submit_save()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self.mode != "save":
            return
        idx = event.option_index
        if 0 <= idx < len(self.entries):
            selected = self.entries[idx]
            if not selected.get("is_dir") and selected.get("path"):
                filename = os.path.basename(selected["path"])
                with contextlib.suppress(Exception):
                    self.query_one("#filename_input", Input).value = filename

    def load_directory(self) -> None:
        """Scan current directory path and populate OptionList with folders, files, and navigation options."""
        self.query_one("#path_label", MarqueeLabel).update(f"Path: {self.current_path}")
        options_list = self.query_one("#options_list", OptionList)
        options_list.clear_options()
        self.entries = []

        try:
            with os.scandir(self.current_path) as it:
                all_entries = list(it)

            if not self.show_hidden_state:
                all_entries = [e for e in all_entries if not e.name.startswith(".")]

            def _is_dir_safe(e: os.DirEntry) -> bool:
                try:
                    return e.is_dir()
                except OSError:
                    return False

            dirs = sorted(
                [e for e in all_entries if _is_dir_safe(e)],
                key=lambda e: e.name.lower(),
            )
            files = sorted(
                [e for e in all_entries if not _is_dir_safe(e)],
                key=lambda e: e.name.lower(),
            )

            if self.allow_new:
                new_lbl = "➕ [ Create New Folder ]" if self.mode == "dir" else "➕ [ Create New File ]"
                self.entries.append(
                    {"name": new_lbl, "is_dir": False, "path": "", "is_new": True}
                )
                options_list.add_option(Option(new_lbl))

            if self.current_path != "/":
                parent_path = os.path.dirname(self.current_path)
                self.entries.append(
                    {"name": ".. (Parent Directory)", "is_dir": True, "path": parent_path}
                )
                options_list.add_option(Option("📁 .. (Parent Directory)"))

            if self.mode == "dir":
                dir_name = os.path.basename(self.current_path) or "/"
                self.entries.append(
                    {
                        "name": f"✔  Use this directory ({dir_name})",
                        "is_dir": True,
                        "path": self.current_path,
                        "is_self": True,
                    }
                )
                options_list.add_option(
                    Option(f"✔  Use this directory ({dir_name})")
                )

            for d in dirs:
                self.entries.append(
                    {"name": f"[DIR] {d.name}/", "is_dir": True, "path": d.path}
                )
                options_list.add_option(Option(f"📁 {d.name}/"))

            if self.mode != "dir":
                for f in files:
                    self.entries.append(
                        {"name": f"[FILE] {f.name}", "is_dir": False, "path": f.path}
                    )
                    options_list.add_option(Option(f"📄 {f.name}"))

        except OSError as e:
            options_list.add_option(Option(f"⚠️ Error loading directory: {e}"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if idx < 0 or idx >= len(self.entries):
            return

        selected = self.entries[idx]
        if selected.get("is_new"):
            self.action_new_item()
            return

        if selected.get("is_self"):
            if self.mode == "save":
                self._submit_save()
            else:
                self.dismiss(selected["path"])
            return

        if selected["is_dir"]:
            self.current_path = selected["path"]
            self.load_directory()
        elif self.mode == "save":
            filename = os.path.basename(selected["path"])
            with contextlib.suppress(Exception):
                self.query_one("#filename_input", Input).value = filename
            self._submit_save()
        elif self.mode in ["file", "any"]:
            self.dismiss(selected["path"])

    def action_new_item(self) -> None:
        if not self.allow_new:
            return
        prompt_type = "Folder" if self.mode == "dir" else "File"

        def name_cb(name: str | None) -> None:
            if name and name.strip():
                new_target = os.path.join(self.current_path, name.strip())
                if self.mode == "dir":
                    try:
                        os.makedirs(new_target, exist_ok=True)
                    except OSError as err:
                        self.app.push_screen(
                            MessageModalScreen("Error", f"Failed to create directory:\n{err}", theme=self.theme)
                        )
                        return
                    self.dismiss(new_target)
                else:
                    self.dismiss(new_target)

        self.app.push_screen(
            InputModalScreen(f"New {prompt_type}", f"Enter new {prompt_type.lower()} name:", theme=self.theme),
            name_cb,
        )

    def action_select_dir(self) -> None:
        if self.mode == "dir":
            self.dismiss(self.current_path)

    def action_toggle_hidden(self) -> None:
        self.show_hidden_state = not self.show_hidden_state
        self.load_directory()
        with contextlib.suppress(Exception):
            self.query_one("#footer", Label).update(self._get_footer_text())
        msg = "Showing hidden files" if self.show_hidden_state else "Hiding hidden files"
        with contextlib.suppress(Exception):
            self.notify(msg, title="File Picker", timeout=1.5)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("ctrl+h", "ctrl+shift+h"):
            event.stop()
            event.prevent_default()
            self.action_toggle_hidden()
            return
        if event.key in ("backspace", "h", "H") and not isinstance(self.focused, Input):
            event.stop()
            event.prevent_default()
            self.action_toggle_hidden()
            return

    def action_cancel(self) -> None:
        self.dismiss(None)


class CreateThemePromptModal(ModalScreen[str | None]):
    """Modal dialog prompting user whether to base a new theme on selected theme or start from scratch."""

    DEFAULT_CSS = """
    CreateThemePromptModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 66;
        height: auto;
        border: thick #555;
        background: #181818;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #eee;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        color: #888;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("b", "select_base", "Base on Selected"),
        Binding("s", "select_scratch", "From Scratch"),
        Binding("c", "cancel", "Cancel"),
    ]

    def __init__(self, selected_theme: str, theme: dict | None = None):
        super().__init__()
        self.selected_theme = selected_theme
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label("Create New Theme", id="title")
                        yield Label(format_close_button_label(self.theme), id="btn_close_x", classes="btn_close_x")
                    msg = (
                        f"Would you like to base the new theme on '[bold]{self.selected_theme}[/bold]',\n"
                        "or start from scratch with monochrome defaults?"
                    )
                    yield Static(formatting_to_rich_text(msg, theme=self.theme), id="message")
                    with Horizontal(id="buttons"):
                        yield Button(f"Base on '{self.selected_theme}'", variant="primary", id="btn_base")
                        yield Button("From Scratch", variant="default", id="btn_scratch")
                        yield Button("Cancel", variant="error", id="btn_cancel")
                    yield Label("[B] Base on Selected  |  [S] From Scratch  |  [ESC] Cancel", id="footer", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_base", Button), self.theme, "button_primary")
            apply_button_theme(self.query_one("#btn_scratch", Button), self.theme, "button_default")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_base":
            self.dismiss("base")
        elif event.button.id == "btn_scratch":
            self.dismiss("scratch")
        elif event.button.id == "btn_cancel":
            self.dismiss(None)

    def action_select_base(self) -> None:
        self.dismiss("base")

    def action_select_scratch(self) -> None:
        self.dismiss("scratch")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ThemePickerModalScreen(ModalScreen[str]):
    """Modal screen for interactive color theme selection with OptionList."""

    DEFAULT_CSS = """
    ThemePickerModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 74;
        height: 20;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    #options_list {
        height: 12;
        border: solid $accent;
    }
    #footer {
        height: 1;
        width: 100%;
        align: center middle;
        margin-top: 1;
    }
    .footer_item {
        color: $accent;
    }
    .footer_item:hover {
        text-style: underline bold;
        color: $text;
    }
    .footer_sep {
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("e", "edit_theme", "Edit"),
        Binding("c", "create_theme", "Create"),
        Binding("d", "delete_theme", "Delete"),
        Binding("delete", "delete_theme", "Delete", show=False),
    ]

    def __init__(self, current_theme: str = "dracula", theme: dict | None = None):
        super().__init__()
        self.current_theme = current_theme
        self.theme = theme or {}
        self.theme_keys = []

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label("Select Color Theme", id="title")
                        yield Label(format_close_button_label(self.theme), id="btn_close_x", classes="btn_close_x")
                    yield OptionList(id="options_list")
                    with Horizontal(id="footer"):
                        yield Label("[ENTER] Select", id="lbl_ft_select", classes="footer_item", markup=False)
                        yield Label(" | ", classes="footer_sep", markup=False)
                        yield Label("[e] Edit", id="lbl_ft_edit", classes="footer_item", markup=False)
                        yield Label(" | ", classes="footer_sep", markup=False)
                        yield Label("[c] Create", id="lbl_ft_create", classes="footer_item", markup=False)
                        yield Label(" | ", classes="footer_sep", markup=False)
                        yield Label("[d] Delete", id="lbl_ft_delete", classes="footer_item", markup=False)
                        yield Label(" | ", classes="footer_sep", markup=False)
                        yield Label("[ESC] Cancel", id="lbl_ft_cancel", classes="footer_item", markup=False)
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        themes_data = load_themes_file()
        opt_list = self.query_one("#options_list", OptionList)
        self.theme_keys = list(themes_data.keys()) if themes_data else ["dracula", "nord", "cyberpunk"]
        initial_idx = 0
        for idx, key in enumerate(self.theme_keys):
            formatted_name = key.replace("_", " ").title()
            if key == self.current_theme:
                initial_idx = idx
                opt_list.add_option(Option(f"✔  {formatted_name} (Active)"))
            else:
                opt_list.add_option(Option(f"   {formatted_name}"))
        opt_list.highlighted = initial_idx
        apply_modal_theme(self, self.theme)

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if not widget:
            return
        w_id = getattr(widget, "id", None)
        if w_id == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", []):
            self.dismiss(None)
        elif w_id == "lbl_ft_select":
            opt_list = self.query_one("#options_list", OptionList)
            idx = opt_list.highlighted
            if idx is not None and 0 <= idx < len(self.theme_keys):
                self.dismiss(self.theme_keys[idx])
        elif w_id == "lbl_ft_edit":
            self.action_edit_theme()
        elif w_id == "lbl_ft_create":
            self.action_create_theme()
        elif w_id == "lbl_ft_delete":
            self.action_delete_theme()
        elif w_id == "lbl_ft_cancel":
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(self.theme_keys):
            self.dismiss(self.theme_keys[idx])

    def action_edit_theme(self) -> None:
        opt_list = self.query_one("#options_list", OptionList)
        idx = opt_list.highlighted
        chosen_theme = (
            self.theme_keys[idx]
            if (idx is not None and 0 <= idx < len(self.theme_keys))
            else self.current_theme
        )
        import themeedit

        def _on_editor_exit(_res: Any = None) -> None:
            self.dismiss(None)

        self.app.push_screen(
            themeedit.ThemeEditScreen(initial_theme=chosen_theme, is_new=False),
            _on_editor_exit,
        )

    def action_create_theme(self) -> None:
        opt_list = self.query_one("#options_list", OptionList)
        idx = opt_list.highlighted
        sel_theme = (
            self.theme_keys[idx]
            if (idx is not None and 0 <= idx < len(self.theme_keys))
            else self.current_theme
        )

        def _on_create_choice(choice: str | None) -> None:
            if not choice:
                return
            import themeedit

            def _on_create_exit(_res: Any = None) -> None:
                self.dismiss(None)

            if choice == "base":
                self.app.push_screen(
                    themeedit.ThemeEditScreen(
                        initial_theme=sel_theme,
                        is_new=True,
                        base_theme=sel_theme,
                    ),
                    _on_create_exit,
                )
            elif choice == "scratch":
                self.app.push_screen(
                    themeedit.ThemeEditScreen(
                        initial_theme="monochrome",
                        is_new=True,
                        base_theme=None,
                    ),
                    _on_create_exit,
                )

        self.app.push_screen(
            CreateThemePromptModal(sel_theme, theme=self.theme),
            _on_create_choice,
        )

    def action_delete_theme(self) -> None:
        opt_list = self.query_one("#options_list", OptionList)
        idx = opt_list.highlighted
        if idx is None or idx < 0 or idx >= len(self.theme_keys):
            return
        target_theme = self.theme_keys[idx]

        if len(self.theme_keys) <= 1:
            self.app.push_screen(
                MessageModalScreen("Cannot Delete Theme", "Cannot delete the only remaining theme.", theme=self.theme)
            )
            return

        if target_theme == self.current_theme:
            self.app.push_screen(
                MessageModalScreen(
                    "Cannot Delete Active Theme",
                    f"Theme '{target_theme}' is currently the active theme.\nPlease switch to another theme first before deleting it.",
                    theme=self.theme,
                )
            )
            return

        def _on_confirm(choice: str | None) -> None:
            if choice == "yes":
                try:
                    import bashmenu
                    themes_filepath = os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.themes")
                    raw_data = load_themes_file()
                    if target_theme in raw_data:
                        del raw_data[target_theme]
                        with open(themes_filepath, "w", encoding="utf-8") as f:
                            yaml.dump(raw_data, f, sort_keys=False, default_flow_style=False)
                        self.theme_keys.remove(target_theme)
                        opt_list.clear_options()
                        new_idx = 0
                        for i, key in enumerate(self.theme_keys):
                            formatted_name = key.replace("_", " ").title()
                            if key == self.current_theme:
                                new_idx = i
                                opt_list.add_option(Option(f"✔  {formatted_name} (Active)"))
                            else:
                                opt_list.add_option(Option(f"   {formatted_name}"))
                        opt_list.highlighted = min(new_idx, len(self.theme_keys) - 1)
                        with contextlib.suppress(Exception):
                            self.notify(f"Theme '{target_theme}' deleted.", title="Theme Deleted")
                except Exception as e:  # noqa: BLE001
                    self.app.push_screen(
                        MessageModalScreen("Delete Failed", f"Error deleting theme '{target_theme}':\n{e}", theme=self.theme)
                    )

        self.app.push_screen(
            ConfirmModalScreen(
                "Delete Theme",
                f"Are you sure you want to permanently delete theme '{target_theme}' from bashmenu.themes?",
                theme=self.theme,
            ),
            _on_confirm,
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class StreamOutputModalScreen(ModalScreen[None]):
    """Modal screen displaying real-time streaming output of a running command."""

    DEFAULT_CSS = """
    StreamOutputModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    StreamOutputModalScreen #modal_frame {
        width: 80%;
        height: 80%;
    }
    StreamOutputModalScreen #dialog_hrow {
        width: 1fr;
        height: 1fr;
    }
    StreamOutputModalScreen #dialog {
        width: 1fr;
        height: 100%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #log {
        height: 1fr;
        width: 100%;
        border: solid $surface-lighten-2;
        background: $surface-darken-1;
    }
    #footer {
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close_modal", "Close"),
        Binding("enter", "close_modal", "Close"),
    ]

    def __init__(self, title: str, command: str, theme: dict | None = None, no_formatting: bool = False):
        super().__init__()
        self.modal_title = title
        self.command = command
        self.theme = theme or {}
        self.no_formatting = no_formatting
        self.process = None

    def compose(self) -> ComposeResult:
        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(f" Output: {self.modal_title} ", id="title")
                        yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                    yield RichLog(id="log", highlight=True, markup=not self.no_formatting)
                    yield Label(" Executing... Please wait ", id="footer")
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.focus()
        apply_modal_theme(self, getattr(self, "theme", None))
        t = threading.Thread(target=self._run_command_stream, daemon=True)
        t.start()

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.action_close_modal()

    def _run_command_stream(self) -> None:
        try:
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in self.process.stdout:
                line_str = line.rstrip("\r\n")
                self.app.call_from_thread(self._append_line, line_str)
            self.process.wait()
        except (OSError, subprocess.SubprocessError) as e:
            self.app.call_from_thread(self._append_line, f"Execution Error: {e}")

        self.app.call_from_thread(self._finish_stream)

    def _append_line(self, line: str) -> None:
        log = self.query_one("#log", RichLog)
        if self.no_formatting:
            log.write(Text(line))
        else:
            log.write(Text.from_ansi(line))

    def _finish_stream(self) -> None:
        footer = self.query_one("#footer", Label)
        footer.update(" [ESC/ENTER]: Close | [UP/DN/PgUp/PgDn]: Scroll ")

    def action_close_modal(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:  # noqa: BLE001, S110
                pass
        self.dismiss(None)


class RichHelpModalScreen(MessageModalScreen):
    """Modal screen displaying Rich Text and BBCode tags reference with examples."""

    def __init__(
        self,
        title: str = "Rich Text & BBCode Tags Reference",
        theme: dict | None = None,
        custom_help_text: str | None = None,
    ):
        help_content = custom_help_text if custom_help_text is not None else RICH_REFERENCE_HELP_TEXT
        super().__init__(
            title=title,
            message=help_content,
            theme=theme,
            is_help=True,
            no_formatting=False,
            is_markdown=False,
        )


class NotebookDumper(yaml.SafeDumper):
    """YAML safe dumper that indents sequences under mapping keys."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow=False, indentless=False)


def _multiline_str_representer(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


NotebookDumper.add_representer(str, _multiline_str_representer)


def load_notebook(filepath: str) -> dict:
    """Load notebook YAML data from filepath.

    If file does not exist, initialize an empty notebook with title derived
    from the filename and save it.
    """
    expanded_path = os.path.expanduser(filepath)
    if not os.path.exists(expanded_path):
        base = os.path.splitext(os.path.basename(expanded_path))[0]
        title = base.replace("_", " ").title() if base else "Notebook"
        data = {
            "notebook": {
                "title": title,
                "format": "markdown",
                "notes": [],
            }
        }
        save_notebook(expanded_path, data)
        return data

    with open(expanded_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        data = {}
    if "notebook" not in data or not isinstance(data["notebook"], dict):
        base = os.path.splitext(os.path.basename(expanded_path))[0]
        title = base.replace("_", " ").title() if base else "Notebook"
        data["notebook"] = {"title": title, "format": "markdown", "notes": []}
    if "notes" not in data["notebook"] or not isinstance(data["notebook"]["notes"], list):
        data["notebook"]["notes"] = []
    return data


def save_notebook(filepath: str, notebook_data: dict) -> None:
    """Save notebook data dictionary to YAML file using clean indentation and literal multiline blocks."""
    expanded_path = os.path.expanduser(filepath)
    dir_name = os.path.dirname(expanded_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(expanded_path, "w", encoding="utf-8") as f:
        yaml.dump(
            notebook_data,
            f,
            Dumper=NotebookDumper,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )


def get_notebook_notes(notebook_data: dict) -> list[tuple[str, dict]]:
    """Extract list of (title, note_dict) from notebook data.

    Supports label-as-key notes:
      - Title: { type: note, content: ... }
    and explicit title mapping:
      - { title: Title, content: ... }
    """
    if not isinstance(notebook_data, dict):
        return []
    nb = notebook_data.get("notebook", {})
    if not isinstance(nb, dict):
        return []
    raw_notes = nb.get("notes", [])
    if not isinstance(raw_notes, list):
        return []

    result = []
    for item in raw_notes:
        if isinstance(item, dict):
            if len(item) == 1 and "title" not in item:
                title, props = next(iter(item.items()))
                if isinstance(props, dict):
                    result.append((str(title), props))
                else:
                    result.append((str(title), {"content": str(props or ""), "type": "note"}))
            elif "title" in item:
                title = item.get("title", "Untitled")
                result.append((str(title), item))
    return result


def get_note_by_title(notebook_data: dict, title: str) -> dict | None:
    """Find note dictionary by title."""
    for n_title, n_dict in get_notebook_notes(notebook_data):
        if n_title == title:
            return n_dict
    return None


def add_or_update_note(
    notebook_data: dict,
    title: str,
    content: str,
    note_type: str = "note",
    note_format: str = "markdown",
    orig_title: str | None = None,
) -> None:
    """Add a new note or update an existing note in the notebook data dictionary."""
    if "notebook" not in notebook_data or not isinstance(notebook_data["notebook"], dict):
        notebook_data["notebook"] = {"title": "Notebook", "format": "markdown", "notes": []}
    notes_list = notebook_data["notebook"].setdefault("notes", [])

    target_title = orig_title if orig_title is not None else title
    updated = False

    for idx, item in enumerate(notes_list):
        if isinstance(item, dict):
            if len(item) == 1 and "title" not in item:
                k = next(iter(item.keys()))
                if k == target_title:
                    props = item[k] if isinstance(item[k], dict) else {}
                    props["type"] = note_type
                    props["format"] = note_format
                    props["content"] = content
                    notes_list[idx] = {title: props}
                    updated = True
                    break
            elif item.get("title") == target_title:
                props = {k: v for k, v in item.items() if k != "title"}
                props["type"] = note_type
                props["format"] = note_format
                props["content"] = content
                notes_list[idx] = {title: props}
                updated = True
                break

    if not updated:
        notes_list.append({
            title: {
                "type": note_type,
                "format": note_format,
                "content": content,
            }
        })


def rename_note(notebook_data: dict, old_title: str, new_title: str) -> bool:
    """Rename a note in the notebook data dictionary while preserving its content, format, and position."""
    if "notebook" not in notebook_data or not isinstance(notebook_data["notebook"], dict):
        return False
    notes_list = notebook_data["notebook"].get("notes", [])
    if not isinstance(notes_list, list):
        return False

    for idx, item in enumerate(notes_list):
        if isinstance(item, dict):
            if len(item) == 1 and "title" not in item:
                k = next(iter(item.keys()))
                if k == old_title:
                    props = item[k]
                    notes_list[idx] = {new_title: props}
                    return True
            elif item.get("title") == old_title:
                props = {k: v for k, v in item.items() if k != "title"}
                notes_list[idx] = {new_title: props}
                return True
    return False


def delete_note(notebook_data: dict, title: str) -> bool:
    """Remove a note by title from notebook data."""
    if "notebook" not in notebook_data or not isinstance(notebook_data["notebook"], dict):
        return False
    notes_list = notebook_data["notebook"].get("notes", [])
    if not isinstance(notes_list, list):
        return False

    del_idx = None
    for idx, item in enumerate(notes_list):
        if isinstance(item, dict):
            if len(item) == 1 and "title" not in item:
                k = next(iter(item.keys()))
                if k == title:
                    del_idx = idx
                    break
            elif item.get("title") == title:
                del_idx = idx
                break

    if del_idx is not None:
        notes_list.pop(del_idx)
        return True
    return False


def get_shared_cutbuffer_path() -> str:
    """Return path to shared cutbuffer fallback file (~/.cache/bashmenu/cutbuffer.txt)."""
    cache_dir = os.environ.get("CACHE_DIR") or os.environ.get("XDG_CACHE_HOME")
    if not cache_dir:
        cache_dir = os.path.expanduser("~/.cache/bashmenu")
    else:
        cache_dir = os.path.expanduser(cache_dir)
        if not cache_dir.endswith("bashmenu"):
            cache_dir = os.path.join(cache_dir, "bashmenu")
    with contextlib.suppress(Exception):
        os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "cutbuffer.txt")


def get_system_clipboard() -> str | None:
    """Read plain text from system clipboard using platform tools or shared cutbuffer fallback."""
    candidates = [
        ["wl-paste", "--no-newline"],
        ["wl-paste"],
        ["pbpaste"],
        ["termux-clipboard-get"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
        ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
    ]
    for cmd in candidates:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=1, check=False)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:  # noqa: BLE001, S110
            pass

    # Fallback to shared cutbuffer file if platform CLI tool is unavailable
    try:
        cb_path = get_shared_cutbuffer_path()
        if os.path.isfile(cb_path):
            with open(cb_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def set_system_clipboard(text: str) -> bool:
    """Copy text to system clipboard using platform tools and shared cutbuffer fallback."""
    if text is None:
        return False
    success = False
    candidates = [
        ["wl-copy"],
        ["pbcopy"],
        ["termux-clipboard-set"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["clip.exe"],
    ]
    for cmd in candidates:
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=1)
            if p.returncode == 0:
                success = True
                break
        except Exception:  # noqa: BLE001, S110
            pass

    # Always persist to shared cutbuffer file for cross-interface consistency
    try:
        cb_path = get_shared_cutbuffer_path()
        with open(cb_path, "w", encoding="utf-8") as f:
            f.write(text)
        success = True
    except Exception:  # noqa: BLE001, S110
        pass

    return success


TASK_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+\[([ xX])\]\s*(.*)$")


class MarkdownCheckbox(Checkbox):
    """Interactive markdown task list item supporting multi-line text wrapping."""

    DEFAULT_CSS = """
    MarkdownCheckbox {
        width: 100%;
        height: auto;
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
        text-wrap: wrap;
    }
    MarkdownCheckbox:focus {
        background: $accent 25%;
    }
    MarkdownCheckbox:hover {
        background: $accent 15%;
    }
    """

    def __init__(
        self,
        raw_text: str,
        value: bool = False,
        indent: str = "",
        line_idx: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(raw_text, value=value, **kwargs)
        self.raw_text = raw_text
        self.indent = indent
        self._line_idx = line_idx

    @property
    def label(self) -> str:
        return self.raw_text

    def _get_wrapped_lines(self, width: int) -> list[str]:
        inner_w = max(10, width - 2 - len(self.indent))
        text_w = max(10, inner_w - 4)
        return textwrap.wrap(self.raw_text, width=text_w) or [self.raw_text]

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        lines = self._get_wrapped_lines(width)
        return len(lines)

    def render(self) -> Text:
        w = max(20, self.size.width or 80)
        wrapped = self._get_wrapped_lines(w)
        box_prefix = "[x] " if self.value else "[ ] "
        box_len = 4
        result = Text()
        ind = self.indent

        box_style = Style(color="green", bold=True) if self.value else Style(color="yellow", bold=True)
        text_style = Style(dim=True) if self.value else Style()

        for i, line in enumerate(wrapped):
            if i > 0:
                result.append("\n")
            if i == 0:
                result.append(ind)
                result.append(box_prefix, style=box_style)
                result.append(line, style=text_style)
            else:
                result.append(ind + (" " * box_len))
                result.append(line, style=text_style)

        return result


class NoteViewerModalScreen(ModalScreen[str | None]):
    """Modal screen to view a formatted notebook note in Markdown or BBCode."""

    DEFAULT_CSS = """
    NoteViewerModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #modal_frame {
        width: 80%;
        height: 80%;
        max-width: 100;
        max-height: 90%;
    }
    NoteViewerModalScreen #dialog_hrow {
        width: 1fr;
        height: 1fr;
    }
    #dialog {
        width: 1fr;
        height: 100%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #scroll_container {
        height: 1fr;
        max-height: 100%;
        overflow-x: hidden;
    }
    #message {
        width: 100%;
        height: auto;
    }
    .markdown_block {
        width: 100%;
        height: auto;
    }
    MarkdownCheckbox.markdown_checkbox, Checkbox.markdown_checkbox {
        border: none;
        padding: 0;
        margin: 0;
        height: auto;
        width: 100%;
        background: transparent;
        text-wrap: wrap;
    }
    MarkdownCheckbox.markdown_checkbox:focus, Checkbox.markdown_checkbox:focus {
        background: $accent 25%;
    }
    MarkdownCheckbox.markdown_checkbox:hover, Checkbox.markdown_checkbox:hover {
        background: $accent 15%;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close_modal", "Close"),
        Binding("enter", "close_modal", "Close"),
        Binding("h", "toggle_completed", "Toggle Completed"),
        Binding("H", "toggle_completed", "Toggle Completed", show=False),
        Binding("ctrl+h", "toggle_completed", "Toggle Completed", show=False),
        Binding("c", "copy_note", "Copy"),
        Binding("ctrl+c", "copy_note", "Copy", show=False),
        Binding("ctrl+shift+c", "copy_note", "Copy", show=False),
        Binding("e", "edit_note", "Edit"),
        Binding("m", "rename_note", "Rename"),
        Binding("M", "rename_note", "Rename", show=False),
        Binding("d", "delete_note", "Delete"),
    ]

    def __init__(
        self,
        title: str,
        content: str,
        note_format: str = "markdown",
        theme: dict | None = None,
        filepath: str = "",
        note_title: str = "",
        on_content_change: Callable[[str], None] | None = None,
        show_completed: bool = False,
    ):
        super().__init__()
        self.modal_title = title
        self.note_title = note_title or title
        self.content = content or ""
        self.note_format = (note_format or "markdown").lower()
        self.theme = theme or {}
        self.filepath = filepath
        self.on_content_change = on_content_change
        self.show_completed = show_completed
        self.lines: list[str] = self.content.split("\n")

    def _get_footer_text(self, has_checkboxes: bool) -> str:
        """Return the footer help gutter text reflecting current checkbox toggle state."""
        if has_checkboxes:
            toggle_action = "Hide Done" if self.show_completed else "Show Done"
            return f"[SPACE] Toggle | [H] {toggle_action} | [C] Copy | [E] Edit | [M] Rename | [D] Delete | [ESC/ENTER] Close"
        return "[C] Copy | [E] Edit | [M] Rename | [D] Delete | [ESC/ENTER] Close"

    def _parse_blocks(self) -> list[tuple[str, Any]]:
        """Parse note content lines into alternating markdown blocks and interactive checkbox items."""
        blocks = []
        current_md = []
        in_fence = False
        fence_token = ""

        for line_idx, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                if not in_fence:
                    in_fence = True
                    fence_token = stripped[:3]
                elif stripped.startswith(fence_token):
                    in_fence = False
                    fence_token = ""
                current_md.append(line)
                continue

            if in_fence:
                current_md.append(line)
                continue

            m = TASK_LIST_RE.match(line)
            if m:
                if current_md:
                    blocks.append(("markdown", "\n".join(current_md)))
                    current_md = []
                indent, marker, check_char, text = m.groups()
                is_checked = check_char.lower() == "x"
                blocks.append(("checkbox", line_idx, indent, marker, is_checked, text))
            else:
                current_md.append(line)

        if current_md:
            blocks.append(("markdown", "\n".join(current_md)))

        return blocks

    def compose(self) -> ComposeResult:
        blocks = self._parse_blocks() if self.note_format == "markdown" else []
        has_checkboxes = any(b[0] == "checkbox" for b in blocks)

        def _render_dialog():
            with Horizontal(id="title_bar"):
                yield Label(self.modal_title or "Note", id="title")
                yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
            with VerticalScroll(id="scroll_container"):
                if not self.content.strip():
                    yield Static(Markdown("*(Empty note — click Edit to add content)*"), id="message")
                elif self.note_format == "bbcode":
                    rendered = formatting_to_rich_text(self.content, theme=self.theme)
                    yield Static(rendered, id="message")
                elif not has_checkboxes:
                    yield Static(Markdown(self.content, hyperlinks=True), id="message")
                else:
                    for b in blocks:
                        if b[0] == "markdown":
                            md_text = b[1]
                            if md_text.strip():
                                yield Static(Markdown(md_text, hyperlinks=True), classes="markdown_block")
                        elif b[0] == "checkbox":
                            line_idx, indent, _, is_checked, text = b[1], b[2], b[3], b[4], b[5]
                            cb = MarkdownCheckbox(
                                text,
                                value=is_checked,
                                indent=indent or "",
                                line_idx=line_idx,
                                classes="markdown_checkbox",
                                id=f"cb_{line_idx}",
                            )
                            if is_checked and not self.show_completed:
                                cb.display = False
                            yield cb
            with Horizontal(id="buttons"):
                yield Button("Copy [C]", variant="default", id="btn_copy")
                yield Button("Edit [E]", variant="primary", id="btn_edit")
                yield Button("Rename [M]", variant="default", id="btn_rename")
                yield Button("Delete [D]", variant="error", id="btn_delete")
                yield Button("Close [ESC]", variant="default", id="btn_close")
            yield Label(self._get_footer_text(has_checkboxes), id="footer", markup=False)

        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    yield from _render_dialog()
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_copy", Button), theme=self.theme, button_type="button_default")
            apply_button_theme(self.query_one("#btn_edit", Button), theme=self.theme, button_type="button_primary")
            apply_button_theme(self.query_one("#btn_rename", Button), theme=self.theme, button_type="button_default")
            apply_button_theme(self.query_one("#btn_delete", Button), theme=self.theme, button_type="button_danger")
            apply_button_theme(self.query_one("#btn_close", Button), theme=self.theme, button_type="button_default")

        visible_cbs = [cb for cb in self.query(Checkbox) if cb.display]
        if visible_cbs:
            visible_cbs[0].focus()
        else:
            with contextlib.suppress(Exception):
                self.query_one("#btn_close", Button).focus()

    def on_key(self, event: events.Key) -> None:
        if isinstance(self.focused, Checkbox):
            cbs = [cb for cb in self.query(Checkbox) if cb.display]
            if self.focused in cbs:
                idx = cbs.index(self.focused)
                if event.key in ("down", "j") and idx < len(cbs) - 1:
                    cbs[idx + 1].focus()
                    event.prevent_default()
                    event.stop()
                elif event.key in ("up", "k") and idx > 0:
                    cbs[idx - 1].focus()
                    event.prevent_default()
                    event.stop()

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        line_idx = getattr(event.checkbox, "_line_idx", None)
        if line_idx is not None and 0 <= line_idx < len(self.lines):
            m = TASK_LIST_RE.match(self.lines[line_idx])
            if m:
                indent, marker, _old_val, text = m.groups()
                new_mark = "x" if event.checkbox.value else " "
                self.lines[line_idx] = f"{indent}{marker} [{new_mark}] {text}"
                self.content = "\n".join(self.lines)

                if self.filepath and self.note_title:
                    with contextlib.suppress(Exception):
                        nb_data = load_notebook(self.filepath)
                        add_or_update_note(nb_data, self.note_title, self.content)
                        save_notebook(self.filepath, nb_data)

                if self.on_content_change:
                    with contextlib.suppress(Exception):
                        self.on_content_change(self.content)

    def action_toggle_completed(self) -> None:
        """Toggle visibility of completed checkboxes in view mode."""
        blocks = self._parse_blocks() if self.note_format == "markdown" else []
        has_checkboxes = any(b[0] == "checkbox" for b in blocks)
        if not has_checkboxes:
            return

        self.show_completed = not self.show_completed
        for cb in self.query(MarkdownCheckbox):
            if cb.value:
                cb.display = self.show_completed

        with contextlib.suppress(Exception):
            footer = self.query_one("#footer", Label)
            footer.update(self._get_footer_text(has_checkboxes=True))

        visible_cbs = [cb for cb in self.query(Checkbox) if cb.display]
        if self.focused not in visible_cbs:
            if visible_cbs:
                visible_cbs[0].focus()
            else:
                with contextlib.suppress(Exception):
                    self.query_one("#btn_close", Button).focus()

        msg = "Showing completed tasks" if self.show_completed else "Hiding completed tasks"
        with contextlib.suppress(Exception):
            self.notify(msg, timeout=1.5)

    def action_copy_note(self) -> None:
        """Copy raw note markdown text to system clipboard and shared cutbuffer."""
        text = self.content
        set_system_clipboard(text)
        with contextlib.suppress(Exception):
            self.app.copy_to_clipboard(text)
        with contextlib.suppress(Exception):
            self.notify("Note copied to clipboard", timeout=2.0)

    def action_edit_note(self) -> None:
        self.dismiss("edit")

    def action_rename_note(self) -> None:
        self.dismiss("rename")

    def action_delete_note(self) -> None:
        self.dismiss("delete")

    def action_close_modal(self) -> None:
        self.dismiss("close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_copy":
            self.action_copy_note()
        elif event.button.id == "btn_edit":
            self.action_edit_note()
        elif event.button.id == "btn_rename":
            self.action_rename_note()
        elif event.button.id == "btn_delete":
            self.action_delete_note()
        elif event.button.id in ("btn_close", "btn_close_x"):
            self.action_close_modal()

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.action_close_modal()


class NotebookTextArea(TextArea):
    """Enhanced TextArea for notes with markdown auto-formatting, ghost text, and unified clipboard."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "copy", "Copy"),
        Binding("ctrl+shift+c", "copy", "Copy", show=False),
        Binding("ctrl+x", "cut", "Cut"),
        Binding("ctrl+shift+x", "cut", "Cut", show=False),
        Binding("ctrl+v", "paste", "Paste"),
        Binding("ctrl+shift+v", "paste", "Paste", show=False),
    ]

    def __init__(self, *args, auto_format: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_format = auto_format

    def edit(self, edit: Edit) -> EditResult:
        """Perform an edit and ensure the cursor is scrolled into view immediately."""
        result = super().edit(edit)
        if self.is_mounted:
            self.scroll_cursor_visible(center=False, animate=False)
            self.call_after_refresh(self.scroll_cursor_visible, center=False, animate=False)
        return result

    def action_copy(self) -> None:
        """Copy selection (or current line if no selection) to unified clipboard."""
        text = self.selected_text
        if not text:
            row, _ = self.cursor_location
            if row < self.document.line_count:
                text = self.document.get_line(row)
        if text:
            set_system_clipboard(text)
            with contextlib.suppress(Exception):
                self.app.copy_to_clipboard(text)

    def action_cut(self) -> None:
        """Cut selection (or current line if no selection) to unified clipboard."""
        if self.read_only:
            return
        start, end = self.selection
        if start == end:
            edit_result = self._delete_cursor_line()
        else:
            edit_result = self._delete_via_keyboard(start, end)
        if edit_result is not None:
            text = edit_result.replaced_text
            set_system_clipboard(text)
            with contextlib.suppress(Exception):
                self.app.copy_to_clipboard(text)

    def action_paste(self) -> None:
        """Paste from system clipboard (or shared cutbuffer fallback) at cursor position."""
        if self.read_only:
            return
        clip = get_system_clipboard()
        if not clip:
            with contextlib.suppress(Exception):
                clip = self.app.clipboard
        if clip and (result := self._replace_via_keyboard(clip, *self.selection)):
            self.move_cursor(result.end_location)

    def update_suggestion(self) -> None:
        """Hook to compute faint ghost text suggestion for markdown formatting."""
        if not self.auto_format or self.read_only:
            self.suggestion = ""
            return

        row, col = self.cursor_location
        if row >= self.document.line_count:
            self.suggestion = ""
            return

        line = self.document.get_line(row)
        prefix = line[:col]

        # 1. Partial checkbox bracket: e.g. "- [", "* [", "+ [", "1. [" -> suggest " ] "
        if re.search(r"^\s*([-*+]|\d+[.)])\s+\[$", prefix):
            self.suggestion = " ] "
            return

        # 2. Checkbox bracket with space: e.g. "- [ " -> suggest "] "
        if re.search(r"^\s*([-*+]|\d+[.)])\s+\[\s+$", prefix):
            self.suggestion = "] "
            return

        self.suggestion = ""

    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses with markdown list continuation and ghost text completion."""
        self._restart_blink()

        if self.read_only:
            return

        # Handle Tab to accept suggestion if ghost text is present
        if event.key == "tab" and self.suggestion:
            event.stop()
            event.prevent_default()
            sug = self.suggestion
            self.suggestion = ""
            self.insert(sug)
            return

        # Handle Enter for auto-formatting continuation / de-escalation
        if event.key == "enter" and self.auto_format and self._handle_auto_format_enter():
            event.stop()
            event.prevent_default()
            return

        await super()._on_key(event)

    def _handle_auto_format_enter(self) -> bool:
        """Inspect current line and insert continuation prefix or de-escalate empty marker."""
        row, col = self.cursor_location
        if row >= self.document.line_count:
            return False

        line = self.document.get_line(row)
        prefix = line[:col]

        # 1. Checkbox item: - [ ] text, * [x] text, + [ ] text, 1. [ ] text
        m_box = re.match(r"^(\s*)([-*+]|\d+[.)])\s+\[([ xX])\]\s*(.*)$", prefix)
        if m_box:
            indent, marker, _check_val, item_text = m_box.groups()
            if item_text.strip() == "":
                # De-escalate empty checkbox
                self._replace_via_keyboard(indent, (row, 0), (row, len(line)))
                self.suggestion = ""
                return True
            # Compute next checkbox marker
            if marker in ("-", "*", "+"):
                next_prefix = f"{indent}{marker} [ ] "
            else:
                delim = marker[-1]
                num = int(marker[:-1]) + 1
                next_prefix = f"{indent}{num}{delim} [ ] "
            self._replace_via_keyboard("\n" + next_prefix, *self.selection)
            self.suggestion = ""
            return True

        # 2. Ordered list item: 1. text, 2) text
        m_num = re.match(r"^(\s*)(\d+)([.)])\s+(.*)$", prefix)
        if m_num:
            indent, num_str, delim, item_text = m_num.groups()
            if item_text.strip() == "":
                # De-escalate empty numbered item
                self._replace_via_keyboard(indent, (row, 0), (row, len(line)))
                self.suggestion = ""
                return True
            next_num = int(num_str) + 1
            next_prefix = f"{indent}{next_num}{delim} "
            self._replace_via_keyboard("\n" + next_prefix, *self.selection)
            self.suggestion = ""
            return True

        # 3. Unordered list item: - text, * text, + text
        m_bullet = re.match(r"^(\s*)([-*+])\s+(.*)$", prefix)
        if m_bullet:
            indent, marker, item_text = m_bullet.groups()
            if item_text.strip() == "":
                # De-escalate empty bullet
                self._replace_via_keyboard(indent, (row, 0), (row, len(line)))
                self.suggestion = ""
                return True
            next_prefix = f"{indent}{marker} "
            self._replace_via_keyboard("\n" + next_prefix, *self.selection)
            self.suggestion = ""
            return True

        # 4. Blockquote item: > text, >> text
        m_quote = re.match(r"^(\s*)(>+)\s*(.*)$", prefix)
        if m_quote:
            indent, marker, item_text = m_quote.groups()
            if item_text.strip() == "":
                # De-escalate empty quote
                self._replace_via_keyboard(indent, (row, 0), (row, len(line)))
                self.suggestion = ""
                return True
            next_prefix = f"{indent}{marker} "
            self._replace_via_keyboard("\n" + next_prefix, *self.selection)
            self.suggestion = ""
            return True

        return False


class NoteEditorModalScreen(ModalScreen[str | None]):
    """Modal screen for editing note content using a Textual TextArea."""

    DEFAULT_CSS = """
    NoteEditorModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #modal_frame {
        width: 85%;
        height: 85%;
        max-width: 110;
        max-height: 90%;
    }
    NoteEditorModalScreen #dialog_hrow {
        width: 1fr;
        height: 1fr;
    }
    #dialog {
        width: 1fr;
        height: 100%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    .btn_close_x:focus {
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
    }
    #text_editor {
        height: 1fr;
        width: 100%;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "save_note", "Save"),
        Binding("escape", "cancel_note", "Cancel"),
        Binding("ctrl+c", "copy_text", "Copy", show=False),
        Binding("ctrl+shift+c", "copy_text", "Copy", show=False),
        Binding("ctrl+v", "paste_text", "Paste", show=False),
        Binding("ctrl+shift+v", "paste_text", "Paste", show=False),
        Binding("ctrl+x", "cut_text", "Cut", show=False),
        Binding("ctrl+shift+x", "cut_text", "Cut", show=False),
    ]

    def __init__(
        self,
        title: str,
        content: str = "",
        note_format: str = "markdown",
        theme: dict | None = None,
        auto_format: bool = True,
    ):
        super().__init__()
        self.modal_title = title
        self.initial_content = content or ""
        self.note_format = (note_format or "markdown").lower()
        self.theme = theme or {}
        self.auto_format = auto_format

    def compose(self) -> ComposeResult:
        lang = "markdown" if self.note_format == "markdown" else None

        def _render_dialog():
            with Horizontal(id="title_bar"):
                yield Label(self.modal_title or "Edit Note", id="title")
                yield Label(format_close_button_label(), id="btn_close_x", classes="btn_close_x")
            yield NotebookTextArea(
                text=self.initial_content,
                language=lang,
                theme="vscode_dark",
                soft_wrap=True,
                auto_format=self.auto_format,
                id="text_editor",
            )
            with Horizontal(id="buttons"):
                yield Button("Save [Ctrl+S]", variant="primary", id="btn_save")
                yield Button("Cancel [ESC]", variant="default", id="btn_cancel")
            yield Label("[Ctrl+S] Save | [Ctrl+C] Copy | [Ctrl+V] Paste | [ESC] Cancel", id="footer", markup=False)

        with ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    yield from _render_dialog()
                yield ShadowWidget(id="shadow_right")
            yield ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_save", Button), theme=self.theme, button_type="button_primary")
            apply_button_theme(self.query_one("#btn_cancel", Button), theme=self.theme, button_type="button_default")
        self.call_after_refresh(self._focus_editor)

    def _focus_editor(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#text_editor", NotebookTextArea).focus()

    def action_save_note(self) -> None:
        try:
            editor = self.query_one("#text_editor", NotebookTextArea)
            self.dismiss(editor.text)
        except (LookupError, AttributeError):
            self.dismiss(self.initial_content)

    def action_cancel_note(self) -> None:
        self.dismiss(None)

    def action_copy_text(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#text_editor", NotebookTextArea).action_copy()

    def action_paste_text(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#text_editor", NotebookTextArea).action_paste()

    def action_cut_text(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#text_editor", NotebookTextArea).action_cut()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.action_save_note()
        elif event.button.id in ("btn_cancel", "btn_close_x"):
            self.action_cancel_note()

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.action_cancel_note()


# Fallback synchronous wrapper functions (for headless / standalone use)
def show_popup_message(stdscr, title, message, theme=None):
    """Fallback helper."""
    print(f"[{title}] {message}")


def show_confirm_box(stdscr, title, message, theme=None):
    """Fallback helper."""
    return "yes"


def show_toggle_box(stdscr, title, message, theme=None):
    """Fallback helper."""
    return "true"


def show_input_box(stdscr, title, prompt, default_text="", theme=None, masked=False):
    """Fallback helper."""
    return default_text


def show_file_picker(
    stdscr,
    title,
    start_dir="~",
    mode="file",
    default_val=None,
    theme=None,
    show_hidden=False,
    allow_new=False,
):
    """Fallback helper."""
    return start_dir
