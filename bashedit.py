#!/usr/bin/env python3
"""
bashedit.py - Built-in Nano-style text editor implemented in Textual.
"""

import contextlib
import os
import re
import sys
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Key
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


def get_token_foreground_style(token_str: str) -> bashmenu_ui.Style | None:
    """Resolve token inside brackets to its assigned curses foreground color style."""
    clean_tok = token_str.strip("\"'")
    if clean_tok in COLOR_TOKEN_MAP:
        return COLOR_TOKEN_MAP[clean_tok]
    if clean_tok == "-1":
        return bashmenu_ui.Style(color="white", dim=True)
    if clean_tok.isdigit():
        val = int(clean_tok)
        if 0 <= val <= 255:
            css = bashmenu_ui.parse_css_color(val)
            if css:
                if val in (0, 16, 232, 233, 234, 235, 236) or css == "black":
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

    def __init__(
        self,
        lines=None,
        show_line_numbers=True,
        show_whitespace=False,
        tab_to_spaces=True,
        tabstop=8,
        theme=None,
        display_theme_colors=False,
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
        if not text or "[" not in text or "]" not in text:
            return []
        if text in self._color_span_cache:
            return self._color_span_cache[text]

        spans = []
        for bm in BRACKET_PATTERN.finditer(text):
            bracket_content = bm.group(1)
            bracket_start = bm.start(1)
            for tm in TOKEN_PATTERN.finditer(bracket_content):
                tok = tm.group(0)
                st = get_token_foreground_style(tok)
                if st:
                    s_idx = bracket_start + tm.start()
                    e_idx = bracket_start + tm.end()
                    spans.append((s_idx, e_idx, st))

        if len(self._color_span_cache) > 2000:
            self._color_span_cache.clear()
        self._color_span_cache[text] = spans
        return spans

    def render(self) -> Text:
        """Render visible text lines with selection, line numbers, and cursor."""
        out = Text()
        height = max(1, self.size.height or 20)
        width = max(1, self.size.width or 80)

        lineno_width = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0

        for row_idx in range(height):
            line_num = self.top_line + row_idx
            if line_num >= len(self.lines):
                out.append("~\n", style="dim cyan")
                continue

            line_text = self.lines[line_num]

            if self.show_line_numbers:
                num_str = f"{line_num + 1:>{lineno_width - 1}} "
                out.append(num_str, style="dim white")

            # Format line content with optional whitespace rendering
            disp_text = line_text
            if self.show_whitespace:
                out_chars = []
                col = 0
                for char in line_text:
                    if char == " ":
                        out_chars.append("·")
                        col += 1
                    elif char == "\t":
                        tab_width = self.tabstop - (col % self.tabstop)
                        out_chars.append("→" + " " * (tab_width - 1))
                        col += tab_width
                    elif char == "\r":
                        out_chars.append("↵")
                        col += 1
                    else:
                        out_chars.append(char)
                        col += 1
                disp_text = "".join(out_chars) + "↵"

            content_width = max(1, width - lineno_width)
            sx = self.left_col
            visible_segment = disp_text[sx : sx + content_width]

            # Render line text with selection / cursor
            line_rich = Text(visible_segment)

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
                        line_rich.stylize("reverse bold magenta", rel_s, rel_e)

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

        if self.cursor_y < self.top_line:
            self.top_line = self.cursor_y
        elif self.cursor_y >= self.top_line + height:
            self.top_line = self.cursor_y - height + 1

        lineno_w = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0
        visible_w = max(10, width - lineno_w)

        if self.cursor_x < self.left_col:
            self.left_col = self.cursor_x
        elif self.cursor_x >= self.left_col + visible_w:
            self.left_col = self.cursor_x - visible_w + 1

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
        sel = self.get_selection_range()
        if not sel:
            line = self.lines[self.cursor_y]
            self.cutbuffer = [line]
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

        self.mark_active = False
        self.refresh()
        return "Selection Copied"

    def cut_line(self) -> str:
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
            self.modified = True
            self.clamp_cursor()
            self.refresh()
            return "Selection Cut"
        else:
            if len(self.lines) > 1:
                removed = self.lines.pop(self.cursor_y)
                self.cutbuffer = [removed]
            else:
                self.cutbuffer = [self.lines[0]]
                self.lines[0] = ""
            self.modified = True
            self.clamp_cursor()
            self.refresh()
            return "Line Cut"

    def paste_buffer(self) -> str:
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


class BashEditScreen(Screen):
    """Full screen Nano-style text editor."""

    DEFAULT_CSS = """
    BashEditScreen {
        layout: vertical;
        background: $surface;
    }
    #editor_header_bar {
        dock: top;
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
    #editor_status {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text-muted;
    }
    #editor_legend {
        dock: bottom;
        height: 1;
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
        dock: bottom;
        height: 1;
        width: 100%;
        color: $accent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+o", "save_file", "Save"),
        Binding("f2", "save_file", "Save", show=False),
        Binding("f3", "save_file", "Save", show=False),
        Binding("ctrl+r", "open_file", "Open"),
        Binding("f5", "open_file", "Open", show=False),
        Binding("f7", "open_file", "Open", show=False),
        Binding("ctrl+e", "new_file", "New", show=False),
        Binding("f4", "new_file", "New", show=False),
        Binding("ctrl+s", "save_file_as", "Save As", show=False),
        Binding("f6", "save_file_as", "Save As", show=False),
        Binding("ctrl+k", "cut_line", "Cut"),
        Binding("f8", "cut_line", "Cut", show=False),
        Binding("ctrl+u", "paste_buffer", "Paste"),
        Binding("ctrl+v", "paste_buffer", "Paste", show=False),
        Binding("f9", "paste_buffer", "Paste", show=False),
        Binding("ctrl+w", "search_text", "WhereIs"),
        Binding("ctrl+x", "exit_editor", "Exit"),
        Binding("escape", "exit_editor", "Exit", show=False),
        Binding("esc", "exit_editor", "Exit", show=False),
        Binding("alt+p", "toggle_whitespace", "Whitespace"),
        Binding("alt+w", "toggle_whitespace", "Whitespace", show=False),
        Binding("ctrl+p", "toggle_whitespace", "Whitespace", show=False),
        Binding("ctrl+6", "toggle_mark", "Mark"),
        Binding("alt+a", "toggle_mark", "Mark", show=False),
        Binding("ctrl+c", "copy_selection", "Copy", show=False),
        Binding("alt+6", "copy_selection", "Copy", show=False),
        Binding("§", "copy_selection", "Copy", show=False),
        Binding("alt+c", "copy_selection", "Copy", show=False),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+y", "redo", "Redo"),
        Binding("ctrl+n", "toggle_lineno", "Line Numbers"),
        Binding("alt+n", "toggle_lineno", "Line Numbers", show=False),
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

    def compose(self) -> ComposeResult:
        file_name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        with Horizontal(id="editor_header_bar"):
            yield Label(f"  BashEdit - {file_name}  ", id="editor_header")
            yield Label(bashmenu_ui.format_close_button_label(), id="btn_close_x", classes="btn_close_x")
        yield EditorWidget(
            lines=self.initial_lines,
            show_whitespace=self.show_whitespace,
            tab_to_spaces=self.tab_to_spaces,
            tabstop=self.tabstop,
            theme=self.theme_styles,
            display_theme_colors=self.display_theme_colors,
            id="editor_widget",
        )
        yield Label("─" * 300, id="editor_divider")
        with Horizontal(id="editor_legend"):
            yield Label("^O Save", id="lbl_save", classes="footer_item", markup=False)
            yield Label("^R Open", id="lbl_open", classes="footer_item", markup=False)
            yield Label("^W Search", id="lbl_search", classes="footer_item", markup=False)
            yield Label("^K Cut", id="lbl_cut", classes="footer_item", markup=False)
            yield Label("Alt+6 Copy", id="lbl_copy", classes="footer_item", markup=False)
            yield Label("^U Paste", id="lbl_paste", classes="footer_item", markup=False)
            yield Label("^^ Mark", id="lbl_mark", classes="footer_item", markup=False)
            yield Label("^P Space", id="lbl_space", classes="footer_item", markup=False)
            yield Label("^N Lineno", id="lbl_lineno", classes="footer_item", markup=False)
            yield Label("F1 Help", id="lbl_help", classes="footer_item", markup=False)
            yield Label("^X Exit", id="lbl_exit", classes="footer_item", markup=False)
        yield Label("  Line 1/1, Col 1  ", id="editor_status")

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if not widget:
            return
        lbl_id = getattr(widget, "id", None)
        if lbl_id == "lbl_save":
            self.action_save_file()
        elif lbl_id == "lbl_open":
            self.action_open_file()
        elif lbl_id == "lbl_search":
            self.action_search_text()
        elif lbl_id == "lbl_cut":
            self.action_cut_line()
        elif lbl_id == "lbl_copy":
            self.action_copy_selection()
        elif lbl_id == "lbl_paste":
            self.action_paste_buffer()
        elif lbl_id == "lbl_mark":
            self.action_toggle_mark()
        elif lbl_id == "lbl_space":
            self.action_toggle_whitespace()
        elif lbl_id == "lbl_lineno":
            self.action_toggle_lineno()
        elif lbl_id == "lbl_help":
            self.action_help_manual()
        elif lbl_id in ("lbl_exit", "btn_close_x"):
            self.action_exit_editor()

    def on_mount(self) -> None:
        self.query_one("#editor_widget", EditorWidget).focus()
        with contextlib.suppress(Exception):
            btn_close = self.query_one("#btn_close_x", Label)
            btn_close.update(bashmenu_ui.format_close_button_label(self.theme_styles))
        divider_style = self.theme_styles.get("divider") or self.theme_styles.get("border") or self.theme_styles.get("accent")
        if divider_style and divider_style.color and divider_style.color.name:
            css_div = bashmenu_ui.parse_css_color(divider_style.color.name)
            if css_div:
                self.query_one("#editor_divider", Label).styles.color = css_div

    def update_status(self, msg: str | None = None):
        ed = self.query_one("#editor_widget", EditorWidget)
        pos_info = f"Line {ed.cursor_y + 1}/{len(ed.lines)}, Col {ed.cursor_x + 1}"
        mod = " *" if ed.modified else ""
        text = f"  {pos_info}{mod} | {msg}  " if msg else f"  {pos_info}{mod}  "
        self.query_one("#editor_status", Label).update(text)

    def on_key(self, event: Key) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)

        # Handle raw ASCII 0x1e (RS) sent by some terminal emulators for Control+^
        if event.character == "\x1e" or event.key == "rs":
            self.action_toggle_mark()
            return

        # Handle section sign (§ / \u00a7) sent by some terminal emulators when no key binding fires
        if event.character in ["§", "\u00a7"] or event.key in ["§", "section"]:
            event.prevent_default()
            event.stop()
            self.action_copy_selection()
            return

        if event.key in ["f1", "ctrl+g", "alt+h", "meta+h"]:
            event.prevent_default()
            event.stop()
            self.action_help_manual()
            return

        if event.key in ["alt+t", "meta+t"]:
            event.prevent_default()
            event.stop()
            self.action_toggle_theme_colors()
            return

        if event.key in ["alt+v", "meta+v"]:
            event.prevent_default()
            event.stop()
            self.action_view_colors()
            return

        # Ignore modifier combinations, function keys & action shortcut keys so Textual bindings process them as actions
        if (
            event.character in ["§", "\u00a7"]
            or event.key.startswith("ctrl+")
            or event.key.startswith("alt+")
            or event.key.startswith("meta+")
            or event.key.startswith("f")
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
                "rs",
                "§",
                "section",
            ]
        ):
            return

        if event.key == "up":
            ed.cursor_y = max(0, ed.cursor_y - 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "down":
            ed.cursor_y = min(len(ed.lines) - 1, ed.cursor_y + 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "left":
            ed.cursor_x = max(0, ed.cursor_x - 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "right":
            ed.cursor_x = min(len(ed.lines[ed.cursor_y]), ed.cursor_x + 1)
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "home":
            ed.cursor_x = 0
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "end":
            ed.cursor_x = len(ed.lines[ed.cursor_y])
            ed.clamp_cursor()
            ed.refresh()
            self.update_status()
        elif event.key == "enter":
            ed.insert_newline()
            self.update_status()
        elif event.key in ["backspace", "ctrl+h"]:
            ed.backspace()
            self.update_status()
        elif event.key == "delete":
            ed.delete_char()
            self.update_status()
        elif event.key == "tab":
            indent = " " * ed.tabstop if ed.tab_to_spaces else "\t"
            ed.insert_char(indent)
            self.update_status()
        elif len(event.character or "") == 1 and event.character.isprintable():
            ed.insert_char(event.character)
            self.update_status()

    def action_save_file(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        if not self.file_path:

            def save_cb(path):
                if path:
                    self.file_path = path
                    self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                    self.action_save_file()

            self.app.push_screen(
                bashmenu_ui.InputModalScreen("Save File As", "Enter file path:", theme=self.theme_styles),
                save_cb,
            )
            return

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ed.lines))
            ed.modified = False
            self.update_status("Wrote file successfully")
        except (OSError, ValueError) as e:
            self.update_status(f"Error saving file: {e}")

    def action_open_file(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)

        def open_cb(path):
            if path and os.path.exists(path):
                self.file_path = path
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read().splitlines()
                        ed.lines = content if content else [""]
                    ed.cursor_y = 0
                    ed.cursor_x = 0
                    ed.top_line = 0
                    ed.left_col = 0
                    ed.modified = False
                    ed.refresh()
                    self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                    self.update_status(f"Opened {os.path.basename(path)}")
                except (OSError, UnicodeDecodeError, ValueError) as e:
                    self.update_status(f"Error opening file: {e}")

        if ed.modified:
            def confirm_open(res):
                if res == "yes":
                    self.action_save_file()
                    self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Open File", mode="file", theme=self.theme_styles), open_cb)
                elif res == "no":
                    self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Open File", mode="file", theme=self.theme_styles), open_cb)

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen("Save Changes?", "File has unsaved changes. Save before opening new file?", theme=self.theme_styles),
                confirm_open,
            )
        else:
            self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Open File", mode="file", theme=self.theme_styles), open_cb)

    def action_new_file(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)

        def reset_buffer():
            self.file_path = None
            ed.lines = [""]
            ed.cursor_y = 0
            ed.cursor_x = 0
            ed.top_line = 0
            ed.left_col = 0
            ed.modified = False
            ed.refresh()
            self.query_one("#editor_header", Label).update("  BashEdit - Untitled  ")
            self.update_status("New File")

        if ed.modified:
            def confirm_new(res):
                if res == "yes":
                    self.action_save_file()
                    reset_buffer()
                elif res == "no":
                    reset_buffer()

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen("Save Changes?", "File has unsaved changes. Save before creating new file?", theme=self.theme_styles),
                confirm_new,
            )
        else:
            reset_buffer()

    def action_exit_editor(self) -> None:
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

        if ed.modified:

            def confirm_cb(res):
                if res == "yes":
                    self.action_save_file()
                    safe_exit(True)
                elif res == "no":
                    safe_exit(False)

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Save Modified File?", "File has unsaved changes. Save before exiting?", theme=self.theme_styles
                ),
                confirm_cb,
            )
        else:
            safe_exit(False)

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
        help_lines = [
            "BashEdit Keybindings & Controls:",
            "",
            "• ^O / F2 / F3       : Write Out (Save file)",
            "• ^R / F5 / F7       : Open File Chooser",
            "• ^S / F6           : Save As",
            "• ^E / F4           : New Document",
            "• ^P / Alt+P        : Toggle Whitespace Display (spaces & tabs)",
            "• ^N / Alt+N        : Toggle Line Numbers",
            "• ^^ / Alt+A        : Toggle Mark Selection",
            "• ^W                : Where Is (Search text)",
            "• ^K / F8           : Cut Line or Selection",
            "• ^C / Alt+6 / Alt+C: Copy Line or Selection",
            "• ^U / F9           : Paste Cut Buffer",
            "• ^Z / ^Y           : Undo / Redo",
            "• ^X / ESC          : Exit Editor",
        ]
        if self.display_theme_colors:
            help_lines.append("• Alt+T              : Toggle Theme Color Display (Refresh)")
            help_lines.append("• Alt+V              : View Terminal Colors (256 Palette)")

        help_text = "\n".join(help_lines)
        self.app.push_screen(bashmenu_ui.MessageModalScreen("BashEdit Manual", help_text, theme=self.theme_styles, is_help=True))

    def action_save_file_as(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)

        def save_cb(path):
            if path:
                self.file_path = path
                try:
                    with open(self.file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(ed.lines))
                    ed.modified = False
                    self.query_one("#editor_header", Label).update(f"  BashEdit - {os.path.basename(path)}  ")
                    self.update_status(f"Saved as {os.path.basename(path)}")
                except (OSError, ValueError) as e:
                    self.update_status(f"Error saving file: {e}")

        self.app.push_screen(
            bashmenu_ui.InputModalScreen("Save File As", "Enter file path:", theme=self.theme_styles),
            save_cb,
        )

    def action_toggle_lineno(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        ed.show_line_numbers = not ed.show_line_numbers
        ed.refresh()
        self.update_status("Toggled Line Numbers")

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
        if not self.display_theme_colors:
            return
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "ncurses_colors.py")
        script_cmd = f"{sys.executable} {script_path}"
        self.app.push_screen(bashmenu_ui.StreamOutputModalScreen("View Colors", script_cmd))


class BashEditApp(App):
    """Standalone App launcher for BashEdit."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, file_path: str | None = None, display_theme_colors: bool = False, theme=None, **kwargs):
        super().__init__()
        self.file_path = file_path
        self.display_theme_colors = display_theme_colors
        self.theme = theme
        self.kwargs = kwargs

    def on_mount(self) -> None:
        theme_name = "dracula"
        if isinstance(self.theme, str):
            theme_name = self.theme
        elif not isinstance(self.theme, dict):
            try:
                import bashmenu
                config = bashmenu.load_config() if hasattr(bashmenu, "load_config") else {}
                if isinstance(config, dict) and "theme" in config:
                    theme_name = config.get("theme", "dracula")
            except Exception:  # noqa: BLE001, S110
                pass
        self.theme_styles = bashmenu_ui.init_theme_colors(theme_name) if isinstance(self.theme, str) or not isinstance(self.theme, dict) else self.theme
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
