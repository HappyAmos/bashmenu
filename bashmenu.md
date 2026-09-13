---
title: Bashmenu Cheatsheet
tags:
  - bashmenu
  - tui
  - curses
  - documentation
  - cheatsheet
---

# Bashmenu Cheatsheet

Lightweight Curses TUI engine for system tasks, settings, and themes.

## Component Overview

- `bashmenu.py`: Core TUI application engine and built-in text editor.
- `menuedit.py`: Interactive TUI visual editor for `bashmenu.mnu`.
- `bashmenu.yml`: Settings store (auto-generated with defaults if missing).
- `bashmenu.mnu`: Menu structure layout and action definitions.
- `bashmenu.themes`: Color palettes for 256, 16, and 8 color modes.
- `ymlcheck.py`: Validation utility for YAML syntax and theme schemas.

---

## Interactive Menu Engine (`bashmenu.py`)

### Main Menu Hotkeys
- `UP` / `DOWN`: Navigate selection row.
- `0-9` / `a-z` / `A-Z`: Jump to option directly by shortcut key.
- `F4`: Launch visual menu editor (`menuedit.py`).
- `F5`: Toggle shortcut key badges display.
- `ENTER`: Execute selected item action.
- `ESC`: Return to parent menu or exit application.

### Built-in Editor Keybindings
- `Ctrl+X`: Exit editor (prompts to save if modified).
- `Ctrl+O` / `F3`: WriteOut (save active file).
- `Ctrl+R` / `F5`: Read File / Open file via file picker modal.
- `Ctrl+S` / `F6`: Save As (prompt destination path).
- `Ctrl+N` / `F4`: Create new empty document in editor.
- `Ctrl+G` / `F1`: Toggle bottom Nano-style help bar.
- `Ctrl+K` / `F8`: Cut line or active selection block.
- `Ctrl+U` / `F9`: Paste (uncut) cutbuffer text.
- `Ctrl+C`: Show cursor location (or copy if mark active).
- `Alt+6`: Copy line or selection block.
- `Alt+U`: Undo edit.
- `Alt+E`: Redo edit.
- `Ctrl+^` / `Alt+A`: Toggle selection mark.
- `Alt+N`: Toggle line numbers.
- `Alt+P` / `Alt+W`: Toggle whitespace visibility (`·` for spaces, `→` for tabs).
- `F2`: Launch external `$EDITOR`.

---

## Interactive Menu Editor (`menuedit.py`)

Visual tree-editor tool for managing `bashmenu.mnu` items and directives.

### Keybindings
- `F4`: Launch visual menu editor instantly from `bashmenu.py`.
- `a` / `Ins`: Insert new menu option node.
- `e` / `ENTER`: Edit node properties or main menu header title.
- `E`: Open raw YAML snippet in editor for selected node.
- `d` / `Del`: Delete selected menu node (with confirmation modal).
- `m`: Move selected node DOWN in the menu list.
- `M`: Move selected node UP in the menu list.
- `>` / `.` / `Tab`: Indent item INTO preceding Submenu folder.
- `<` / `,` / `Shift+Tab`: Outdent item OUT to Parent menu list.
- `t`: Test-run selected menu item action directly.
- `s`: Save changes to `bashmenu.mnu` (creates `.bak` backup).
- `ESC`: Exit editor (prompts if unsaved changes exist).

---

## Schema: bashmenu.mnu Directives

### Directives & Attributes

- `type`: `command` | `script` | `config` | `toggle` | `editor` | `confirm` |
  `message` | `python` | `inject_block` | `theme_selector` | `back` | `exit` |
  `submenu`
- `label`: Display string shown in menu row.
- `icon`: Separate icon string utilizing `nf:FALLBACK:GLYPH` syntax to display icons on supporting systems.
- `action`: Shell command, script path, or editor target file path.
- `template`: Template source file path for dynamic block injection.
- `target`: Target destination file path where the block should be injected.
- `block_id`: Unique identifier tag for the code block boundary markers.
- `quiet`: `true` | `false` (suppresses headers/prompts for interactive items).
- `refresh`: `true` | `false` (reloads menu layout structure on return).
- `stream`: `true` | `false` (live line-by-line output streaming window).
- `interactive`: `true` | `false` (suspend TUI for terminal console tools).
- `external`: `true` | `false` (launches scripts in a new process; set to `false` for dynamic in-process Python loading).
- `user_mode`: `"root"` | `"user"` (requires elevated root privileges).
- `key`: Target key path in `bashmenu.yml` using dot notation.
- `picker`: `"file"` | `"dir"` | `"none"` (launches visual picker modal).
- `start_dir`: Starting folder for picker modal (e.g. `"~"`).
- `masked`: `true` | `false` (masks sensitive input with asterisks).
- `show_whitespace`: `true` | `false` (displays spaces as `·` and tabs as `→`).
- `tab_to_spaces`: `true` | `false` (converts TAB key input to spaces).
- `tabstop`: Integer space width for TAB key indentation (default: 8).
- `on_yes`: Sub-item dictionary executed if Yes is selected in confirm box.
- `on_no`: Sub-item dictionary executed if No is selected in confirm box.
- `message`: Text prompt query string used in confirm, message, or toggle boxes.

