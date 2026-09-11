# HA Bash Menu (v0.0.1)

A lightweight, data-driven Curses TUI (Text User Interface) menu engine
for Linux systems, written in Python. It provides a modular framework
configured entirely through YAML files.

---

## Component Overview

| File              | Description                                        |
| ----------------- | -------------------------------------------------- |
| `bashmenu.sh`     | Launcher script with auto-setup and self-healing.  |
| `bashmenu.py`     | Core TUI Python engine and built-in text editor.   |
| `menuedit.py`     | Interactive TUI visual editor for `bashmenu.mnu`.  |
| `requirements.txt`| Formally declared PyYAML package dependencies.      |
| `bashmenu.yml`    | User settings store (auto-generated if missing).   |
| `bashmenu.mnu`    | Menu layout structure and item directives.         |
| `bashmenu.themes` | Color palettes for 256, 16, and 8 color modes.     |
| `ymlcheck.py`     | Validator for YAML theme and schema definitions.   |

---

## Core Features

* **Visual Tree Editor (`menuedit.py`)**: Keyboard-driven visual editor for
  managing `bashmenu.mnu`. Reorder items (`m`/`M`), indent (`>`), outdent (`<`),
  add (`a`), edit (`e`/`ENTER`), edit raw YAML (`E`), delete (`d`), and test
  items (`t`). Press `F4` in `bashmenu.py` to launch.
* **Built-in Nano-style Editor**: Multi-level undo/redo (`Alt+U`/`Alt+E`),
  Save As (`Ctrl+S`/`F6`), Open (`Ctrl+R`/`F5`), New document (`Ctrl+N`/`F4`),
  cut/copy/paste (`Ctrl+K`/`Alt+6`/`Ctrl+U`), text selection mark (`Ctrl+^`),
  line numbers toggle (`Alt+N`), whitespace display (`Alt+P`), tabstop width
  settings, and `$EDITOR` fallback (`F2`).
* **Variable Interpolation**: Dynamic string interpolation supporting `{user}`,
  `{home}`, `{bashrc}`, `{vimrc}`, `{bashmenu_dir}`, and configuration settings
  like `{settings.ping_target}` or `{git_pat}`.
* **Nerd Fonts & Fallback Symbols**: Seamless support for terminal icons
  via the `nf:FALLBACK:GLYPH` syntax (and `{nf:FALLBACK:GLYPH}` bracketed syntax).
  If `settings.use_nerd_fonts` is `true` in `bashmenu.yml`, the Nerd Font glyph is resolved.
  If disabled, the fallback representation is used (or `""`, which automatically collapses the icon column for perfect, compact alignment).
* **Settings Toggle Dialog (`type: toggle`)**: Interactive themed popups with True, False, and Cancel buttons, dynamically persisting selections in `bashmenu.yml`.
* **Dynamic Block Injection**: Custom `inject_block` action type that allows
  injecting modular configuration blocks from templates into target files (e.g.
  injecting alias sourcing into `~/.bashrc`), with automatic, interactive
  installation, updating, and uninstallation prompts.
* **Self-Healing Virtual Environment**: The main `bashmenu.sh` launcher script
  checks, sets up, and automatically repairs its `.venv` dependencies, ensuring
  cross-platform stability.
* **Modal Dialogs**: File/directory chooser modal (`picker: file|dir`),
  confirmation dialogs (`type: confirm`), text input prompts, and scrolling
  message boxes.
* **Theme Support**: Adaptive color themes supporting 256-color, 16-color, and
  8-color terminfo fallbacks with auto-validation via `ymlcheck.py`.

---

## Setup & Execution

Run the launcher script to start the application. The launcher will
automatically handle Python virtual environment creation and download the
necessary `PyYAML` dependency if missing or corrupted:

```bash
./bashmenu.sh
```

---

## Menu Navigation & Hotkeys (`bashmenu.py`)

