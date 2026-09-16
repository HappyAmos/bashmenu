"""
bashmenu_ui.py - Reusable TUI primitives, dialogs and text boxes for bashmenu and bashedit.
"""

import curses
import os
import unicodedata


def safe_isprintable(s: str) -> bool:
    """
    Returns True if the string contains only valid printable characters,
    specifically preserving Nerd Font / PUA glyphs.
    """
    for char in s:
        # Get the 2-letter Unicode category (e.g., 'Cc', 'Lo', 'Co')
        category = unicodedata.category(char)
        
        # 'Co' is the category for Private Use Areas (where Nerd Fonts live)
        if category == 'Co':
            continue
            
        # 'C' covers Control (Cc), Format (Cf), Surrogate (Cs), and Unassigned (Cn)
        # 'Z' covers separators (except regular space, handled by 'Zs' checks natively)
        if category.startswith('C') or category == 'Zl' or category == 'Zp':
            return False
            
    return True


def safe_addstr(win, y, x, text, attr=0):
    """
    Safely write a string within window boundaries to prevent curses crashes.

    Args:
        win (curses.window): Target curses window object.
        y (int): Row position on window.
        x (int): Column position on window.
        text (str): String content to render.
        attr (int): Curses text attributes/color pairs.
    """
    h, w = win.getmaxyx()
    if y >= h or x >= w:
        return
    max_len = w - x if y < h - 1 else w - x - 1
    if max_len > 0:
        try:
            win.addstr(y, x, text[:max_len], attr)
        except curses.error:
            pass


def draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme=None):
    """
    Draw a drop shadow behind a popup modal window on stdscr.

    Args:
        stdscr (curses.window): Main curses screen window.
        start_y (int): Top row position of modal dialog box.
        start_x (int): Left column position of modal dialog box.
        box_h (int): Height of modal dialog box.
        box_w (int): Width of modal dialog box.
        theme (dict, optional): Active theme pair mapping.
    """
    max_y, max_x = stdscr.getmaxyx()
    shadow_attr = (
        theme["shadow"]
        if (theme and "shadow" in theme)
        else (curses.A_DIM | curses.A_REVERSE)
    )

    for y in range(start_y + 1, min(max_y, start_y + box_h + 1)):
        for x in range(start_x + box_w, min(max_x, start_x + box_w + 2)):
            try:
                ch = stdscr.inch(y, x) & 0xFF
                if ch in [0, 32]:
                    stdscr.addch(y, x, " ", shadow_attr)
                else:
                    stdscr.addch(y, x, ch, shadow_attr | curses.A_DIM)
            except curses.error:
                pass

    for x in range(start_x + 2, min(max_x, start_x + box_w + 2)):
        y = start_y + box_h
        if y < max_y:
            try:
                ch = stdscr.inch(y, x) & 0xFF
                if ch in [0, 32]:
                    stdscr.addch(y, x, " ", shadow_attr)
                else:
                    stdscr.addch(y, x, ch, shadow_attr | curses.A_DIM)
            except curses.error:
                pass

    stdscr.refresh()


