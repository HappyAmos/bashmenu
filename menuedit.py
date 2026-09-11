#!/usr/bin/env python3
"""
menuedit.py - Interactive Visual Menu Editor for HA Bash Menu (bashmenu.mnu)

Provides a keyboard-navigable tree interface to add, modify, reorder, delete,
preview, test, and validate menu items in bashmenu.mnu. Imports shared UI
dialogs, themes, and configuration utilities directly from bashmenu.py.
"""

import copy
import curses

__version__ = "0.0.1"
__author__ = "HA Bash Menu Development Team"
import os
import shutil
import subprocess
import sys
import textwrap
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASHMENU_DIR = SCRIPT_DIR
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

def get_clipboard_tool():
    """Detect available system clipboard tools."""
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    return None

CLIPBOARD_TOOL = get_clipboard_tool()

def copy_to_clipboard(text):
    """Copies string text to system clipboard using the detected tool."""
    if not CLIPBOARD_TOOL:
        return False
    try:
        if CLIPBOARD_TOOL == "xclip":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        elif CLIPBOARD_TOOL == "xsel":
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
    except Exception:
        pass
    return False

import bashmenu

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
    "popup": "[MSG]",
    "info": "[MSG]",
    "python": "[PY ]",
    "inject_block": "[INJ]",
    "theme_selector": "[THM]",
    "back": "[BCK]",
    "exit": "[EXT]",
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
]

def find_parent_options(menu_data, target_list):
    """
    Finds the options list and index of the submenu item that owns target_list.
    Returns (parent_options_list, parent_item_index) or (None, None).
    """
    def _search(opts):
        for idx, item in enumerate(opts):
            if isinstance(item, dict) and "submenu" in item:
                sub_opts = item["submenu"].get("options")
                if sub_opts is target_list:
                    return opts, idx
                if isinstance(sub_opts, list):
                    res = _search(sub_opts)
                    if res[0] is not None:
                        return res
        return None, None

    root_opts = menu_data.get("options", [])
    if root_opts is target_list:
        return None, None
    return _search(root_opts)

def _build_option_nodes(options_list, depth=1, expanded_map=None):
    """Helper to recursively convert options lists into tree nodes."""
    nodes = []
    if expanded_map is None:
        expanded_map = {}

    for idx, item in enumerate(options_list):
        if not isinstance(item, dict):
            continue

        item_id = id(item)
        is_expanded = expanded_map.get(item_id, True)
        has_children = "submenu" in item or item.get("type") == "confirm"

        node = {
            "item": item,
            "parent_list": options_list,
            "index": idx,
            "depth": depth,
            "expanded": is_expanded,
            "has_children": has_children,
            "id": item_id,
        }
        nodes.append(node)

        if is_expanded:
            if "submenu" in item and isinstance(item.get("submenu"), dict):
                sub_opts = item["submenu"].setdefault("options", [])
                nodes.extend(_build_option_nodes(sub_opts, depth + 1, expanded_map))

            if item.get("type") == "confirm":
                if "on_yes" in item and isinstance(item["on_yes"], dict):
                    nodes.append({
                        "item": item["on_yes"],
                        "parent_list": None,
                        "key_in_parent": ("on_yes", item),
                        "index": 0,
                        "depth": depth + 1,
                        "expanded": False,
                        "has_children": False,
                        "id": id(item["on_yes"]),
                        "prefix": "[YES] ",
                    })
                if "on_no" in item and isinstance(item["on_no"], dict):
                    nodes.append({
                        "item": item["on_no"],
                        "parent_list": None,
                        "key_in_parent": ("on_no", item),
                        "index": 0,
                        "depth": depth + 1,
                        "expanded": False,
                        "has_children": False,
                        "id": id(item["on_no"]),
                        "prefix": "[NO]  ",
                    })
    return nodes

def build_tree_nodes(menu_data, expanded_map=None):
    """Flattens root menu dictionary and children into list of node mappings."""
    if expanded_map is None:
        expanded_map = {}

    root_id = id(menu_data)
    is_expanded = expanded_map.get(root_id, True)

    root_node = {
        "item": {
            "label": f"Menu Title: {menu_data.get('title', 'Main Menu')}",
            "type": "root_menu",
        },
        "root_data": menu_data,
        "parent_list": None,
        "index": 0,
        "depth": 0,
        "expanded": is_expanded,
        "has_children": bool(menu_data.get("options")),
        "id": root_id,
    }

    nodes = [root_node]
    if is_expanded:
        options_list = menu_data.setdefault("options", [])
        nodes.extend(_build_option_nodes(options_list, depth=1, expanded_map=expanded_map))

    return nodes