* `UP` / `DOWN` / `j` / `k`: Navigate menu selection rows.
* `0`-`9`, `a`-`z`, `A`-`Z`: Direct option shortcut selection.
* `F4`: Launch visual menu editor (`menuedit.py`).
* `F5`: Toggle display of option shortcut key badges.
* `ENTER`: Activate selected menu option.
* `ESC`: Return to parent menu or exit application.

---

## Built-in Text Editor Hotkeys

* `Ctrl+X`: Exit editor (prompts save if modified).
* `Ctrl+O` / `F3`: WriteOut (save active file).
* `Ctrl+R` / `F5`: Read File / Open file via file picker.
* `Ctrl+S` / `F6`: Save As (prompt destination path).
* `Ctrl+N` / `F4`: Create new empty document.
* `Ctrl+G` / `F1`: Toggle help bar.
* `Ctrl+K` / `F8`: Cut line or highlighted text block.
* `Ctrl+U` / `F9`: Paste (uncut) cutbuffer text.
* `Ctrl+C`: Show cursor position or copy selection.
* `Alt+6`: Copy line or selection block.
* `Alt+U`: Undo edit operation.
* `Alt+E`: Redo edit operation.
* `Ctrl+^` / `Alt+A`: Set or unset text selection mark.
* `Alt+N`: Toggle line number gutter display.
* `Alt+P` / `Alt+W`: Toggle whitespace visibility (`·` for spaces, `→` for tabs).
* `F2`: Launch external `$EDITOR` (e.g. `nano` or `vim`).

---

## Menu Directives (`bashmenu.mnu`)

* `type`: Option type (`command`, `script`, `config`, `editor`, `confirm`,
  `message`, `python`, `inject_block`, `theme_selector`, `back`, `exit`,
  `submenu`).
* `label`: Display text label shown in menu row.
* `action`: Command line string, script path, or editor file path.
* `template`: Source template path for dynamic block injection (e.g.,
  `templates/aliases.tmpl`).
* `target`: Destination file path for dynamic block injection (e.g., `{bashrc}`).
* `block_id`: Unique identifier tag for dynamic code block boundaries.
* `stream`: `true` | `false` (real-time streaming process output).
* `interactive`: `true` | `false` (suspend curses for terminal output).
* `quiet`: `true` | `false` (suppress execution headers and pause prompts).
* `refresh`: `true` | `false` (reload environment and menu files on return).
* `user_mode`: `"root"` | `"user"` (requires elevated root privileges).
* `key`: Target YAML dot-notation key path in `bashmenu.yml`.
* `picker`: `"file"` | `"dir"` | `"none"` (opens visual file/folder chooser).
* `start_dir`: Starting path for file/folder picker modal.
* `masked`: `true` | `false` (masks password input entries with asterisks).
* `show_whitespace`: `true` | `false` (renders spaces as `·` and tabs as `→`).
* `tab_to_spaces`: `true` | `false` (converts TAB key input to spaces).
* `tabstop`: Integer space width for TAB key indentation.
* `on_yes` / `on_no`: Nested action definitions for confirmation dialogs.

---

## Directive Example: Dynamic Block Injection (`inject_block`)

The `inject_block` type provides a clean way to manage modular code injection
and updates inside shell config files (e.g., `.bashrc`, `.zshrc`, `.vimrc`)
interactively.

```yaml
- label: Configure Custom Aliases
  type: inject_block
  template: "templates/aliases.tmpl"
  target: "{bashrc}"
  block_id: "custom_aliases"
  refresh: true
```

### Block Template Example (e.g., `templates/aliases.tmpl`):
The template file can contain standard configurations or scripts and utilize
any dot-notation keys from `bashmenu.yml` or global environment placeholders.
Lines are expanded dynamically upon injection.

```bash
# Custom system alias definitions for user {user}
alias system-ip="echo 'Your current IP is: {settings.dns.ip}'"
alias edit-menu="bashmenu.sh"
```

