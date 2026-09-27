"""
bashedit.py - Built-in Nano-style text editor implemented in Textual.
"""

import os
import sys

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Label

import bashmenu_ui


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
    ):
        super().__init__()
        self.lines = list(lines) if lines else [""]
        self.cursor_y = 0
        self.cursor_x = 0
        self.scroll_y = 0
        self.scroll_x = 0
        self.show_line_numbers = show_line_numbers
        self.show_whitespace = show_whitespace
        self.tab_to_spaces = tab_to_spaces
        self.tabstop = tabstop
        self.theme = theme or {}

        self.mark_active = False
        self.mark_y = 0
        self.mark_x = 0

        self.cutbuffer = []
        self.undo_stack = []
        self.redo_stack = []
        self.MAX_HISTORY = 100
        self.modified = False

    def render(self) -> Text:
        """Render visible text lines with selection, line numbers, and cursor."""
        out = Text()
        height = self.size.height or 20
        width = self.size.width or 80

        lineno_width = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0

        for row_idx in range(height):
            line_num = self.scroll_y + row_idx
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
                disp_text = disp_text.replace(" ", "·").replace("\t", "➔" + " " * (self.tabstop - 1))

            content_width = max(1, width - lineno_width)
            visible_segment = disp_text[self.scroll_x : self.scroll_x + content_width]

            # Render line text with selection / cursor
            line_rich = Text(visible_segment)

            # Highlight current line cursor position
            if line_num == self.cursor_y:
                rel_cursor_x = self.cursor_x - self.scroll_x
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
        self.refresh()
        return "Redo"

    def clamp_cursor(self):
        self.cursor_y = max(0, min(self.cursor_y, len(self.lines) - 1))
        current_line_len = len(self.lines[self.cursor_y])
        self.cursor_x = max(0, min(self.cursor_x, current_line_len))

        # Adjust viewport scroll position
        height = max(1, self.size.height or 20)
        width = max(1, self.size.width or 80)

        if self.cursor_y < self.scroll_y:
            self.scroll_y = self.cursor_y
        elif self.cursor_y >= self.scroll_y + height:
            self.scroll_y = self.cursor_y - height + 1

        lineno_w = len(str(len(self.lines))) + 2 if self.show_line_numbers else 0
        visible_w = max(10, width - lineno_w)

        if self.cursor_x < self.scroll_x:
            self.scroll_x = self.cursor_x
        elif self.cursor_x >= self.scroll_x + visible_w:
            self.scroll_x = self.cursor_x - visible_w + 1

    def insert_char(self, char: str):
        self.push_undo()
        line = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = line[: self.cursor_x] + char + line[self.cursor_x :]
        self.cursor_x += len(char)
        self.modified = True
        self.clamp_cursor()
        self.refresh()

    def insert_newline(self):
        self.push_undo()
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

    def cut_line(self) -> str:
        self.push_undo()
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
    #editor_header {
        dock: top;
        height: 1;
        background: $accent;
        color: $text-primary;
        text-align: center;
        text-style: bold;
    }
    #editor_status {
        dock: bottom;
        height: 1;
        background: $primary-dark;
        color: $text-muted;
    }
    #editor_legend {
        dock: bottom;
        height: 2;
        background: $surface-darken-1;
        color: $accent;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("ctrl+o", "save_file", "WriteOut"),
        Binding("ctrl+x", "exit_editor", "Exit"),
        Binding("ctrl+w", "search_text", "WhereIs"),
        Binding("ctrl+k", "cut_line", "Cut"),
        Binding("ctrl+u", "paste_buffer", "Paste"),
        Binding("ctrl+z", "undo", "Undo"),
        Binding("ctrl+y", "redo", "Redo"),
        Binding("ctrl+n", "toggle_lineno", "Line Numbers"),
        Binding("ctrl+c", "show_pos", "Cur Pos"),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("left", "move_left", "Left", show=False),
        Binding("right", "move_right", "Right", show=False),
        Binding("home", "move_home", "Home", show=False),
        Binding("end", "move_end", "End", show=False),
    ]

    def __init__(
        self,
        file_path: str = None,
        theme: dict = None,
        show_whitespace: bool = False,
        tab_to_spaces: bool = True,
        tabstop: int = 8,
    ):
        super().__init__()
        self.file_path = file_path
        self.theme = theme or {}
        self.show_whitespace = show_whitespace
        self.tab_to_spaces = tab_to_spaces
        self.tabstop = tabstop

        lines = [""]
        if self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().splitlines()
                    lines = content if content else [""]
            except Exception as e:
                lines = [f"# Error reading file: {e}"]

        self.initial_lines = lines

    def compose(self) -> ComposeResult:
        file_name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        yield Label(f"  BashEdit - {file_name}  ", id="editor_header")
        yield EditorWidget(
            lines=self.initial_lines,
            show_whitespace=self.show_whitespace,
            tab_to_spaces=self.tab_to_spaces,
            tabstop=self.tabstop,
            theme=self.theme,
            id="editor_widget",
        )
        yield Label(
            "^O WriteOut  ^W Where Is  ^K Cut Line  ^U Paste  ^Z Undo  ^X Exit",
            id="editor_legend",
        )
        yield Label("  Line 1/1, Col 1  ", id="editor_status")

    def update_status(self, msg: str = None):
        ed = self.query_one("#editor_widget", EditorWidget)
        pos_info = f"Line {ed.cursor_y + 1}/{len(ed.lines)}, Col {ed.cursor_x + 1}"
        mod = " *" if ed.modified else ""
        text = f"  {pos_info}{mod} | {msg}  " if msg else f"  {pos_info}{mod}  "
        self.query_one("#editor_status", Label).update(text)

    def on_key(self, event: Key) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)

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
                    self.action_save_file()

            self.app.push_screen(
                bashmenu_ui.InputModalScreen("Save File As", "Enter file path:"),
                save_cb,
            )
            return

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ed.lines))
            ed.modified = False
            self.update_status("Wrote file successfully")
        except Exception as e:
            self.update_status(f"Error saving file: {e}")

    def action_exit_editor(self) -> None:
        ed = self.query_one("#editor_widget", EditorWidget)
        if ed.modified:

            def confirm_cb(res):
                if res == "yes":
                    self.action_save_file()
                    self.dismiss(True)
                elif res == "no":
                    self.dismiss(False)

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Save Modified File?", "File has unsaved changes. Save before exiting?"
                ),
                confirm_cb,
            )
        else:
            self.dismiss(False)

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
            bashmenu_ui.InputModalScreen("Search Text", "Enter search query:"),
            search_cb,
        )


class BashEditApp(App):
    """Standalone App launcher for BashEdit."""

    def __init__(self, file_path: str = None, **kwargs):
        super().__init__()
        self.file_path = file_path
        self.kwargs = kwargs

    def on_mount(self) -> None:
        self.push_screen(BashEditScreen(file_path=self.file_path, **self.kwargs))


def run_curses_editor(
    stdscr,
    file_path,
    theme,
    show_whitespace=False,
    tab_to_spaces=True,
    tabstop=8,
):
    """Compatibility runner for launching BashEdit in Textual."""
    app = BashEditApp(
        file_path=file_path,
        theme=theme,
        show_whitespace=show_whitespace,
        tab_to_spaces=tab_to_spaces,
        tabstop=tabstop,
    )
    app.run()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    app = BashEditApp(file_path=target)
    app.run()
