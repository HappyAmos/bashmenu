"""
bashmenu_ui.py - Reusable Textual TUI primitives, modal screens, text formatting and theme utilities.
"""

import contextlib
import os
import re
import subprocess
import threading
import unicodedata
from pathlib import Path
from typing import ClassVar

from rich._palettes import EIGHT_BIT_PALETTE
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, RichLog, Static
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


TAG_PATTERN = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")


def get_visible_len(text, config=None) -> int:
    """
    Return the visible length of a string by stripping formatting tags [tag].
    """
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)

    clean_text = strip_formatting_tags(text)
    return get_display_width(clean_text, config)


def parse_formatting_to_segments(text, base_attr=0, theme=None, no_formatting: bool = False):
    """
    Parse console bracket formatting tags [b], [u], [dim], [reverse], [color=...] and
    return a list of (text, attr) segments for backward compatibility.
    """
    if not isinstance(text, str):
        text = str(text)

    if no_formatting:
        return [(text, base_attr)]

    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
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
) -> Text:
    """
    Convert custom bracket formatting ([b], [u], [dim], [color=name]) into a Rich Text object.
    Supports backslash escaping (\\\\[tag]) and suppresses formatting inside backtick code spans/blocks.
    """
    if not isinstance(text, str):
        text = str(text)

    if no_formatting:
        return Text(text, style=default_style or Style())

    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
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
                    except Exception:  # noqa: BLE001, S110
                        pass

            style_stack.append(new_style)
            current_style = new_style

        last_idx = end

    if last_idx < len(text):
        rich_text.append(text[last_idx:], style=current_style)

    return rich_text


def strip_formatting_tags(text: str, no_formatting: bool = False) -> str:
    """
    Strip all bracketed formatting tags [b], [color=...], etc.
    """
    if not isinstance(text, str):
        text = str(text)
    if no_formatting:
        return text

    code_ranges = [m.span() for m in re.finditer(r"```[\s\S]*?```|`[^`\n]+`", text)]
    tag_pattern = re.compile(r"\[(/?[a-zA-Z_0-9=]+)\]")
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
    """Compatibility shim."""


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
        return val
    return None


_themes_file_cache = {}
_theme_styles_cache = {}


def init_theme_colors(theme_name: str = "dracula", raw_theme_data: dict | None = None) -> dict:
    """
    Initialize theme data and construct Rich Style mapping for elements.
    """
    if not raw_theme_data:
        raw_theme_data = load_themes_file()

    cache_key = (theme_name, id(raw_theme_data))
    if cache_key in _theme_styles_cache:
        return _theme_styles_cache[cache_key]

    theme_def = raw_theme_data.get(theme_name, {})
    if not theme_def and raw_theme_data:
        theme_def = next(iter(raw_theme_data.values()), {})

    palette = theme_def.get(256, theme_def.get(16, theme_def.get(8, {})))
    indicator = theme_def.get("indicator", ">")

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
        if isinstance(spec, list) and len(spec) >= 2:
            fg = parse_color_val(spec[0])
            bg = parse_color_val(spec[1]) or bg_color
            styles[key] = Style(color=fg, bgcolor=bg)
        elif isinstance(spec, str):
            styles[key] = Style(color=parse_color_val(spec), bgcolor=bg_color)
        else:
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
    styles.setdefault("status_bar", Style(color="black", bgcolor="cyan"))
    styles.setdefault("shortcut_key", Style(color="magenta", bold=True, bgcolor=bg_color))
    styles.setdefault("shortcut_label", Style(color="white", bgcolor=bg_color))
    styles.setdefault("divider", Style(color="blue", bgcolor=bg_color))
    styles.setdefault("button_primary", Style(color="white", bgcolor="blue"))
    styles.setdefault("button_error", Style(color="white", bgcolor="red"))
    styles.setdefault("button_cancel", Style(color="white", bgcolor="grey37"))
    styles.setdefault("button_success", Style(color="white", bgcolor="green"))
    styles.setdefault("help_text", Style(color="cyan", bgcolor=bg_color))
    styles.setdefault("plugin", Style(color="cyan", bgcolor=bg_color))
    styles["indicator"] = indicator

    _theme_styles_cache[cache_key] = styles
    return styles


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
        config = bashmenu.load_config() if hasattr(bashmenu, "load_config") else {}
        if isinstance(config, dict) and "theme" in config:
            active_name = config.get("theme", "dracula")
            return init_theme_colors(active_name)
    except Exception:  # noqa: BLE001, S110
        pass

    return init_theme_colors("dracula")


