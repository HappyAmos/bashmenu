# HA Bash Menu

A lightweight, data-driven Curses TUI (Text User Interface) menu engine
and settings editor for Linux, configured entirely through modular YAML files.

Extend your shell script experience with beautiful widgets, visual file choosers,
in-process python sub-apps, and self-installing settings templates!

Contains a few personal scripts as examples, all of which have been cleared
as clean by shellcheck, a linux shell script validator.

---

## 🚀 Core Features

- **Visual Tree Editor (`menuedit.py`)**: A visual menu tree editor accessed via
  `F4`. Add, reorder (`m`/`M`), indent (`|`), outdent (`<`), delete (`d`), edit
  properties (`e`/`ENTER`), edit raw YAML snippets (`E`), or test actions (`t`)
  live.
- **Dynamic Prompts & Pickers**: Prompt the user on action select using `{param}`
  text modals, or `{file_picker}`/`{dir_picker}` filesystem navigators. Includes
  intelligent path-aware folder pre-loading.
- **Adaptive Icons**: Beautiful icons mapped via `{nf:[char]:[hex]:[emoji]}`.
  Toggles gracefully between Unicode Emojis, Nerd Font Glyphs, or Fallback ASCII
  characters. If disabled, icon paddings collapse for compact alignment.
- **Dynamic Settings Injection (`type: inject_block`)**: Interactively inject
  modular configuration snippets from templates into shell profiles (e.g.
  `~/.bashrc`), with automatic install, update, and uninstall prompts.
- **Self-Healing Virtualenv**: The `bashmenu.sh` launcher manages Python virtual
  environments and dependencies automatically without user friction.
- **Multi-Platform Support**: Features smart environment detection and package
  manager abstraction (pkg, apt, dnf, pacman, brew) ensuring seamless execution
  across standard Linux, Termux, WSL, and macOS.

---

## 📂 Component Directory

| File/Folder | Description |
| :--- | :---------- |
| `bashmenu.sh` | Wrapper launcher. Auto-creates and repairs virtualenv. |
| `bashmenu.py` | Core TUI rendering engine and main menu rendering window. |
| `bashedit.py` | Built-in Nano-style terminal text editor engine. |
| `menuedit.py` | Visual layout tree editor for `bashmenu.mnu` (run with `F4`). |
| `bashmenu.yml` | Dynamic user settings store (YAML). |
| `bashmenu.mnu` | Hierarchical menu layout options definitions list. |
| `bashmenu.themes`| Theme palettes for 256, 16, and 8 color standard screens. |
| `ymlcheck.py` | Command line utility to validate YAML syntax and schemas. |
| `scripts/` | Useful scripts collection (DNS setup, glyph search, etc.). |
| `templates/` | Sample settings block templates (aliases, autoexec). |

### local Manual Pages (Man Pages)
- `bashmenu.1` : Exhaustively comprehensive man page for HA Bash Menu.

---

## ⚡ Quick Start

Launch the menu interface directly:
```bash
./bashmenu.sh
```

---

## 📖 Complete Documentation & Manuals

For comprehensive guides, lists of all item types, placeholder directives, and
full YAML schemas:

- **Complete User Manual** : Refer to the localized **[bashmenu.md](bashmenu.md)** file.
- **Unix Man Page**        : Execute **`man ./bashmenu.1`** from your terminal
  to pull up the exhaustively detailed manual page in standard formatting.

---

## 📜 License
Distributed under the generous MIT License. See `LICENSE` for details.
