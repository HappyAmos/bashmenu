#!/usr/bin/env python3
"""
menuedit.py - Interactive Visual Menu Editor for HA Bash Menu (bashmenu.mnu) implemented in Textual.
Features a side-by-side Tree navigation layout and Property Inspector panel.
"""

__version__ = "0.0.1"
__author__ = "HappyAmos"

import contextlib
import os
import sys
import textwrap
from typing import ClassVar

import yaml
from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Static, Tree
from textual.widgets.option_list import Option

import bashmenu
import bashmenu_ui

TYPE_BADGES = {
    "root_menu": "[MNU]",
    "submenu": "[DIR]",
    "command": "[CMD]",
    "script": "[SCR]",
    "config": "[CFG]",
    "toggle": "[TGL]",
    "editor": "[EDT]",
    "confirm": "[CNF]",
    "message": "[MSG]",
    "python": "[PY ]",
    "inject_block": "[INJ]",
    "theme_selector": "[THM]",
    "back": "[BCK]",
    "exit": "[EXT]",
    "divider": "[DIV]",
}

ITEM_TYPES = [
    ("submenu", "Submenu Folder (nested options list)"),
    ("command", "Shell Command (executes shell command)"),
    ("script", "Script File (runs script from app folder)"),
    ("config", "Config Setting (edits bashmenu.yml value)"),
    ("toggle", "Settings Toggle (True/False/Cancel toggle modal)"),
    ("editor", "File Editor (opens file in built-in editor)"),
    ("confirm", "Confirm Dialog (Yes/No/Cancel dialog)"),
    ("message", "Message Popup (alert / info text dialog)"),
    ("python", "Python Routine (built-in python function)"),
    ("inject_block", "Inject Block (dynamic code block template)"),
    ("theme_selector", "Theme Selector (dynamic theme menu)"),
    ("back", "Back Button (returns to parent menu)"),
    ("exit", "Exit Button (terminates application)"),
    ("divider", "Visual Divider Line (aesthetic separator)"),
]


from bashmenu_ui import PLACEHOLDER_HELP_TEXT


