"""
bashedit.py - A standalone curses text editor module.
"""

import curses
import os
import shlex
import subprocess
import sys
import termios

import bashmenu_ui


def run_curses_editor(
    stdscr,
    file_path,
    theme,
    show_whitespace=False,
    tab_to_spaces=True,
    tabstop=8,
):
    """
    Launch full-screen curses text editor with Nano-style shortcuts.

    Args:
        stdscr (curses.window): Main screen window handle.
        file_path (str | None): Path of target file to create or edit.
        theme (dict): Active theme color attribute map.
        show_whitespace (bool): Toggle rendering of space/tab glyphs.
        tab_to_spaces (bool): If True, convert Tab key presses to spaces.
        tabstop (int): Number of spaces per tab indentation.
    """
    import bashmenu

    if file_path:
        expanded_path = os.path.expanduser(file_path)
        abs_path = (
            os.path.abspath(expanded_path)
            if os.path.isabs(expanded_path)
            else os.path.abspath(os.path.join(bashmenu.BASHMENU_DIR, expanded_path))
        )
        rel_name = os.path.basename(abs_path)
    else:
        abs_path = ""
        rel_name = "Untitled"

    fd = sys.stdin.fileno()
    old_settings = None
    try:
        old_settings = termios.tcgetattr(fd)
        new_settings = termios.tcgetattr(fd)
        new_settings[0] &= ~termios.IXON
        termios.tcsetattr(fd, termios.TCSANOW, new_settings)
    except (termios.error, AttributeError):  # Catch termios configuration or parameter access failures safely
        pass

    lines = [""]
    if abs_path and os.path.exists(abs_path):
        try:
            with open(abs_path, "r") as f:
                content = f.read().splitlines()
                lines = content if content else [""]
        except OSError as e:  # Catch filesystem read access errors safely
            lines = [f"# Error opening file: {e}"]

    cursor_y = cursor_x = scroll_y = scroll_x = 0
    modified = False
    status_msg = ""

    cutbuffer = []
    cutbuffer_is_block = last_action_was_cut = mark_active = False
    mark_y = mark_x = 0

    undo_stack = []
    redo_stack = []
    MAX_HISTORY = 100
    typing_group = False

    show_line_numbers = show_help = True

    curses.curs_set(1)
    stdscr.keypad(True)

    def push_undo():
        """Push current editor state onto undo history stack."""
        nonlocal undo_stack, redo_stack
        undo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        if len(undo_stack) > MAX_HISTORY:
            undo_stack.pop(0)
        redo_stack.clear()

    def action_undo():
        """Revert editor to previous state from undo history stack."""
        nonlocal cursor_y, cursor_x, mark_active, mark_y, mark_x, lines
        nonlocal modified, status_msg, typing_group
        typing_group = False
        if not undo_stack:
            status_msg = " [ Nothing to undo ] "
            return
        redo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        prev_lines, cursor_y, cursor_x, mark_active, mark_y, mark_x = (
            undo_stack.pop()
        )
        lines = list(prev_lines)
        modified = True
        status_msg = " [ Undo ] "

    def action_redo():
        """Reapply previously undone changes from redo history stack."""
        nonlocal cursor_y, cursor_x, mark_active, mark_y, mark_x, lines
        nonlocal modified, status_msg, typing_group
        typing_group = False
        if not redo_stack:
            status_msg = " [ Nothing to redo ] "
            return
        undo_stack.append((
            list(lines),
            cursor_y,
            cursor_x,
            mark_active,
            mark_y,
            mark_x,
        ))
        next_lines, cursor_y, cursor_x, mark_active, mark_y, mark_x = (
            redo_stack.pop()
        )
        lines = list(next_lines)
        modified = True
        status_msg = " [ Redo ] "

    def restore_termios():
        """Restore initial terminal attributes prior to editor launch."""
        if old_settings:
            try:
                termios.tcsetattr(fd, termios.TCSANOW, old_settings)
            except (termios.error, AttributeError):  # Catch termios restoration failures safely
                pass

    def action_exit():
        """Exit editor, prompting for confirmation if modified."""
        nonlocal typing_group, mark_active, status_msg
        typing_group = False
        if mark_active:
            mark_active = False
            status_msg = " [ Mark Cancelled ] "
            return False
        if modified:
            confirm = bashmenu_ui.show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Do you want to save before closing?",
                theme,
            )
            if confirm is None:
                status_msg = " [ Exit Cancelled ] "
                return False
            elif confirm == "yes":
                save_file()

        restore_termios()
        curses.curs_set(0)
        return True

    def save_file():
        """Save current buffer contents to disk."""
        nonlocal modified, status_msg
        if not abs_path:
            action_save_as()
            return
        try:
            with open(abs_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            modified = False
            status_msg = " [ File Saved Successfully! ] "
        except OSError as e:  # Catch filesystem write access errors safely
            status_msg = f" [ Save Error: {e} ] "

    def action_save_as():
        """Prompt user for destination path and save buffer."""
        nonlocal abs_path, rel_name
        default_p = abs_path if abs_path else "untitled.txt"
        new_path = bashmenu_ui.show_input_box(
            stdscr, "Save As", "Enter destination path:", default_p, theme
        )
        if new_path and new_path.strip():
            expanded = os.path.expanduser(new_path.strip())
            abs_path = (
                os.path.abspath(expanded)
                if os.path.isabs(expanded)
                else os.path.abspath(os.path.join(bashmenu.BASHMENU_DIR, expanded))
            )
            rel_name = os.path.basename(abs_path)
            save_file()

    def action_open():
        """Prompt user for a file to open into the editor."""
        nonlocal lines, cursor_y, cursor_x, scroll_y, scroll_x
        nonlocal abs_path, rel_name, modified, status_msg, typing_group
        if modified:
            confirm = bashmenu_ui.show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Save before opening another file?",
                theme,
            )
            if confirm is None:
                status_msg = " [ Open Cancelled ] "
                return
            elif confirm == "yes":
                save_file()
                if modified:
                    return

        start_d = os.path.dirname(abs_path) if abs_path else bashmenu.USER_HOME
        chosen = bashmenu_ui.show_file_picker(
            stdscr, "Open File", start_dir=start_d, mode="file", theme=theme
        )
        if chosen and os.path.isfile(chosen):
            try:
                with open(chosen, "r") as f:
                    content = f.read().splitlines()
                    lines = content if content else [""]
                abs_path = os.path.abspath(chosen)
                rel_name = os.path.basename(abs_path)
                cursor_y = cursor_x = scroll_y = scroll_x = 0
                modified = False
                undo_stack.clear()
                redo_stack.clear()
                typing_group = False
                status_msg = f" [ Opened '{rel_name}' ] "
            except OSError as e:  # Catch filesystem read access errors safely
                status_msg = f" [ Open Error: {e} ] "

    def action_new():
        """Clear buffer and reset editor for a new document."""
        nonlocal lines, cursor_y, cursor_x, scroll_y, scroll_x
        nonlocal abs_path, rel_name, modified, status_msg, typing_group
        if modified:
            confirm = bashmenu_ui.show_confirm_box(
                stdscr,
                "Unsaved Changes",
                f"File '{rel_name}' has unsaved changes.\n"
                f"Save before creating a new document?",
                theme,
            )
            if confirm is None:
                status_msg = " [ New Document Cancelled ] "
                return
            elif confirm == "yes":
                save_file()
                if modified:
                    return

        lines = [""]
        abs_path = ""
        rel_name = "Untitled"
        cursor_y = cursor_x = scroll_y = scroll_x = 0
        modified = False
        undo_stack.clear()
        redo_stack.clear()
        typing_group = False
        status_msg = " [ New Document Created ] "

    def open_external_editor():
        """Suspend curses interface and spawn external editor ($EDITOR)."""
        if not abs_path:
            action_save_as()
            if not abs_path:
                return
        restore_termios()
        curses.endwin()
        editor_bin = os.environ.get("EDITOR", "nano")
        print(f"\n--- Launching {editor_bin} for '{rel_name}' ---\n")
        try:
            cmd = shlex.split(editor_bin) + [abs_path]
            subprocess.run(cmd, check=False)
        except (OSError, subprocess.SubprocessError) as e:  # Catch binary invocation or process execution failures safely
            print(f"Error starting editor '{editor_bin}': {e}")
            input("Press [ENTER] to continue...")
        stdscr.clear()
        stdscr.refresh()
        try:
                termios.tcsetattr(fd, termios.TCSANOW, new_settings)
        except (termios.error, AttributeError):  # Catch termios configuration or attribute access failures safely
            pass

    def get_selection_range():
        """Calculate sorted start and end coordinates of selection."""
        if not mark_active:
            return None
        return (
            ((cursor_y, cursor_x), (mark_y, mark_x))
            if (cursor_y, cursor_x) < (mark_y, mark_x)
            else ((mark_y, mark_x), (cursor_y, cursor_x))
        )

    def extract_selected_text():
        """Extract lines or substrings bounded by active selection mark."""
        rng = get_selection_range()
        if not rng:
            return []
        (sy, sx), (ey, ex) = rng
        if sy == ey:
            return [lines[sy][sx:ex]]
        res = [lines[sy][sx:]]
        for y in range(sy + 1, ey):
            res.append(lines[y])
        res.append(lines[ey][:ex])
        return res

    def delete_selected_text():
        """Remove text currently highlighted by selection bounds."""
        nonlocal cursor_y, cursor_x, mark_active, modified, typing_group
        rng = get_selection_range()
        if not rng:
            return
        typing_group = False
        push_undo()
        (sy, sx), (ey, ex) = rng
        if sy == ey:
            lines[sy] = lines[sy][:sx] + lines[sy][ex:]
        else:
            lines[sy] = lines[sy][:sx] + lines[ey][ex:]
            del lines[sy + 1 : ey + 1]
        cursor_y, cursor_x = sy, sx
        mark_active = False
        modified = True
        if not lines:
            lines.append("")

    def action_cut():
        """Cut active line or selected text block into cutbuffer."""
        nonlocal cutbuffer, cutbuffer_is_block, last_action_was_cut, status_msg
        nonlocal modified, cursor_y, cursor_x, mark_active, typing_group
        typing_group = False
        if mark_active:
            cutbuffer = extract_selected_text()
            cutbuffer_is_block = True
            delete_selected_text()
            last_action_was_cut = False
            status_msg = f" [ Cut {len(cutbuffer)} line selection ] "
        else:
            push_undo()
            if last_action_was_cut and not cutbuffer_is_block:
                cutbuffer.append(lines[cursor_y])
            else:
                cutbuffer = [lines[cursor_y]]
                cutbuffer_is_block = False

            if len(lines) > 1:
                lines.pop(cursor_y)
                if cursor_y >= len(lines):
                    cursor_y = len(lines) - 1
                cursor_x = min(cursor_x, len(lines[cursor_y]))
            else:
                lines[0] = ""
                cursor_x = 0
            modified = True
            last_action_was_cut = True
            plural = "s" if len(cutbuffer) > 1 else ""
            status_msg = f" [ Cut {len(cutbuffer)} line{plural} ] "

    def action_copy():
        """Copy active line or selection block into cutbuffer."""
        nonlocal cutbuffer, cutbuffer_is_block, last_action_was_cut
        nonlocal status_msg, mark_active, typing_group
        typing_group = False
        if mark_active:
            cutbuffer = extract_selected_text()
            cutbuffer_is_block = True
            mark_active = False
            status_msg = f" [ Copied {len(cutbuffer)} line selection ] "
        else:
            cutbuffer = [lines[cursor_y]]
            cutbuffer_is_block = False
            status_msg = f" [ Copied Line {cursor_y + 1} ] "
        last_action_was_cut = False

    def action_paste():
        """Paste current cutbuffer contents at cursor location."""
        nonlocal last_action_was_cut, status_msg, modified, cursor_y, cursor_x
        nonlocal mark_active, typing_group
        typing_group = False
        last_action_was_cut = False
        if not cutbuffer:
            status_msg = " [ Cutbuffer is empty ] "
            return

        if mark_active:
            delete_selected_text()
        else:
            push_undo()

        if cutbuffer_is_block:
            if len(cutbuffer) == 1:
                # Single-line block paste: insert text directly at cursor position
                lines[cursor_y] = (
                    lines[cursor_y][:cursor_x]
                    + cutbuffer[0]
                    + lines[cursor_y][cursor_x:]
                )
                cursor_x += len(cutbuffer[0])
            else:
                # Multi-line block paste: split current line, insert middle lines, and append the tail
                tail = lines[cursor_y][cursor_x:]
                lines[cursor_y] = lines[cursor_y][:cursor_x] + cutbuffer[0]
                for idx, mid in enumerate(cutbuffer[1:-1]):
                    lines.insert(cursor_y + 1 + idx, mid)
                last_idx = cursor_y + len(cutbuffer) - 1
                lines.insert(last_idx, cutbuffer[-1] + tail)
                cursor_y = last_idx
                cursor_x = len(cutbuffer[-1])
        else:
            # Full-line paste: insert entire lines directly below or at cursor line
            for idx, l in enumerate(cutbuffer):
                lines.insert(cursor_y + idx, l)
            cursor_y += len(cutbuffer)
            cursor_x = 0
        modified = True
        plural = "s" if len(cutbuffer) > 1 else ""
        status_msg = f" [ Pasted {len(cutbuffer)} line{plural} ] "

    while True:
        height, width = stdscr.getmaxyx()
        use_help = show_help and height >= 14
        view_h = max(3, height - 1 - 1 - (2 if use_help else 0) - 1)
        gutter_w = 7 if show_line_numbers else 0
        view_w = max(10, width - 2 - gutter_w)

        if cursor_y < scroll_y:
            scroll_y = cursor_y
        elif cursor_y >= scroll_y + view_h:
            scroll_y = cursor_y - view_h + 1

        if cursor_x < scroll_x:
            scroll_x = cursor_x
        elif cursor_x >= scroll_x + view_w:
            scroll_x = cursor_x - view_w + 1

        stdscr.erase()
        stdscr.attron(theme["border"])
        stdscr.border(0)
        stdscr.attroff(theme["border"])

        mod_tag = " *" if modified else ""
        ws_tag = " [WS]" if show_whitespace else ""
        header = f" Editing: {rel_name}{mod_tag}{ws_tag} "
        bashmenu_ui.safe_addstr(
            stdscr,
            0,
            max(2, (width - len(header)) // 2),
            header,
            theme["title"] | curses.A_BOLD,
        )

        rng = get_selection_range()

        for i in range(view_h):
            line_idx = scroll_y + i
            if line_idx >= len(lines):
                break

            line_text = lines[line_idx]
            row_screen_y = i + 1

            if show_line_numbers:
                gutter_attr = (
                    (theme["accent"] | curses.A_BOLD)
                    if line_idx == cursor_y
                    else theme["gutter"]
                )
                bashmenu_ui.safe_addstr(
                    stdscr,
                    row_screen_y,
                    1,
                    f"{line_idx + 1:4d} │ ",
                    gutter_attr,
                )

            text_start_x = 1 + gutter_w
            visible_text = line_text[scroll_x : scroll_x + view_w]
            tab_glyph = "→" + (" " * (max(1, tabstop) - 1))
            disp_text = (
                visible_text.replace(" ", "·").replace("\t", tab_glyph)
                if show_whitespace
                else visible_text.replace("\t", " " * max(1, tabstop))
            )

            if not rng:
                bashmenu_ui.safe_addstr(
                    stdscr, row_screen_y, text_start_x, disp_text, theme["text"]
                )
            else:
                (sy, sx), (ey, ex) = rng
                if line_idx < sy or line_idx > ey:
                    bashmenu_ui.safe_addstr(
                        stdscr,
                        row_screen_y,
                        text_start_x,
                        disp_text,
                        theme["text"],
                    )
                else:
                    sel_start = sx if line_idx == sy else 0
                    sel_end = ex if line_idx == ey else len(line_text) + 1
                    if sy == ey:
                        sel_start, sel_end = sx, ex

                    line_len = len(disp_text)
                    for col_idx in range(line_len):
                        actual_col = scroll_x + col_idx
                        char_attr = (
                            theme["selection"]
                            if (sel_start <= actual_col < sel_end)
                            else theme["text"]
                        )
                        bashmenu_ui.safe_addstr(
                            stdscr,
                            row_screen_y,
                            text_start_x + col_idx,
                            disp_text[col_idx],
                            char_attr,
                        )

        status_y = 1 + view_h
        bashmenu_ui.safe_addstr(
            stdscr, status_y, 1, " " * (width - 2), theme["status_bar"]
        )
        disp_msg = status_msg if status_msg else f" Editing: {rel_name}"
        bashmenu_ui.safe_addstr(
            stdscr,
            status_y,
            2,
            disp_msg[: max(10, width - 28)],
            theme["status_bar"] | curses.A_BOLD,
        )

        mark_badge = "[MARK] " if mark_active else ""
        pos_str = (
            f" {mark_badge}Ln {cursor_y + 1}/{len(lines)}, Col {cursor_x + 1} "
        )
        bashmenu_ui.safe_addstr(
            stdscr,
            status_y,
            max(2, width - len(pos_str) - 2),
            pos_str,
            theme["shortcut_key"] | curses.A_BOLD,
        )

        if use_help:
            shortcuts_r1 = [
                ("^G", "Get Help"),
                ("^O", "WriteOut"),
                ("^R", "Read File"),
                ("^N", "New Doc"),
                ("^K", "Cut"),
                ("^U", "Paste"),
                ("^C", "Location"),
                ("M-6", "Copy"),
            ]
            shortcuts_r2 = [
                ("^X", "Exit"),
                ("^S", "SaveAs"),
                ("M-U", "Undo"),
                ("M-E", "Redo"),
                ("M-A", "Mark"),
                ("M-N", "LineNo"),
                ("M-P", "ShowWS"),
                ("F2", "ExtEdit"),
            ]

            # Clear both lines first with theme's standard background
            bashmenu_ui.safe_addstr(stdscr, status_y + 1, 1, " " * (width - 2), theme["text"])
            bashmenu_ui.safe_addstr(stdscr, status_y + 2, 1, " " * (width - 2), theme["text"])

            num_cols_total = max(len(shortcuts_r1), len(shortcuts_r2))
            col_widths = []
            for col in range(num_cols_total):
                w1 = len(shortcuts_r1[col][0]) + 1 + len(shortcuts_r1[col][1]) if col < len(shortcuts_r1) else 0
                w2 = len(shortcuts_r2[col][0]) + 1 + len(shortcuts_r2[col][1]) if col < len(shortcuts_r2) else 0
                col_widths.append(max(w1, w2))

            usable_w = max(1, width - 4)
            C = num_cols_total
            while C > 1:
                required_w = sum(col_widths[:C])
                if required_w + (C - 1) <= usable_w:
                    break
                C -= 1

            col_x = []
            if C > 1:
                required_w = sum(col_widths[:C])
                gap = (usable_w - required_w) / (C - 1)
                current_x = 2.0
                for col in range(C):
                    col_x.append(int(current_x))
                    current_x += col_widths[col] + gap
            else:
                col_x = [2]

            for col in range(C):
                x = col_x[col]
                if col < len(shortcuts_r1):
                    badge, label = shortcuts_r1[col]
                    if x + len(badge) + 1 + len(label) <= width - 2:
                        bashmenu_ui.safe_addstr(
                            stdscr,
                            status_y + 1,
                            x,
                            badge,
                            theme["shortcut_key"] | curses.A_BOLD,
                        )
                        bashmenu_ui.safe_addstr(
                            stdscr,
                            status_y + 1,
                            x + len(badge) + 1,
                            label,
                            theme["shortcut_label"],
                        )
                if col < len(shortcuts_r2):
                    badge, label = shortcuts_r2[col]
                    if x + len(badge) + 1 + len(label) <= width - 2:
                        bashmenu_ui.safe_addstr(
                            stdscr,
                            status_y + 2,
                            x,
                            badge,
                            theme["shortcut_key"] | curses.A_BOLD,
                        )
                        bashmenu_ui.safe_addstr(
                            stdscr,
                            status_y + 2,
                            x + len(badge) + 1,
                            label,
                            theme["shortcut_label"],
                        )

        screen_y = (cursor_y - scroll_y) + 1
        screen_x = (cursor_x - scroll_x) + 1 + gutter_w
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.move(
            min(view_h, max(1, screen_y)),
            min(width - 2, max(1 + gutter_w, screen_x)),
        )
        stdscr.refresh()

        key = stdscr.getch()
        status_msg = ""

        if key == 24:  # ^X: Exit
            if action_exit():
                break
        elif key in [15, curses.KEY_F3]:  # ^O, F3: WriteOut / Save
            save_file()
            last_action_was_cut = False
            typing_group = False
        elif key in [18, curses.KEY_F5, curses.KEY_F7]:  # ^R, F5, F7: Read File / Open
            action_open()
            last_action_was_cut = False
            typing_group = False
        elif key in [19, curses.KEY_F6]:  # ^S, F6: Save As
            action_save_as()
            last_action_was_cut = False
            typing_group = False
        elif key in [14, curses.KEY_F4]:  # ^N, F4: New Document
            action_new()
            last_action_was_cut = False
            typing_group = False
        elif key in [7, curses.KEY_F1]:  # ^G, F1: Get Help / Toggle Help Bar
            show_help = not show_help
            status_msg = f" [ Help bar {'enabled' if show_help else 'disabled'} ] "
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_F2]:  # F2: External $EDITOR
            save_file()
            open_external_editor()
            if abs_path and os.path.exists(abs_path):
                with open(abs_path, "r") as f:
                    lines = f.read().splitlines() or [""]
            cursor_y = min(cursor_y, len(lines) - 1)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
            undo_stack.clear()
            redo_stack.clear()
        elif key == 26:
            action_undo()
            last_action_was_cut = False
        elif key == 25:
            action_redo()
            last_action_was_cut = False
        elif key in [11, curses.KEY_F8]:  # ^K, F8: Cut
            action_cut()
        elif key in [21, 22, curses.KEY_F9]:  # ^U, ^V, F9: Paste / Uncut
            action_paste()
        elif key == 30:  # ^^ / Ctrl+^: Toggle Mark
            typing_group = False
            if mark_active:
                mark_active = False
                status_msg = " [ Mark Unset ] "
            else:
                mark_active = True
                mark_y, mark_x = cursor_y, cursor_x
                status_msg = " [ Mark Set ] "
            last_action_was_cut = False
        elif key == 3:  # ^C: Position info or Copy if mark active
            if mark_active:
                action_copy()
            else:
                pct = int((cursor_y + 1) / max(1, len(lines)) * 100)
                status_msg = f" [ Line {cursor_y + 1}/{len(lines)} ({pct}%), Col {cursor_x + 1} ] "
            last_action_was_cut = False
        elif key in [9, ord('\t')]:
            typing_group = False
            if mark_active:
                delete_selected_text()
            else:
                push_undo()

            insert_str = (" " * max(1, tabstop)) if tab_to_spaces else "\t"
            lines[cursor_y] = (
                lines[cursor_y][:cursor_x]
                + insert_str
                + lines[cursor_y][cursor_x:]
            )
            cursor_x += len(insert_str)
            modified = True
            last_action_was_cut = False
        elif key == 27:
            stdscr.timeout(50)
            next_k = stdscr.getch()
            stdscr.timeout(-1)

            if next_k != -1:
                if next_k in [ord('n'), ord('N')]:
                    show_line_numbers = not show_line_numbers
                    status_msg = f" [ Line numbers {'enabled' if show_line_numbers else 'disabled'} ] "
                elif next_k in [ord('p'), ord('P'), ord('w'), ord('W')]:
                    show_whitespace = not show_whitespace
                    status_msg = f" [ Whitespace display {'enabled' if show_whitespace else 'disabled'} ] "
                elif next_k in [ord('u'), ord('U')]:
                    action_undo()
                elif next_k in [ord('e'), ord('E')]:
                    action_redo()
                elif next_k == ord('6'):
                    action_copy()
                elif next_k in [ord('a'), ord('A')]:
                    typing_group = False
                    mark_active = not mark_active
                    mark_y, mark_x = cursor_y, cursor_x
                    status_msg = f" [ Mark {'Set' if mark_active else 'Unset'} ] "
                elif next_k in [ord('g'), ord('G'), ord('h'), ord('H')]:
                    show_help = not show_help
                    status_msg = f" [ Help bar {'enabled' if show_help else 'disabled'} ] "
                last_action_was_cut = False
            else:
                if action_exit():
                    break
                last_action_was_cut = False
        elif key == curses.KEY_UP and cursor_y > 0:
            cursor_y -= 1
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_DOWN and cursor_y < len(lines) - 1:
            cursor_y += 1
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_LEFT:
            if cursor_x > 0:
                cursor_x -= 1
            elif cursor_y > 0:
                cursor_y -= 1
                cursor_x = len(lines[cursor_y])
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_RIGHT:
            if cursor_x < len(lines[cursor_y]):
                cursor_x += 1
            elif cursor_y < len(lines) - 1:
                cursor_y += 1
                cursor_x = 0
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_PPAGE:
            cursor_y = max(0, cursor_y - view_h)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key == curses.KEY_NPAGE:
            cursor_y = min(len(lines) - 1, cursor_y + view_h)
            cursor_x = min(cursor_x, len(lines[cursor_y]))
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_HOME, 1]:
            cursor_x = 0
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_END, 5]:
            cursor_x = len(lines[cursor_y])
            last_action_was_cut = False
            typing_group = False
        elif key in [curses.KEY_BACKSPACE, 8, 127]:
            if mark_active:
                delete_selected_text()
            elif cursor_x > 0:
                if not typing_group:
                    push_undo()
                    typing_group = True
                lines[cursor_y] = (
                    lines[cursor_y][: cursor_x - 1] + lines[cursor_y][cursor_x:]
                )
                cursor_x -= 1
                modified = True
            elif cursor_y > 0:
                typing_group = False
                push_undo()
                prev_len = len(lines[cursor_y - 1])
                lines[cursor_y - 1] += lines[cursor_y]
                lines.pop(cursor_y)
                cursor_y -= 1
                cursor_x = prev_len
                modified = True
            last_action_was_cut = False
        elif key == curses.KEY_DC:
            if mark_active:
                delete_selected_text()
            elif cursor_x < len(lines[cursor_y]):
                if not typing_group:
                    push_undo()
                    typing_group = True
                lines[cursor_y] = (
                    lines[cursor_y][:cursor_x] + lines[cursor_y][cursor_x + 1 :]
                )
                modified = True
            elif cursor_y < len(lines) - 1:
                typing_group = False
                push_undo()
                lines[cursor_y] += lines[cursor_y + 1]
                lines.pop(cursor_y + 1)
                modified = True
            last_action_was_cut = False
        elif key in [curses.KEY_ENTER, 10, 13]:
            typing_group = False
            if mark_active:
                delete_selected_text()
            else:
                push_undo()
            remainder = lines[cursor_y][cursor_x:]
            lines[cursor_y] = lines[cursor_y][:cursor_x]
            lines.insert(cursor_y + 1, remainder)
            cursor_y += 1
            cursor_x = 0
            modified = True
            last_action_was_cut = False
        elif 32 <= key <= 126:
            if mark_active:
                typing_group = False
                delete_selected_text()
            elif not typing_group or key == 32:
                push_undo()
                typing_group = key != 32
            lines[cursor_y] = (
                lines[cursor_y][:cursor_x] + chr(key) + lines[cursor_y][cursor_x:]
            )
            cursor_x += 1
            modified = True
            last_action_was_cut = False
