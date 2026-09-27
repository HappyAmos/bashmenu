#!/usr/bin/env python3
"""
menuedit.py - Interactive Visual Menu Editor for HA Bash Menu (bashmenu.mnu) implemented in Textual.
"""

__version__ = "0.0.1"
__author__ = "HappyAmos"

import os
import sys
from typing import ClassVar

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, OptionList, Tree
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


class ItemTypePickerModal(ModalScreen[str]):
    """Modal dialog to select type when adding a new item."""

    DEFAULT_CSS = """
    ItemTypePickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 70;
        height: 20;
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

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Select Item Type", id="title")
            yield OptionList(id="option_list")
            yield Label("[ENTER] Select | [ESC] Cancel", id="footer")

    def on_mount(self) -> None:
        opts = self.query_one("#option_list", OptionList)
        for type_key, desc in ITEM_TYPES:
            badge = TYPE_BADGES.get(type_key, "[???]")
            opts.add_option(Option(f"{badge} {type_key:<15} - {desc}"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(ITEM_TYPES):
            self.dismiss(ITEM_TYPES[idx][0])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ItemEditModal(ModalScreen[dict]):
    """Modal dialog to edit properties of a menu item."""

    DEFAULT_CSS = """
    ItemEditModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #dialog {
        width: 75;
        height: 22;
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
    .field_label {
        color: $accent;
        margin-top: 1;
    }
    Input {
        margin-bottom: 1;
    }
    #buttons {
        align: center middle;
        margin-top: 1;
    }
    Button {
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, item: dict):
        super().__init__()
        self.item = item.copy()

    def compose(self) -> ComposeResult:
        item_type = self.item.get("type", "command")
        title_val = self.item.get("title", self.item.get("label", ""))

        with Vertical(id="dialog"):
            yield Label(f"Edit {item_type.upper()} Item", id="title")

            yield Label("Title / Label:", classes="field_label")
            yield Input(value=str(title_val), id="inp_title")

            if item_type == "command":
                yield Label("Command:", classes="field_label")
                yield Input(value=str(self.item.get("command", "")), id="inp_action")
            elif item_type == "script":
                yield Label("Script Path:", classes="field_label")
                yield Input(value=str(self.item.get("script", "")), id="inp_action")
            elif item_type == "editor":
                yield Label("File Path:", classes="field_label")
                yield Input(value=str(self.item.get("file", "")), id="inp_action")
            elif item_type == "message":
                yield Label("Message Text:", classes="field_label")
                yield Input(value=str(self.item.get("message", "")), id="inp_action")
            elif item_type == "python":
                yield Label("Python Routine:", classes="field_label")
                yield Input(value=str(self.item.get("python", "")), id="inp_action")
            elif item_type == "toggle":
                yield Label("Config Key:", classes="field_label")
                yield Input(value=str(self.item.get("key", "")), id="inp_action")
            else:
                yield Label("Action / Target:", classes="field_label")
                yield Input(value=str(self.item.get("action", "")), id="inp_action")

            with Horizontal(id="buttons"):
                yield Button("Save", variant="primary", id="btn_save")
                yield Button("Cancel", variant="default", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            item_type = self.item.get("type", "command")
            new_title = self.query_one("#inp_title", Input).value.strip()
            new_action = self.query_one("#inp_action", Input).value.strip()

            self.item["title"] = new_title

            if item_type == "command":
                self.item["command"] = new_action
            elif item_type == "script":
                self.item["script"] = new_action
            elif item_type == "editor":
                self.item["file"] = new_action
            elif item_type == "message":
                self.item["message"] = new_action
            elif item_type == "python":
                self.item["python"] = new_action
            elif item_type == "toggle":
                self.item["key"] = new_action
            else:
                self.item["action"] = new_action

            self.dismiss(self.item)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class MenuEditScreen(Screen):
    """Visual Menu Tree Editor Screen in Textual."""

    DEFAULT_CSS = """
    MenuEditScreen {
        layout: vertical;
        background: $surface;
    }
    #header {
        dock: top;
        height: 1;
        background: $accent;
        color: $text-primary;
        text-align: center;
        text-style: bold;
    }
    #footer {
        dock: bottom;
        height: 2;
        background: $surface-darken-1;
        color: $accent;
        text-align: center;
    }
    #tree {
        height: 1fr;
        border: solid $accent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("a", "add_item", "Add Item"),
        Binding("e", "edit_item", "Edit Item"),
        Binding("enter", "edit_item", "Edit Item"),
        Binding("d", "delete_item", "Delete Item"),
        Binding("m", "move_down", "Move Down"),
        Binding("M", "move_up", "Move Up"),
        Binding("pipe", "indent_item", "Indent"),
        Binding("less", "outdent_item", "Outdent"),
        Binding("s", "save_menu", "Save Menu"),
        Binding("ctrl+s", "save_menu", "Save Menu"),
        Binding("escape", "exit_editor", "Exit"),
        Binding("q", "exit_editor", "Exit"),
    ]

    def __init__(self, menu_file_path: str | None = None):
        super().__init__()
        self.menu_file_path = menu_file_path or bashmenu.MENU_FILE
        self.menu_data, _ = bashmenu.load_yaml_file(self.menu_file_path)
        self.modified = False

    def compose(self) -> ComposeResult:
        yield Label(f"  Visual Menu Editor - {os.path.basename(self.menu_file_path)}  ", id="header")
        yield Tree("Root Menu", id="tree")
        yield Label(
            " [a]: Add | [e/ENTER]: Edit | [d]: Delete | [m/M]: Reorder | [|/<]: Indent/Outdent | [s]: Save | [ESC]: Exit ",
            id="footer",
        )

    def on_mount(self) -> None:
        self.populate_tree()

    def populate_tree(self) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.data = self.menu_data
        root_title = self.menu_data.get("title", "Root Menu")
        tree.root.label = f"[MNU] {root_title}"

        opts = self.menu_data.get("options", [])
        self._build_tree_branch(tree.root, opts)
        tree.root.expand()

    def _build_tree_branch(self, parent_node, options_list):
        for item in options_list:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "command")
            title = item.get("title", item.get("label", item.get("divider", "Divider")))
            badge = TYPE_BADGES.get(item_type, "[???]")

            node_label = f"{badge} {title}"
            node = parent_node.add(node_label, data=item)

            if item_type == "submenu" or "submenu" in item:
                sub_opts = item.get("submenu", {}).get("options", [])
                self._build_tree_branch(node, sub_opts)
                node.expand()

    def action_edit_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node
        if not node or not node.data or node == tree.root:
            return

        def save_cb(updated_item):
            if updated_item:
                node.data.update(updated_item)
                item_type = updated_item.get("type", "command")
                badge = TYPE_BADGES.get(item_type, "[???]")
                title = updated_item.get("title", updated_item.get("label", ""))
                node.label = f"{badge} {title}"
                self.modified = True
                tree.refresh()

        self.app.push_screen(ItemEditModal(node.data), save_cb)

    def action_add_item(self) -> None:
        tree = self.query_one("#tree", Tree)
        parent_node = tree.cursor_node or tree.root

        def type_cb(selected_type):
            if not selected_type:
                return

            new_item = {"type": selected_type, "title": f"New {selected_type}"}
            if selected_type == "submenu":
                new_item["submenu"] = {"title": "New Submenu", "options": []}

            def edit_cb(final_item):
                if final_item:
                    # Append to parent list
                    parent_data = parent_node.data
                    if isinstance(parent_data, dict):
                        if "submenu" in parent_data:
                            parent_data.setdefault("submenu", {}).setdefault("options", []).append(final_item)
                        else:
                            parent_data.setdefault("options", []).append(final_item)

                    badge = TYPE_BADGES.get(selected_type, "[???]")
                    parent_node.add(f"{badge} {final_item['title']}", data=final_item)
                    parent_node.expand()
                    self.modified = True

            self.app.push_screen(ItemEditModal(new_item), edit_cb)

        self.app.push_screen(ItemTypePickerModal(), type_cb)

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

        self.app.push_screen(
            bashmenu_ui.ConfirmModalScreen("Delete Item", "Are you sure you want to delete this menu item?"),
            confirm_cb,
        )

    def action_save_menu(self) -> None:
        try:
            with open(self.menu_file_path, "w", encoding="utf-8") as f:
                yaml.dump(self.menu_data, f, sort_keys=False, default_flow_style=False)
            self.modified = False
            self.app.push_screen(bashmenu_ui.MessageModalScreen("Save Menu", "Menu saved successfully to disk."))
        except Exception as e:
            self.app.push_screen(bashmenu_ui.MessageModalScreen("Error", f"Failed to save menu:\n{e}"))

    def action_exit_editor(self) -> None:
        if self.modified:

            def confirm_cb(res):
                if res == "yes":
                    self.action_save_menu()
                    self.dismiss(True)
                elif res == "no":
                    self.dismiss(False)

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Unsaved Changes", "You have unsaved changes in the menu. Save before exiting?"
                ),
                confirm_cb,
            )
        else:
            self.dismiss(False)


class MenuEditApp(App):
    """App launcher for Visual Menu Editor."""

    def __init__(self, menu_file_path: str | None = None):
        super().__init__()
        self.menu_file_path = menu_file_path

    def on_mount(self) -> None:
        self.push_screen(MenuEditScreen(menu_file_path=self.menu_file_path))


def run_curses_menuedit(stdscr, menu_file=None, theme=None):
    """Compatibility runner for launching MenuEdit in Textual."""
    app = MenuEditApp(menu_file_path=menu_file)
    app.run()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    app = MenuEditApp(menu_file_path=target)
    app.run()
