"""
bashmenu_ui.py - Reusable Textual TUI primitives, modal screens, text formatting and theme utilities.
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import ClassVar

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


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
    ]:
        return True
    return content_clean.startswith("color=") and "]" not in content_clean


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
    )


def get_char_width(c: str, config=None) -> int:
    """
    Get the display width of a single character in terminal columns.
    """
    if not c:
        return 0
    if 0xFE00 <= ord(c) <= 0xFE0F:
        return 0
    if is_pua_glyph(c):
        return get_nerd_font_width(config)
    if unicodedata.east_asian_width(c) in ("W", "F"):
        return 2
    return 1


def get_display_width(s: str, config=None) -> int:
    """
    Calculate the visual display width of a string on screen in terminal columns.
    """
    if not s:
        return 0
    total = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        cp = ord(c)

        if i + 1 < n and s[i + 1] == "\uFE0F":
            total += 2
            i += 2
            continue

        if 0xFE00 <= cp <= 0xFE0F:
            i += 1
            continue

        if is_pua_glyph(c):
            total += get_nerd_font_width(config)
            i += 1
            continue

        if is_emoji_char(c) or unicodedata.east_asian_width(c) in ("W", "F"):
            total += 2
            i += 1
            continue

        if unicodedata.category(c).startswith("M"):
            i += 1
            continue

        total += 1
        i += 1

    return total


def get_visible_len(text, config=None) -> int:
    """
    Return the visible length of a string by stripping formatting tags [tag].
    """
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")

    def replace_tag(match):
        tag = match.group(1)
        if is_formatting_tag(tag):
            return ""
        return match.group(0)

    clean_text = tag_pattern.sub(replace_tag, text)
    return get_display_width(clean_text, config)


def parse_formatting_to_segments(text, base_attr=0, theme=None):
    """
    Parse console bracket formatting tags [b], [u], [dim], [reverse], [color=...] and
    return a list of (text, attr) segments for backward compatibility.
    """
    if not isinstance(text, str):
        text = str(text)

    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")
    segments = []
    current_attr = base_attr
    attr_stack = [current_attr]
    last_idx = 0

    for match in tag_pattern.finditer(text):
        tag = match.group(1)
        if not is_formatting_tag(tag):
            continue

        start, end = match.span()
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


def formatting_to_rich_text(text: str, default_style: Style | None = None, theme: dict | None = None) -> Text:
    """
    Convert custom bracket formatting ([b], [u], [dim], [color=name]) into a Rich Text object.
    """
    if not isinstance(text, str):
        text = str(text)

    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")
    rich_text = Text()

    current_style = default_style or Style()
    style_stack = [current_style]
    last_idx = 0

    for match in tag_pattern.finditer(text):
        tag = match.group(1)
        if not is_formatting_tag(tag):
            continue

        start, end = match.span()
        if start > last_idx:
            rich_text.append(text[last_idx:start], style=current_style)

        if tag.startswith("/"):
            if len(style_stack) > 1:
                style_stack.pop()
                current_style = style_stack[-1]
        else:
            tag_clean = tag.strip().lower()
            new_style = current_style
            if tag_clean == "b":
                new_style = new_style + Style(bold=True)
            elif tag_clean == "u":
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
                    except Exception:
                        pass

            style_stack.append(new_style)
            current_style = new_style

        last_idx = end

    if last_idx < len(text):
        rich_text.append(text[last_idx:], style=current_style)

    return rich_text


def strip_formatting_tags(text: str) -> str:
    """
    Strip all bracketed formatting tags [b], [color=...], etc.
    """
    if not isinstance(text, str):
        text = str(text)
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")

    def replace_tag(match):
        tag = match.group(1)
        if is_formatting_tag(tag):
            return ""
        return match.group(0)

    return tag_pattern.sub(replace_tag, text)


def safe_addstr_segments(win, y, x=None, segments=None, config=None):
    """Compatibility shim."""


def safe_addstr(win, y_or_text, x_or_attr=None, text_or_none=None, attr=0):
    """Compatibility shim."""


def draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme=None):
    """Compatibility shim."""


# ==============================================================================
# THEME PARSING AND CONVERSION
# ==============================================================================

COLOR_MAP = {
    "COLOR_BLACK": "black",
    "COLOR_RED": "red",
    "COLOR_GREEN": "green",
    "COLOR_YELLOW": "yellow",
    "COLOR_BLUE": "blue",
    "COLOR_MAGENTA": "magenta",
    "COLOR_CYAN": "cyan",
    "COLOR_WHITE": "white",
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
        return val
    return None


def init_theme_colors(theme_name: str = "dracula", raw_theme_data: dict | None = None) -> dict:
    """
    Initialize theme data and construct Rich Style mapping for elements.
    """
    if not raw_theme_data:
        raw_theme_data = {}

    theme_def = raw_theme_data.get(theme_name, {})
    if not theme_def and raw_theme_data:
        theme_def = next(iter(raw_theme_data.values()), {})

    palette = theme_def.get(256, theme_def.get(16, theme_def.get(8, {})))
    indicator = theme_def.get("indicator", ">")

    styles = {}
    for key, spec in palette.items():
        if isinstance(spec, list) and len(spec) >= 2:
            fg = parse_color_val(spec[0])
            bg = parse_color_val(spec[1])
            styles[key] = Style(color=fg, bgcolor=bg)
        elif isinstance(spec, str):
            styles[key] = Style(color=parse_color_val(spec))
        else:
            styles[key] = Style()

    # Provide fallback styles if keys are missing
    default_text = styles.get("text", Style(color="white"))
    styles.setdefault("title", Style(color="magenta", bold=True))
    styles.setdefault("border", Style(color="blue"))
    styles.setdefault("text", default_text)
    styles.setdefault("highlight", Style(color="white", bgcolor="magenta", bold=True))
    styles.setdefault("accent", Style(color="cyan"))
    styles.setdefault("footer", Style(color="blue"))
    styles.setdefault("shadow", Style(color="black", dim=True))
    styles.setdefault("gutter", Style(color="blue"))
    styles.setdefault("selection", Style(color="white", bgcolor="blue"))
    styles.setdefault("status_bar", Style(color="black", bgcolor="cyan"))
    styles.setdefault("shortcut_key", Style(color="magenta", bold=True))
    styles.setdefault("shortcut_label", Style(color="white"))
    styles.setdefault("divider", Style(color="blue"))
    styles.setdefault("background", Style(bgcolor="black"))
    styles["indicator"] = indicator

    return styles


def load_themes_file(filepath: str | None = None) -> dict:
    """
    Load bashmenu.themes file and parse YAML.
    """
    import yaml

    if not filepath or not os.path.exists(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(base_dir, "bashmenu.themes")

    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ==============================================================================
# TEXTUAL MODAL SCREENS
# ==============================================================================


class MessageModalScreen(ModalScreen[None]):
    """Modal screen to display popup messages."""

    DEFAULT_CSS = """
    MessageModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #scroll_container {
        height: auto;
        max-height: 15;
    }
    #message {
        width: 100%;
    }
    #footer {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close_modal", "Close"),
        Binding("enter", "close_modal", "Close"),
    ]

    def __init__(self, title: str, message: str, theme: dict | None = None):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            if self.modal_title:
                yield Label(self.modal_title, id="title")
            with VerticalScroll(id="scroll_container"):
                yield Static(self.message, id="message")
            yield Label("[ENTER/ESC] Close", id="footer")

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
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
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
        with Vertical(id="dialog"):
            if self.modal_title:
                yield Label(self.modal_title, id="title")
            yield Static(self.message, id="message")
            with Horizontal(id="buttons"):
                yield Button("Yes", variant="primary", id="btn_yes")
                yield Button("No", variant="error", id="btn_no")
                yield Button("Cancel", variant="default", id="btn_cancel")

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
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #message {
        text-align: center;
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
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
        with Vertical(id="dialog"):
            if self.modal_title:
                yield Label(self.modal_title, id="title")
            yield Static(self.message, id="message")
            with Horizontal(id="buttons"):
                yield Button("True", variant="success", id="btn_true")
                yield Button("False", variant="error", id="btn_false")
                yield Button("Cancel", variant="default", id="btn_cancel")

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
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
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
    }
    Button {
        margin: 0 1;
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
        with Vertical(id="dialog"):
            if self.modal_title:
                yield Label(self.modal_title, id="title")
            if self.prompt:
                yield Static(self.prompt, id="prompt")
            yield Input(
                value=self.default_text,
                password=self.masked,
                id="input",
            )
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="btn_ok")
                yield Button("Cancel", variant="default", id="btn_cancel")

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

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
        width: 80;
        height: 24;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
    }
    #path_label {
        color: $text-muted;
        margin-bottom: 1;
    }
    #options_list {
        height: 14;
        border: solid $accent;
    }
    #footer {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+h", "toggle_hidden", "Toggle Hidden"),
        Binding("space", "select_dir", "Select Folder"),
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
        self.show_hidden_state = show_hidden
        self.allow_new = allow_new
        self.theme = theme or {}

        resolved_start = os.path.abspath(os.path.expanduser(start_dir))
        if not os.path.exists(resolved_start) or not os.path.isdir(resolved_start):
            resolved_start = str(Path.home())
        self.current_path = resolved_start
        self.entries = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.modal_title or "File Picker", id="title")
            yield Label(f"Path: {self.current_path}", id="path_label")
            yield OptionList(id="options_list")
            yield Label("[ENTER] Open/Select | [ESC] Cancel", id="footer")

    def on_mount(self) -> None:
        self.load_directory()

    def load_directory(self) -> None:
        self.query_one("#path_label", Label).update(f"Path: {self.current_path}")
        options_list = self.query_one("#options_list", OptionList)
        options_list.clear_options()
        self.entries = []

        try:
            with os.scandir(self.current_path) as it:
                all_entries = list(it)

            if not self.show_hidden_state:
                all_entries = [e for e in all_entries if not e.name.startswith(".")]

            dirs = sorted(
                [e for e in all_entries if e.is_dir()],
                key=lambda e: e.name.lower(),
            )
            files = sorted(
                [e for e in all_entries if not e.is_dir()],
                key=lambda e: e.name.lower(),
            )

            if self.current_path != "/":
                parent_path = os.path.dirname(self.current_path)
                self.entries.append(
                    {"name": ".. (Parent Directory)", "is_dir": True, "path": parent_path}
                )
                options_list.add_option(Option("📁 .. (Parent Directory)"))

            if self.mode == "dir":
                self.entries.append(
                    {
                        "name": f"[ Select Current Directory: {os.path.basename(self.current_path) or '/'} ]",
                        "is_dir": True,
                        "path": self.current_path,
                        "is_self": True,
                    }
                )
                options_list.add_option(
                    Option("✔ [ Select Current Directory ]")
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

        except Exception as e:
            options_list.add_option(Option(f"⚠️ Error loading directory: {e}"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if idx < 0 or idx >= len(self.entries):
            return

        selected = self.entries[idx]
        if selected.get("is_self"):
            self.dismiss(selected["path"])
            return

        if selected["is_dir"]:
            self.current_path = selected["path"]
            self.load_directory()
        elif self.mode in ["file", "any"]:
            self.dismiss(selected["path"])

    def action_select_dir(self) -> None:
        if self.mode == "dir":
            self.dismiss(self.current_path)

    def action_toggle_hidden(self) -> None:
        self.show_hidden_state = not self.show_hidden_state
        self.load_directory()

    def action_cancel(self) -> None:
        self.dismiss(None)


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
