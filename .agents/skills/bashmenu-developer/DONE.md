# Completed Tasks Log (DONE.md)

This log documents completed items from `TODO.md`, detailing root causes, implementations, and automated test verifications.

---

### 1. Theme Editor Border Misalignment in 'Menu Editor' Tab
- **Item:** `- [x] BUG: border misalignment in theme editor 'menu editor' tab`
- **Root Cause:** In `themeedit.py::_render_menu_editor`, `avail_top` used an incorrect overhead offset (-7 instead of -6), and body pane content width `right_w` had inadequate padding, resulting in line width mismatch between top border, content lines, and drop shadow.
- **Fix:** In `themeedit.py`, adjusted `avail_top` and `rem_top` with `- 6` overhead; set body pane content width `right_w = max(8, w - split_x - 4)`. Formatted every preview row to exact width `w` with trailing drop shadow (`░░`).
- **Tests:** Added `test_theme_preview_tabs_border_alignment` in `.tests/test_themeedit.py`.

---

### 2. Border Misalignment in 'Modals & Popups' Tab
- **Item:** `- [x] BUG: Misalignment of borders in Modals & Popups tab of theme editor`
- **Root Cause:** In `themeedit.py::_render_modals`, `avail_top` had an off-by-one overhead (-7 instead of -6), causing `rem_top` calculation to differ from modal dialog width.
- **Fix:** Corrected top border and title padding calculations in `_render_modals` to strictly match `modal_w` (+2 drop shadow).
- **Tests:** Verified via `test_theme_preview_tabs_border_alignment` in `.tests/test_themeedit.py`.

---

### 3. Plugin Wallpaper Transparency Compositing
- **Item:** `- [x] BUG: Background of plugins still does not appear 'transparent', meaning it does not show the wallpaper behind the text of the plugins`
- **Root Cause:** Textual widgets render space padding characters `' '` across empty cells, which overwrote the canvas grid half-block characters (`▀`) rendered by the wallpaper engine.
- **Fix:** In `bashmenu.py::PluginBuffer.render()`, resolved `_screen` and `menu_view._canvas.grid`. Sliced the wallpaper canvas grid at `(x_offset, y_offset + idx)` for each line and composited using `bashmenu_ui.composite_single_row(line_rt, row_cache)` so space padding renders as half-blocks showing the wallpaper background.
- **Tests:** Added `test_plugin_buffer_wallpaper_transparency` in `.tests/test_wallpaper.py`.

---

### 4. Clock Time Display 2 Hours Ahead
- **Item:** `- [x] CRITICAL BUG: the time is displaying two hours ahead of the actual system time.`
- **Root Cause:** Inverted timezone offset calculations or incorrect time formatting helper usage.
- **Fix:** Synchronized clock interpolation with local timezone using `datetime.now().astimezone()`.
- **Tests:** Verified across status bar and placeholder clock tests in `.tests/test_improvements.py`.

---

### 5. Placeholders & Macros Help Modal Documentation Parity
- **Item:** `- [x] BUG: {toast:SECONDS:"MESSAGE"} popup toast message was not added to the Placeholders and Macros help popup modal.`
- **Root Cause:** Missing entries for `{toast:SECONDS:"MESSAGE"}` and `{screen_width}` in `PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT` in `bashmenu_ui.py`.
- **Fix:** Registered `{toast:SECONDS:"MESSAGE"}` and `{screen_width}` in `PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT`. Added `{battery_status}` alias. Added mandatory rule to `SKILL.md` Section 10 requiring updating `PLACEHOLDER_SECTIONS` whenever new placeholders are introduced.
- **Tests:** Updated `test_placeholder_documentation_parity` in `.tests/test_improvements.py`.

---

### 6. Built-in Text Editor Swap File Directory Invariant
- **Item:** `- [x] BUG: Built-in text editors swap files should be created and deleted in the exact directory where the file being edited is located.`
- **Root Cause:** `bashedit.py::get_swap_path` fell back to a shared cache directory when the target file's directory was writable, violating the local swap file invariant.
- **Fix:** Updated `get_swap_path` to strictly place swap files (`.{basename}.swp`) in `os.path.dirname(file_path)` without cache fallback. Enhanced `remove_swap_file` to also clean up temporary atomic backup files (`{basename}.*.tmp`).
- **Tests:** Added unit tests in `.tests/test_improvements.py`.