def show_popup_message(stdscr, title, message, theme):
    """
    Display a modal popup dialog with scrolling support for multi-line text.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Header title of message dialog.
        message (str): Body text or detailed exception content.
        theme (dict): Active color theme mapping.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(8, len(lines) + 4))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(46, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)

    max_visible = box_h - 3
    scroll_offset = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        if title:
            safe_addstr(
                win,
                0,
                max(2, (box_w - len(title) - 2) // 2),
                f" {title} ",
                theme["title"] | curses.A_BOLD,
            )

        for i in range(max_visible):
            line_idx = scroll_offset + i
            if line_idx < len(lines):
                safe_addstr(win, i + 1, 2, lines[line_idx], theme["text"])

        footer = (
            " [Press ENTER or ESC] "
            if len(lines) <= max_visible
            else " [UP/DN/PgUp/PgDn]: Scroll | [ESC/ENTER]: Close "
        )
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, curses.KEY_ENTER, 10, 13]:
            break
        elif key in [curses.KEY_UP, ord('k')] and scroll_offset > 0:
            scroll_offset -= 1
        elif (
            key in [curses.KEY_DOWN, ord('j')]
            and scroll_offset < len(lines) - max_visible
        ):
            scroll_offset += 1
        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - max_visible)
        elif key == curses.KEY_NPAGE:
            scroll_offset = min(
                max(0, len(lines) - max_visible), scroll_offset + max_visible
            )
        elif key in [curses.KEY_HOME, ord('g')]:
            scroll_offset = 0
        elif key in [curses.KEY_END, ord('G')]:
            scroll_offset = max(0, len(lines) - max_visible)


def show_confirm_box(stdscr, title, message, theme):
    """
    Display an interactive modal confirmation box (Yes / No / Cancel).

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        message (str): Confirmation prompt query string.
        theme (dict): Active theme color mapping.

    Returns:
        str | None: 'yes', 'no', or None if user pressed ESC or Cancel.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(7, len(lines) + 5))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(52, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(0)

    buttons = ["Yes", "No", "Cancel"]
    active_btn = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        if title:
            safe_addstr(
                win,
                0,
                max(2, (box_w - len(title) - 2) // 2),
                f" {title} ",
                theme["title"] | curses.A_BOLD,
            )

        for i, line in enumerate(lines[: box_h - 4]):
            safe_addstr(
                win, 2 + i, max(2, (box_w - len(line)) // 2), line, theme["text"]
            )

        btn_y = box_h - 2
        btn_labels = [f" [ {b} ] " for b in buttons]
        total_btns_w = sum(len(b) for b in btn_labels) + 4
        btn_start_x = max(2, (box_w - total_btns_w) // 2)

        curr_x = btn_start_x
        for idx, (btn_name, btn_str) in enumerate(zip(buttons, btn_labels)):
            attr = (
                (theme["highlight"] | curses.A_BOLD)
                if idx == active_btn
                else theme["text"]
            )
            safe_addstr(win, btn_y, curr_x, btn_str, attr)
            curr_x += len(btn_str) + 2

        footer = " [LEFT/RIGHT]: Select | [ENTER]: Confirm | [ESC]: Cancel "
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, ord('c'), ord('C')]:
            return None
        elif key in [ord('y'), ord('Y')]:
            return "yes"
        elif key in [ord('n'), ord('N')]:
            return "no"
        elif key in [curses.KEY_LEFT, curses.KEY_UP, ord('h')]:
            active_btn = (active_btn - 1) % len(buttons)
        elif key in [curses.KEY_RIGHT, curses.KEY_DOWN, 9, ord('l')]:
            active_btn = (active_btn + 1) % len(buttons)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if active_btn == 0:
                return "yes"
            elif active_btn == 1:
                return "no"
            else:
                return None


def show_toggle_box(stdscr, title, message, theme):
    """
    Display an interactive modal toggle box (True / False / Cancel).

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        message (str): Toggle prompt query string.
        theme (dict): Active theme color mapping.

    Returns:
        str | None: 'true', 'false', or None if user pressed ESC or Cancel.
    """
    height, width = stdscr.getmaxyx()
    lines = str(message).splitlines() if str(message).strip() else [""]

    box_h = min(height - 2, max(7, len(lines) + 5))
    max_line_w = max((len(l) for l in lines), default=30)
    box_w = min(width - 4, max(52, max_line_w + 6))

    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(0)

    buttons = ["True", "False", "Cancel"]
    active_btn = 0

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        if title:
            safe_addstr(
                win,
                0,
                max(2, (box_w - len(title) - 2) // 2),
                f" {title} ",
                theme["title"] | curses.A_BOLD,
            )

        for i, line in enumerate(lines[: box_h - 4]):
            safe_addstr(
                win, 2 + i, max(2, (box_w - len(line)) // 2), line, theme["text"]
            )

        btn_y = box_h - 2
        btn_labels = [f" [ {b} ] " for b in buttons]
        total_btns_w = sum(len(b) for b in btn_labels) + 4
        btn_start_x = max(2, (box_w - total_btns_w) // 2)

        curr_x = btn_start_x
        for idx, (btn_name, btn_str) in enumerate(zip(buttons, btn_labels)):
            attr = (
                (theme["highlight"] | curses.A_BOLD)
                if idx == active_btn
                else theme["text"]
            )
            safe_addstr(win, btn_y, curr_x, btn_str, attr)
            curr_x += len(btn_str) + 2

        footer = " [LEFT/RIGHT]: Select | [ENTER]: Confirm | [ESC]: Cancel "
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        win.refresh()
        key = win.getch()

        if key in [27, ord('c'), ord('C')]:
            return None
        elif key in [ord('t'), ord('T')]:
            return "true"
        elif key in [ord('f'), ord('F')]:
            return "false"
        elif key in [curses.KEY_LEFT, curses.KEY_UP, ord('h')]:
            active_btn = (active_btn - 1) % len(buttons)
        elif key in [curses.KEY_RIGHT, curses.KEY_DOWN, 9, ord('l')]:
            active_btn = (active_btn + 1) % len(buttons)
        elif key in [curses.KEY_ENTER, 10, 13]:
            if active_btn == 0:
                return "true"
            elif active_btn == 1:
                return "false"
            else:
                return None


def show_input_box(
    stdscr, title, prompt, default_text="", theme=None, masked=False
):
    """
    Display a single-line modal text input prompt.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Dialog box title header.
        prompt (str): Text prompt label displayed above input line.
        default_text (str): Initial string value inside input field.
        theme (dict, optional): Active theme color mapping.
        masked (bool): If True, input characters are rendered as asterisks.

    Returns:
        str | None: User input string, or None if cancelled via ESC.
    """
    height, width = stdscr.getmaxyx()
    box_h = 7
    box_w = min(width - 4, max(50, len(prompt) + 8))
    start_y = (height - box_h) // 2
    start_x = (width - box_w) // 2

    draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

    win = curses.newwin(box_h, box_w, start_y, start_x)
    win.bkgd(' ', theme["text"])
    win.keypad(True)
    curses.curs_set(1)

    input_text = list(default_text)
    cursor_pos = len(input_text)
    field_w = box_w - 6

    while True:
        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        if title:
            safe_addstr(
                win,
                0,
                max(2, (box_w - len(title) - 2) // 2),
                f" {title} ",
                theme["title"] | curses.A_BOLD,
            )
        safe_addstr(win, 2, 3, prompt, theme["text"])

        raw_str = "".join(input_text)
        display_str = "*" * len(raw_str) if masked else raw_str

        offset = max(0, cursor_pos - field_w + 1)
        visible_text = display_str[offset : offset + field_w]

        field_padded = visible_text.ljust(field_w)
        safe_addstr(win, 4, 3, f" {field_padded} ", theme["highlight"])
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - 32) // 2),
            " [ENTER]: Confirm | [ESC]: Cancel ",
            theme["footer"],
        )

        win.move(4, 4 + (cursor_pos - offset))
        win.refresh()

        try:
            key = win.get_wch()
        except curses.error:
            continue

        if key == 27 or key == '\x1b':
            curses.curs_set(0)
            return None
        elif key in [curses.KEY_ENTER, 10, 13, '\n', '\r']:
            curses.curs_set(0)
            return "".join(input_text)
        elif key in [curses.KEY_BACKSPACE, 8, 127, '\x08', '\x7f', '\b']:
            if cursor_pos > 0:
                input_text.pop(cursor_pos - 1)
                cursor_pos -= 1
        elif key == curses.KEY_DC:
            if cursor_pos < len(input_text):
                input_text.pop(cursor_pos)
        elif key == curses.KEY_LEFT:
            if cursor_pos > 0:
                cursor_pos -= 1
        elif key == curses.KEY_RIGHT:
            if cursor_pos < len(input_text):
                cursor_pos += 1
        elif key in [curses.KEY_HOME, 1, '\x01']:
            cursor_pos = 0
        elif key in [curses.KEY_END, 5, '\x05']:
            cursor_pos = len(input_text)
        elif isinstance(key, str) and len(key) == 1 and safe_isprintable(key):
            input_text.insert(cursor_pos, key)
            cursor_pos += 1


def show_file_picker(
    stdscr, title, start_dir="~", mode="file", default_val=None, theme=None, show_hidden=False, allow_new=False
):
    """
    Display a themed interactive file and directory chooser modal dialog.

    Args:
        stdscr (curses.window): Main screen window.
        title (str): Header title for file picker modal.
        start_dir (str): Initial filesystem path to list.
        mode (str): Selection mode filter ('file', 'dir', or 'any').
        default_val (str, optional): Pre-selected item path.
        theme (dict, optional): Active theme color mapping.
        show_hidden (bool, optional): Whether to display hidden files/folders.

    Returns:
        str | None: Selected absolute path, or None if cancelled via ESC.
    """
    import bashmenu

    show_hidden_state = show_hidden
    target_item = None
    if default_val:
        resolved_default = os.path.abspath(
            os.path.expanduser(str(default_val).strip())
        )
        if os.path.exists(resolved_default):
            target_item = resolved_default

    current_path = os.path.abspath(os.path.expanduser(start_dir))
    if not os.path.exists(current_path) or not os.path.isdir(current_path):
        if os.path.exists(os.path.dirname(current_path)) and os.path.isdir(
            os.path.dirname(current_path)
        ):
            current_path = os.path.dirname(current_path)
        else:
            current_path = bashmenu.USER_HOME

    cursor_idx = 0
    scroll_offset = 0
    curses.curs_set(0)
    initial_selection_done = False

    config, _ = bashmenu.load_config()
    ind = bashmenu.interpolate_placeholders(theme.get("indicator", ">"), config) if theme else ">"
    prefix_str = f"{ind} " if ind else "  "
    indent_str = " " * len(prefix_str)

    while True:
        entries = []
        try:
            with os.scandir(current_path) as it:
                all_entries = list(it)

            if not show_hidden_state:
                all_entries = [e for e in all_entries if not e.name.startswith(".")]

            dirs = sorted(
                [e for e in all_entries if e.is_dir()],
                key=lambda e: e.name.lower(),
            )
            files = sorted(
                [e for e in all_entries if not e.is_dir()],
                key=lambda e: e.name.lower(),
            )

            if current_path != "/":
                entries.append({
                    "name": ".. (Parent Directory)",
                    "is_dir": True,
                    "path": os.path.dirname(current_path),
                    "is_parent": True,
                })

            if mode == "dir":
                entries.append({
                    "name": (
                        f"[ Select Current Directory: "
                        f"{os.path.basename(current_path) or '/'} ]"
                    ),
                    "is_dir": True,
                    "path": current_path,
                    "is_self": True,
                })

            for d in dirs:
                entries.append({
                    "name": f"[DIR]  {d.name}/",
                    "is_dir": True,
                    "path": d.path,
                    "is_parent": False,
                })

            if mode != "dir":
                for f in files:
                    entries.append({
                        "name": f"[FILE] {f.name}",
                        "is_dir": False,
                        "path": f.path,
                        "is_parent": False,
                    })

        except PermissionError:
            entries = [{
                "name": "![ Permission Denied ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]
        except OSError as e:  # Catch directory scanning/listing issues safely
            entries = [{
                "name": f"![ Error: {e} ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]

        if not entries:
            entries = [{
                "name": "[ Empty Directory ]",
                "is_dir": False,
                "path": None,
                "error": True,
            }]

        if not initial_selection_done:
            if target_item:
                for idx, ent in enumerate(entries):
                    if (
                        mode == "dir"
                        and ent.get("is_self")
                        and target_item == current_path
                    ) or ent.get("path") == target_item:
                        cursor_idx = idx
                        break
            elif mode == "dir":
                for idx, ent in enumerate(entries):
                    if ent.get("is_self"):
                        cursor_idx = idx
                        break
            initial_selection_done = True

        cursor_idx = max(0, min(cursor_idx, len(entries) - 1))

        height, width = stdscr.getmaxyx()
        box_h = max(12, int(height * 0.75))
        box_w = max(50, int(width * 0.75))
        start_y = (height - box_h) // 2
        start_x = (width - box_w) // 2

        draw_shadow(stdscr, start_y, start_x, box_h, box_w, theme)

        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.bkgd(' ', theme["text"])
        win.keypad(True)

        max_visible = box_h - 4

        if cursor_idx < scroll_offset:
            scroll_offset = cursor_idx
        elif cursor_idx >= scroll_offset + max_visible:
            scroll_offset = cursor_idx - max_visible + 1

        win.erase()
        win.attron(theme["border"])
        win.border(0)
        win.attroff(theme["border"])

        if title:
            header = f" {title} "
            safe_addstr(
                win,
                0,
                max(2, (box_w - len(header)) // 2),
                header,
                theme["title"] | curses.A_BOLD,
            )

        path_disp = f" Path: {current_path} "
        if len(path_disp) > box_w - 4:
            path_disp = " Path: ..." + path_disp[-(box_w - 10) :]
        safe_addstr(win, 1, 2, path_disp, theme["accent"])

        footer_parts = []
        if mode == "dir":
            footer_parts.append("[ENTER]: Open")
            footer_parts.append("[SPACE]: Select Folder")
        else:
            footer_parts.append("[ENTER]: Select/Open")

        if allow_new:
            if mode == "dir":
                footer_parts.append("[N]: New Folder")
            else:
                footer_parts.append("[N]: New File")

        footer_parts.append("[Ctrl+H]: Hidden")
        footer_parts.append("[ESC]: Cancel")

        footer = " " + " | ".join(footer_parts) + " " 
        safe_addstr(
            win,
            box_h - 1,
            max(2, (box_w - len(footer)) // 2),
            footer,
            theme["footer"],
        )

        for i in range(max_visible):
            idx = scroll_offset + i
            if idx >= len(entries):
                break

            entry = entries[idx]
            y = 2 + i
            max_len = box_w - 6
            label = entry["name"][:max_len]

            if idx == cursor_idx:
                safe_addstr(
                    win,
                    y,
                    2,
                    f"{prefix_str}{label:<{max_len}}",
                    theme["highlight"] | curses.A_BOLD,
                )
            else:
                attr = theme["accent"] if entry.get("is_dir") else theme["text"]
                safe_addstr(win, y, 2, f"{indent_str}{label}", attr)

        win.refresh()
        key = win.getch()

        if key == 27:
            return None
        elif key == 8:  # Ctrl+H: Toggle Hidden Files/Directories
            prev_selected_path = None
            if entries and 0 <= cursor_idx < len(entries):
                prev_selected_path = entries[cursor_idx].get("path")

            show_hidden_state = not show_hidden_state

            if prev_selected_path:
                target_item = prev_selected_path
                initial_selection_done = False
        elif key in [curses.KEY_UP, ord('k')] and cursor_idx > 0:
            cursor_idx -= 1
        elif key in [curses.KEY_DOWN, ord('j')] and cursor_idx < len(entries) - 1:
            cursor_idx += 1
        elif key == curses.KEY_PPAGE:
            cursor_idx = max(0, cursor_idx - max_visible)
        elif key == curses.KEY_NPAGE:
            cursor_idx = min(len(entries) - 1, cursor_idx + max_visible)
        elif key in [curses.KEY_HOME, ord('g')]:
            cursor_idx = 0
        elif key in [curses.KEY_END, ord('G')]:
            cursor_idx = len(entries) - 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            if not entries or cursor_idx >= len(entries):
                continue
            selected = entries[cursor_idx]
            if selected.get("error") or selected.get("path") is None:
                continue
            if selected.get("is_parent") or selected["is_dir"]:
                if selected.get("is_self"):
                    return selected["path"]
                current_path = selected["path"]
                cursor_idx = 0
                scroll_offset = 0
            elif mode in ["file", "any"]:
                return selected["path"]
        elif key == ord(' ') and mode == "dir":
            return current_path
        elif key in [ord('n'), ord('N')] and allow_new:
            if mode == "dir":
                new_name = show_input_box(
                    stdscr, "Create New Directory", "Enter new directory name:", "", theme
                )
                if new_name is not None:
                    new_name = new_name.strip()
                    if new_name:
                        new_dirpath = os.path.join(current_path, new_name)
                        if os.path.exists(new_dirpath):
                            show_popup_message(
                                stdscr,
                                "Error",
                                f"Directory or file already exists:\n{new_name}",
                                theme,
                            )
                        else:
                            try:
                                os.makedirs(new_dirpath, exist_ok=True)
                                target_item = new_dirpath
                                initial_selection_done = False
                            except OSError as e:  # Catch directory creation failures safely
                                show_popup_message(
                                    stdscr,
                                    "Error",
                                    f"Failed to create directory:\n{e}",
                                    theme,
                                )
            else:
                new_name = show_input_box(
                    stdscr, "Create New File", "Enter new filename:", "", theme
                )
                if new_name is not None:
                    new_name = new_name.strip()
                    if new_name:
                        new_filepath = os.path.join(current_path, new_name)
                        if os.path.exists(new_filepath):
                            show_popup_message(
                                stdscr,
                                "Error",
                                f"File already exists:\n{new_name}",
                                theme,
                            )
                        else:
                            try:
                                with open(new_filepath, "w", encoding="utf-8"):
                                    pass
                                target_item = new_filepath
                                initial_selection_done = False
                            except OSError as e:  # Catch filesystem write errors safely
                                show_popup_message(
                                    stdscr,
                                    "Error",
                                    f"Failed to create file:\n{e}",
                                    theme,
                                )