class ItemTypePickerModal(ModalScreen[str]):
    """Modal dialog to select type when adding a new item."""

    DEFAULT_CSS = """
    ItemTypePickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 78;
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
    #option_list {
        height: 13;
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
        Binding("c", "cancel", "Cancel"),
    ]

    def __init__(self, theme: dict | None = None):
        super().__init__()
        self.theme = theme or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Horizontal(id="title_bar"):
                yield Label("Select Item Type", id="title")
                yield Label(bashmenu_ui.format_close_button_label(self.theme), id="btn_close_x", classes="btn_close_x")
            yield OptionList(id="option_list")
            yield Label("[ENTER] Select | [ESC / C] Cancel", id="footer")

    def on_mount(self) -> None:
        bashmenu_ui.apply_modal_theme(self, self.theme)
        opts = self.query_one("#option_list", OptionList)
        col1_width = 24
        indent_spaces = " " * col1_width
        for type_key, desc in ITEM_TYPES:
            badge = TYPE_BADGES.get(type_key, "[???]")
            col1 = f"{badge} {type_key:<15} │ "
            wrapped_desc = textwrap.wrap(desc, width=44)
            if wrapped_desc:
                first_line = f"{col1}{wrapped_desc[0]}"
                subsequent_lines = [f"{indent_spaces}{line}" for line in wrapped_desc[1:]]
                option_str = "\n".join([first_line] + subsequent_lines)
            else:
                option_str = col1
            opts.add_option(Option(option_str))

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(ITEM_TYPES):
            self.dismiss(ITEM_TYPES[idx][0])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ExecModeContainer(Vertical):
    """Focusable container for 3-way Execution Mode selector."""

    DEFAULT_CSS = """
    ExecModeContainer {
        height: 5;
        border: solid $accent;
        margin-bottom: 1;
        padding: 0;
    }
    ExecModeContainer:focus {
        border: double $accent;
        background: $surface-lighten-1;
    }
    .mode_row {
        height: 1;
        width: 100%;
        layout: horizontal;
        padding: 0 1;
    }
    .mode_row:hover {
        background: $boost;
    }
    .mode_row.selected {
        background: $accent-darken-1;
        color: $text;
    }
    .mode_indicator {
        width: 2;
        color: $accent;
    }
    .mode_row.selected .mode_indicator {
        color: $text;
    }
    .mode_emoji {
        width: 4;
    }
    .mode_text {
        width: 1fr;
    }
    """

    can_focus = True

    def __init__(self, selected_mode_idx: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.selected_mode_idx = selected_mode_idx

    def compose(self) -> ComposeResult:
        with Horizontal(id="mode_row_0", classes="mode_row"):
            yield Label("● ", classes="mode_indicator", id="ind_0")
            yield Label("📡", classes="mode_emoji")
            yield Label("Streaming Mode (stream=true, live TUI modal output)", classes="mode_text")
        with Horizontal(id="mode_row_1", classes="mode_row"):
            yield Label("○ ", classes="mode_indicator", id="ind_1")
            yield Label("🖥️", classes="mode_emoji")
            yield Label("Interactive Mode (interactive=true, full-screen TTY tool)", classes="mode_text")
        with Horizontal(id="mode_row_2", classes="mode_row"):
            yield Label("○ ", classes="mode_indicator", id="ind_2")
            yield Label("📄", classes="mode_emoji")
            yield Label("Standard Terminal Mode (quiet=false, header & pause prompt)", classes="mode_text")

    def on_mount(self) -> None:
        self.set_selected_mode(self.selected_mode_idx, emit_message=False)

    class ModeChanged(Message):
        """Event emitted when selected execution mode changes."""

        def __init__(self, mode_idx: int) -> None:
            self.mode_idx = mode_idx
            super().__init__()

    def set_selected_mode(self, idx: int, emit_message: bool = True) -> None:
        old_idx = getattr(self, "selected_mode_idx", None)
        self.selected_mode_idx = idx % 3
        for i in range(3):
            with contextlib.suppress(Exception):
                row = self.query_one(f"#mode_row_{i}", Horizontal)
                ind = self.query_one(f"#ind_{i}", Label)
                if i == self.selected_mode_idx:
                    row.add_class("selected")
                    ind.update("● ")
                else:
                    row.remove_class("selected")
                    ind.update("○ ")
        if emit_message and old_idx != self.selected_mode_idx:
            self.post_message(self.ModeChanged(self.selected_mode_idx))

    def on_click(self, event) -> None:
        self.focus()
        target = getattr(event, "target", None) or getattr(event, "widget", None)
        if target:
            for i in range(3):
                with contextlib.suppress(Exception):
                    row = self.query_one(f"#mode_row_{i}", Horizontal)
                    if target == row or (hasattr(target, "ancestors") and row in target.ancestors):
                        self.set_selected_mode(i)
                        break

    def on_key(self, event) -> None:
        if event.key in ["up", "k"]:
            self.set_selected_mode((self.selected_mode_idx - 1) % 3)
            event.stop()
        elif event.key in ["down", "j"]:
            self.set_selected_mode((self.selected_mode_idx + 1) % 3)
            event.stop()
        elif event.key in ["1", "2", "3"]:
            self.set_selected_mode(int(event.key) - 1)
            event.stop()
        elif event.key in ["space"]:
            self.set_selected_mode((self.selected_mode_idx + 1) % 3)
            event.stop()


def format_pipe_footer(segments: list[str], max_width: int = 82) -> str:
    """Format a list of pipe-delimited segment strings so each segment wraps cleanly without breaking."""
    lines = []
    curr = ""
    for i, seg in enumerate(segments):
        token = seg.strip() + (" | " if i < len(segments) - 1 else "")
        if curr and len(curr + token.rstrip()) > max_width:
            lines.append(curr.rstrip())
            curr = token
        else:
            curr += token
    if curr:
        lines.append(curr.rstrip())
    return "\n".join(lines)


def resolve_glyph_preview(glyph_def: str, config: dict | None = None) -> str:
    """Self-contained glyph resolver for Menu Editor Property Inspector previews."""
    if not isinstance(glyph_def, str) or not glyph_def.startswith("{nf:"):
        return glyph_def

    inner = glyph_def[4:-1]
    parts = inner.split(":")

    char_part = ""
    hex_part = ""
    emoji_part = ""

    if len(parts) >= 3:
        char_part = parts[0]
        hex_part = parts[1]
        emoji_part = ":".join(parts[2:])
    elif len(parts) == 2:
        if parts[0] == "":
            char_part = ""
            hex_part = parts[1]
            emoji_part = ""
        elif parts[0].startswith("#") or parts[0].startswith("$") or (parts[0] and all(c in "0123456789abcdefABCDEF" for c in parts[0])):
            char_part = ""
            hex_part = parts[0]
            emoji_part = parts[1]
        else:
            char_part = parts[0]
            hex_part = parts[1]
            emoji_part = ""
    elif len(parts) == 1:
        part = parts[0]
        if part.startswith("#") or part.startswith("$"):
            hex_part = part
        else:
            char_part = part

    cfg = config if config else bashmenu.load_config()[0]
    use_nerd = bashmenu.get_config_value(cfg, "settings.use_nerd_fonts", False)

    if use_nerd:
        if emoji_part:
            if r"\u" in emoji_part.lower():
                try:
                    import codecs
                    emoji_part = codecs.decode(emoji_part, "unicode-escape")
                except Exception:
                    pass
            return emoji_part
        if hex_part:
            try:
                hex_clean = hex_part.lstrip("#$").replace("0x", "").strip()
                if hex_clean:
                    return chr(int(hex_clean, 16))
            except ValueError:
                pass

    return char_part


def render_menu_item_preview(item: dict, config: dict | None = None, width: int = 38) -> str:
    """Render a visual preview string for a menu item (command, divider, submenu, script, etc.)."""
    if not isinstance(item, dict):
        return ""

    cfg = config if config else bashmenu.load_config()[0]
    item_type = item.get("type", "command" if "command" in item else "submenu" if "submenu" in item else "unknown")

    if item_type == "divider":
        char_val = item.get("char", "{ascii:196}")
        length_val = item.get("length", "{window_width}")
        expanded_char = bashmenu.interpolate_placeholders(char_val, cfg)
        expanded_char = resolve_glyph_preview(expanded_char, cfg)
        if not expanded_char:
            expanded_char = "─"

        expanded_len = bashmenu.interpolate_placeholders(length_val, cfg, extra_vars={"window_width": width})
        try:
            target_len = int(expanded_len)
        except (ValueError, TypeError):
            target_len = width

        disp_len = min(max(1, target_len), width)
        char_len = max(1, len(expanded_char))
        return (expanded_char * ((disp_len // char_len) + 1))[:disp_len]

    raw_title = item.get("title") or item.get("label") or "(No Title)"
    icon_raw = item.get("icon") or item.get("glyph") or ""

    expanded_title = bashmenu.interpolate_placeholders(raw_title, cfg)
    expanded_icon = ""
    if icon_raw:
        res = bashmenu.interpolate_placeholders(icon_raw, cfg)
        expanded_icon = resolve_glyph_preview(res, cfg)

    left_label, right_bracket = bashmenu.split_label_brackets(expanded_title)

    if expanded_icon:
        vis_w = bashmenu.get_display_width(expanded_icon, cfg) if hasattr(bashmenu, "get_display_width") else len(expanded_icon)
        pad_str = " " * max(1, 4 - vis_w)
        icon_str = f"{expanded_icon}{pad_str}"
    else:
        icon_str = "    "
    prefix = f"  1.  {icon_str}"

    if hasattr(bashmenu, "get_visible_len"):
        prefix_len = bashmenu.get_visible_len(prefix, cfg)
        left_len = bashmenu.get_visible_len(left_label, cfg)
        right_len = bashmenu.get_visible_len(right_bracket, cfg) if right_bracket else 0
    else:
        prefix_len = len(prefix)
        left_len = len(left_label)
        right_len = len(right_bracket) if right_bracket else 0

    if right_bracket:
        spacer_len = max(1, width - prefix_len - left_len - right_len)
        return f"{prefix}{left_label}{' ' * spacer_len}{right_bracket}"
    else:
        return f"{prefix}{left_label}"


class ItemEditModal(ModalScreen[dict]):
    """Modal dialog to edit comprehensive properties of a menu item."""

    DEFAULT_CSS = """
    ItemEditModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 86;
        height: 85%;
        max-height: 34;
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
        min-width: 3;
        background: transparent;
        color: $text-muted;
    }
    .btn_close_x:hover {
        color: red;
        background: transparent;
    }
    #form_scroll {
        height: 1fr;
        margin-bottom: 1;
    }
    .field_label {
        color: $accent;
        margin-top: 1;
    }
    .field_row {
        height: auto;
        align: left middle;
        margin-bottom: 1;
    }
    .field_row Input {
        width: 1fr;
        height: auto;
        min-height: 3;
        margin-bottom: 0;
    }
    .field_row Button {
        height: 3;
        margin-left: 1;
    }
    Input {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
    }
    Checkbox {
        background: transparent;
        margin-bottom: 0;
    }
    Checkbox:focus {
        background: transparent;
    }
    Checkbox > .checkbox--label {
        background: transparent;
    }
    Checkbox > .checkbox--input {
        background: transparent;
    }
    Switch {
        background: transparent;
    }
    Switch:focus {
        background: transparent;
    }
    .divider_preview_box {
        height: 3;
        border: solid $accent;
        background: $surface-lighten-1;
        color: $accent;
        content-align: center middle;
        margin-top: 0;
        margin-bottom: 1;
        padding: 0 1;
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
        height: auto;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "cancel", "Cancel"),
        Binding("s", "save_changes", "Save Changes"),
        Binding("ctrl+s", "save_changes", "Save Changes"),
        Binding("f2", "save_changes", "Save Changes"),
        Binding("ctrl+a", "lookup_ascii", "ASCII Table"),
        Binding("f3", "lookup_ascii", "ASCII Table"),
        Binding("ctrl+p", "show_placeholders", "Placeholders"),
        Binding("f4", "show_placeholders", "Placeholders"),
    ]

    def __init__(self, item: dict, theme: dict | None = None):
        super().__init__()
        self.item = item.copy()
        self.theme = theme or {}
        self.selected_mode_idx = 0

    def compose(self) -> ComposeResult:
        item_type = self.item.get("type", "command" if "command" in self.item else "submenu" if "submenu" in self.item else "unknown")
        footer_text = format_pipe_footer([
            "[CTRL+S / F2] Save",
            "[CTRL+A / F3] ASCII",
            "[CTRL+P / F4] Placeholders",
            "[ESC / C] Cancel",
        ], max_width=82)

        if item_type == "divider":
            char_val = self.item.get("char", "{ascii:196}")
            length_val = self.item.get("length", "{window_width}")
            with Vertical(id="dialog"):
                with Horizontal(id="title_bar"):
                    yield Label("Edit Properties [DIVIDER]", id="title")
                    yield Label(bashmenu_ui.format_close_button_label(), id="btn_close_x", classes="btn_close_x")
                with VerticalScroll(id="form_scroll"):
                    yield Label("Repeating Character (char):", classes="field_label")
                    yield Input(value=str(char_val), id="inp_char")
                    yield Label("Length Directive (length):", classes="field_label")
                    yield Input(value=str(length_val), id="inp_length")
                    yield Label("Preview:", classes="field_label")
                    yield Static("", id="lbl_divider_preview", classes="divider_preview_box")
                with Horizontal(id="buttons"):
                    yield Button("Save Changes [CTRL+S]", variant="primary", id="btn_save")
                    yield Button("Cancel [ESC]", variant="default", id="btn_cancel")
                yield Label(footer_text, id="footer", markup=False)
            return

        title_val = self.item.get("title", self.item.get("label", ""))
        icon_val = self.item.get("icon", self.item.get("glyph", ""))
        action_val = self.item.get("action", self.item.get("command", self.item.get("script", self.item.get("file", self.item.get("key", self.item.get("python", ""))))))
        prompt_val = self.item.get("message", self.item.get("prompt", self.item.get("text", "")))
        template_val = self.item.get("template", "")
        target_val = self.item.get("target", "")
        block_id_val = self.item.get("block_id", "")
        start_dir_val = self.item.get("start_dir", "")
        tabstop_val = str(self.item.get("tabstop", 4))
        if self.item.get("stream"):
            initial_mode_idx = 0
        elif self.item.get("quiet"):
            initial_mode_idx = 1
        else:
            initial_mode_idx = 2

        with Vertical(id="dialog"):
            with Horizontal(id="title_bar"):
                yield Label(f"Edit Properties [{item_type.upper()}]", id="title")
                yield Label(bashmenu_ui.format_close_button_label(), id="btn_close_x", classes="btn_close_x")

            with VerticalScroll(id="form_scroll"):
                yield Label("Title / Label:", classes="field_label")
                yield Input(value=str(title_val), id="inp_title")

                yield Label("Icon / Glyph ({nf:<char>:<hex>:<emoji>}):", classes="field_label")
                yield Input(value=str(icon_val), id="inp_icon")

                yield Label("Action / Command / Script / File / Key:", classes="field_label")
                with Horizontal(classes="field_row"):
                    yield Input(value=str(action_val), id="inp_action")
                    yield Button("Browse", id="btn_browse_action", variant="primary")

                yield Label("Message / Prompt Text:", classes="field_label")
                yield Input(value=str(prompt_val), id="inp_prompt")

                yield Label("Template Path (inject_block):", classes="field_label")
                with Horizontal(classes="field_row"):
                    yield Input(value=str(template_val), id="inp_template")
                    yield Button("Browse", id="btn_browse_template", variant="primary")

                yield Label("Target Path (inject_block):", classes="field_label")
                with Horizontal(classes="field_row"):
                    yield Input(value=str(target_val), id="inp_target")
                    yield Button("Browse", id="btn_browse_target", variant="primary")

                yield Label("Block ID (inject_block):", classes="field_label")
                yield Input(value=str(block_id_val), id="inp_block_id")

                yield Label("Start Directory ({file_picker} / {dir_picker}):", classes="field_label")
                with Horizontal(classes="field_row"):
                    yield Input(value=str(start_dir_val), id="inp_start_dir")
                    yield Button("Browse", id="btn_browse_start_dir", variant="primary")

                yield Label("Tabstop:", classes="field_label")
                yield Input(value=str(tabstop_val), id="inp_tabstop")

                yield Label("Execution Mode:", classes="field_label")
                yield ExecModeContainer(selected_mode_idx=initial_mode_idx, id="exec_mode_container")

                chk_alt = Checkbox(
                    "Run in Alternate Screen Buffer (alt_buffer=true)",
                    value=bool(self.item.get("alt_buffer", True)),
                    id="chk_alt_buffer",
                )
                chk_alt.display = initial_mode_idx != 0
                yield chk_alt
                yield Checkbox("Disable Formatting (no_formatting=true)", value=bool(self.item.get("no_formatting", False)), id="chk_no_formatting")
                yield Checkbox("Mask Input (masked=true)", value=bool(self.item.get("masked", False)), id="chk_masked")
                yield Checkbox("Refresh Environment (refresh=true)", value=bool(self.item.get("refresh", False)), id="chk_refresh")
                yield Checkbox("Show Whitespace in Editor (show_whitespace=true)", value=bool(self.item.get("show_whitespace", False)), id="chk_show_whitespace")
                yield Checkbox("External Execution (external=true)", value=bool(self.item.get("external", False)), id="chk_external")

                yield Label("Preview:", classes="field_label")
                yield Static("", id="lbl_item_preview", classes="divider_preview_box")

            with Horizontal(id="buttons"):
                yield Button("Save Changes [CTRL+S]", variant="primary", id="btn_save")
                yield Button("Cancel [ESC]", variant="default", id="btn_cancel")

            yield Label(footer_text, id="footer", markup=False)

    def on_mount(self) -> None:
        bashmenu_ui.apply_modal_theme(self, self.theme)
        with contextlib.suppress(Exception):
            bashmenu_ui.apply_button_theme(self.query_one("#btn_save", Button), theme=self.theme, button_type="button_primary")
            bashmenu_ui.apply_button_theme(self.query_one("#btn_cancel", Button), theme=self.theme, button_type="button_cancel")
        if self.item.get("type") == "divider":
            self.update_divider_preview()
        else:
            self.update_item_preview()

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("inp_char", "inp_length"):
            self.update_divider_preview()
        elif event.input.id in ("inp_title", "inp_icon"):
            self.update_item_preview()

    def update_item_preview(self) -> None:
        with contextlib.suppress(Exception):
            inp_title = self.query_one("#inp_title", Input)
            inp_icon = self.query_one("#inp_icon", Input)
            preview_box = self.query_one("#lbl_item_preview", Static)

            temp_item = dict(self.item)
            temp_item["title"] = inp_title.value
            temp_item["icon"] = inp_icon.value

            try:
                cfg = getattr(self.app, "config", {})
            except Exception:  # noqa: BLE001
                cfg = {}

            preview_str = render_menu_item_preview(temp_item, config=cfg, width=60)
            preview_box.update(escape(preview_str))

    def update_divider_preview(self) -> None:
        with contextlib.suppress(Exception):
            inp_char = self.query_one("#inp_char", Input)
            inp_length = self.query_one("#inp_length", Input)
            preview_box = self.query_one("#lbl_divider_preview", Static)

            raw_char = inp_char.value
            raw_len = inp_length.value

            try:
                cfg = getattr(self.app, "config", {})
            except Exception:  # noqa: BLE001
                cfg = {}

            expanded_char = bashmenu.interpolate_placeholders(raw_char, cfg)
            if not expanded_char:
                expanded_char = "─"

            expanded_len = bashmenu.interpolate_placeholders(raw_len, cfg, extra_vars={"window_width": 60})
            try:
                target_len = int(expanded_len)
            except (ValueError, TypeError):
                target_len = 60

            max_preview_len = 60
            disp_len = min(max(1, target_len), max_preview_len)

            char_len = max(1, len(expanded_char))
            repeated = (expanded_char * ((disp_len // char_len) + 1))[:disp_len]

            preview_box.update(escape(repeated))

    def on_exec_mode_container_mode_changed(self, message: ExecModeContainer.ModeChanged) -> None:
        self.update_alt_buffer_visibility(message.mode_idx)

    def update_alt_buffer_visibility(self, mode_idx: int) -> None:
        with contextlib.suppress(Exception):
            chk = self.query_one("#chk_alt_buffer", Checkbox)
            chk.display = mode_idx != 0

    def perform_save(self) -> None:
        item_type = self.item.get("type", "command")
        if item_type == "divider":
            self.item = {
                "type": "divider",
                "char": self.query_one("#inp_char", Input).value.strip() or "{ascii:196}",
                "length": self.query_one("#inp_length", Input).value.strip() or "{window_width}",
            }
            self.dismiss(self.item)
            return

        new_title = self.query_one("#inp_title", Input).value.strip()
        new_icon = self.query_one("#inp_icon", Input).value.strip()
        new_action = self.query_one("#inp_action", Input).value.strip()
        new_prompt = self.query_one("#inp_prompt", Input).value.strip()
        new_template = self.query_one("#inp_template", Input).value.strip()
        new_target = self.query_one("#inp_target", Input).value.strip()
        new_block_id = self.query_one("#inp_block_id", Input).value.strip()
        new_start_dir = self.query_one("#inp_start_dir", Input).value.strip()
        new_tabstop = self.query_one("#inp_tabstop", Input).value.strip()

        if "title" in self.item or not ("label" in self.item):
            self.item["title"] = new_title
        else:
            self.item["label"] = new_title

        if new_icon:
            self.item["icon"] = new_icon

        if new_action:
            if item_type == "command":
                self.item["command"] = new_action
            elif item_type == "script":
                self.item["script"] = new_action
            elif item_type == "editor":
                self.item["file"] = new_action
            elif item_type in ["toggle", "config"]:
                self.item["key"] = new_action
            elif item_type == "python":
                self.item["python"] = new_action
            else:
                self.item["action"] = new_action

        if new_prompt:
            if item_type in ["message", "info", "popup"]:
                self.item["message"] = new_prompt
            else:
                self.item["prompt"] = new_prompt

        if new_template:
            self.item["template"] = new_template
        if new_target:
            self.item["target"] = new_target
        if new_block_id:
            self.item["block_id"] = new_block_id
        if new_start_dir:
            self.item["start_dir"] = new_start_dir

        if new_tabstop.isdigit():
            self.item["tabstop"] = int(new_tabstop)

        mode_container = self.query_one("#exec_mode_container", ExecModeContainer)
        if mode_container.selected_mode_idx == 0:  # Streaming
            self.item["stream"] = True
            self.item["interactive"] = False
            self.item["quiet"] = True
        elif mode_container.selected_mode_idx == 1:  # Interactive Mode
            self.item["stream"] = False
            self.item["interactive"] = True
            self.item["quiet"] = True
            self.item["alt_buffer"] = self.query_one("#chk_alt_buffer", Checkbox).value
        else:  # Standard Terminal Mode
            self.item["stream"] = False
            self.item["interactive"] = True
            self.item["quiet"] = False
            self.item["alt_buffer"] = self.query_one("#chk_alt_buffer", Checkbox).value

        self.item["no_formatting"] = self.query_one("#chk_no_formatting", Checkbox).value
        self.item["masked"] = self.query_one("#chk_masked", Checkbox).value
        self.item["refresh"] = self.query_one("#chk_refresh", Checkbox).value
        self.item["show_whitespace"] = self.query_one("#chk_show_whitespace", Checkbox).value
        self.item["external"] = self.query_one("#chk_external", Checkbox).value

        self.dismiss(self.item)

    def action_save_changes(self) -> None:
        self.perform_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn_close_x":
            self.dismiss(None)
        elif btn_id == "btn_browse_action":
            def file_cb(path):
                if path:
                    self.query_one("#inp_action", Input).value = path
            self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Select Action File", mode="file"), file_cb)
        elif btn_id == "btn_browse_template":
            def t_cb(path):
                if path:
                    self.query_one("#inp_template", Input).value = path
            self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Select Template File", mode="file"), t_cb)
        elif btn_id == "btn_browse_target":
            def target_cb(path):
                if path:
                    self.query_one("#inp_target", Input).value = path
            self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Select Target File", mode="file"), target_cb)
        elif btn_id == "btn_browse_start_dir":
            def dir_cb(path):
                if path:
                    self.query_one("#inp_start_dir", Input).value = path
            self.app.push_screen(bashmenu_ui.FilePickerModalScreen("Select Start Directory", mode="dir"), dir_cb)
        elif btn_id == "btn_save":
            self.perform_save()
        else:
            self.dismiss(None)

    def action_lookup_ascii(self) -> None:
        try:
            app_obj = self.app
            cfg = getattr(app_obj, "config", {})
        except Exception:  # noqa: BLE001
            app_obj = getattr(self, "_app", None)
            cfg = getattr(app_obj, "config", {}) if app_obj else {}
        cmd = bashmenu.interpolate_placeholders("{scripts_dir}/ascii.sh", cfg)
        if app_obj:
            app_obj.push_screen(bashmenu_ui.StreamOutputModalScreen("ASCII Character Table", cmd))

    def action_show_placeholders(self) -> None:
        try:
            app_obj = self.app
        except Exception:  # noqa: BLE001
            app_obj = getattr(self, "_app", None)
        if app_obj:
            app_obj.push_screen(
                bashmenu_ui.MessageModalScreen(
                    "Available Placeholders & Macros",
                    PLACEHOLDER_HELP_TEXT,
                    is_help=True,
                )
            )

    def action_cancel(self) -> None:
        self.dismiss(None)


class MenuEditTree(Tree):
    """Custom Tree widget using Enter to edit items and Space to expand/collapse nodes."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("space", "toggle_node", "Expand/Collapse", show=False),
        Binding("enter", "edit_node", "Edit Item", show=False),
    ]

    def action_toggle_node(self) -> None:
        if self.cursor_node:
            self.cursor_node.toggle()

    def action_edit_node(self) -> None:
        if self.cursor_node and self.cursor_node != self.root:
            screen = getattr(self, "screen", None)
            if screen and hasattr(screen, "action_edit_item"):
                screen.action_edit_item()


class MenuEditScreen(Screen):
    """Visual Menu Tree & Property Inspector Editor Screen in Textual."""

    DEFAULT_CSS = """
    MenuEditScreen {
        layout: vertical;
        background: $surface;
    }
    #header {
        dock: top;
        height: 1;
        width: 100%;
        background: $accent;
        color: $text;
    }
    #header_title {
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
    #footer {
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
    .footer_sep {
        color: $text-muted;
    }
    #workspace {
        height: 1fr;
        width: 100%;
    }
    #tree_panel {
        width: 50%;
        height: 100%;
        border: solid $accent;
    }
    #inspector_panel {
        width: 50%;
        height: 100%;
        border: solid $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    #tree {
        height: 100%;
        width: 100%;
    }
    #inspector_title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }
    #inspector_content {
        height: auto;
    }
    Checkbox {
        background: transparent;
    }
    Checkbox:focus {
        background: transparent;
    }
    Checkbox > .checkbox--label {
        background: transparent;
    }
    Checkbox > .checkbox--input {
        background: transparent;
    }
    Switch {
        background: transparent;
    }
    Switch:focus {
        background: transparent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "add_item", "Add Item"),
        Binding("e", "edit_item", "Edit Item"),
        Binding("enter", "edit_item", "Edit Item"),
        Binding("space", "toggle_tree_node", "Expand/Collapse", show=False),
        Binding("d", "delete_item", "Delete Item"),
        Binding("m", "move_down", "Move Down"),
        Binding("M", "move_up", "Move Up"),
        Binding("greater", "indent_item", "Indent"),
        Binding(">", "indent_item", "Indent", show=False),
        Binding("pipe", "indent_item", "Indent", show=False),
        Binding("less", "outdent_item", "Outdent"),
        Binding("<", "outdent_item", "Outdent", show=False),
        Binding("ctrl+a", "lookup_ascii", "ASCII Table"),
        Binding("f3", "lookup_ascii", "ASCII Table", show=False),
        Binding("ctrl+p", "show_placeholders", "Placeholders"),
        Binding("f4", "show_placeholders", "Placeholders", show=False),
        Binding("s", "save_menu", "Save Menu"),
        Binding("ctrl+s", "save_menu", "Save Menu"),
        Binding("escape", "exit_editor", "Exit"),
        Binding("q", "exit_editor", "Exit"),
    ]

    def __init__(
        self,
        menu_file_path: str | None = None,
        selected_item: dict | None = None,
        title_chain: list[str] | None = None,
        theme: dict | str | None = None,
    ):
        super().__init__()
        self.menu_file_path = menu_file_path or bashmenu.MENU_FILE
        self.menu_data, _ = bashmenu.load_yaml_file(self.menu_file_path)
        self.selected_item = selected_item
        self.title_chain = title_chain or []
        self.raw_theme = theme
        self.theme_styles = bashmenu_ui.resolve_theme_dict(theme)
        try:
            self.config, _ = bashmenu.load_config()
        except Exception:
            self.config = {}
        self._target_node_to_focus = None
        self.modified = False

    def compose(self) -> ComposeResult:
        file_name = os.path.basename(self.menu_file_path)
        with Horizontal(id="header"):
            yield Label(f"  Visual Menu Editor - {file_name}  ", id="header_title")
            yield Label(bashmenu_ui.format_close_button_label(), id="btn_close_x", classes="btn_close_x")
        with Horizontal(id="workspace"):
            with Vertical(id="tree_panel"):
                yield MenuEditTree("Root Menu", id="tree")
            with Vertical(id="inspector_panel"):
                yield Label("── Property Inspector ──", id="inspector_title")
                yield Static("Select a menu item in the hierarchy tree to inspect properties.", id="inspector_content")
        with Horizontal(id="footer"):
            yield Label("[a] Add", id="lbl_add", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[e/ENTER] Edit", id="lbl_edit", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[SPACE] Toggle", id="lbl_toggle", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[d] Delete", id="lbl_delete", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[m] Move Dn", id="lbl_move_down", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[M] Move Up", id="lbl_move_up", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[>] Indent", id="lbl_indent", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[<] Outdent", id="lbl_outdent", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[CTRL+A] ASCII", id="lbl_ascii", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[CTRL+P] Placeholders", id="lbl_placeholders", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[s] Save", id="lbl_save", classes="footer_item", markup=False)
            yield Label("|", classes="footer_sep", markup=False)
            yield Label("[ESC/q] Exit", id="lbl_exit", classes="footer_item", markup=False)

    def action_toggle_tree_node(self) -> None:
        with contextlib.suppress(Exception):
            tree = self.query_one("#tree", Tree)
            if tree.cursor_node:
                tree.cursor_node.toggle()

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if not widget:
            return

        # 1. Tree node click / selection
        tree = self.query_one("#tree", Tree)
        if widget == tree or (hasattr(widget, "ancestors") and tree in widget.ancestors):
            meta = getattr(getattr(event, "style", None), "meta", {}) or {}
            line = meta.get("line")
            node = tree.get_node_at_line(line) if line is not None else tree.cursor_node
            if node:
                tree.focus()
                tree.select_node(node)
                self.update_inspector(node.data)
                is_right_click = getattr(event, "button", 1) == 3
                is_double_click = getattr(event, "chain", 1) == 2 or getattr(event, "count", 1) == 2
                if node != tree.root and (is_right_click or is_double_click):
                    self.action_edit_item()
            return

        # 2. Interactive footer items / close button
        lbl_id = getattr(widget, "id", None)
        if lbl_id == "lbl_add":
            self.action_add_item()
        elif lbl_id == "lbl_edit":
            self.action_edit_item()
        elif lbl_id == "lbl_toggle":
            self.action_toggle_tree_node()
        elif lbl_id == "lbl_delete":
            self.action_delete_item()
        elif lbl_id == "lbl_move_down":
            self.action_move_down()
        elif lbl_id == "lbl_move_up":
            self.action_move_up()
        elif lbl_id == "lbl_indent":
            self.action_indent_item()
        elif lbl_id == "lbl_outdent":
            self.action_outdent_item()
        elif lbl_id == "lbl_ascii":
            self.action_lookup_ascii()
        elif lbl_id == "lbl_placeholders":
            self.action_show_placeholders()
        elif lbl_id == "lbl_save":
            self.action_save_menu()
        elif lbl_id in ("lbl_exit", "btn_close_x"):
            self.action_exit_editor()

    def action_lookup_ascii(self) -> None:
        try:
            app_obj = self.app
            cfg = getattr(app_obj, "config", {})
        except Exception:  # noqa: BLE001
            app_obj = getattr(self, "_app", None)
            cfg = getattr(app_obj, "config", {}) if app_obj else {}
        cmd = bashmenu.interpolate_placeholders("{scripts_dir}/ascii.sh", cfg)
        if app_obj:
            app_obj.push_screen(bashmenu_ui.StreamOutputModalScreen("ASCII Character Table", cmd, theme=self.theme_styles))

    def action_show_placeholders(self) -> None:
        try:
            app_obj = self.app
        except Exception:  # noqa: BLE001
            app_obj = getattr(self, "_app", None)
        if app_obj:
            app_obj.push_screen(
                bashmenu_ui.MessageModalScreen(
                    "Available Placeholders & Macros",
                    PLACEHOLDER_HELP_TEXT,
                    theme=self.theme_styles,
                    is_help=True,
                )
            )

    def apply_theme(self) -> None:
        """Apply dynamic theme colors to MenuEditScreen and its subwidgets."""
        with contextlib.suppress(Exception):
            self.theme_styles = bashmenu_ui.resolve_theme_dict(
                self.raw_theme or getattr(self.app, "theme_styles", None), self.app
            )
            bg_style = self.theme_styles.get("background")
            if bg_style and bg_style.bgcolor and bg_style.bgcolor.name:
                css_bg = bashmenu_ui.parse_css_color(bg_style.bgcolor.name)
                if css_bg:
                    for wid in ["#workspace", "#tree_panel", "#inspector_panel", "#tree", "#inspector_content"]:
                        with contextlib.suppress(Exception):
                            self.query_one(wid).styles.background = css_bg

            hdr_style = self.theme_styles.get("header") or self.theme_styles.get("title")
            if hdr_style:
                if hdr_style.bgcolor and hdr_style.bgcolor.name:
                    css_hdr_bg = bashmenu_ui.parse_css_color(hdr_style.bgcolor.name)
                    if css_hdr_bg:
                        with contextlib.suppress(Exception):
                            self.query_one("#header").styles.background = css_hdr_bg
                if hdr_style.color and hdr_style.color.name:
                    css_hdr_fg = bashmenu_ui.parse_css_color(hdr_style.color.name)
                    if css_hdr_fg:
                        with contextlib.suppress(Exception):
                            self.query_one("#header_title", Label).styles.color = css_hdr_fg

            with contextlib.suppress(Exception):
                btn_close = self.query_one("#btn_close_x", Label)
                btn_close.update(bashmenu_ui.format_close_button_label(self.theme_styles))

            border_style = self.theme_styles.get("border") or self.theme_styles.get("accent")
            if border_style and border_style.color and border_style.color.name:
                css_border = bashmenu_ui.parse_css_color(border_style.color.name)
                if css_border:
                    for pid in ["#tree_panel", "#inspector_panel"]:
                        with contextlib.suppress(Exception):
                            self.query_one(pid).styles.border = ("solid", css_border)

            title_style = self.theme_styles.get("title") or self.theme_styles.get("accent")
            if title_style and title_style.color and title_style.color.name:
                css_title = bashmenu_ui.parse_css_color(title_style.color.name)
                if css_title:
                    with contextlib.suppress(Exception):
                        self.query_one("#inspector_title", Label).styles.color = css_title

            text_style = self.theme_styles.get("text")
            if text_style and text_style.color and text_style.color.name:
                css_text = bashmenu_ui.parse_css_color(text_style.color.name)
                if css_text:
                    for wid in ["#tree", "#inspector_content"]:
                        with contextlib.suppress(Exception):
                            self.query_one(wid).styles.color = css_text

            footer_style = self.theme_styles.get("footer") or self.theme_styles.get("background")
            if footer_style and footer_style.bgcolor and footer_style.bgcolor.name:
                css_ftr_bg = bashmenu_ui.parse_css_color(footer_style.bgcolor.name)
                if css_ftr_bg:
                    with contextlib.suppress(Exception):
                        self.query_one("#footer").styles.background = css_ftr_bg

            accent_style = self.theme_styles.get("accent") or self.theme_styles.get("help_text")
            if accent_style and accent_style.color and accent_style.color.name:
                css_accent = bashmenu_ui.parse_css_color(accent_style.color.name)
                if css_accent:
                    with contextlib.suppress(Exception):
                        for item in self.query(".footer_item"):
                            item.styles.color = css_accent

    def on_mount(self) -> None:
        self.populate_tree()
        self.apply_theme()
        if self._target_node_to_focus:
            tn = self._target_node_to_focus
            self.call_after_refresh(self._focus_target_node, tn)
            self.set_timer(0.05, lambda: self._focus_target_node(tn))

    def _focus_target_node(self, target_node) -> None:
        with contextlib.suppress(Exception):
            tree = self.query_one("#tree", Tree)
            curr = target_node.parent
            while curr:
                curr.expand()
                curr = curr.parent
            tree.focus()
            tree.select_node(target_node)
            tree.scroll_to_node(target_node)
            self.update_inspector(target_node.data)

    def _find_node_by_chain(self, root_node, title_chain):
        if not title_chain:
            return None
        curr_node = root_node
        for target_title in title_chain:
            clean_target = bashmenu_ui.strip_formatting_tags(str(target_title)).strip().lower()
            if not clean_target:
                continue
            matched_child = None
            for child in curr_node.children:
                if not isinstance(child.data, dict):
                    continue
                child_title = bashmenu_ui.strip_formatting_tags(
                    str(child.data.get("title") or child.data.get("label") or "")
                ).strip().lower()
                if child_title == clean_target:
                    matched_child = child
                    break
            if matched_child:
                curr_node = matched_child
            else:
                return None
        return curr_node if curr_node != root_node else None

    def _find_node_for_item(self, parent_node, target_item):
        if not target_item or not isinstance(target_item, dict):
            return None

        # Pass 1: Exact object identity match (100% precise)
        def find_by_identity(node):
            if node.data is target_item:
                return node
            for child in node.children:
                res = find_by_identity(child)
                if res:
                    return res
            return None

        matched = find_by_identity(parent_node)
        if matched:
            return matched

        # Pass 2: Fallback attribute comparison
        def find_by_attributes(node):
            if node != parent_node and isinstance(node.data, dict):
                t1 = bashmenu_ui.strip_formatting_tags(str(node.data.get("title") or node.data.get("label") or "")).strip().lower()
                t2 = bashmenu_ui.strip_formatting_tags(str(target_item.get("title") or target_item.get("label") or "")).strip().lower()
                type1 = node.data.get("type")
                type2 = target_item.get("type")
                if t1 and t1 == t2 and type1 == type2:
                    return node
            for child in node.children:
                res = find_by_attributes(child)
                if res:
                    return res
            return None

        return find_by_attributes(parent_node)

    def populate_tree(self, target_item=None) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.data = self.menu_data
        root_title = self.menu_data.get("title", "Root Menu")
        tree.root.label = f"[MNU] {root_title}"

        opts = self.menu_data.get("options", [])
        self._build_tree_branch(tree.root, opts)
        tree.root.expand()

        target_node = None
        if target_item:
            target_node = self._find_node_for_item(tree.root, target_item)
            if target_node:
                self.selected_item = target_item
        elif self.selected_item:
            target_node = self._find_node_for_item(tree.root, self.selected_item)
        elif self.title_chain:
            target_node = self._find_node_by_chain(tree.root, self.title_chain)

        if target_node:
            self._target_node_to_focus = target_node
            curr = target_node.parent
            while curr:
                curr.expand()
                curr = curr.parent
            tree.select_node(target_node)
            tree.scroll_to_node(target_node)
            self.update_inspector(target_node.data)
            self.call_after_refresh(self._focus_target_node, target_node)

        tree.focus()

    def _build_tree_branch(self, parent_node, options_list):
        for item in options_list:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "command" if "command" in item else "submenu" if "submenu" in item else "unknown")
            title = item.get("title", item.get("label", item.get("divider", "Divider")))
            badge = TYPE_BADGES.get(item_type, "[???]")

            node_label = f"{badge} {title}"
            node = parent_node.add(node_label, data=item)

            if item_type == "submenu" or "submenu" in item:
                sub_opts = item.get("submenu", {}).get("options", [])
                self._build_tree_branch(node, sub_opts)
                node.expand()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        self.update_inspector(event.node.data if event.node else None)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        self.update_inspector(event.node.data if event.node else None)

    def update_inspector(self, item: dict | None) -> None:
        inspector = self.query_one("#inspector_content", Static)
        if not item or not isinstance(item, dict):
            inspector.update("[dim]No menu item selected.[/dim]")
            return

        item_type = item.get("type", "command" if "command" in item else "submenu" if "submenu" in item else "unknown")
        badge = TYPE_BADGES.get(item_type, "[???]")

        try:
            cfg = getattr(self.app, "config", None) or getattr(self, "config", None) or bashmenu.load_config()[0]
        except Exception:  # noqa: BLE001
            cfg = {}

        if item_type == "divider":
            char_val = item.get("char", "{ascii:196}")
            length_val = item.get("length", "{window_width}")
            lines = [
                f"[bold magenta]{badge} DIVIDER[/bold magenta]",
                f"[bold white]Repeating Char:[/bold white] {escape(str(char_val))}",
                f"[bold white]Length Directive:[/bold white] {escape(str(length_val))}",
            ]
        else:
            title = item.get("title", item.get("label", "(No Title)"))

            lines = [
                f"[bold magenta]{badge} {item_type.upper()}[/bold magenta]",
                f"[bold white]Title/Label:[/bold white] {escape(str(title))}",
            ]

            icon = item.get("icon") or item.get("glyph")
            if icon:
                lines.append(f"[bold cyan]Icon/Glyph:[/bold cyan] {escape(str(icon))}")

            action = item.get("action") or item.get("command") or item.get("script") or item.get("file") or item.get("python")
            if action:
                lines.append(f"[bold yellow]Action/Target:[/bold yellow] {escape(str(action))}")

            key = item.get("key")
            if key:
                lines.append(f"[bold green]Config Key:[/bold green] {escape(str(key))}")

            msg = item.get("message") or item.get("prompt") or item.get("text")
            if msg:
                lines.append(f"[bold blue]Message/Prompt:[/bold blue] {escape(str(msg))}")

            template = item.get("template")
            if template:
                lines.append(f"[bold cyan]Template:[/bold cyan] {escape(str(template))}")

            target = item.get("target")
            if target:
                lines.append(f"[bold cyan]Target File:[/bold cyan] {escape(str(target))}")

            block_id = item.get("block_id")
            if block_id:
                lines.append(f"[bold cyan]Block ID:[/bold cyan] {escape(str(block_id))}")

            start_dir = item.get("start_dir")
            if start_dir:
                lines.append(f"[bold cyan]Start Directory:[/bold cyan] {escape(str(start_dir))}")

            picker = item.get("picker")
            if picker:
                lines.append(f"[bold cyan]Picker Type:[/bold cyan] {escape(str(picker))}")

            on_yes = item.get("on_yes")
            if on_yes is not None:
                lines.append(f"[bold green]On Yes Action:[/bold green] {escape(str(on_yes))}")

            on_no = item.get("on_no")
            if on_no is not None:
                lines.append(f"[bold red]On No Action:[/bold red] {escape(str(on_no))}")

            if "alt_buffer" in item:
                lines.append(f"[bold cyan]Alt Buffer:[/bold cyan] {item['alt_buffer']}")

            if "no_formatting" in item:
                lines.append(f"[bold cyan]No Formatting:[/bold cyan] {item['no_formatting']}")

            flags = []
            for flag_name in [
                "stream",
                "quiet",
                "interactive",
                "show_whitespace",
                "masked",
                "refresh",
                "external",
                "display_theme_colors",
            ]:
                if flag_name in item:
                    flags.append(f"{flag_name}={item[flag_name]}")
            if "tabstop" in item:
                flags.append(f"tabstop={item['tabstop']}")
            if flags:
                lines.append(f"[dim]Flags: {', '.join(flags)}[/dim]")

            if "submenu" in item:
                sub_opts = item.get("submenu", {}).get("options", [])
                lines.append(f"[bold magenta]Submenu Options:[/bold magenta] {len(sub_opts)} items")

            known_keys = {
                "type",
                "title",
                "label",
                "icon",
                "glyph",
                "action",
                "command",
                "script",
                "file",
                "python",
                "key",
                "message",
                "prompt",
                "text",
                "template",
                "target",
                "block_id",
                "start_dir",
                "picker",
                "on_yes",
                "on_no",
                "alt_buffer",
                "no_formatting",
                "stream",
                "quiet",
                "interactive",
                "show_whitespace",
                "masked",
                "refresh",
                "external",
                "display_theme_colors",
                "tabstop",
                "submenu",
                "options",
                "char",
                "length",
                "divider",
            }
            extra_keys = [k for k in item if k not in known_keys]
            if extra_keys:
                extras = ", ".join(f"{k}={escape(str(item[k]))}" for k in sorted(extra_keys))
                lines.append(f"[bold yellow]Extra Properties:[/bold yellow] [dim]{extras}[/dim]")

        preview_str = render_menu_item_preview(item, config=cfg, width=38)
        lines.append(f"[bold cyan]Preview:[/bold cyan]\n{escape(preview_str)}")

        inspector.update("\n\n".join(lines))

    def action_edit_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node == tree.root:
            return

        def save_cb(updated_item):
            if updated_item:
                node.data.clear()
                node.data.update(updated_item)
                item_type = updated_item.get("type", "command")
                badge = TYPE_BADGES.get(item_type, "[???]")
                title = updated_item.get("title") or updated_item.get("label") or updated_item.get("divider") or "Divider"
                node.label = f"{badge} {title}"
                self.modified = True
                self.update_inspector(node.data)
                self.action_save_menu()
                tree.refresh()

        self.app.push_screen(ItemEditModal(node.data, theme=self.theme_styles), save_cb)

    def action_add_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        cursor_node = tree.cursor_node or tree.root

        def type_cb(selected_type):
            if not selected_type:
                return

            if selected_type == "divider":
                new_item = {
                    "type": "divider",
                    "char": "{ascii:196}",
                    "length": "{window_width}",
                }
            else:
                new_item = {"type": selected_type, "title": f"New {selected_type}"}
                if selected_type == "submenu":
                    new_item["submenu"] = {"title": f"New {selected_type}", "options": []}

            def edit_cb(final_item):
                if final_item:
                    is_container = (
                        cursor_node == tree.root
                        or cursor_node.data.get("type") == "submenu"
                        or "submenu" in (cursor_node.data or {})
                    )
                    if is_container:
                        parent_data = cursor_node.data
                        if isinstance(parent_data, dict):
                            if "submenu" in parent_data:
                                parent_data.setdefault("submenu", {}).setdefault("options", []).append(final_item)
                            else:
                                parent_data.setdefault("options", []).append(final_item)
                    else:
                        res = self._find_item_parent_list(cursor_node.data)
                        if res:
                            opts, idx = res
                            opts.insert(idx + 1, final_item)
                        else:
                            self.menu_data.setdefault("options", []).append(final_item)

                    self.modified = True
                    self.populate_tree(target_item=final_item)
                    self._save_menu_quietly()

            self.app.push_screen(ItemEditModal(new_item, theme=self.theme_styles), edit_cb)

        self.app.push_screen(ItemTypePickerModal(theme=self.theme_styles), type_cb)

    def action_delete_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node == tree.root:
            return

        def confirm_cb(res):
            if res == "yes":
                parent = node.parent
                if parent and isinstance(parent.data, dict):
                    opts = (
                        parent.data.get("submenu", {}).get("options")
                        if "submenu" in parent.data
                        else parent.data.get("options")
                    )
                    if isinstance(opts, list) and node.data in opts:
                        opts.remove(node.data)
                        node.remove()
                        self.modified = True
                        self.update_inspector(None)

        self.app.push_screen(
            bashmenu_ui.ConfirmModalScreen("Delete Item", "Are you sure you want to delete this menu item?", theme=self.theme_styles),
            confirm_cb,
        )

    def _find_item_parent_list(self, item_data):
        def search(opts):
            for idx, el in enumerate(opts):
                if el is item_data:
                    return opts, idx
                if isinstance(el, dict) and ("submenu" in el or el.get("type") == "submenu"):
                    sub_opts = el.get("submenu", {}).get("options", [])
                    res = search(sub_opts)
                    if res:
                        return res
            return None

        root_opts = self.menu_data.get("options", [])
        return search(root_opts)

    def _save_menu_quietly(self) -> None:
        with contextlib.suppress(Exception):
            with open(self.menu_file_path, "w", encoding="utf-8") as f:
                yaml.dump(self.menu_data, f, sort_keys=False, default_flow_style=False)
            self.modified = False

    def action_move_up(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if (not node or not node.data or node == tree.root) and self.selected_item:
            node = self._find_node_for_item(tree.root, self.selected_item)
        if not node or not node.data or node == tree.root:
            return

        res = self._find_item_parent_list(node.data)
        if not res:
            return
        opts, idx = res
        if idx > 0:
            target_item = node.data
            opts[idx], opts[idx - 1] = opts[idx - 1], opts[idx]
            self.selected_item = target_item
            self.modified = True
            self.populate_tree(target_item=target_item)
            self._save_menu_quietly()

    def action_move_down(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if (not node or not node.data or node == tree.root) and self.selected_item:
            node = self._find_node_for_item(tree.root, self.selected_item)
        if not node or not node.data or node == tree.root:
            return

        res = self._find_item_parent_list(node.data)
        if not res:
            return
        opts, idx = res
        if idx < len(opts) - 1:
            target_item = node.data
            opts[idx], opts[idx + 1] = opts[idx + 1], opts[idx]
            self.selected_item = target_item
            self.modified = True
            self.populate_tree(target_item=target_item)
            self._save_menu_quietly()

    def action_indent_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if (not node or not node.data or node == tree.root) and self.selected_item:
            node = self._find_node_for_item(tree.root, self.selected_item)
        if not node or not node.data or node == tree.root:
            return

        res = self._find_item_parent_list(node.data)
        if not res:
            return
        opts, idx = res
        if idx > 0:
            prev_sibling = opts[idx - 1]
            if isinstance(prev_sibling, dict):
                if prev_sibling.get("type") == "divider":
                    return
                target_item = node.data
                if "submenu" not in prev_sibling and prev_sibling.get("type") != "submenu":
                    prev_sibling["type"] = "submenu"
                    prev_sibling["submenu"] = {
                        "title": prev_sibling.get("title") or prev_sibling.get("label", "Submenu"),
                        "options": [],
                    }
                prev_sibling.setdefault("submenu", {}).setdefault("options", []).append(opts.pop(idx))
                self.selected_item = target_item
                self.modified = True
                self.populate_tree(target_item=target_item)
                self._save_menu_quietly()

    def action_outdent_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if (not node or not node.data or node == tree.root) and self.selected_item:
            node = self._find_node_for_item(tree.root, self.selected_item)
        if not node or not node.data or node == tree.root or not node.parent or node.parent == tree.root:
            return

        parent_item = node.parent.data
        res = self._find_item_parent_list(parent_item)
        if not res:
            return
        grand_opts, parent_idx = res
        parent_res = self._find_item_parent_list(node.data)
        if parent_res:
            parent_opts, idx = parent_res
            target_item = node.data
            moved_item = parent_opts.pop(idx)
            grand_opts.insert(parent_idx + 1, moved_item)
            self.selected_item = target_item
            self.modified = True
            self.populate_tree(target_item=target_item)
            self._save_menu_quietly()

    def action_save_menu(self) -> None:
        try:
            with open(self.menu_file_path, "w", encoding="utf-8") as f:
                yaml.dump(self.menu_data, f, sort_keys=False, default_flow_style=False)
            self.modified = False
            self.app.push_screen(bashmenu_ui.MessageModalScreen("Save Menu", "Menu saved successfully to disk.", theme=self.theme_styles))
        except (yaml.YAMLError, OSError) as e:
            self.app.push_screen(bashmenu_ui.MessageModalScreen("Error", f"Failed to save menu:\n{e}", theme=self.theme_styles))

    def action_exit_editor(self) -> None:
        def safe_exit(res_val):
            if len(self.app.screen_stack) > 1:
                try:
                    self.dismiss(res_val)
                except Exception:  # noqa: BLE001
                    self.app.pop_screen()
            else:
                self.app.exit(res_val)

        if self.modified:

            def confirm_cb(res):
                if res == "yes":
                    self.action_save_menu()
                    safe_exit(True)
                elif res == "no":
                    safe_exit(False)

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Unsaved Changes", "You have unsaved changes in the menu. Save before exiting?", theme=self.theme_styles
                ),
                confirm_cb,
            )
        else:
            safe_exit(False)


class MenuEditApp(App):
    """App launcher for Visual Menu Editor."""

    ENABLE_COMMAND_PALETTE = False

    def __init__(self, menu_file_path: str | None = None, selected_item: dict | None = None):
        super().__init__()
        self.menu_file_path = menu_file_path
        self.selected_item = selected_item
        try:
            self.config, _ = bashmenu.load_config()
        except Exception:
            self.config = {}

    def on_mount(self) -> None:
        self.push_screen(MenuEditScreen(menu_file_path=self.menu_file_path, selected_item=self.selected_item))


def run_curses_menuedit(stdscr, menu_file=None, theme=None):
    """Compatibility runner for launching MenuEdit in Textual."""
    app = MenuEditApp(menu_file_path=menu_file)
    app.run()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    app = MenuEditApp(menu_file_path=target)
    app.run()
