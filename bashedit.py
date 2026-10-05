#!/usr/bin/env python3
"""
bashedit.py - Built-in Nano-style text editor implemented in Textual.
"""

import contextlib
import os
import re
import subprocess
import sys
from typing import ClassVar

from rich.color import Color, ColorParseError
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Label

import bashmenu_ui

BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
TOKEN_PATTERN = re.compile(
    r"\"?\'?(COLOR_[A-Z_]+)\"?\'?|#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|(-1)\b|\b([0-9]{1,3})\b"
)

COLOR_TOKEN_MAP = {
    "COLOR_BLACK": bashmenu_ui.Style(color="#000000", bgcolor="white", bold=True),
    "COLOR_RED": bashmenu_ui.Style(color="#ff0000", bold=True),
    "COLOR_GREEN": bashmenu_ui.Style(color="#00ff00", bold=True),
    "COLOR_YELLOW": bashmenu_ui.Style(color="#ffff00", bold=True),
    "COLOR_BLUE": bashmenu_ui.Style(color="#5f87ff", bold=True),
    "COLOR_MAGENTA": bashmenu_ui.Style(color="#ff00ff", bold=True),
    "COLOR_CYAN": bashmenu_ui.Style(color="#00ffff", bold=True),
    "COLOR_WHITE": bashmenu_ui.Style(color="#ffffff", bold=True),
    "COLOR_GREY": bashmenu_ui.Style(color="#808080", bold=True),
    "COLOR_GRAY": bashmenu_ui.Style(color="#808080", bold=True),
    "COLOR_BRIGHT_BLACK": bashmenu_ui.Style(color="#808080", bold=True),
    "COLOR_BRIGHT_RED": bashmenu_ui.Style(color="#ff5555", bold=True),
    "COLOR_BRIGHT_GREEN": bashmenu_ui.Style(color="#55ff55", bold=True),
    "COLOR_BRIGHT_YELLOW": bashmenu_ui.Style(color="#ffff55", bold=True),
    "COLOR_BRIGHT_BLUE": bashmenu_ui.Style(color="#5555ff", bold=True),
    "COLOR_BRIGHT_MAGENTA": bashmenu_ui.Style(color="#ff55ff", bold=True),
    "COLOR_BRIGHT_CYAN": bashmenu_ui.Style(color="#55ffff", bold=True),
    "COLOR_BRIGHT_WHITE": bashmenu_ui.Style(color="#ffffff", bold=True),
    "COLOR_ORANGE": bashmenu_ui.Style(color="#ff8700", bold=True),
    "COLOR_PURPLE": bashmenu_ui.Style(color="#af00ff", bold=True),
    "COLOR_PINK": bashmenu_ui.Style(color="#ff87af", bold=True),
    "COLOR_BROWN": bashmenu_ui.Style(color="#af5f00", bold=True),
}


def is_same_color(c1: str | None, c2: str | None) -> bool:
    """Check if two color specs represent the same or nearly identical color."""
    if not c1 or not c2:
        return False
    parsed1 = bashmenu_ui.parse_css_color(c1) or c1
    parsed2 = bashmenu_ui.parse_css_color(c2) or c2
    if str(parsed1).strip().lower() == str(parsed2).strip().lower():
        return True
    try:
        rgb1 = Color.parse(str(parsed1)).get_truecolor()
        rgb2 = Color.parse(str(parsed2)).get_truecolor()
        return (
            abs(rgb1.red - rgb2.red)
            + abs(rgb1.green - rgb2.green)
            + abs(rgb1.blue - rgb2.blue)
        ) < 25
    except (ColorParseError, ValueError, TypeError, AttributeError, KeyError):
        return False


def get_contrast_neutral_color(css_color: str | None) -> str:
    """Return a neutral primary 8 color ('white' or 'black') contrasting input."""
    if not css_color:
        return "white"
    parsed = bashmenu_ui.parse_css_color(css_color) or css_color
    try:
        rgb = Color.parse(str(parsed)).get_truecolor()
        lum = 0.299 * rgb.red + 0.587 * rgb.green + 0.114 * rgb.blue
        return "black" if lum >= 128 else "white"
    except (ColorParseError, ValueError, TypeError, AttributeError, KeyError):
        return "white"


def has_sufficient_contrast(c1: str | None, c2: str | None) -> bool:
    """Determine whether two colors provide adequate luminance contrast."""
    if not c1 or not c2 or is_same_color(c1, c2):
        return False
    parsed1 = bashmenu_ui.parse_css_color(c1) or c1
    parsed2 = bashmenu_ui.parse_css_color(c2) or c2
    try:
        rgb1 = Color.parse(str(parsed1)).get_truecolor()
        rgb2 = Color.parse(str(parsed2)).get_truecolor()
        lum1 = 0.299 * rgb1.red + 0.587 * rgb1.green + 0.114 * rgb1.blue
        lum2 = 0.299 * rgb2.red + 0.587 * rgb2.green + 0.114 * rgb2.blue
        return abs(lum1 - lum2) >= 60
    except (ColorParseError, ValueError, TypeError, AttributeError, KeyError):
        return True


def get_theme_background_color(theme: dict | None) -> str:
    """Resolve active theme background color to a normalized CSS hex string."""
    if isinstance(theme, dict):
        bg_style = theme.get("background")
        if bg_style and getattr(bg_style, "bgcolor", None):
            bg_val = getattr(bg_style.bgcolor, "name", None) or str(bg_style.bgcolor)
            parsed = bashmenu_ui.parse_css_color(bg_val)
            if parsed:
                return parsed
    return "#000000"


def get_token_foreground_style(token_str: str, theme_bg: str | None = None) -> bashmenu_ui.Style | None:
    """Resolve token inside brackets to its assigned curses foreground color style."""
    clean_tok = token_str.strip("\"'")
    if clean_tok in COLOR_TOKEN_MAP:
        st = COLOR_TOKEN_MAP[clean_tok]
        if theme_bg and clean_tok == "COLOR_BLACK" and not is_same_color(theme_bg, "#000000"):
            neutral = get_contrast_neutral_color(theme_bg)
            if neutral == "black":
                return bashmenu_ui.Style(color="#000000", bold=True)
        return st
    if clean_tok == "-1":
        return bashmenu_ui.Style(color="white", dim=True)
    if clean_tok.isdigit():
        val = int(clean_tok)
        if 0 <= val <= 255:
            css = bashmenu_ui.parse_css_color(val)
            if css:
                if val in (0, 16, 232, 233, 234, 235, 236) or css == "black":
                    neutral = get_contrast_neutral_color(theme_bg or "#000000")
                    if neutral == "black":
                        return bashmenu_ui.Style(color=css, bold=True)
                    return bashmenu_ui.Style(color=css, bgcolor="white", bold=True)
                return bashmenu_ui.Style(color=css, bold=True)
    if clean_tok.startswith("#"):
        return bashmenu_ui.Style(color=clean_tok, bold=True)
    return None