def apply_modal_theme(screen: ModalScreen, theme=None) -> None:
    """Apply theme border, background, title, message, prompt, and footer colors to a modal screen."""
    theme_dict = resolve_theme_dict(theme, getattr(screen, "app", None))
    if not theme_dict:
        return
    with contextlib.suppress(Exception):
        dialog = screen.query_one("#dialog")
        border_style = theme_dict.get("border") or theme_dict.get("accent")
        if border_style and border_style.color and border_style.color.name:
            css_border = parse_css_color(border_style.color.name)
            if css_border:
                dialog.styles.border = ("thick", css_border)
        bg_style = theme_dict.get("background")
        if bg_style and bg_style.bgcolor and bg_style.bgcolor.name:
            css_bg = parse_css_color(bg_style.bgcolor.name)
            if css_bg:
                dialog.styles.background = css_bg

    with contextlib.suppress(Exception):
        title = screen.query_one("#title", Label)
        title_style = theme_dict.get("title") or theme_dict.get("accent")
        if title_style and title_style.color and title_style.color.name:
            css_title = parse_css_color(title_style.color.name)
            if css_title:
                title.styles.color = css_title

    with contextlib.suppress(Exception):
        msg = screen.query_one("#message", Static)
        msg_style = theme_dict.get("text")
        if msg_style and msg_style.color and msg_style.color.name:
            css_msg = parse_css_color(msg_style.color.name)
            if css_msg:
                msg.styles.color = css_msg

    with contextlib.suppress(Exception):
        prompt = screen.query_one("#prompt", Static)
        prompt_style = theme_dict.get("text") or theme_dict.get("accent")
        if prompt_style and prompt_style.color and prompt_style.color.name:
            css_prompt = parse_css_color(prompt_style.color.name)
            if css_prompt:
                prompt.styles.color = css_prompt

    with contextlib.suppress(Exception):
        footer = screen.query_one("#footer", Label)
        footer_style = theme_dict.get("help_text") or theme_dict.get("footer") or theme_dict.get("text")
        if footer_style and footer_style.color and footer_style.color.name:
            css_footer = parse_css_color(footer_style.color.name)
            if css_footer:
                footer.styles.color = css_footer

    with contextlib.suppress(Exception):
        path_lbl = screen.query_one("#path_label", Label)
        path_style = theme_dict.get("accent") or theme_dict.get("text")
        if path_style and path_style.color and path_style.color.name:
            css_path = parse_css_color(path_style.color.name)
            if css_path:
                path_lbl.styles.color = css_path

    for opt_id in ["#options_list", "#option_list"]:
        with contextlib.suppress(Exception):
            opt_list = screen.query_one(opt_id, OptionList)
            border_style = theme_dict.get("border") or theme_dict.get("accent")
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


def apply_button_theme(button: Button, theme=None, button_type: str = "button_primary") -> None:
    """Apply foreground and background colors to a Textual Button based on theme dictionary."""
    theme_dict = resolve_theme_dict(theme, getattr(button, "app", None))
    if not theme_dict:
        return
    style = theme_dict.get(button_type) or theme_dict.get("button_primary")
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
    import yaml

    if not filepath or not os.path.exists(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(base_dir, "bashmenu.themes")

    if not os.path.exists(filepath):
        return {}

    try:
        mtime = os.path.getmtime(filepath)
        cached = _themes_file_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1]

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            _themes_file_cache[filepath] = (mtime, data)
            return data
    except (yaml.YAMLError, OSError):
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
    MessageModalScreen.help_modal #dialog {
        width: 95%;
        height: 95%;
        max-width: 100%;
        max-height: 100%;
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
    MessageModalScreen.help_modal #scroll_container {
        height: 1fr;
        max-height: 100%;
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

    def __init__(
        self,
        title: str,
        message: str,
        theme: dict | None = None,
        is_help: bool = False,
        no_formatting: bool = False,
    ):
        super().__init__()
        self.modal_title = title
        self.message = message
        self.theme = theme or {}
        self.is_help = is_help
        self.no_formatting = no_formatting
        if is_help:
            self.add_class("help_modal")

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            if self.modal_title:
                yield Label(self.modal_title, id="title")
            with VerticalScroll(id="scroll_container"):
                content = (
                    self.message
                    if isinstance(self.message, Text)
                    else formatting_to_rich_text(
                        str(self.message), theme=self.theme, no_formatting=self.no_formatting
                    )
                )
                yield Static(content, id="message")
            yield Label("[ENTER/ESC] Close", id="footer")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)

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
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        color: $text-muted;
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
            yield Label("[Y] Yes | [N] No | [C / ESC] Cancel", id="footer")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_yes", Button), self.theme, "button_primary")
            apply_button_theme(self.query_one("#btn_no", Button), self.theme, "button_error")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

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
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        color: $text-muted;
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
            yield Label("[T] True | [F] False | [C / ESC] Cancel", id="footer")

    def on_mount(self) -> None:
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_true", Button), self.theme, "button_success")
            apply_button_theme(self.query_one("#btn_false", Button), self.theme, "button_error")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

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
        margin-bottom: 1;
    }
    Button {
        margin: 0 1;
    }
    #footer {
        text-align: center;
        color: $text-muted;
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
            yield Label("[ENTER] OK | [ESC] Cancel", id="footer")

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            apply_button_theme(self.query_one("#btn_ok", Button), self.theme, "button_primary")
            apply_button_theme(self.query_one("#btn_cancel", Button), self.theme, "button_cancel")

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
        apply_modal_theme(self, self.theme)

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

        except OSError as e:
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


class StreamOutputModalScreen(ModalScreen[None]):
    """Modal screen displaying real-time streaming output of a running command."""

    DEFAULT_CSS = """
    StreamOutputModalScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 80%;
        height: 80%;
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
    #log {
        height: 1fr;
        width: 100%;
        border: solid $surface-lighten-2;
        background: $surface-darken-1;
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

    def __init__(self, title: str, command: str, theme: dict | None = None, no_formatting: bool = False):
        super().__init__()
        self.modal_title = title
        self.command = command
        self.theme = theme or {}
        self.no_formatting = no_formatting
        self.process = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f" Output: {self.modal_title} ", id="title")
            yield RichLog(id="log", highlight=True, markup=not self.no_formatting)
            yield Label(" Executing... Please wait ", id="footer")

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.focus()
        apply_modal_theme(self, getattr(self, "theme", None))
        t = threading.Thread(target=self._run_command_stream, daemon=True)
        t.start()

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