---

## Settings Toggle Box (`type: toggle`)

The `toggle` and `config_toggle` item types display an interactive themed modal with **True**, **False**, and **Cancel** buttons.
* Selecting **True** sets the designated `key` (in dot-notation) in `bashmenu.yml` to `True`.
* Selecting **False** sets the key to `False`.
* Selecting **Cancel** (or pressing `ESC`) aborts the action without updating the configuration.

---

## Dynamic Command Directives

Any execution type (`command`, `script`, or `param`) can dynamically trigger
user input or visual file/directory pickers by placing these placeholder
directives within the `action` string:

- `{param}`: Prompts the user using a single-line modal text input box.
  The placeholder `{param}` is replaced with the user's typed value.
  * *Attributes:* Uses `title` (modal header, defaults to blank),
    `prompt` (message, defaults to `"Enter a parameter:"`), and `masked`
    (`true`|`false` to mask text with asterisks).
- `{file_picker}`: Displays a visual file selection dialog. The placeholder
  `{file_picker}` is replaced with the absolute path of the chosen file.
  * *Attributes:* Uses `title` (modal header, defaults to `"Select File"`)
    and `start_dir` (starting path, defaults to `"~"`).
- `{dir_picker}`: Displays a visual directory selection dialog. The
  placeholder `{dir_picker}` is replaced with the absolute path of the
  chosen directory.
  * *Attributes:* Uses `title` (modal header, defaults to
    `"Select Directory"`) and `start_dir` (starting path, defaults to `"~"`).

If the user cancels any of these modals/pickers (by pressing `ESC`),
execution of the command/script is immediately and safely aborted.

#### Example:
```yaml
- label: Search Nerd Font & Emoji
  type: script
  action: '{scripts_dir}/glyphs.sh {param}'
  title: Search Glyph
  prompt: 'Enter search keyword:'

- label: Check Logs
  type: command
  action: 'cat "{file_picker}"'
  start_dir: '/var/log'
```

---
```yaml
- label: Toggle Nerd Fonts [{settings.use_nerd_fonts}]
  type: toggle
  key: settings.use_nerd_fonts
  title: Toggle Nerd Fonts
  message: 'Enable colorful menu emojis and Nerd Fonts?'
```

---

## Dynamic Variables

- `{user}` / `{username}`: Current system username.
- `{home}`: User home directory path.
- `{bashrc}` / `{vimrc}` / `{bash_aliases}`: Path to config files.
- `{bashmenu_dir}`: Application script directory path.
- `{settings.path}`: Dot-notation config lookup from `bashmenu.yml`.
- `nf:FALLBACK:GLYPH` or `{nf:FALLBACK:GLYPH}`: Dynamic font/emoji resolution based on `settings.use_nerd_fonts`:
  * **Nerd Fonts Enabled**: Resolves to the `GLYPH` value (which can be a raw unicode character or a hex code prefixed with `#`, e.g. `#f0a4` or `#f07c0`).
  * **Nerd Fonts Disabled**: Resolves to the `FALLBACK` value.
  
  *Theme Indicator Example*: `"nf:>:\uf0a4"` or `"nf:>:#f0a4"` (renders `\uf0a4` if enabled, otherwise `>`).
  *Menu Icon Example*: `"{nf::\U0001F3AE}"` or `"{nf::#f11b}"` (renders the glyph if enabled, otherwise `""` collapsing the icon column).

---

## Block Template Example

Template file (e.g., `templates/aliases.tmpl`) supporting interpolation:
```bash
# Sourced for {user}
alias system-ip="echo 'Your current IP is: {settings.dns.ip}'"
```