def select_item_type(stdscr, theme):
    """Displays a modal chooser for selecting a menu item type."""
    height, width = stdscr.getmaxyx()
    box_h = len(ITEM_TYPES) + 4
    box_w = min(width - 4, 62)
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    bashmenu.draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)
    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)

    curr_idx = 0
    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        title = " Select Item Type "
        bashmenu.safe_addstr(win, 0, (box_w - len(title)) // 2, title, theme["title"] | curses.A_BOLD)

        for idx, (type_key, desc) in enumerate(ITEM_TYPES):
            attr = (theme["highlight"] | curses.A_BOLD) if idx == curr_idx else theme["text"]
            badge = TYPE_BADGES.get(type_key, "[   ]")
            label_str = f" {badge} {type_key:<15} {desc[:box_w - 28]}"
            bashmenu.safe_addstr(win, 2 + idx, 2, label_str, attr)

        footer = " [UP/DN]: Navigate | [ENTER]: Select | [ESC]: Cancel "
        bashmenu.safe_addstr(win, box_h - 1, (box_w - len(footer)) // 2, footer, theme["footer"])

        win.refresh()
        key = win.getch()

        if key == 27:
            return None
        elif key in [curses.KEY_UP, ord('k')] and curr_idx > 0:
            curr_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')] and curr_idx < len(ITEM_TYPES) - 1:
            curr_idx += 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            return ITEM_TYPES[curr_idx][0]


def select_script_action(stdscr, curr_val, config, theme):
    """Chooser modal for script action with option to browse or enter manually."""
    presets = [
        ("[PICK]", "Browse Local Directory (File Picker)..."),
        ("[EDIT]", "Manual Command Entry (Custom script/args)..."),
    ]

    height, width = stdscr.getmaxyx()
    box_h = len(presets) + 4
    box_w = min(width - 4, 66)
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    bashmenu.draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)
    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)

    curr_idx = 0
    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        title = " Select Script Action Input Method "
        bashmenu.safe_addstr(win, 0, (box_w - len(title)) // 2, title, theme["title"] | curses.A_BOLD)

        for idx, (var_key, desc) in enumerate(presets):
            attr = (theme["highlight"] | curses.A_BOLD) if idx == curr_idx else theme["text"]
            disp = f" {var_key:<12} {desc[:box_w - 16]}"
            bashmenu.safe_addstr(win, 2 + idx, 2, disp, attr)

        footer = " [UP/DN]: Navigate | [ENTER]: Select | [ESC]: Cancel "
        bashmenu.safe_addstr(win, box_h - 1, (box_w - len(footer)) // 2, footer, theme["footer"])

        win.refresh()
        key = win.getch()

        if key == 27:
            return None
        elif key in [curses.KEY_UP, ord('k')] and curr_idx > 0:
            curr_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')] and curr_idx < len(presets) - 1:
            curr_idx += 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            selected_key, _ = presets[curr_idx]
            if selected_key == "[PICK]":
                scripts_dir = (
                    bashmenu.get_config_value(config, "settings.scripts_dir")
                    or (config.get("scripts", "scripts") if config else "scripts")
                )
                scripts_dir = bashmenu.interpolate_placeholders(scripts_dir, config)
                if not os.path.isabs(scripts_dir):
                    scripts_dir = os.path.abspath(os.path.join(SCRIPT_DIR, scripts_dir))
                return bashmenu.show_file_picker(stdscr, "Select Script File", start_dir=scripts_dir, mode="file", default_val=curr_val, theme=theme)
            elif selected_key == "[EDIT]":
                return bashmenu.show_input_box(stdscr, "Script Action", "Script filename or command line:", curr_val, theme)


def select_editor_target(stdscr, curr_val, item_type, selected_key, config, theme):
    """Chooser modal for editor target path or built-in file variable."""
    presets = [
        ("{bashrc}", "User Bash Config (~/.bashrc)"),
        ("{vimrc}", "User Vim Config (~/.vimrc)"),
        ("{home}/autoexec.sh", "User Autoexec Script"),
        ("{home}/.bash_aliases", "User Bash Aliases"),
        ("[PICK]", "Browse Filesystem (File Picker)..."),
        ("[EDIT]", "Manual Text Entry (Custom Path / Placeholder)..."),
    ]

    height, width = stdscr.getmaxyx()
    box_h = len(presets) + 4
    box_w = min(width - 4, 66)
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    bashmenu.draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)
    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)

    curr_idx = 0
    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        title = " Select Target File / Directive "
        bashmenu.safe_addstr(win, 0, (box_w - len(title)) // 2, title, theme["title"] | curses.A_BOLD)

        for idx, (var_key, desc) in enumerate(presets):
            attr = (theme["highlight"] | curses.A_BOLD) if idx == curr_idx else theme["text"]
            disp = f" {var_key:<22} {desc[:box_w - 26]}"
            bashmenu.safe_addstr(win, 2 + idx, 2, disp, attr)

        footer = " [UP/DN]: Navigate | [ENTER]: Select | [ESC]: Cancel "
        bashmenu.safe_addstr(win, box_h - 1, (box_w - len(footer)) // 2, footer, theme["footer"])

        win.refresh()
        key = win.getch()

        if key == 27:
            return None
        elif key in [curses.KEY_UP, ord('k')] and curr_idx > 0:
            curr_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')] and curr_idx < len(presets) - 1:
            curr_idx += 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            selected_key_opt, _ = presets[curr_idx]
            if selected_key_opt == "[PICK]":
                start_dir = "~"
                if item_type == "inject_block":
                    templates_dir = (
                        bashmenu.get_config_value(config, "settings.templates_dir")
                        or (config.get("templates", "templates") if config else "templates")
                    )
                    templates_dir = bashmenu.interpolate_placeholders(templates_dir, config)
                    if not os.path.isabs(templates_dir):
                        templates_dir = os.path.abspath(os.path.join(SCRIPT_DIR, templates_dir))
                    start_dir = templates_dir
                return bashmenu.show_file_picker(stdscr, "Select Target File", start_dir=start_dir, mode="file", default_val=curr_val, theme=theme)
            elif selected_key_opt == "[EDIT]":
                return bashmenu.show_input_box(stdscr, "Target File Path", "File path or placeholder:", curr_val, theme)
            else:
                return selected_key_opt

def edit_item_properties(stdscr, item_dict, config, theme):
    """Interactive property inspector modal for editing an item's keys."""
    while True:
        item_type = item_dict.get("type")
        if "submenu" in item_dict:
            item_type = "submenu"

        fields = [
            ("label", "Display Label", str(item_dict.get("label", ""))),
            ("icon", "Nerd Font Icon / Emoji", str(item_dict.get("icon", "")))
        ]

        if item_type == "submenu":
            sub_title = item_dict.get("submenu", {}).get("title", "")
            fields.append(("submenu.title", "Submenu Header Title", str(sub_title)))
        elif item_type in ["command", "script", "python"]:
            fields.append(("action", "Command / Script Action", str(item_dict.get("action", ""))))
            if item_type == "script":
                fields.append(("external", "Run in separate process (true/false)", str(item_dict.get("external", True))))
            fields.append(("stream", "Stream Output (true/false)", str(item_dict.get("stream", False))))
            fields.append(("interactive", "Interactive Console Mode", str(item_dict.get("interactive", False))))
            fields.append(("user_mode", "User Privilege Mode (user/root)", str(item_dict.get("user_mode", "user"))))
            fields.append(("quiet", "Quiet Mode (suppress headers)", str(item_dict.get("quiet", False))))
            fields.append(("refresh", "Reload Menu On Return", str(item_dict.get("refresh", False))))
        elif item_type == "config":
            fields.append(("key", "YAML Setting Key (dot notation)", str(item_dict.get("key", ""))))
            fields.append(("title", "Input Popup Title", str(item_dict.get("title", ""))))
            fields.append(("prompt", "Input Prompt Text", str(item_dict.get("prompt", ""))))
            fields.append(("picker", "Picker Type (none/file/dir)", str(item_dict.get("picker", "none"))))
            fields.append(("start_dir", "Picker Starting Directory", str(item_dict.get("start_dir", "~"))))
            fields.append(("masked", "Mask Typed Password Input", str(item_dict.get("masked", False))))
        elif item_type in ["toggle", "config_toggle"]:
            fields.append(("key", "YAML Setting Key (dot notation)", str(item_dict.get("key", ""))))
            fields.append(("title", "Toggle Popup Title", str(item_dict.get("title", ""))))
            fields.append(("message", "Toggle Message Text", str(item_dict.get("message", item_dict.get("prompt", "")))))
        elif item_type == "editor":
            fields.append(("action", "Target File Path (empty for new)", str(item_dict.get("action", ""))))
            fields.append(("show_whitespace", "Show Whitespace (true/false)", str(item_dict.get("show_whitespace", False))))
            fields.append(("tab_to_spaces", "Convert Tab to Spaces", str(item_dict.get("tab_to_spaces", True))))
            fields.append(("tabstop", "Tabstop Width (spaces)", str(item_dict.get("tabstop", 8))))
        elif item_type == "inject_block":
            fields.append(("template", "Template File Path", str(item_dict.get("template", ""))))
            fields.append(("target", "Target File Path", str(item_dict.get("target", ""))))
            fields.append(("block_id", "Inject Block Unique ID", str(item_dict.get("block_id", ""))))
            fields.append(("refresh", "Reload Menu On Return", str(item_dict.get("refresh", False))))
        elif item_type == "confirm":
            fields.append(("title", "Confirmation Box Title", str(item_dict.get("title", ""))))
            fields.append(("message", "Confirmation Prompt Message", str(item_dict.get("message", ""))))
        elif item_type in ["message", "popup", "info"]:
            fields.append(("title", "Message Box Title", str(item_dict.get("title", ""))))
            fields.append(("message", "Message Text Body", str(item_dict.get("message", ""))))

        fields.append(("[TYPE]", "Change Item Type", f"Current: {item_type}"))
        fields.append(("[DONE]", "Save & Close Inspector", ""))

        height, width = stdscr.getmaxyx()
        box_h = min(height - 2, len(fields) + 5)
        box_w = min(width - 4, 68)
        start_y = (height - box_h) // 2
        start_x = (width - box_w) // 2

        bashmenu.draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)
        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.bkgd(' ', theme["text"])
        win.keypad(True)

        curr_field = 0
        prop_marquee_offset = 0
        prop_marquee_pause_ticks = 4
        last_field = -1
        copied_feedback_ticks = 0

        while True:
            if curr_field != last_field:
                prop_marquee_offset = 0
                prop_marquee_pause_ticks = 4
                last_field = curr_field

            win.erase()
            win.attron(theme["border"])
            win.border(0)
            win.attroff(theme["border"])

            badge = TYPE_BADGES.get(item_type, "[   ]")
            title_str = f" Property Inspector: {badge} {item_type} "
            bashmenu.safe_addstr(win, 0, (box_w - len(title_str)) // 2, title_str, theme["title"] | curses.A_BOLD)

            for idx, (f_key, f_name, f_val) in enumerate(fields):
                y = 2 + idx
                if y >= box_h - 2:
                    break

                attr = (theme["highlight"] | curses.A_BOLD) if idx == curr_field else theme["text"]
                val_avail_w = box_w - 35
                if idx == curr_field and not f_key.startswith("[") and len(f_val) > val_avail_w:
                    padded_text = f_val + (" " * val_avail_w) + f_val[:val_avail_w]
                    scroll_text = padded_text[prop_marquee_offset : prop_marquee_offset + val_avail_w]
                    disp = f" {f_name:<28} : {scroll_text}"
                elif f_key.startswith("["):
                    disp = f" {f_name:<28} {f_val}"
                else:
                    disp = f" {f_name:<28} : {f_val[:val_avail_w]}"
                bashmenu.safe_addstr(win, y, 2, disp, attr)

            if copied_feedback_ticks > 0:
                footer = " [ Copied to Clipboard! ] "
            elif CLIPBOARD_TOOL:
                footer = " [UP/DN]: Navigate | [ENTER]: Edit | [Y]: Copy | [ESC]: Close "
            else:
                footer = " [UP/DN]: Navigate | [ENTER]: Edit Field | [ESC]: Close "
            bashmenu.safe_addstr(win, box_h - 1, (box_w - len(footer)) // 2, footer, theme["footer"])

            win.refresh()
            win.timeout(250)
            key = win.getch()

            if key != -1 and key not in [ord('y'), ord('Y')]:
                copied_feedback_ticks = 0

            if key == -1:
                if copied_feedback_ticks > 0:
                    copied_feedback_ticks -= 1
                if fields and curr_field < len(fields):
                    fk, fn, fv = fields[curr_field]
                    val_avail_w = box_w - 35
                    if not fk.startswith("[") and len(fv) > val_avail_w:
                        if prop_marquee_pause_ticks > 0:
                            prop_marquee_pause_ticks -= 1
                        else:
                            prop_marquee_offset += 1
                            if prop_marquee_offset >= len(fv) + val_avail_w:
                                prop_marquee_offset = 0
                                prop_marquee_pause_ticks = 4
                continue

            if key == 27:
                return
            elif CLIPBOARD_TOOL and key in [ord('y'), ord('Y')]:
                if fields and curr_field < len(fields):
                    selected_key, field_label, curr_val = fields[curr_field]
                    if not selected_key.startswith("["):
                        if copy_to_clipboard(curr_val):
                            copied_feedback_ticks = 4
                continue
            elif key in [curses.KEY_UP, ord('k')] and curr_field > 0:
                curr_field -= 1
            elif key in [curses.KEY_DOWN, ord('j')] and curr_field < len(fields) - 1:
                curr_field += 1
            elif key in [curses.KEY_ENTER, 10, 13]:
                selected_key, field_label, curr_val = fields[curr_field]

                if selected_key == "[DONE]":
                    return
                elif selected_key == "[TYPE]":
                    win.timeout(-1)
                    new_t = select_item_type(stdscr, theme)
                    if new_t and new_t != item_type:
                        item_dict["type"] = new_t
                        if new_t == "submenu":
                            item_dict.pop("type", None)
                            item_dict.setdefault("submenu", {"title": item_dict.get("label", "Submenu"), "options": []})
                        break
                elif selected_key == "submenu.title":
                    win.timeout(-1)
                    new_val = bashmenu.show_input_box(stdscr, "Edit Submenu Title", "Submenu Header:", curr_val, theme)
                    if new_val is not None:
                        item_dict.setdefault("submenu", {})["title"] = new_val.strip()
                        break
                elif selected_key in ["stream", "interactive", "masked", "show_whitespace", "tab_to_spaces", "quiet", "refresh", "external"]:
                    bool_val = curr_val.lower() == "true"
                    item_dict[selected_key] = not bool_val
                    break
                elif selected_key in ["picker", "user_mode"]:
                    if selected_key == "picker":
                        opts = ["none", "file", "dir"]
                    else:
                        opts = ["user", "root"]
                    next_idx = (opts.index(curr_val) + 1) % len(opts) if curr_val in opts else 0
                    item_dict[selected_key] = opts[next_idx]
                    break
                elif selected_key == "action" and item_type == "script":
                    win.timeout(-1)
                    chosen = select_script_action(stdscr, curr_val, config, theme)
                    if chosen is not None:
                        item_dict[selected_key] = chosen
                        break
                elif (
                    (selected_key == "action" and item_type == "editor")
                    or (selected_key in ["template", "target"] and item_type == "inject_block")
                ):
                    win.timeout(-1)
                    chosen = select_editor_target(stdscr, curr_val, item_type, selected_key, config, theme)
                    if chosen is not None:
                        item_dict[selected_key] = chosen
                        break
                else:
                    win.timeout(-1)
                    new_val = bashmenu.show_input_box(stdscr, f"Edit {field_label}", f"{field_label}:", curr_val, theme)
                    if new_val is not None:
                        val_str = new_val.strip()
                        if val_str.isdigit():
                            val_str = int(val_str)
                        elif val_str.lower() in ["true", "false"]:
                            val_str = val_str.lower() == "true"
                        item_dict[selected_key] = val_str
                        break

def create_default_item(item_type):
    """Constructs default directive mapping for a newly added menu item."""
    if item_type == "submenu":
        return {
            "label": "New Submenu",
            "submenu": {"title": "New Submenu Options", "options": []}
        }
    elif item_type == "command":
        return {"label": "New Command", "type": "command", "action": "echo Hello"}
    elif item_type == "script":
        return {"label": "New Script", "type": "script", "action": "script.sh"}
    elif item_type == "config":
        return {
            "label": "New Config Setting",
            "type": "config",
            "key": "settings.new_key",
            "title": "Edit Setting",
            "prompt": "Enter value:"
        }
    elif item_type == "toggle":
        return {
            "label": "Toggle Setting",
            "type": "toggle",
            "key": "settings.new_key",
            "title": "Toggle Option",
            "message": "Enable option?"
        }
    elif item_type == "editor":
        return {"label": "Edit File", "type": "editor", "action": "file.txt", "show_whitespace": True}
    elif item_type == "confirm":
        return {
            "label": "New Confirmation Task",
            "type": "confirm",
            "title": "Confirm Task",
            "message": "Proceed with operation?",
            "on_yes": {"label": "Yes Action", "type": "message", "title": "Confirmed", "message": "Task executed."},
            "on_no": {"label": "No Action", "type": "message", "title": "Cancelled", "message": "Task aborted."}
        }
    elif item_type == "message":
        return {"label": "Show Message", "type": "message", "title": "Notice", "message": "Information text."}
    elif item_type == "python":
        return {"label": "Configure Autoexec", "type": "python", "action": "configure_autoexec"}
    elif item_type == "inject_block":
        return {
            "label": "Inject Code Block",
            "type": "inject_block",
            "template": "templates/block.tmpl",
            "target": "~/.bashrc",
            "block_id": "new_block_id",
            "refresh": False
        }
    elif item_type == "theme_selector":
        return {"label": "Change Color Theme", "type": "theme_selector"}
    elif item_type == "back":
        return {"label": "Back to Main Menu", "type": "back"}
    elif item_type == "exit":
        return {"label": "Exit Utility", "type": "exit"}
    return {"label": "New Option"}

def wrap_detail_lines(details, prop_w):
    """
    Wraps detail lines so that they fit within prop_w.
    If a line contains a colon, the value part is wrapped and indented to align with the colon.
    """
    wrapped_details = []
    for det in details:
        if ":" in det:
            colon_idx = det.index(":")
            prefix = det[:colon_idx + 2]
            value = det[colon_idx + 2:]
            
            avail_w = prop_w - len(prefix)
            if avail_w < 10:
                avail_w = prop_w
                prefix = ""
            
            wrapped_vals = textwrap.wrap(value, width=avail_w, break_long_words=True, break_on_hyphens=True)
            if not wrapped_vals:
                wrapped_details.append(prefix)
            else:
                wrapped_details.append(prefix + wrapped_vals[0])
                indent_spaces = " " * len(prefix)
                for val_part in wrapped_vals[1:]:
                    wrapped_details.append(indent_spaces + val_part)
        else:
            wrapped_details.extend(textwrap.wrap(det, width=prop_w, break_long_words=True, break_on_hyphens=True))
    return wrapped_details

def save_menu_file(menu_data, stdscr, theme):
    """Validates syntax and saves modified menu structure to bashmenu.mnu."""
    bak_file = bashmenu.MENU_FILE + ".bak"
    try:
        if os.path.exists(bashmenu.MENU_FILE):
            with open(bashmenu.MENU_FILE, "r", encoding="utf-8") as f_in:
                with open(bak_file, "w", encoding="utf-8") as f_out:
                    f_out.write(f_in.read())

        with open(bashmenu.MENU_FILE, "w", encoding="utf-8") as f:
            yaml.dump(menu_data, f, default_flow_style=False, sort_keys=False)

        msg = "Menu structure saved successfully to bashmenu.mnu!\nBackup written to bashmenu.mnu.bak."
        bashmenu.show_popup_message(stdscr, "Save Successful", msg, theme)
        return True
    except Exception as e:
        bashmenu.show_popup_message(stdscr, "Save Error", f"Error writing file:\n{e}", theme)
        return False

def main(stdscr):
    curses.curs_set(0)
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)

    stdscr.keypad(True)
    config, _ = bashmenu.load_config()
    theme = bashmenu.apply_theme(config.get("theme", "dracula"))
    stdscr.bkgd(' ', theme["text"])

    raw_menu, err = bashmenu.load_menu()
    if err or not raw_menu:
        bashmenu.show_popup_message(stdscr, "Menu Load Error", f"Could not load menu file:\n{err}", theme)
        return

    menu_data = raw_menu
    expanded_map = {}
    selected_idx = 0
    modified = False

    marquee_offset = 0
    marquee_pause_ticks = 4
    last_idx = -1

    while True:
        if selected_idx != last_idx:
            marquee_offset = 0
            marquee_pause_ticks = 4
            last_idx = selected_idx

        stdscr.erase()
        height, width = stdscr.getmaxyx()

        stdscr.attron(theme["border"])
        stdscr.border(0)
        stdscr.attroff(theme["border"])

        mod_tag = " *" if modified else ""
        header = f" HA Bash Menu - Visual Menu Editor (menuedit.py){mod_tag} "
        bashmenu.safe_addstr(stdscr, 1, max(2, (width - len(header)) // 2), header, theme["title"] | curses.A_BOLD)

        nodes = build_tree_nodes(menu_data, expanded_map=expanded_map)
        selected_idx = max(0, min(selected_idx, len(nodes) - 1))
        curr_node = nodes[selected_idx]

        tree_w = max(32, int(width * 0.48))
        if tree_w >= width - 4:
            tree_w = max(10, width - 15)
        prop_w = max(1, width - tree_w - 3)

        max_visible = height - 5
        scroll_top = max(0, selected_idx - (max_visible // 2))

        for i in range(max_visible):
            node_idx = scroll_top + i
            if node_idx >= len(nodes):
                break

            nd = nodes[node_idx]
            y = 3 + i
            item = nd["item"]

            item_type = item.get("type", "submenu" if "submenu" in item else "option")
            badge = TYPE_BADGES.get(item_type, "[OPT]")

            fold = " "
            if nd["has_children"]:
                fold = "▼" if nd["expanded"] else "▶"

            indent = "  " * nd["depth"]
            label = item.get("label", "Untitled")
            pfx = nd.get("prefix", "")

            pfx_len = len(indent) + len(fold) + 1 + len(badge) + 1 + len(pfx)
            label_avail_w = max(1, tree_w - 4 - pfx_len)

            if node_idx == selected_idx and len(label) > label_avail_w:
                padded_text = label + (" " * label_avail_w) + label[:label_avail_w]
                scroll_text = padded_text[marquee_offset : marquee_offset + label_avail_w]
                line_str = f"{indent}{fold} {badge} {pfx}{scroll_text}"
            else:
                line_str = f"{indent}{fold} {badge} {pfx}{label}"

            line_padded = f"{line_str:<{tree_w - 4}}"[:tree_w - 4]

            attr = (theme["highlight"] | curses.A_BOLD) if node_idx == selected_idx else theme["text"]
            bashmenu.safe_addstr(stdscr, y, 2, line_padded, attr)

        for y in range(3, height - 2):
            bashmenu.safe_addstr(stdscr, y, tree_w, "│", theme["border"])

        prop_x = tree_w + 2
        bashmenu.safe_addstr(stdscr, 3, prop_x, " Node Inspector & Details ", theme["accent"] | curses.A_BOLD)

        curr_item = curr_node["item"]
        curr_type = curr_item.get("type", "submenu" if "submenu" in curr_item else "option")

        if curr_type == "root_menu":
            details = [
                f"Title : {curr_node['root_data'].get('title', '')}",
                f"Type  : Main Menu Root",
                f"Count : {len(curr_node['root_data'].get('options', []))} top-level options",
            ]
        else:
            details = [
                f"Label : {curr_item.get('label', '')}",
                f"Type  : {curr_type}",
            ]
            for k in ["icon", "action", "key", "title", "prompt", "user_mode", "stream", "interactive", "show_whitespace", "tabstop", "quiet", "refresh"]:
                if k in curr_item:
                    details.append(f"{k:<10}: {curr_item[k]}")

        wrapped_details = wrap_detail_lines(details, prop_w)

        for idx, det in enumerate(wrapped_details[:height - 8]):
            bashmenu.safe_addstr(stdscr, 5 + idx, prop_x, det[:prop_w], theme["text"])

        # Calculate dynamic state flags for current node
        is_root = curr_type == "root_menu"
        pl = curr_node.get("parent_list")
        idx_in_parent = curr_node.get("index")

        can_move_up = pl is not None and idx_in_parent is not None and idx_in_parent > 0
        can_move_dn = pl is not None and idx_in_parent is not None and idx_in_parent < len(pl) - 1

        can_indent = False
        if not is_root and pl and idx_in_parent is not None and idx_in_parent > 0:
            prev_item = pl[idx_in_parent - 1]
            if isinstance(prev_item, dict) and "submenu" in prev_item:
                can_indent = True

        can_outdent = False
        if not is_root and pl and idx_in_parent is not None:
            parent_opts, _ = find_parent_options(menu_data, pl)
            if parent_opts is not None:
                can_outdent = True

        # Construct dynamic footer keyboard shortcut string
        footer_parts = ["[a]: Add", "[e/ENTER]: Edit"]
        if not is_root:
            footer_parts.append("[d]: Del")

        if can_move_up and can_move_dn:
            footer_parts.append("[m/M]: Move")
        elif can_move_dn:
            footer_parts.append("[m]: Move Dn")
        elif can_move_up:
            footer_parts.append("[M]: Move Up")

        if can_outdent and can_indent:
            footer_parts.append("[</>]: Out/In")
        elif can_outdent:
            footer_parts.append("[<]: Outdent")
        elif can_indent:
            footer_parts.append("[>]: Indent")

        if not is_root:
            footer_parts.append("[t]: Test")

        footer_parts.extend(["[s]: Save", "[ESC]: Exit"])
        footer = " " + " | ".join(footer_parts) + " "

        bashmenu.safe_addstr(stdscr, height - 2, max(2, (width - len(footer)) // 2), footer, theme["footer"])

        stdscr.refresh()
        stdscr.timeout(250)
        key = stdscr.getch()

        if key == -1:
            if nodes and selected_idx < len(nodes):
                nd = nodes[selected_idx]
                item = nd["item"]
                label = item.get("label", "Untitled")
                indent = "  " * nd["depth"]
                fold = "▼" if nd["expanded"] else "▶" if nd["has_children"] else " "
                badge = TYPE_BADGES.get(item.get("type", "submenu" if "submenu" in item else "option"), "[OPT]")
                pfx = nd.get("prefix", "")
                pfx_len = len(indent) + len(fold) + 1 + len(badge) + 1 + len(pfx)
                law = max(1, tree_w - 4 - pfx_len)
                if len(label) > law:
                    if marquee_pause_ticks > 0:
                        marquee_pause_ticks -= 1
                    else:
                        marquee_offset += 1
                        if marquee_offset >= len(label) + law:
                            marquee_offset = 0
                            marquee_pause_ticks = 4
            continue

        if key in [curses.KEY_UP, ord('k')]:
            if selected_idx > 0:
                selected_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')]:
            if selected_idx < len(nodes) - 1:
                selected_idx += 1
        elif key in [ord(' '), curses.KEY_RIGHT] and curr_node["has_children"]:
            expanded_map[curr_node["id"]] = not curr_node["expanded"]
        elif key in [curses.KEY_ENTER, 10, 13, ord('e')]:
            stdscr.timeout(-1)
            if curr_node["item"].get("type") == "root_menu":
                curr_title = curr_node["root_data"].get("title", "")
                new_title = bashmenu.show_input_box(stdscr, "Edit Main Menu Title", "Main Menu Header Title:", curr_title, theme)
                if new_title is not None:
                    curr_node["root_data"]["title"] = new_title.strip()
                    modified = True
            else:
                edit_item_properties(stdscr, curr_node["item"], config, theme)
                modified = True
        elif key == ord('E'):
            stdscr.timeout(-1)
            if curr_node["item"].get("type") == "root_menu":
                target_dict = curr_node["root_data"]
            else:
                target_dict = curr_node["item"]

            raw_str = yaml.dump(target_dict, default_flow_style=False, sort_keys=False)
            tmp_path = os.path.join(SCRIPT_DIR, ".tmp_node.yml")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(raw_str)

            bashmenu.run_curses_editor(stdscr, tmp_path, theme, show_whitespace=True)
            try:
                with open(tmp_path, "r", encoding="utf-8") as f:
                    parsed = yaml.safe_load(f)
                    if isinstance(parsed, dict):
                        target_dict.clear()
                        target_dict.update(parsed)
                        modified = True
            except Exception as ex:
                bashmenu.show_popup_message(stdscr, "YAML Error", f"Invalid YAML structure:\n{ex}", theme)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        elif key in [ord('a'), curses.KEY_IC]:
            stdscr.timeout(-1)
            sel_type = select_item_type(stdscr, theme)
            if sel_type:
                new_item = create_default_item(sel_type)
                if curr_node["item"].get("type") == "root_menu":
                    opts = curr_node["root_data"].setdefault("options", [])
                    opts.insert(0, new_item)
                else:
                    parent_lst = curr_node["parent_list"]
                    if parent_lst is not None:
                        parent_lst.insert(curr_node["index"] + 1, new_item)
                    else:
                        menu_data.setdefault("options", []).append(new_item)

                edit_item_properties(stdscr, new_item, config, theme)
                modified = True
        elif key in [ord('d'), curses.KEY_DC]:
            if curr_node["item"].get("type") == "root_menu":
                stdscr.timeout(-1)
                bashmenu.show_popup_message(stdscr, "Notice", "Main Menu Root node cannot be deleted.", theme)
            else:
                lbl = curr_node["item"].get("label", "Selected Item")
                stdscr.timeout(-1)
                res = bashmenu.show_confirm_box(stdscr, "Delete Item", f"Delete menu item '{lbl}'?", theme)
                if res == "yes":
                    pl = curr_node["parent_list"]
                    if pl is not None and curr_node["index"] < len(pl):
                        pl.pop(curr_node["index"])
                    elif curr_node.get("key_in_parent"):
                        k, parent_dict = curr_node["key_in_parent"]
                        parent_dict.pop(k, None)
                    modified = True
        elif key == ord('m') and can_move_dn:
            idx = curr_node["index"]
            pl[idx], pl[idx + 1] = pl[idx + 1], pl[idx]
            selected_idx += 1
            modified = True
        elif key == ord('M') and can_move_up:
            idx = curr_node["index"]
            pl[idx], pl[idx - 1] = pl[idx - 1], pl[idx]
            selected_idx -= 1
            modified = True
        elif key in [ord('>'), ord('.'), 9] and can_indent:
            prev_item = pl[idx_in_parent - 1]
            sub_opts = prev_item["submenu"].setdefault("options", [])
            item = pl.pop(idx_in_parent)
            sub_opts.append(item)
            expanded_map[id(prev_item)] = True
            modified = True
        elif key in [ord('<'), ord(','), curses.KEY_BTAB] and can_outdent:
            parent_opts, parent_idx = find_parent_options(menu_data, pl)
            if parent_opts is not None and parent_idx is not None:
                item = pl.pop(idx_in_parent)
                parent_opts.insert(parent_idx + 1, item)
                modified = True
        elif key == ord('t'):
            if curr_node["item"].get("type") != "root_menu":
                stdscr.timeout(-1)
                bashmenu.process_item_action(curr_node["item"], stdscr, config, theme, [], [0])
        elif key in [ord('s'), 19]:
            stdscr.timeout(-1)
            if save_menu_file(menu_data, stdscr, theme):
                modified = False
        elif key == 27:
            if modified:
                stdscr.timeout(-1)
                res = bashmenu.show_confirm_box(stdscr, "Unsaved Changes", "Save changes to bashmenu.mnu before exiting?", theme)
                if res == "yes":
                    save_menu_file(menu_data, stdscr, theme)
                    break
                elif res == "no":
                    break
            else:
                break

if __name__ == "__main__":
    is_tty = os.environ.get("TERM") == "linux" or not os.isatty(sys.stdout.fileno())
    sys.stdout.write("\033[?1049h")
    sys.stdout.flush()

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    finally:
        if is_tty:
            sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()
        sys.exit(0)