### Injection Behavior & Workflow:
1. **Placeholder Resolution:** The template file path, target path, and the
   content of the template are dynamically interpolated using setting values from
   `bashmenu.yml` (e.g. `{settings.dns.ip}`).
2. **Boundary Marking:** The content is wrapped inside automatic boundaries:
   ```bash
   # CODEBLOCK:custom_aliases:START
   # (Your interpolated template content here)
   # CODEBLOCK:custom_aliases:END
   ```
3. **Interactive Control:**
   * **If Block is Missing:** The system prompts the user to confirm
     installation. Upon agreement, it creates parent folders if needed and
     injects the block.
   * **If Block is Present:** The system prompts: "Code block already present".
     Selecting **YES** updates/reinstalls the block with the latest template.
     Selecting **NO** cleanly uninstalls (removes) the block from the file.
     Selecting **Cancel** aborts the operation.

---

## Nerd Fonts Configuration & Syntax

The system natively supports custom Nerd Font glyphs with automatic simpler emoji or text fallbacks. In your `bashmenu.mnu`, menu option labels are separated from their icons:

```yaml
- label: "Applications"
  icon: "{nf::\U0001F3AE}"
```

### How it Works:
1. **With Nerd Fonts Enabled:** If `settings.use_nerd_fonts` is `true` in `bashmenu.yml`, the engine translates the tag into the colorful glyph (e.g. `\U0001F3AE` / 🎮).
2. **With Nerd Fonts Disabled:** If disabled, the tag resolves to an empty string `""`. The layout engine automatically collapses the icon padding column, so that option labels slide left and align compactly and perfectly next to shortcut numbers without any visual gaps.
3. **Themes Integration**: Theme indicators can use the raw `nf:FALLBACK:GLYPH` syntax (e.g., `indicator: "nf:>:\uf0a4"` or `indicator: "nf:>:#f0a4"`), which dynamically renders the glyph character if Nerd Fonts are enabled, and `>` otherwise. The glyph can be specified as a raw character, or as a hexadecimal code point prefixed with `#` (e.g., `#f0a4` or `#f07c0`).
4. **Width Precision**: The layout engine tracks true visual column widths (including 0-width variation selectors like `\uFE0F` and 2-width terminal emojis), ensuring everything stays pixel-perfectly aligned.

---

## Settings Toggle Dialog (`type: toggle`)

The `toggle` or `config_toggle` directive displays a themed interactive pop-up with **True**, **False**, and **Cancel** buttons.
* **True** (or `T`): Sets the designated dot-notation key (e.g., `settings.use_nerd_fonts`) in `bashmenu.yml` to `True`.
* **False** (or `F`): Sets the key to `False`.
* **Cancel** (or `C`/`ESC`): Exits without saving changes.

#### Example:
```yaml
- label: Toggle Nerd Fonts [{settings.use_nerd_fonts}]
  type: toggle
  key: settings.use_nerd_fonts
  title: Toggle Nerd Fonts
  message: 'Enable colorful menu emojis and Nerd Fonts?'
```

---

## Modularity & In-Process Plugins (`external: false`)

To enable a plug-and-play plugin architecture, Python scripts (of `type: script`) can configure the `external` boolean directive in `bashmenu.mnu`:
* **`external: true` (Default)**: Launches the script in a separate shell/subprocess. It temporarily suspends the current curses window.
* **`external: false`**: Executes the Python script in-process using dynamic module loading. It avoids spinning up another shell/Python VM, eliminating terminal flashes entirely.

#### Plugin Requirements:
For an in-process script to run inside `bashmenu`'s parent process, it must:
1. Be a Python script (`.py`).
2. Implement a `def main(stdscr)` entry point function which takes the curses window as an argument.

#### Example:
```yaml
- label: Visual Menu Editor (menuedit.py)
  type: script
  action: menuedit.py
  external: false
```