---

### 7. Toast Nested Placeholders Expansion
- **Item:** `- [x] BUG: Toast: Placeholders included in {toast:"{date_time_24_short}"} do not expand.`
- **Root Cause:** `interpolate_placeholders.replace_toast` called `trigger_toast` directly on literal content without recursing to evaluate nested macro tokens.
- **Fix:** Called `interpolate_placeholders(msg_clean, config, depth=depth+1, trigger_toasts=False)` to expand nested placeholders inside the toast message string before triggering the toast notification.
- **Tests:** Added unit test in `.tests/test_improvements.py`.

---

### 8. Menu Editor Property Inspector Preview Width Scaling
- **Item:** `- [x] BUG: UI: Bashmenu editor property inspector panel is not utilizing as much space as it can for the preview pane`
- **Root Cause:** `MenuEditScreen.update_inspector` passed a hardcoded `width=38` to `render_menu_item_preview()`, leaving unused blank space on wider terminal windows.
- **Fix:** In `menuedit.py`, dynamically compute preview width based on inspector panel width (`preview_w = max(38, panel.size.width - 6)` or `max(38, (self.size.width // 2) - 6)`), and re-render on terminal resize (`on_resize`).
- **Tests:** Added `test_menuedit_inspector_preview_width_scaling` in `.tests/test_improvements.py`.

---

### 9. DONE.md Logging Directive
- **Item:** `- [x] Add a directive to SKILL.md to append .agents/skills/bashmenu-developer/DONE.md with completed TODO.md items, and include a description and summary of what you did.`
- **Root Cause:** Absence of a standardized log for recording completed tasks, their root causes, and resolutions.
- **Fix:** Added `Done Log Directive (DONE.md)` to `SKILL.md` Section 11 and initialized `.agents/skills/bashmenu-developer/DONE.md` with all completed items.

---

### 10. Notebook Editor List & Checkbox Auto-Formatting with Faint Ghost Text
- **Item:** `- [x] FEATURE: Notebook editor: If the user has created a checkbox, or is creating a list, or similar related formatting item, when they hit enter, create a new line below the line they pressed enter on, and include the basic formatting for that item...`
- **Design & Architecture:** Implemented `NotebookTextArea(TextArea)` in `bashmenu_ui.py`. Intercepted `<Enter>` to continue task-list checkboxes (`- [ ]`, `* [ ]`, `+ [ ]`, `1. [ ]`), ordered numbered lists (`1. ` -> `2. `, `1) ` -> `2) `), unordered bullet lists (`- `, `* `, `+ `), and blockquotes (`> `), preserving leading indentation. Implemented smart de-escalation: pressing Enter on an empty marker clears the marker from that line. Integrated Textual reactive `suggestion` for faint ghost text completion on partial markers (`- [` -> ` ] `) accepted via <kbd>Tab</kbd>.
- **Tests:** Added `test_notebook_text_area_auto_format_checkboxes`, `test_notebook_text_area_ordered_and_unordered_lists`, and `test_notebook_text_area_ghost_text_and_tab_completion` in `.tests/test_notebook.py`.

---

### 11. Cross-Interface Clipboard Interoperability for Notes and Built-in Editor
- **Item:** `- [x] FEATURE: Make sure the copy and paste buffer for notes can pass information back to any interface such as the built-in text editor`
- **Design & Architecture:** Implemented unified clipboard subsystem in `bashmenu_ui.py` (`get_system_clipboard`, `set_system_clipboard`, `get_shared_cutbuffer_path`) supporting system CLI tools (`wl-copy`/`wl-paste`, `xclip`, `xsel`, `pbcopy`/`pbpaste`, `termux`) with persistent fallback to `~/.cache/bashmenu/cutbuffer.txt`. Integrated with `bashedit.py` so cutting, copying, and pasting seamlessly transfers between the built-in text editor, `NotebookTextArea`, and `NoteViewerModalScreen` (`[C]` / `Ctrl+C` raw markdown copy action).
- **Tests:** Added `test_notebook_cross_interface_clipboard` in `.tests/test_notebook.py`.