class EditorWidget(Widget):
    """Custom line-oriented text editor widget displaying code buffer and cursor."""

    DEFAULT_CSS = """
    EditorWidget {
        width: 100%;
        height: 1fr;
        background: $surface;
        color: $text;
    }
    """

    show_line_numbers = reactive(True)
    show_whitespace = reactive(False)
    display_theme_colors = reactive(False)
    show_markdown = reactive(False)

    def __init__(
        self,
        lines=None,
        show_line_numbers=True,
        show_whitespace=False,
        tab_to_spaces=True,
        tabstop=8,
        theme=None,
        display_theme_colors=False,
        show_markdown=False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.can_focus = True
        self.lines = list(lines) if lines else [""]
        self.cursor_y = 0
        self.cursor_x = 0
        self.top_line = 0
        self.left_col = 0
        self.show_line_numbers = show_line_numbers
        self.show_whitespace = show_whitespace
        self.tab_to_spaces = tab_to_spaces
        self.tabstop = tabstop
        self.theme = theme or {}
        self.display_theme_colors = display_theme_colors
        self.show_markdown = show_markdown
        self._rendered_md_lines = None
        self._color_span_cache = {}

        self.mark_active = False
        self.mark_y = 0
        self.mark_x = 0

        self.cutbuffer = []
        self.undo_stack = []
        self.redo_stack = []
        self.MAX_HISTORY = 100
        self.modified = False

    def get_line_color_spans(self, text: str) -> list[tuple[int, int, bashmenu_ui.Style]]:
        """Compute Rich style spans for color code brackets in text line."""
        if not text or "[" not in text or "]" not in text:
            return []

        theme_bg = get_theme_background_color(self.theme)
        cache_key = (text, theme_bg)
        if cache_key in self._color_span_cache:
            return self._color_span_cache[cache_key]

        contrast_neutral = get_contrast_neutral_color(theme_bg)
        spans = []

        for bm in BRACKET_PATTERN.finditer(text):
            bracket_content = bm.group(1)
            bracket_start = bm.start(1)
            token_matches = list(TOKEN_PATTERN.finditer(bracket_content))
            if not token_matches:
                continue

            if len(token_matches) == 2:
                tm0, tm1 = token_matches[0], token_matches[1]
                tok0, tok1 = tm0.group(0), tm1.group(0)
                clean0, clean1 = tok0.strip("\"'"), tok1.strip("\"'")
                css0 = bashmenu_ui.parse_css_color(clean0)
                css1 = bashmenu_ui.parse_css_color(clean1)

                match0 = clean0 != "-1" and is_same_color(css0, theme_bg)
                match1 = clean1 != "-1" and is_same_color(css1, theme_bg)

                same_pair_values = clean0 == clean1 or (
                    css0 and css1 and is_same_color(css0, css1)
                )

                # Check if foreground and background values match theme background
                if (match0 and match1) or (same_pair_values and (match0 or match1)):
                    # Choose a neutral primary 8 color value that contrasts the background
                    for tm, clean, css in [
                        (tm0, clean0, css0),
                        (tm1, clean1, css1),
                    ]:
                        s_idx = bracket_start + tm.start()
                        e_idx = bracket_start + tm.end()
                        if clean == "-1":
                            st = bashmenu_ui.Style(color="white", dim=True)
                        else:
                            st = bashmenu_ui.Style(
                                color=css or "white",
                                bgcolor=contrast_neutral,
                                bold=True,
                            )
                        spans.append((s_idx, e_idx, st))
                elif match0:
                    # Invert foreground and background color for token 0
                    bg_col = (
                        css1
                        if (
                            css1
                            and clean1 != "-1"
                            and has_sufficient_contrast(css0, css1)
                        )
                        else contrast_neutral
                    )
                    st0 = bashmenu_ui.Style(
                        color=css0 or "white", bgcolor=bg_col, bold=True
                    )
                    st1 = get_token_foreground_style(tok1, theme_bg=theme_bg)
                    spans.append(
                        (bracket_start + tm0.start(), bracket_start + tm0.end(), st0)
                    )
                    if st1:
                        spans.append(
                            (bracket_start + tm1.start(), bracket_start + tm1.end(), st1)
                        )
                elif match1:
                    # Invert foreground and background color for token 1
                    bg_col = (
                        css0
                        if (
                            css0
                            and clean0 != "-1"
                            and has_sufficient_contrast(css1, css0)
                        )
                        else contrast_neutral
                    )
                    st0 = get_token_foreground_style(tok0, theme_bg=theme_bg)
                    st1 = bashmenu_ui.Style(
                        color=css1 or "white", bgcolor=bg_col, bold=True
                    )
                    if st0:
                        spans.append(
                            (bracket_start + tm0.start(), bracket_start + tm0.end(), st0)
                        )
                    spans.append(
                        (bracket_start + tm1.start(), bracket_start + tm1.end(), st1)
                    )
                else:
                    # Neither token matches theme background; render default styles
                    st0 = get_token_foreground_style(tok0, theme_bg=theme_bg)
                    st1 = get_token_foreground_style(tok1, theme_bg=theme_bg)
                    if st0:
                        spans.append(
                            (bracket_start + tm0.start(), bracket_start + tm0.end(), st0)
                        )
                    if st1:
                        spans.append(
                            (bracket_start + tm1.start(), bracket_start + tm1.end(), st1)
                        )
            else:
                for tm in token_matches:
                    tok = tm.group(0)
                    clean = tok.strip("\"'")
                    css = bashmenu_ui.parse_css_color(clean)
                    s_idx = bracket_start + tm.start()
                    e_idx = bracket_start + tm.end()
                    if clean != "-1" and is_same_color(css, theme_bg):
                        st = bashmenu_ui.Style(
                            color=css or "white",
                            bgcolor=contrast_neutral,
                            bold=True,
                        )
                    else:
                        st = get_token_foreground_style(tok, theme_bg=theme_bg)
                    if st:
                        spans.append((s_idx, e_idx, st))

        if len(self._color_span_cache) > 2000:
            self._color_span_cache.clear()
        self._color_span_cache[cache_key] = spans
        return spans

    def render(self) -> Text:
        """Render visible text lines with selection, line numbers, and cursor."""
        out = Text()
        height = max(1, self.size.height or 20)
        width = max(1, self.size.width or 80)

        lineno_width = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0
        theme_dict = self.theme if isinstance(self.theme, dict) else {}
        gutter_style = theme_dict.get("gutter") or theme_dict.get("help_text") or "dim cyan"
        lineno_style = theme_dict.get("gutter") or theme_dict.get("text") or "dim white"
        sel_style = theme_dict.get("selection") or "reverse bold magenta"
        ws_style = (
            theme_dict.get("whitespace")
            or theme_dict.get("whitespace_color")
            or "dim white"
        )

        if self.show_markdown:
            content_width = max(1, width)
            console = (
                self.app.console
                if (hasattr(self, "app") and self.app and getattr(self.app, "console", None))
                else Console(width=content_width)
            )
            options = console.options.update_width(content_width)
            try:
                rendered_lines = console.render_lines(Markdown("\n".join(self.lines)), options)
            except Exception:  # noqa: BLE001
                rendered_lines = []
            self._rendered_md_lines = rendered_lines

            for row_idx in range(height):
                line_idx = self.top_line + row_idx
                if line_idx >= len(rendered_lines):
                    out.append("~\n", style=gutter_style)
                    continue
                line_segs = rendered_lines[line_idx]
                line_rich = Text.assemble(*[(seg.text, seg.style) for seg in line_segs])
                out.append_text(line_rich)
                out.append("\n")
            return out

        for row_idx in range(height):
            line_num = self.top_line + row_idx
            if line_num >= len(self.lines):
                out.append("~\n", style=gutter_style)
                continue

            line_text = self.lines[line_num]

            if self.show_line_numbers:
                num_str = f"{line_num + 1:>{lineno_width - 1}} "
                out.append(num_str, style=lineno_style)

            # Format line content with optional whitespace rendering
            disp_text = line_text
            ws_indices = set()
            if self.show_whitespace:
                out_chars = []
                col = 0
                for char in line_text:
                    if char == " ":
                        ws_indices.add(len(out_chars))
                        out_chars.append("·")
                        col += 1
                    elif char == "\t":
                        tab_width = self.tabstop - (col % self.tabstop)
                        ws_indices.add(len(out_chars))
                        out_chars.append("→")
                        for _ in range(tab_width - 1):
                            ws_indices.add(len(out_chars))
                            out_chars.append(" ")
                        col += tab_width
                    elif char == "\r":
                        ws_indices.add(len(out_chars))
                        out_chars.append("↵")
                        col += 1
                    else:
                        out_chars.append(char)
                        col += 1
                ws_indices.add(len(out_chars))
                out_chars.append("↵")
                disp_text = "".join(out_chars)

            content_width = max(1, width - lineno_width)
            sx = self.left_col
            visible_segment = disp_text[sx : sx + content_width]

            # Render line text with selection / cursor
            line_rich = Text(visible_segment)

            if self.show_whitespace and ws_indices:
                sorted_indices = sorted(ws_indices)
                start_i = None
                end_i = None
                for idx in sorted_indices:
                    rel_idx = idx - sx
                    if 0 <= rel_idx < len(visible_segment):
                        if start_i is None:
                            start_i = rel_idx
                            end_i = rel_idx + 1
                        elif rel_idx == end_i:
                            end_i = rel_idx + 1
                        else:
                            line_rich.stylize(ws_style, start_i, end_i)
                            start_i = rel_idx
                            end_i = rel_idx + 1
                if start_i is not None:
                    line_rich.stylize(ws_style, start_i, end_i)

            if self.display_theme_colors:
                for start_idx, end_idx, st in self.get_line_color_spans(visible_segment):
                    line_rich.stylize(st, start_idx, end_idx)

            # Highlight text selection if mark is active
            if self.mark_active:
                sy, ey = min(self.mark_y, self.cursor_y), max(self.mark_y, self.cursor_y)
                if sy <= line_num <= ey:
                    if sy == ey:
                        sm_x, em_x = min(self.mark_x, self.cursor_x), max(self.mark_x, self.cursor_x)
                    elif line_num == sy:
                        sm_x = self.mark_x if self.mark_y == sy else self.cursor_x
                        em_x = len(disp_text)
                    elif line_num == ey:
                        sm_x = 0
                        em_x = self.mark_x if self.mark_y == ey else self.cursor_x
                    else:
                        sm_x = 0
                        em_x = len(disp_text)

                    rel_s = max(0, sm_x - sx)
                    rel_e = min(len(visible_segment), em_x - sx)
                    if rel_s < rel_e:
                        line_rich.stylize(sel_style, rel_s, rel_e)

            # Highlight current line cursor position
            if line_num == self.cursor_y:
                rel_cursor_x = self.cursor_x - sx
                if 0 <= rel_cursor_x <= len(line_rich):
                    if rel_cursor_x < len(line_rich):
                        line_rich.stylize("reverse bold", rel_cursor_x, rel_cursor_x + 1)
                    else:
                        line_rich.append(" ", style="reverse bold")

            out.append_text(line_rich)
            out.append("\n")

        return out

    def push_undo(self):
        self.undo_stack.append(
            (list(self.lines), self.cursor_y, self.cursor_x, self.mark_active, self.mark_y, self.mark_x)
        )
        if len(self.undo_stack) > self.MAX_HISTORY:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> str:
        if not self.undo_stack:
            return "Nothing to undo"
        self.redo_stack.append(
            (list(self.lines), self.cursor_y, self.cursor_x, self.mark_active, self.mark_y, self.mark_x)
        )
        prev_lines, self.cursor_y, self.cursor_x, self.mark_active, self.mark_y, self.mark_x = self.undo_stack.pop()
        self.lines = list(prev_lines)
        self.modified = True
        self.clamp_cursor()
        self.refresh()
        return "Undo"

    def redo(self) -> str:
        if not self.redo_stack:
            return "Nothing to redo"
        self.undo_stack.append(
            (list(self.lines), self.cursor_y, self.cursor_x, self.mark_active, self.mark_y, self.mark_x)
        )
        next_lines, self.cursor_y, self.cursor_x, self.mark_active, self.mark_y, self.mark_x = self.redo_stack.pop()
        self.lines = list(next_lines)
        self.modified = True
        self.clamp_cursor()
        self.refresh()
        return "Redo"

    def clamp_cursor(self):
        self.cursor_y = max(0, min(self.cursor_y, len(self.lines) - 1))
        current_line_len = len(self.lines[self.cursor_y])
        self.cursor_x = max(0, min(self.cursor_x, current_line_len))

        # Adjust viewport scroll position
        height = max(1, self.size.height or 20)
        width = max(1, self.size.width or 80)

        max_top = max(0, len(self.lines) - 1)
        if self.cursor_y < self.top_line:
            self.top_line = self.cursor_y
        elif self.cursor_y >= self.top_line + height:
            self.top_line = self.cursor_y - height + 1
        self.top_line = min(self.top_line, max_top)

        lineno_w = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0
        visible_w = max(10, width - lineno_w)

        if self.cursor_x < self.left_col:
            self.left_col = self.cursor_x
        elif self.cursor_x >= self.left_col + visible_w:
            self.left_col = self.cursor_x - visible_w + 1

    def _get_rendered_md_lines(self) -> list:
        if self._rendered_md_lines is not None:
            return self._rendered_md_lines
        width = max(1, self.size.width or 80)
        console = (
            self.app.console
            if (hasattr(self, "app") and self.app and getattr(self.app, "console", None))
            else Console(width=width)
        )
        options = console.options.update_width(width)
        try:
            self._rendered_md_lines = console.render_lines(Markdown("\n".join(self.lines)), options)
        except Exception:  # noqa: BLE001
            self._rendered_md_lines = []
        return self._rendered_md_lines

    def scroll_lines_down(self, count: int = 3) -> None:
        """Scroll the editor viewport down by count lines (navigate page down)."""
        total_lines = len(self._get_rendered_md_lines()) if self.show_markdown else len(self.lines)
        max_top = max(0, total_lines - 1)
        if self.top_line >= max_top:
            return
        self.top_line = min(max_top, self.top_line + count)
        if not self.show_markdown and self.cursor_y < self.top_line:
            self.cursor_y = self.top_line
            self.clamp_cursor()
        self.refresh()

    def scroll_lines_up(self, count: int = 3) -> None:
        """Scroll the editor viewport up by count lines (navigate page up)."""
        height = max(1, self.size.height or 20)
        if self.top_line <= 0:
            return
        self.top_line = max(0, self.top_line - count)
        if not self.show_markdown and self.cursor_y >= self.top_line + height:
            self.cursor_y = max(0, self.top_line + height - 1)
            self.clamp_cursor()
        self.refresh()

    def on_mouse_scroll_down(self, event) -> None:
        self.scroll_lines_down(3)
        if hasattr(self.screen, "update_status"):
            self.screen.update_status()
        event.prevent_default()
        event.stop()

    def on_mouse_scroll_up(self, event) -> None:
        self.scroll_lines_up(3)
        if hasattr(self.screen, "update_status"):
            self.screen.update_status()
        event.prevent_default()
        event.stop()

    def insert_char(self, char: str):
        self.push_undo()
        self._color_span_cache.clear()
        line = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = line[: self.cursor_x] + char + line[self.cursor_x :]
        self.cursor_x += len(char)
        self.modified = True
        self.clamp_cursor()
        self.refresh()

    def insert_newline(self):
        self.push_undo()
        self._color_span_cache.clear()
        line = self.lines[self.cursor_y]
        left_part = line[: self.cursor_x]
        right_part = line[self.cursor_x :]
        self.lines[self.cursor_y] = left_part
        self.lines.insert(self.cursor_y + 1, right_part)
        self.cursor_y += 1
        self.cursor_x = 0
        self.modified = True
        self.clamp_cursor()
        self.refresh()

    def backspace(self):
        self.push_undo()
        self._color_span_cache.clear()
        if self.cursor_x > 0:
            line = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = line[: self.cursor_x - 1] + line[self.cursor_x :]
            self.cursor_x -= 1
            self.modified = True
        elif self.cursor_y > 0:
            prev_line = self.lines[self.cursor_y - 1]
            curr_line = self.lines[self.cursor_y]
            self.cursor_x = len(prev_line)
            self.lines[self.cursor_y - 1] = prev_line + curr_line
            self.lines.pop(self.cursor_y)
            self.cursor_y -= 1
            self.modified = True
        self.clamp_cursor()
        self.refresh()

    def delete_char(self):
        self.push_undo()
        self._color_span_cache.clear()
        line = self.lines[self.cursor_y]
        if self.cursor_x < len(line):
            self.lines[self.cursor_y] = line[: self.cursor_x] + line[self.cursor_x + 1 :]
            self.modified = True
        elif self.cursor_y < len(self.lines) - 1:
            next_line = self.lines.pop(self.cursor_y + 1)
            self.lines[self.cursor_y] += next_line
            self.modified = True
        self.clamp_cursor()
        self.refresh()

    def get_selection_range(self):
        if not self.mark_active:
            return None
        if (self.mark_y, self.mark_x) <= (self.cursor_y, self.cursor_x):
            return (self.mark_y, self.mark_x), (self.cursor_y, self.cursor_x)
        else:
            return (self.cursor_y, self.cursor_x), (self.mark_y, self.mark_x)

    def toggle_mark(self) -> str:
        self.mark_active = not self.mark_active
        self.mark_y = self.cursor_y
        self.mark_x = self.cursor_x
        self.refresh()
        return "Mark Set" if self.mark_active else "Mark Unset"

    def copy_selection(self) -> str:
        """Copy active selection block or current line into cutbuffer and system clipboard."""
        sel = self.get_selection_range()
        if not sel:
            line = self.lines[self.cursor_y]
            self.cutbuffer = [line]
            set_system_clipboard(line)
            self.mark_active = False
            self.refresh()
            return "Line Copied"

        (sy, sx), (ey, ex) = sel
        if sy == ey:
            line = self.lines[sy]
            s_idx, e_idx = min(sx, ex), max(sx, ex)
            if s_idx == e_idx:
                self.cutbuffer = [line]
            else:
                self.cutbuffer = [line[s_idx:e_idx]]
        else:
            cut = [self.lines[sy][sx:]]
            for r in range(sy + 1, ey):
                cut.append(self.lines[r])
            end_segment = self.lines[ey][:ex] if ex > 0 else self.lines[ey]
            if end_segment or ex > 0:
                cut.append(end_segment)
            self.cutbuffer = cut

        copied_str = "\n".join(self.cutbuffer)
        set_system_clipboard(copied_str)
        self.mark_active = False
        self.refresh()
        return "Selection Copied"

    def cut_line(self) -> str:
        """Cut active selection block or current line into cutbuffer and push undo state."""
        self.push_undo()
        sel = self.get_selection_range()
        if sel:
            (sy, sx), (ey, ex) = sel
            if sy == ey:
                line = self.lines[sy]
                s_idx, e_idx = min(sx, ex), max(sx, ex)
                if s_idx == e_idx:
                    self.cutbuffer = [line]
                    if len(self.lines) > 1:
                        del self.lines[sy]
                    else:
                        self.lines[0] = ""
                else:
                    self.cutbuffer = [line[s_idx:e_idx]]
                    self.lines[sy] = line[:s_idx] + line[e_idx:]
            else:
                cut = [self.lines[sy][sx:]]
                for r in range(sy + 1, ey):
                    cut.append(self.lines[r])
                end_segment = self.lines[ey][:ex] if ex > 0 else self.lines[ey]
                if end_segment or ex > 0:
                    cut.append(end_segment)
                self.cutbuffer = cut
                self.lines[sy] = self.lines[sy][:sx] + (self.lines[ey][ex:] if ex > 0 else "")
                del self.lines[sy + 1 : ey + 1]
            self.mark_active = False
            self.cursor_y, self.cursor_x = sy, min(sx, len(self.lines[min(sy, len(self.lines) - 1)]))
        else:
            if len(self.lines) > 1:
                removed = self.lines.pop(self.cursor_y)
                self.cutbuffer = [removed]
            else:
                self.cutbuffer = [self.lines[0]]
                self.lines[0] = ""
        copied_str = "\n".join(self.cutbuffer)
        set_system_clipboard(copied_str)
        self.modified = True
        self.clamp_cursor()
        self.refresh()
        return "Selection Cut" if sel else "Line Cut"

    def paste_buffer(self) -> str:
        """Paste text from system clipboard (or local cutbuffer fallback) at cursor position."""
        clip = get_system_clipboard()
        if clip is not None and clip != "":
            clip_lines = clip.splitlines()
            if not clip_lines:
                clip_lines = [""]
            self.push_undo()
            if len(clip_lines) == 1:
                line = self.lines[self.cursor_y]
                self.lines[self.cursor_y] = line[: self.cursor_x] + clip_lines[0] + line[self.cursor_x :]
                self.cursor_x += len(clip_lines[0])
            else:
                curr_line = self.lines[self.cursor_y]
                prefix = curr_line[: self.cursor_x]
                suffix = curr_line[self.cursor_x :]
                self.lines[self.cursor_y] = prefix + clip_lines[0]
                for idx, c_line in enumerate(clip_lines[1:], start=1):
                    self.lines.insert(self.cursor_y + idx, c_line)
                self.cursor_y += len(clip_lines) - 1
                self.lines[self.cursor_y] += suffix
                self.cursor_x = len(self.lines[self.cursor_y]) - len(suffix)
            self.modified = True
            self.clamp_cursor()
            self.refresh()
            return "Pasted"

        if not self.cutbuffer:
            return "Buffer empty"
        self.push_undo()
        for idx, text in enumerate(self.cutbuffer):
            self.lines.insert(self.cursor_y + idx, text)
        self.cursor_y += len(self.cutbuffer)
        self.modified = True
        self.clamp_cursor()
        self.refresh()
        return "Pasted"


def get_system_clipboard() -> str | None:
    """Read plain text from system clipboard using platform tools (wl-paste, pbpaste, termux, xclip, xsel)."""
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
            if res.returncode == 0 and res.stdout is not None:
                return res.stdout
        except Exception:  # noqa: BLE001, S110
            pass
    return None


def set_system_clipboard(text: str) -> bool:
    """Copy text to system clipboard using platform tools (wl-copy, pbcopy, termux, xclip, xsel, clip.exe)."""
    if text is None:
        return False
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
                return True
        except Exception:  # noqa: BLE001, S110
            pass
    return False


class EditorTab:
    """Represents an open document tab buffer in BashEdit."""

    def __init__(self, file_path: str | None = None, lines: list[str] | None = None, show_markdown: bool = False):
        self.file_path = file_path
        self.lines = list(lines) if lines else [""]
        self.cursor_y = 0
        self.cursor_x = 0
        self.top_line = 0
        self.left_col = 0
        self.mark_active = False
        self.mark_y = 0
        self.mark_x = 0
        self.undo_stack = []
        self.redo_stack = []
        self.modified = False
        self.show_markdown = show_markdown


class BashEditScreen(Screen):
    """Full screen Nano-style text editor with tab support."""

    DEFAULT_CSS = """
    BashEditScreen {
        layout: vertical;
        background: $surface;
    }
    #editor_header_area {
        dock: top;
        height: auto;
        width: 100%;
    }
    #editor_header_bar {
        height: 1;
        width: 100%;
        background: $accent;
        color: $text;
    }
    #editor_header {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    #editor_tab_bar {
        height: 1;
        width: 100%;
        background: $panel;
        color: $text-muted;
    }
    .editor_tab {
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    .editor_tab_active {
        padding: 0 1;
        background: $surface;
        color: $text;
        text-style: bold;
    }
    .editor_tab_close {
        padding: 0 1;
        color: $error;
    }
    .editor_tab_close:hover {
        color: $text;
    }
    .editor_tab_add {
        padding: 0 1;
        color: $accent;
    }
    .editor_tab_add:hover {
        color: $text;
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
    #editor_footer_area {
        dock: bottom;
        height: auto;
        width: 100%;
    }
    #editor_status {
        height: 1;
        width: 100%;
        background: $panel;
        color: $text-muted;
    }
    #editor_legend {
        height: 1;
        width: 100%;
        background: $surface;
        color: $accent;
        align: center middle;
    }
    .footer_item {
        padding: 0 1;
        color: $accent;
    }
    .footer_item:hover {
        text-style: underline;
        color: $text;
    }
    #editor_divider {
        height: 1;
        width: 100%;
        color: $accent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+o", "open_file", "Open"),
        Binding("ctrl+r", "open_file", "Open", show=False),
        Binding("f5", "open_file", "Open", show=False),
        Binding("f7", "open_file", "Open", show=False),
        Binding("ctrl+s", "save_file", "Save"),
        Binding("f2", "save_file", "Save", show=False),
        Binding("f3", "save_file", "Save", show=False),
        Binding("ctrl+e", "new_file", "New", show=False),
        Binding("f4", "new_file", "New", show=False),
        Binding("ctrl+shift+s", "save_file_as", "Save As", show=False),
        Binding("alt+s", "save_file_as", "Save As", show=False),
        Binding("meta+s", "save_file_as", "Save As", show=False),
        Binding("f6", "save_file_as", "Save As", show=False),
        Binding("ctrl+k", "cut_line", "Cut"),
        Binding("f8", "cut_line", "Cut", show=False),
        Binding("ctrl+u", "paste_buffer", "Paste"),
        Binding("ctrl+v", "paste_buffer", "Paste", show=False),
        Binding("ctrl+shift+v", "paste_buffer", "Paste", show=False),
        Binding("f9", "paste_buffer", "Paste", show=False),
        Binding("ctrl+w", "search_text", "WhereIs"),
        Binding("ctrl+x", "exit_editor", "Exit"),
        Binding("escape", "exit_editor", "Exit", show=False),
        Binding("alt+1", "toggle_whitespace", "Whitespace"),
        Binding("meta+1", "toggle_whitespace", "Whitespace", show=False),
        Binding("m-1", "toggle_whitespace", "Whitespace", show=False),
        Binding("m+1", "toggle_whitespace", "Whitespace", show=False),
        Binding("ctrl+p", "show_placeholders", "Placeholders"),
        Binding("alt+m", "show_placeholders", "Placeholders", show=False),
        Binding("ctrl+6", "toggle_mark", "Mark"),
        Binding("alt+a", "toggle_mark", "Mark", show=False),
        Binding("ctrl+c", "copy_selection", "Copy", show=False),
        Binding("ctrl+shift+c", "copy_selection", "Copy", show=False),
        Binding("alt+6", "copy_selection", "Copy", show=False),
        Binding("§", "copy_selection", "Copy", show=False),
        Binding("alt+c", "copy_selection", "Copy", show=False),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+y", "redo", "Redo"),
        Binding("ctrl+n", "toggle_lineno", "Line Numbers"),
        Binding("alt+n", "toggle_lineno", "Line Numbers", show=False),
        Binding("f12", "toggle_markdown", "Markdown", show=False),
        Binding("f1", "help_manual", "Help"),
        Binding("ctrl+g", "help_manual", "Help", show=False),
        Binding("alt+h", "help_manual", "Help", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("left", "move_left", "Left", show=False),
        Binding("right", "move_right", "Right", show=False),
        Binding("home", "move_home", "Home", show=False),
        Binding("end", "move_end", "End", show=False),
        Binding("alt+t", "toggle_theme_colors", "Toggle Theme Colors", show=False),
        Binding("alt+v", "view_colors", "View Colors", show=False),
        Binding("f10", "view_colors", "View Colors", show=False),
        Binding("ctrl+a", "show_ascii_table", "ASCII Table", show=False),
        Binding("f11", "show_ascii_table", "ASCII Table", show=False),
        Binding("alt+]", "next_tab", "Next Tab", show=False),
        Binding("alt+[", "prev_tab", "Prev Tab", show=False),
        Binding("ctrl+tab", "next_tab", "Next Tab", show=False),
        Binding("ctrl+shift+tab", "prev_tab", "Prev Tab", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def __init__(
        self,
        file_path: str | None = None,
        theme: dict | None = None,
        show_whitespace: bool = False,
        tab_to_spaces: bool = True,
        tabstop: int = 8,
        display_theme_colors: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.file_path = file_path
        self.show_whitespace = show_whitespace
        self.tab_to_spaces = tab_to_spaces
        self.tabstop = tabstop
        self.display_theme_colors = display_theme_colors or bool(
            file_path and (file_path.endswith(".themes") or "bashmenu.themes" in file_path)
        )
        self.display_theme_colors_flag = self.display_theme_colors or display_theme_colors

        theme_name = "dracula"
        if isinstance(theme, str):
            theme_name = theme
            self.theme_styles = bashmenu_ui.init_theme_colors(theme_name)
        elif isinstance(theme, dict) and theme:
            self.theme_styles = theme
        else:
            try:
                import bashmenu
                config = bashmenu.load_config() if hasattr(bashmenu, "load_config") else {}
                if isinstance(config, dict) and "theme" in config:
                    theme_name = config.get("theme", "dracula")
            except Exception:  # noqa: BLE001, S110
                pass
            self.theme_styles = bashmenu_ui.init_theme_colors(theme_name)
        self.theme_name = theme_name
        self.theme = self.theme_styles

        lines = [""]
        if self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().splitlines()
                    lines = content if content else [""]
            except (OSError, UnicodeDecodeError) as e:
                lines = [f"# Error reading file: {e}"]

        self.initial_lines = lines
        self.tabs = [EditorTab(file_path=self.file_path, lines=self.initial_lines)]
        self.active_tab_idx = 0

    def compose(self) -> ComposeResult:
        file_name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        with Vertical(id="editor_header_area"):
            with Horizontal(id="editor_header_bar"):
                yield Label(f"  BashEdit - {file_name}  ", id="editor_header")
                yield Label(bashmenu_ui.format_close_button_label(), id="btn_close_x", classes="btn_close_x")
            with Horizontal(id="editor_tab_bar"):
                for idx, tab in enumerate(self.tabs):
                    name = os.path.basename(tab.file_path) if tab.file_path else "Untitled"
                    mod = " *" if tab.modified else ""
                    cls = "editor_tab_active" if idx == self.active_tab_idx else "editor_tab"
                    yield Label(f" {idx + 1}: {name}{mod} ", classes=f"editor_tab_select tab_select_{idx} {cls}")
                    if len(self.tabs) > 1:
                        yield Label(" ✕ ", classes=f"editor_tab_close tab_close_{idx}")
                yield Label(" [ + ] ", id="tab_add_new", classes="editor_tab_add")
        yield EditorWidget(
            lines=self.initial_lines,
            show_whitespace=self.show_whitespace,
            tab_to_spaces=self.tab_to_spaces,
            tabstop=self.tabstop,
            theme=self.theme_styles,
            display_theme_colors=self.display_theme_colors,
            id="editor_widget",
        )
        theme_div = bashmenu_ui.get_theme_divider(getattr(self, "theme_name", "dracula"))
        div_char = theme_div.get("char", "─") if theme_div else "─"
        if "{" in div_char:
            import bashmenu
            div_char = bashmenu.interpolate_placeholders(div_char, getattr(self, "config", {}))
            div_char = bashmenu.resolve_glyph(div_char, getattr(self, "config", {}))
        if not div_char:
            div_char = "─"
        with Vertical(id="editor_footer_area"):
            yield Label(div_char * 500, id="editor_divider")
            with Horizontal(id="editor_legend"):
                yield Label("^O Open", id="lbl_open", classes="footer_item lbl_open", markup=False)
                yield Label("^S Save", id="lbl_save", classes="footer_item lbl_save", markup=False)
                yield Label("Alt+S SaveAs", id="lbl_save_as", classes="footer_item lbl_save_as", markup=False)
                yield Label("^W Search", id="lbl_search", classes="footer_item", markup=False)
                yield Label("^K Cut", id="lbl_cut", classes="footer_item", markup=False)
                yield Label("Alt+6 Copy", id="lbl_copy", classes="footer_item", markup=False)
                yield Label("^U Paste", id="lbl_paste", classes="footer_item", markup=False)
                yield Label("^^ Mark", id="lbl_mark", classes="footer_item", markup=False)
                yield Label("^P Macros", id="lbl_placeholders", classes="footer_item", markup=False)
                yield Label("^A ASCII", id="lbl_ascii", classes="footer_item", markup=False)
                yield Label("Alt+V Colors", id="lbl_colors", classes="footer_item", markup=False)
                yield Label("Alt+1 Space", id="lbl_space", classes="footer_item", markup=False)
                yield Label("^N Lineno", id="lbl_lineno", classes="footer_item", markup=False)
                yield Label("F12 MD", id="lbl_markdown", classes="footer_item", markup=False)
                yield Label("F1 Help", id="lbl_help", classes="footer_item", markup=False)
                yield Label("^X/ESC Exit", id="lbl_exit", classes="footer_item", markup=False)
            yield Label("  Line 1/1, Col 1  ", id="editor_status")

    def on_click(self, event) -> None:
        """Route mouse click events across tabs, close buttons, and interactive footer action labels."""
        node = getattr(event, "target", None) or getattr(event, "widget", None)
        target_action = None
        target_idx = None

        while node is not None:
            nid = getattr(node, "id", None) or ""
            classes = set(getattr(node, "classes", []))

            if nid == "tab_add_new" or "tab_add_new" in classes:
                target_action = "add"
                break
            if nid == "btn_close_x" or "btn_close_x" in classes:
                target_action = "close_app"
                break

            if nid.startswith("tab_select_"):
                target_action = "select"
                with contextlib.suppress(ValueError):
                    target_idx = int(nid.split("_")[-1])
                break
            if nid.startswith("tab_close_"):
                target_action = "close_tab"
                with contextlib.suppress(ValueError):
                    target_idx = int(nid.split("_")[-1])
                break

            if nid.startswith("lbl_"):
                target_action = nid
                break

            for cls in classes:
                if cls.startswith("tab_select_"):
                    target_action = "select"
                    with contextlib.suppress(ValueError):
                        target_idx = int(cls.split("_")[-1])
                    break
                if cls.startswith("tab_close_"):
                    target_action = "close_tab"
                    with contextlib.suppress(ValueError):
                        target_idx = int(cls.split("_")[-1])
                    break
                if cls.startswith("lbl_"):
                    target_action = cls
                    break

            if target_action:
                break

            node = getattr(node, "parent", None)

        if not target_action:
            return

        with contextlib.suppress(Exception):
            event.prevent_default()
            event.stop()

        if target_action == "select" and target_idx is not None:
            self.load_tab_state(target_idx)
        elif target_action == "close_tab" and target_idx is not None:
            self.action_close_tab(target_idx)
        elif target_action == "add":
            self.action_new_tab()
        elif target_action in ("close_app", "lbl_exit"):
            self.action_exit_editor()
        elif target_action == "lbl_save":
            self.action_save_file()
        elif target_action in ("lbl_save_as", "lbl_saveas"):
            self.action_save_file_as()
        elif target_action == "lbl_open":
            self.action_open_file()
        elif target_action == "lbl_search":
            self.action_search_text()
        elif target_action == "lbl_cut":
            self.action_cut_line()
        elif target_action == "lbl_copy":
            self.action_copy_selection()
        elif target_action == "lbl_paste":
            self.action_paste_buffer()
        elif target_action == "lbl_mark":
            self.action_toggle_mark()
        elif target_action == "lbl_placeholders":
            self.action_show_placeholders()
        elif target_action == "lbl_ascii":
            self.action_show_ascii_table()
        elif target_action == "lbl_colors":
            self.action_view_colors()
        elif target_action == "lbl_space":
            self.action_toggle_whitespace()
        elif target_action == "lbl_lineno":
            self.action_toggle_lineno()
        elif target_action == "lbl_markdown":
            self.action_toggle_markdown()
        elif target_action == "lbl_help":
            self.action_help_manual()

    def save_active_tab_state(self) -> None:
        if 0 <= self.active_tab_idx < len(self.tabs):
            tab = self.tabs[self.active_tab_idx]
            try:
                ed = self.query_one("#editor_widget", EditorWidget)
                tab.file_path = self.file_path
                tab.lines = list(ed.lines)
                tab.cursor_y = ed.cursor_y
                tab.cursor_x = ed.cursor_x
                tab.top_line = ed.top_line
                tab.left_col = ed.left_col
                tab.mark_active = ed.mark_active
                tab.mark_y = ed.mark_y
                tab.mark_x = ed.mark_x
                tab.undo_stack = list(ed.undo_stack)
                tab.redo_stack = list(ed.redo_stack)
                tab.modified = ed.modified
                tab.show_markdown = getattr(ed, "show_markdown", False)
            except Exception:  # noqa: BLE001, S110
                pass

    def load_tab_state(self, index: int) -> None:
        if not (0 <= index < len(self.tabs)):
            return
        self.save_active_tab_state()
        self.active_tab_idx = index
        tab = self.tabs[index]
        self.file_path = tab.file_path

        try:
            ed = self.query_one("#editor_widget", EditorWidget)
            ed.lines = list(tab.lines)
            ed.cursor_y = tab.cursor_y
            ed.cursor_x = tab.cursor_x
            ed.top_line = tab.top_line
            ed.left_col = tab.left_col
            ed.mark_active = tab.mark_active
            ed.mark_y = tab.mark_y
            ed.mark_x = tab.mark_x
            ed.undo_stack = list(tab.undo_stack)
            ed.redo_stack = list(tab.redo_stack)
            ed.modified = tab.modified
            ed.show_markdown = getattr(tab, "show_markdown", False)
            ed.clamp_cursor()
            ed.refresh()

            file_name = os.path.basename(self.file_path) if self.file_path else "Untitled"
            borders = getattr(self, "theme_styles", {}).get("window_borders") or bashmenu_ui.get_theme_window_borders(getattr(self, "theme_name", "dracula"))
            l_cap = borders.get("title_left_cap", "[").strip() or "["
            r_cap = borders.get("title_right_cap", "]").strip() or "]"
            self.query_one("#editor_header", Label).update(f"  {l_cap} BashEdit - {file_name} {r_cap}  ")
            self.update_status()
            self.refresh_tab_bar()
        except Exception:  # noqa: BLE001, S110
            pass

    def refresh_tab_bar(self) -> None:
        try:
            tab_bar = self.query_one("#editor_tab_bar", Horizontal)
            tab_bar.remove_children()

            widgets = []
            for idx, tab in enumerate(self.tabs):
                name = os.path.basename(tab.file_path) if tab.file_path else "Untitled"
                mod = " *" if tab.modified else ""
                tab_label = f" {idx + 1}: {name}{mod} "
                cls = "editor_tab_active" if idx == self.active_tab_idx else "editor_tab"
                widgets.append(Label(tab_label, classes=f"editor_tab_select tab_select_{idx} {cls}"))
                if len(self.tabs) > 1:
                    widgets.append(Label(" ✕ ", classes=f"editor_tab_close tab_close_{idx}"))

            widgets.append(Label(" [ + ] ", id="tab_add_new", classes="editor_tab_add"))
            tab_bar.mount(*widgets)
        except Exception:  # noqa: BLE001, S110
            pass

    def action_new_tab(self, file_path: str | None = None, lines: list[str] | None = None) -> None:
        self.save_active_tab_state()
        new_tab = EditorTab(file_path=file_path, lines=lines or [""])
        self.tabs.append(new_tab)
        self.load_tab_state(len(self.tabs) - 1)

    def action_next_tab(self) -> None:
        if len(self.tabs) > 1:
            next_idx = (self.active_tab_idx + 1) % len(self.tabs)
            self.load_tab_state(next_idx)

    def action_prev_tab(self) -> None:
        if len(self.tabs) > 1:
            prev_idx = (self.active_tab_idx - 1) % len(self.tabs)
            self.load_tab_state(prev_idx)

    def action_close_tab(self, index: int | None = None) -> None:
        if index is None:
            index = self.active_tab_idx
        if not (0 <= index < len(self.tabs)):
            return

        self.save_active_tab_state()
        target_tab = self.tabs[index]

        def do_close():
            if len(self.tabs) == 1:
                self.tabs[0] = EditorTab()
                self.load_tab_state(0)
            else:
                self.tabs.pop(index)
                if index < self.active_tab_idx:
                    new_idx = max(0, self.active_tab_idx - 1)
                else:
                    new_idx = min(self.active_tab_idx, len(self.tabs) - 1)
                self.load_tab_state(new_idx)

        if target_tab.modified:
            tab_name = os.path.basename(target_tab.file_path) if target_tab.file_path else "Untitled"

            def confirm_cb(res):
                if res == "yes":
                    if index == self.active_tab_idx:
                        self.action_save_file()
                    do_close()
                elif res == "no":
                    do_close()

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Save Modified Tab?",
                    f"Tab '{tab_name}' has unsaved changes. Save before closing?",
                    theme=self.theme_styles,
                ),
                confirm_cb,
            )
        else:
            do_close()

    def action_exit_editor_force(self) -> None:
        if len(self.app.screen_stack) > 1:
            try:
                self.dismiss(False)
            except Exception:  # noqa: BLE001
                self.app.pop_screen()
        else:
            self.app.exit(False)

    def apply_theme(self) -> None:
        """Apply dynamic theme styles to BashEditScreen, EditorWidget, and header/footer elements."""
        with contextlib.suppress(Exception):
            self.theme_styles = bashmenu_ui.resolve_theme_dict(
                getattr(self, "theme_styles", None) or getattr(self.app, "theme_styles", None), self.app
            )
            t_name = self.theme_styles.get("theme_name") if isinstance(self.theme_styles, dict) else None
            if t_name:
                self.theme_name = t_name
                bashmenu_ui.apply_theme_to_textual_borders(t_name)
            bg_style = self.theme_styles.get("background")
            if bg_style and bg_style.bgcolor and bg_style.bgcolor.name:
                css_bg = bashmenu_ui.parse_css_color(bg_style.bgcolor.name)
                if css_bg:
                    with contextlib.suppress(Exception):
                        self.styles.background = css_bg
                    with contextlib.suppress(Exception):
                        self.query_one("#editor_widget", EditorWidget).styles.background = css_bg

            text_style = self.theme_styles.get("text")
            if text_style and text_style.color and text_style.color.name:
                css_text = bashmenu_ui.parse_css_color(text_style.color.name)
                if css_text:
                    with contextlib.suppress(Exception):
                        self.query_one("#editor_widget", EditorWidget).styles.color = css_text

            hdr_style = self.theme_styles.get("header") or self.theme_styles.get("title")
            if hdr_style:
                if hdr_style.bgcolor and hdr_style.bgcolor.name:
                    css_hdr_bg = bashmenu_ui.parse_css_color(hdr_style.bgcolor.name)
                    if css_hdr_bg:
                        with contextlib.suppress(Exception):
                            self.query_one("#editor_header_bar").styles.background = css_hdr_bg
                if hdr_style.color and hdr_style.color.name:
                    css_hdr_fg = bashmenu_ui.parse_css_color(hdr_style.color.name)
                    if css_hdr_fg:
                        with contextlib.suppress(Exception):
                            self.query_one("#editor_header", Label).styles.color = css_hdr_fg

            with contextlib.suppress(Exception):
                borders = self.theme_styles.get("window_borders") or bashmenu_ui.get_theme_window_borders(getattr(self, "theme_name", "dracula"))
                l_cap = borders.get("title_left_cap", "[").strip() or "["
                r_cap = borders.get("title_right_cap", "]").strip() or "]"
                file_name = os.path.basename(self.file_path) if self.file_path else "Untitled"
                self.query_one("#editor_header", Label).update(f"  {l_cap} BashEdit - {file_name} {r_cap}  ")

            with contextlib.suppress(Exception):
                btn_close = self.query_one("#btn_close_x", Label)
                btn_close.update(bashmenu_ui.format_close_button_label(self.theme_styles))

            theme_div = bashmenu_ui.get_theme_divider(getattr(self, "theme_name", "dracula"))
            div_char = theme_div.get("char", "─") if theme_div else "─"
            if "{" in div_char:
                import bashmenu
                div_char = bashmenu.interpolate_placeholders(div_char, getattr(self, "config", {}))
                div_char = bashmenu.resolve_glyph(div_char, getattr(self, "config", {}))
            if not div_char:
                div_char = "─"
            with contextlib.suppress(Exception):
                self.query_one("#editor_divider", Label).update(div_char * 500)

            divider_style = self.theme_styles.get("divider") or self.theme_styles.get("border") or self.theme_styles.get("accent")
            if divider_style and divider_style.color and divider_style.color.name:
                css_div = bashmenu_ui.parse_css_color(divider_style.color.name)
                if css_div:
                    with contextlib.suppress(Exception):
                        self.query_one("#editor_divider", Label).styles.color = css_div

            status_style = self.theme_styles.get("status") or self.theme_styles.get("footer") or self.theme_styles.get("header")
            if status_style:
                if status_style.bgcolor and status_style.bgcolor.name:
                    css_st_bg = bashmenu_ui.parse_css_color(status_style.bgcolor.name)
                    if css_st_bg:
                        with contextlib.suppress(Exception):
                            self.query_one("#editor_status", Label).styles.background = css_st_bg
                if status_style.color and status_style.color.name:
                    css_st_fg = bashmenu_ui.parse_css_color(status_style.color.name)
                    if css_st_fg:
                        with contextlib.suppress(Exception):
                            self.query_one("#editor_status", Label).styles.color = css_st_fg

            footer_style = self.theme_styles.get("footer") or self.theme_styles.get("background")
            if footer_style and footer_style.bgcolor and footer_style.bgcolor.name:
                css_ftr_bg = bashmenu_ui.parse_css_color(footer_style.bgcolor.name)
                if css_ftr_bg:
                    with contextlib.suppress(Exception):
                        self.query_one("#editor_legend").styles.background = css_ftr_bg

            accent_style = self.theme_styles.get("accent") or self.theme_styles.get("help_text")
            if accent_style and accent_style.color and accent_style.color.name:
                css_accent = bashmenu_ui.parse_css_color(accent_style.color.name)
                if css_accent:
                    with contextlib.suppress(Exception):
                        for item in self.query(".footer_item"):
                            item.styles.color = css_accent

            with contextlib.suppress(Exception):
                ed = self.query_one("#editor_widget", EditorWidget)
                ed.theme = self.theme_styles
                ed._color_span_cache.clear()
                ed.refresh()

    def on_mount(self) -> None:
        self.query_one("#editor_widget", EditorWidget).focus()
        self.apply_theme()

    def update_status(self, msg: str | None = None):
        ed = self.query_one("#editor_widget", EditorWidget)
        if ed.show_markdown:
            total_lines = len(ed._get_rendered_md_lines())
            cur_line = min(total_lines, ed.top_line + 1)
            pos_info = f"[MD View] Line {cur_line}/{total_lines}"
        else:
            pos_info = f"Line {ed.cursor_y + 1}/{len(ed.lines)}, Col {ed.cursor_x + 1}"
        mod = " *" if ed.modified else ""
        text = f"  {pos_info}{mod} | {msg}  " if msg else f"  {pos_info}{mod}  "
        self.query_one("#editor_status", Label).update(text)

    def on_key(self, event: Key) -> None:
        """Process keyboard shortcut bindings, navigation, editing commands, and character entry."""
        ed = self.query_one("#editor_widget", EditorWidget)
        key_lower = (event.key or "").lower()
        char_lower = (event.character or "").lower()

        if key_lower in ["alt+]", "meta+]", "ctrl+tab", "alt+right"]:
            event.prevent_default()
            event.stop()
            self.action_next_tab()
            return

        if key_lower in ["alt+[", "meta+[", "ctrl+shift+tab", "alt+left"]:
            event.prevent_default()
            event.stop()
            self.action_prev_tab()
            return

        if key_lower in ["alt+1", "meta+1", "m-1", "m+1", "alt_1", "meta_1", "esc 1", "escape 1", "¡"] or (
            key_lower.startswith(("alt+", "meta+", "m-", "alt_", "meta_")) and key_lower.endswith("1")
        ) or char_lower in ["¡", "\u00a1"]:
            event.prevent_default()
            event.stop()
            self.action_toggle_whitespace()
            return

        if key_lower in ["escape", "esc"]:
            event.prevent_default()
            event.stop()
            if ed.mark_active:
                ed.mark_active = False
                ed.refresh()
                self.update_status("Mark Unset")
            else:
                self.action_exit_editor()
            return

        # Handle raw ASCII 0x1e (RS) sent by some terminal emulators for Control+^
        if event.character == "\x1e" or key_lower == "rs":
            self.action_toggle_mark()
            return

        # Handle section sign (§ / \u00a7) sent by some terminal emulators when no key binding fires
        if char_lower in ["§", "\u00a7"] or key_lower in ["§", "section"]:
            event.prevent_default()
            event.stop()
            self.action_copy_selection()
            return

        if key_lower in ["f1", "ctrl+g", "alt+h", "meta+h"]:
            event.prevent_default()
            event.stop()
            self.action_help_manual()
            return

        if key_lower in ["alt+t", "meta+t"]:
            event.prevent_default()
            event.stop()
            if self.display_theme_colors:
                self.action_toggle_theme_colors()
            else:
                self.action_new_tab()
            return

        if key_lower in ["alt+v", "meta+v", "f10"]:
            event.prevent_default()
            event.stop()
            self.action_view_colors()
            return

        if key_lower in ["ctrl+a", "ctrl_a", "f11"] or char_lower in ["\x01"]:
            event.prevent_default()
            event.stop()
            self.action_show_ascii_table()
            return

        if key_lower in ["ctrl+p", "alt+m", "meta+m"]:
            event.prevent_default()
            event.stop()
            self.action_show_placeholders()
            return

        if key_lower in ["ctrl+c", "ctrl+shift+c", "ctrl_c", "ctrl_shift_c"] or char_lower in ["\x03"]:
            event.prevent_default()
            event.stop()
            self.action_copy_selection()
            return

        if key_lower in ["ctrl+v", "ctrl+shift+v", "ctrl_v", "ctrl_shift_v"] or char_lower in ["\x16"]:
            event.prevent_default()
            event.stop()
            self.action_paste_buffer()
            return

        if key_lower in ["ctrl+k", "ctrl+shift+k"] or char_lower in ["\x0b"]:
            event.prevent_default()
            event.stop()
            self.action_cut_line()
            return

        if key_lower in ["ctrl+u", "ctrl+shift+u"] or char_lower in ["\x15"]:
            event.prevent_default()
            event.stop()
            self.action_paste_buffer()
            return

        if key_lower == "f12":
            event.prevent_default()
            event.stop()
            self.action_toggle_markdown()
            return

        if ed.show_markdown:
            if event.key == "up":
                ed.scroll_lines_up(1)
                self.update_status()
            elif event.key == "down":
                ed.scroll_lines_down(1)
                self.update_status()
            elif event.key in ("pageup", "page_up"):
                page_size = max(1, (ed.size.height or 20) - 2)
                ed.scroll_lines_up(page_size)
                self.update_status()
            elif event.key in ("pagedown", "page_down"):
                page_size = max(1, (ed.size.height or 20) - 2)
                ed.scroll_lines_down(page_size)
                self.update_status()
            elif event.key == "home":
                ed.top_line = 0
                ed.refresh()
                self.update_status()
            elif event.key == "end":
                total_lines = len(ed._get_rendered_md_lines())
                ed.top_line = max(0, total_lines - 1)
                ed.refresh()
                self.update_status()
            elif (
                key_lower in ["enter", "return", "backspace", "ctrl+h", "delete", "tab", "space", "full_stop"]
                or char_lower in ["\r", "\n", "\t", " "]
                or (len(event.character or "") == 1 and event.character.isprintable())
                or (len(event.key or "") == 1 and event.key.isprintable())
            ):
                self.update_status("Markdown preview active (Press F12 to edit)")
            return

        # Navigation keys
        if event.key == "up":
            ed.cursor_y = max(0, ed.cursor_y - 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
            return
        if event.key == "down":
            if ed.cursor_y < len(ed.lines) - 1:
                ed.cursor_y += 1
                ed.clamp_cursor()
            else:
                ed.scroll_lines_down(1)
            ed.refresh()
            self.update_status()
            return
        if event.key == "left":
            ed.cursor_x = max(0, ed.cursor_x - 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
            return
        if event.key == "right":
            ed.cursor_x = min(len(ed.lines[ed.cursor_y]), ed.cursor_x + 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
            return
        if event.key == "home":
            ed.cursor_x = 0
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
            return
        if event.key == "end":
            ed.cursor_x = len(ed.lines[ed.cursor_y])
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
            return
        if event.key in ("pageup", "page_up"):
            page_size = max(1, (ed.size.height or 20) - 2)
            ed.scroll_lines_up(page_size)
            self.update_status()
            return
        if event.key in ("pagedown", "page_down"):
            page_size = max(1, (ed.size.height or 20) - 2)
            ed.scroll_lines_down(page_size)
            self.update_status()
            return

        # Core editing keys (Enter, Backspace, Delete, Tab, Space)
        if key_lower in ["enter", "return", "ctrl+m", "ctrl+j"] or char_lower in ["\r", "\n"]:
            ed.insert_newline()
            self.update_status()
            return

        if key_lower in ["backspace", "ctrl+h"] or char_lower in ["\x08", "\x7f"]:
            ed.backspace()
            self.update_status()
            return

        if key_lower == "delete":
            ed.delete_char()
            self.update_status()
            return

        if key_lower in ["tab", "ctrl+i"] or char_lower in ["\t"]:
            indent = " " * ed.tabstop if ed.tab_to_spaces else "\t"
            ed.insert_char(indent)
            self.update_status()
            return

        if key_lower == "space" or char_lower == " ":
            ed.insert_char(" ")
            self.update_status()
            return

        # Ignore modifier combinations, function keys & action shortcut keys so Textual bindings process them as actions
        if (
            event.character in ["§", "\u00a7", "\x03", "\x16", "\x0b", "\x15"]
            or (event.character and ord(event.character[0]) < 32)
            or event.key.startswith("ctrl+")
            or event.key.startswith("alt+")
            or event.key.startswith("meta+")
            or (event.key.startswith("f") and event.key[1:].isdigit())
            or event.key
            in [
                "escape",
                "esc",
                "ctrl+6",
                "ctrl+caret",
                "ctrl+circumflex",
                "ctrl+^",
                "ctrl+shift+6",
                "ctrl+rs",
                "ctrl+at",
                "ctrl+space",
                "alt+6",
                "meta+6",
                "alt+c",
                "ctrl+c",
                "ctrl+v",
                "ctrl+shift+c",
                "ctrl+shift+v",
                "rs",
                "§",
                "section",
            ]
        ):
            return

        if len(event.character or "") == 1 and event.character.isprintable():
            ed.insert_char(event.character)
            self.update_status()
        elif event.key == "full_stop":
            ed.insert_char(".")
            self.update_status()
        elif len(event.key or "") == 1 and event.key.isprintable():
            ed.insert_char(event.key)
            self.update_status()

    def on_mouse_scroll_down(self, event) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.scroll_lines_down(3)
        self.update_status()

    def on_mouse_scroll_up(self, event) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.scroll_lines_up(3)
        self.update_status()

    def action_page_up(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        page_size = max(1, (ed.size.height or 20) - 2)
        ed.scroll_lines_up(page_size)
        self.update_status()

    def action_page_down(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        page_size = max(1, (ed.size.height or 20) - 2)
        ed.scroll_lines_down(page_size)
        self.update_status()

    def action_save_file(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        if not self.file_path:
            start_dir = os.getcwd()

            def save_cb(path):
                if path:
                    self.file_path = path
                    self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                    self.action_save_file()

            self.app.push_screen(
                bashmenu_ui.FilePickerModalScreen(
                    "Save File As",
                    start_dir=start_dir,
                    mode="save",
                    default_val="untitled.txt",
                    theme=self.theme_styles,
                ),
                save_cb,
            )
            return

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ed.lines))
            ed.modified = False
            if 0 <= self.active_tab_idx < len(self.tabs):
                self.tabs[self.active_tab_idx].modified = False
                self.tabs[self.active_tab_idx].file_path = self.file_path
            self.refresh_tab_bar()
            self.update_status("Wrote file successfully")
        except (OSError, ValueError) as e:
            self.update_status(f"Error saving file: {e}")

    def action_open_file(self) -> None:
        """Prompt user with file picker modal and load chosen file into current or new editor tab."""
        ed = self.query_one("#editor_widget", EditorWidget)

        def open_cb(path):
            if path and os.path.exists(path):
                # Check if file is already open in a tab
                for idx, tab in enumerate(self.tabs):
                    if tab.file_path and os.path.abspath(tab.file_path) == os.path.abspath(path):
                        self.load_tab_state(idx)
                        self.update_status(f"Switched to open tab {os.path.basename(path)}")
                        return

                # If current active tab is empty and unmodified, load into current tab
                if not self.file_path and not ed.modified and ed.lines == [""]:
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read().splitlines()
                            lines = content if content else [""]
                        self.file_path = path
                        ed.lines = lines
                        ed.cursor_y = 0
                        ed.cursor_x = 0
                        ed.top_line = 0
                        ed.left_col = 0
                        ed.modified = False
                        ed.refresh()
                        if 0 <= self.active_tab_idx < len(self.tabs):
                            self.tabs[self.active_tab_idx].file_path = path
                            self.tabs[self.active_tab_idx].lines = lines
                            self.tabs[self.active_tab_idx].modified = False
                        self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                        self.update_status(f"Opened {os.path.basename(path)}")
                        self.refresh_tab_bar()
                    except (OSError, UnicodeDecodeError, ValueError) as e:
                        self.update_status(f"Error opening file: {e}")
                else:
                    # Open in new tab
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read().splitlines()
                            lines = content if content else [""]
                        self.action_new_tab(file_path=path, lines=lines)
                        self.update_status(f"Opened {os.path.basename(path)} in new tab")
                    except (OSError, UnicodeDecodeError, ValueError) as e:
                        self.update_status(f"Error opening file: {e}")

        start_dir = (
            os.path.dirname(os.path.abspath(self.file_path))
            if self.file_path and os.path.exists(self.file_path)
            else os.getcwd()
        )
        self.app.push_screen(
            bashmenu_ui.FilePickerModalScreen("Open File", start_dir=start_dir, mode="file", theme=self.theme_styles),
            open_cb,
        )

    def action_new_file(self) -> None:
        self.action_new_tab()

    def action_exit_editor(self) -> None:
        self.save_active_tab_state()
        ed = self.query_one("#editor_widget", EditorWidget)
        if ed.mark_active:
            ed.mark_active = False
            ed.refresh()
            self.update_status("Mark Unset")
            return

        def safe_exit(res_val):
            if len(self.app.screen_stack) > 1:
                try:
                    self.dismiss(res_val)
                except Exception:  # noqa: BLE001
                    self.app.pop_screen()
            else:
                self.app.exit(res_val)

        modified_tabs = [t for t in self.tabs if t.modified]
        if not modified_tabs:
            safe_exit(False)
            return

        target_tab = self.tabs[self.active_tab_idx] if self.tabs[self.active_tab_idx].modified else modified_tabs[0]
        tab_name = os.path.basename(target_tab.file_path) if target_tab.file_path else "Untitled"

        def confirm_cb(res):
            if res == "yes":
                if target_tab == self.tabs[self.active_tab_idx]:
                    self.action_save_file()
                safe_exit(True)
            elif res == "no":
                safe_exit(False)

        self.app.push_screen(
            bashmenu_ui.ConfirmModalScreen(
                "Save Modified Tab?", f"Tab '{tab_name}' has unsaved changes. Save before exiting?", theme=self.theme_styles
            ),
            confirm_cb,
        )

    def action_cut_line(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.cut_line()
        self.update_status(msg)

    def action_paste_buffer(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.paste_buffer()
        self.update_status(msg)

    def action_undo(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.undo()
        self.update_status(msg)

    def action_redo(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.redo()
        self.update_status(msg)

    def action_toggle_mark(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.toggle_mark()
        self.update_status(msg)

    def action_copy_selection(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        msg = ed.copy_selection()
        self.update_status(msg)

    def action_toggle_whitespace(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.show_whitespace = not ed.show_whitespace
        ed.refresh()
        status = "enabled" if ed.show_whitespace else "disabled"
        self.update_status(f"Whitespace display {status}")

    def action_toggle_help(self) -> None:
        legend = self.query_one("#editor_legend", Label)
        legend.display = not legend.display
        status = "enabled" if legend.display else "disabled"
        self.update_status(f"Help bar {status}")

    def action_help_manual(self) -> None:
        table_lines = [
            "# BashEdit Keybindings & Controls",
            "",
            "| Keybinding / Shortcut | Description / Action |",
            "| :--- | :--- |",
            "| `^O` / `^R` / `F5` / `F7` | Open File Picker |",
            "| `^S` / `F2` / `F3` | Save File |",
            "| `Alt+S` / `^Shift+S` / `F6` | Save File As (Save Under New Name) |",
            "| `^E` / `F4` / `[ + ]` | New Tab / New File |",
            "| `Alt+]` / `Ctrl+Tab` | Next Tab |",
            "| `Alt+[` / `Shift+Tab` | Previous Tab |",
            "| `^P` / `Alt+M` | Show Available Placeholders & Macros |",
            "| `^A` / `F11` | View ASCII Character Table (`ascii.sh`) |",
            "| `Alt+V` / `F10` | View Terminal Colors (`ncurses_colors.py`) |",
            "| `Alt+1` | Toggle Whitespace Display (spaces & tabs) |",
            "| `^N` / `Alt+N` | Toggle Line Numbers |",
            "| `F12` | Toggle Markdown Rendering |",
            "| `^^` / `Alt+A` | Toggle Mark Selection |",
            "| `^W` | Where Is (Search text) |",
            "| `^K` / `F8` | Cut Line or Selection |",
            "| `^C` / `Alt+6` / `Alt+C` | Copy Line or Selection |",
            "| `^U` / `F9` | Paste Cut Buffer |",
            "| `^Z` / `^Y` | Undo / Redo |",
            "| `^X` / `ESC` | Exit Editor |",
        ]
        if self.display_theme_colors:
            table_lines.append("| `Alt+T` | Toggle Theme Color Display (Refresh) |")

        help_text = "\n".join(table_lines)
        self.app.push_screen(
            bashmenu_ui.MessageModalScreen(
                "BashEdit Manual",
                help_text,
                theme=self.theme_styles,
                is_help=True,
                is_markdown=True,
            )
        )

    def action_save_file_as(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        start_dir = (
            os.path.dirname(os.path.abspath(self.file_path))
            if self.file_path and os.path.exists(self.file_path)
            else os.getcwd()
        )
        default_name = os.path.basename(self.file_path) if self.file_path else "untitled.txt"

        def save_cb(path):
            if path:
                self.file_path = path
                try:
                    with open(self.file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(ed.lines))
                    ed.modified = False
                    if 0 <= self.active_tab_idx < len(self.tabs):
                        self.tabs[self.active_tab_idx].modified = False
                        self.tabs[self.active_tab_idx].file_path = self.file_path
                    self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                    self.refresh_tab_bar()
                    self.update_status(f"Saved as {os.path.basename(path)}")
                except (OSError, ValueError) as e:
                    self.update_status(f"Error saving file: {e}")

        self.app.push_screen(
            bashmenu_ui.FilePickerModalScreen(
                "Save File As",
                start_dir=start_dir,
                mode="save",
                default_val=default_name,
                theme=self.theme_styles,
            ),
            save_cb,
        )

    def action_toggle_lineno(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.show_line_numbers = not ed.show_line_numbers
        ed.refresh()
        self.update_status("Toggled Line Numbers")

    def action_toggle_markdown(self) -> None:
        """Toggles Markdown rendering for the active document buffer."""
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.show_markdown = not ed.show_markdown
        if 0 <= self.active_tab_idx < len(self.tabs):
            self.tabs[self.active_tab_idx].show_markdown = ed.show_markdown
        if not ed.show_markdown:
            ed.clamp_cursor()
        status = "enabled" if ed.show_markdown else "disabled"
        self.update_status(f"Markdown rendering {status}")
        ed.refresh()

    def action_show_pos(self) -> None:
        self.update_status()

    def action_search_text(self) -> None:
        def search_cb(query):
            if not query:
                return
            ed = self.query_one("#editor_widget", EditorWidget)
            for idx, line in enumerate(ed.lines[ed.cursor_y :], start=ed.cursor_y):
                c_idx = line.find(query)
                if c_idx != -1:
                    ed.cursor_y = idx
                    ed.cursor_x = c_idx
                    ed.clamp_cursor()
                    ed.refresh()
                    self.update_status(f"Found '{query}'")
                    return
            self.update_status(f"'{query}' not found")

        self.app.push_screen(
            bashmenu_ui.InputModalScreen("Search Text", "Enter search query:", theme=self.theme_styles),
            search_cb,
        )

    def action_toggle_theme_colors(self) -> None:
        if not self.display_theme_colors:
            return
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.display_theme_colors = not ed.display_theme_colors
        ed._color_span_cache.clear()
        ed.refresh()
        status = "enabled" if ed.display_theme_colors else "disabled"
        self.update_status(f"Theme color display {status}")

    def action_view_colors(self) -> None:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "ncurses_colors.py")
        if not os.path.exists(script_path):
            try:
                import bashmenu
                app_obj = getattr(self, "app", None)
                cfg = getattr(app_obj, "config", {}) if app_obj else {}
                script_path = bashmenu.interpolate_placeholders("{scripts_dir}/ncurses_colors.py", cfg)
            except Exception:  # noqa: BLE001, S110
                pass
        script_cmd = f"{sys.executable} {script_path}"
        self.app.push_screen(bashmenu_ui.StreamOutputModalScreen("View Terminal Colors", script_cmd, theme=self.theme_styles))

    def action_show_ascii_table(self) -> None:
        """Stream ASCII character table modal."""
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "ascii.sh")
        if not os.path.exists(script_path):
            try:
                import bashmenu
                app_obj = getattr(self, "app", None)
                cfg = getattr(app_obj, "config", {}) if app_obj else {}
                script_path = bashmenu.interpolate_placeholders("{scripts_dir}/ascii.sh", cfg)
            except Exception:  # noqa: BLE001, S110
                pass
        script_cmd = f'bash "{script_path}"'
        self.app.push_screen(bashmenu_ui.StreamOutputModalScreen("ASCII Character Table", script_cmd, theme=self.theme_styles))

    def action_show_placeholders(self) -> None:
        self.app.push_screen(
            bashmenu_ui.MessageModalScreen(
                "Available Placeholders & Macros",
                bashmenu_ui.PLACEHOLDER_HELP_TEXT,
                theme=self.theme_styles,
                is_help=True,
            )
        )


class BashEditApp(App):
    """Standalone App launcher for BashEdit."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, file_path: str | None = None, display_theme_colors: bool = False, theme=None, **kwargs):
        super().__init__()
        self.file_path = file_path
        self.display_theme_colors = display_theme_colors
        self.editor_theme = theme
        self.kwargs = kwargs

    def on_mount(self) -> None:
        theme_name = "dracula"
        if isinstance(self.editor_theme, str):
            theme_name = self.editor_theme
        elif not isinstance(self.editor_theme, dict):
            try:
                import bashmenu
                config = bashmenu.load_config() if hasattr(bashmenu, "load_config") else {}
                if isinstance(config, dict) and "theme" in config:
                    theme_name = config.get("theme", "dracula")
            except Exception:  # noqa: BLE001, S110
                pass
        self.theme_styles = (
            bashmenu_ui.init_theme_colors(theme_name)
            if isinstance(self.editor_theme, str) or not isinstance(self.editor_theme, dict)
            else self.editor_theme
        )
        self.push_screen(
            BashEditScreen(
                file_path=self.file_path,
                display_theme_colors=self.display_theme_colors,
                theme=self.theme_styles,
                **self.kwargs,
            )
        )


def run_curses_editor(
    stdscr,
    file_path,
    theme,
    show_whitespace=False,
    tab_to_spaces=True,
    tabstop=8,
    display_theme_colors=False,
):
    """Compatibility runner for launching BashEdit in Textual."""
    app = BashEditApp(
        file_path=file_path,
        theme=theme,
        show_whitespace=show_whitespace,
        tab_to_spaces=tab_to_spaces,
        tabstop=tabstop,
        display_theme_colors=display_theme_colors,
    )
    app.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BashEdit - Nano-style text editor")
    parser.add_argument("file_path", nargs="?", default=None, help="File path to edit")
    parser.add_argument(
        "--display-theme-colors",
        action="store_true",
        help="Display theme color codes in their assigned colors",
    )
    args, _ = parser.parse_known_args()

    app = BashEditApp(
        file_path=args.file_path,
        display_theme_colors=args.display_theme_colors,
    )
    app.run()
