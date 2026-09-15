# HA Bash Menu Specification & User Manual (v0.0.1)

Welcome to the comprehensive specification and user manual for HA Bash Menu,
a lightweight, data-driven Curses Text User Interface (TUI) menu engine and
configuration editor for Linux systems.

---

## 1. Component Overview & Files

HA Bash Menu is comprised of modular scripts and configuration files:

- `bashmenu.sh`  : Launcher shell script with auto-setup and self-healing.
- `bashmenu.py`  : Core TUI application engine and main rendering window.
- `bashedit.py`  : Built-in Nano-style text editor engine.
- `menuedit.py`  : Interactive TUI visual editor for `bashmenu.mnu` (run via `F4`).
- `bashmenu.yml`  : YAML user settings configuration store.
- `bashmenu.mnu`  : YAML menu layout structure and action definitions.
- `bashmenu.themes` : YAML color themes for 256, 16, and 8 color modes.
- `ymlcheck.py`  : Command line validator for theme and configuration YAML files.

### 1.1 Local Manual Pages (Man Pages)
- `bashmenu.1`   : Exhaustive terminal manual page for HA Bash Menu.

---

## 2. Dynamic Scripts & Templates References

### 2.1 Provided Utility Scripts (`scripts/`)
These scripts are stored in the `/scripts` directory and can be used directly or as action references:

- `scripts/dnsconfig.sh`    : Interactive shell script that configures IPv4
                              and IPv6 DNS server addresses for active network
                              connections using nmcli and systemd-resolved.
- `scripts/get_api_key.sh`   : Script to securely retrieve and format API
                              keys or credentials.
- `scripts/getdns.py`       : CLI python utility to query and discover currently
                              active upstream system DNS server settings.
- `scripts/glyphs.sh`       : Curses search and preview dialog box utility for
                              selecting Unicode emojis and Nerd Font icons.
- `scripts/install_cheat.sh` : Setup script that installs interactive cheat sheet
                              terminal tools into the local environment.
- `scripts/install_kmscon.sh`: Installer script for the kmscon console
                              emulator, enabling beautiful Unicode and KMS/DRM
                              video support on raw Linux text consoles.
- `scripts/install_scripts.sh`: Deployment script to copy and register utility
                              bash configurations.

### 2.2 Provided Templates (`templates/`)
Used as dynamic templates for code generation, settings, or block injections:

- `templates/autoexec.sh.tmpl` : Configurable template for system autoexec shell
                                 scripts (used by configure_autoexec plugin).
- `templates/bash_aliases.tmpl`: Sourced shell alias definitions injected
                                 dynamically into user profiles.

---

## 3. Keyboard Shortcuts & Navigation Reference

### 3.1 Main Menu Engine (`bashmenu.py`)
- `UP` / `DOWN` / `j` / `k` : Navigate highlighted selection row.
- `0` - `9`, `a` - `z`, `A` - `Z` : Direct option shortcut hotkey jump.
- `F4`                     : Launch visual menu editor (`menuedit.py`).
- `F5`                     : Toggle option shortcut key badges display.
- `ENTER`                  : Execute selected item action.
- `ESC`                    : Return to parent submenu or exit application.

### 3.2 Visual Menu Editor (`menuedit.py`)
- `a` / `Ins`             : Insert new menu option node.
- `e` / `ENTER`           : Edit selected node properties or menu header.
- `E`                     : Open raw YAML snippet in editor for selected node.
- `d` / `Del`             : Delete selected option node (with confirm box).
- `m` / `M`               : Move selected node down (`m`) or up (`M`).
- `>` / `.` / `Tab`       : Indent item into preceding Submenu folder.
- `<` / `,` / `Shift+Tab` : Outdent item out to Parent menu list.
- `t`                     : Test-run selected menu item action directly.
- `s`                     : Save changes to `bashmenu.mnu` (creates `.bak`).
- `?` / `h` / `F1`         : Display comprehensive General Help modal.
- `ESC`                   : Exit editor (prompts if unsaved changes exist).

### 3.3 Built-in Text Editor (`bashedit.py`)
- `Ctrl+X`                : Exit editor (prompts save if modified).
- `Ctrl+O` / `F3`          : WriteOut (save active file).
- `Ctrl+R` / `F5`          : Read File / Open file via file picker modal.
- `Ctrl+S` / `F6`          : Save As (prompt destination path).
- `Ctrl+N` / `F4`          : Create new empty document.
- `Ctrl+G` / `F1`          : Toggle bottom Nano-style shortcut keys bar.
- `Ctrl+K` / `F8`          : Cut line or active selection block.
- `Ctrl+U` / `F9`          : Paste (uncut) cutbuffer text.
- `Ctrl+C`                : Show cursor position or copy selection block.
- `Alt+6`                 : Copy line or selection block.
- `Alt+U`                 : Undo edit operation.
- `Alt+E`                 : Redo edit operation.
- `Ctrl+^` / `Alt+A`       : Set or unset text selection mark.
- `Alt+N`                 : Toggle line numbers gutter display.
- `Alt+P` / `Alt+W`       : Toggle whitespace characters visibility.
- `F2`                    : Launch external `$EDITOR` (e.g. `vim`).

---

## 4. Configuration & Schema Specifications

### 4.1 Settings Store (`bashmenu.yml`)
The settings file stores nested key-value pairs used throughout the menu.
Example:
```yaml
theme: dracula
settings:
  use_nerd_fonts: true
  tabstop: 4
  dns:
    ipv4:
      primary: 1.1.1.1
```
Any dot-notation key (e.g., `settings.dns.ipv4.primary`) can be interpolated
inside menu titles, actions, labels, or template files using brackets.

### 4.2 Menu Structure (`bashmenu.mnu`)
The menu structure is defined as a hierarchical list of dictionaries under
a main `options` list. Each option dictionary supports several attributes:

- `type`      : The action option type (see Section 5 for complete list).
- `label`     : The row label string. Can use bracketed placeholders.
- `icon`      : Icon tag using `{nf:[char]:[nerd-font hex]:[emoji]}` syntax.
- `action`    : Shell command, script, or editor file path. Can use
                dynamic directives like `{param}` or `{file_picker}`.
- `template`  : Source template path for dynamic block injection.
- `target`    : Destination path for dynamic block injection.
- `block_id`  : Unique tag for dynamic block boundary markers.
- `quiet`     : `true`|`false` (suppresses headers and prompts for tools).
- `stream`    : `true`|`false` (real-time streamed command output window).
- `interactive`: `true`|`false` (suspends curses for command line tools).
- `external`  : `true`|`false` (runs scripts in separate shell or process).
- `user_mode` : `"root"`|`"user"` (defines execution privilege levels).
- `key`       : YAML dot-notation settings key path in `bashmenu.yml`.
- `picker`    : `"file"`|`"dir"`|`"none"` (launches visual configuration chooser).
- `start_dir` : Default folder path for file/directory picker modals.
- `masked`    : `true`|`false` (masks password input fields with asterisks).
- `show_whitespace`: `true`|`false` (enables spaces/tabs visual indicators).
- `tab_to_spaces`  : `true`|`false` (converts typed tab keystrokes to spaces).
- `tabstop`   : Tab indents column width as integer.
- `on_yes`    : Nested action executed when "Yes" is selected.
- `on_no`     : Nested action executed when "No" is selected.
- `message`   : Body text prompt string for toggle or confirmation popups.

---

## 5. Complete Menu Option Types Reference

| Type | Description & Behavior | Primary Attributes |
| :--- | :--------------------- | :----------------- |
| `submenu` | Opens nested list of menu choices | `submenu: {options: []}` |
| `command` | Runs a standard shell command string | `action`, `interactive` |
| `script` | Launches an external executable script | `action`, `external` |
| `config` | Prompts user to edit setting value | `key`, `picker`, `start_dir` |
| `toggle` | Interactive True/False/Cancel modal | `key`, `message`, `title` |
| `editor` | Opens file inside built-in text editor | `action`, `show_whitespace` |
| `confirm` | Triggers a Yes/No confirmation dialog | `message`, `on_yes`, `on_no` |
| `message` | Displays an informational pop-up dialog | `message`, `title` |
| `python` | Dispatches internal Python utility function | `action` |
| `inject_block` | Installs/removes modular code segments | `template`, `target`, `block_id` |
| `theme_selector`| Launches list of registered themes | *(automatic)* |
| `divider` | Renders an aesthetic horizontal line separator | `length`, `char` |
| `back` | Navigates back to the preceding menu level| *(automatic)* |
| `exit` | Shuts down the menu interface completely | *(automatic)* |

---

## 6. Dynamic Directives & Variables

### 6.1 Dynamic Input Directives
Dynamic input directives trigger curses prompt dialogs when selected,
substituting the placeholder in the action string prior to execution:

- `{param}` : Prompts for a single-line parameter value using a text modal.
  * Uses attributes: `title` (modal header) and `prompt` (body text).
- `{file_picker}` : Launches a visual file chooser dialog.
  * Uses attributes: `title` and `start_dir`.
- `{dir_picker}` : Launches a visual directory chooser dialog.
  * Uses attributes: `title` and `start_dir`.

#### Picker Auto-Starting Folders (Pro Tip):
If you precede `{file_picker}` or `{dir_picker}` with a valid folder path in
the action (e.g., `"{templates_dir}/{file_picker}"` or `"/var/log/{file_picker}"`),
the engine parses the prefix, validates it, and **automatically launches the
visual chooser inside that directory**, completely avoiding double-prefixing.

### 6.2 System & Path Placeholders
These variables are dynamically resolved using active configuration and environment values:

- `{user}` / `{username}` : Current system username.
- `{home}`              : User's absolute home directory path.
- `{bashmenu_dir}`      : Application root directory path.
- `{templates_dir}`     : Templates folder path (`settings.templates_dir`).
- `{scripts_dir}`       : Scripts folder path (`settings.scripts_dir`).
- `{bash_aliases}`      : Path to `~/.bash_aliases`.
- `{bashrc}`            : Path to `~/.bashrc`.
- `{vimrc}`             : Path to `~/.vimrc`.
- `{window_width}`      : Current active window width in character columns.
- `{window_height}`     : Current active window height in character lines.
- `{ascii:decimal}`     : Prints characters by their decimal code (using CP437 for extended ASCII, e.g. `{ascii:168}` resolves to `¿`).
- `{settings.dot_key}`  : Resolves any nested configuration path from `bashmenu.yml`.

### 6.3 Nerd Fonts & Emoji Adaptive Resolution
The application resolves icons dynamically according to terminal features and
user configurations using three properties: a fallback ASCII character, a Nerd
Font PUA code point, and a Unicode emoji icon:

```text
{nf:[character]:[nerd-font hex]:[emoji-glyph]}
```

#### Precedence of Evaluation & Display:
The layout engine processes this tag with the following strict hierarchy:
1. **Emoji Icon (Unicode capable)**: If the system is Unicode-capable and
   the `emoji-glyph` is provided, it is chosen and displayed.
2. **Nerd Font Glyph (Nerd Fonts enabled)**: If the system is Unicode-capable,
   `settings.use_nerd_fonts` is `true` in `bashmenu.yml`, and the `nerd-font hex`
   (e.g., `#f0a4`) is provided, it translates and displays the Nerd Font glyph.
3. **Fallback ASCII Character**: If Unicode is unsupported, or both Nerd Fonts and
   Emojis are disabled or missing, the plain ASCII `character` is displayed.
4. **Wiped Default**: If all three parameters are missing, the layout engine
   returns an empty string `""` and automatically collapses the icon column,
   sliding the option labels left with zero padding gaps.

*Theme Indicator Syntax:* Uses the exact same bracketed syntax (e.g.,
`indicator: "{nf:[char]:[nerd-font hex]:[emoji-glyph]}"` inside the theme file).

---

## 7. Advanced Integration Use Cases

### 7.1 Modular Block Injection (`type: inject_block`)
Managing templates injected cleanly inside shell profiles (`~/.bashrc`, etc.):
```yaml
- label: Configure Sudo Prompt
  type: inject_block
  template: "{templates_dir}/sudo_lecture.tmpl"
  target: "/etc/sudoers.d/lecture"
  block_id: "sudo_lecture_setting"
  user_mode: "root"
```
The template is injected wrapped in distinct boundaries:
```bash
# CODEBLOCK:sudo_lecture_setting:START
# (Injected template settings here)
# CODEBLOCK:sudo_lecture_setting:END
```
Selecting **Yes** installs or updates the settings block; selecting **No**
uninstalls (erases) the code block cleanly from the target file.

### 7.2 In-Process Python Plugins (`external: false`)
You can run any custom python script directly in-process, preventing terminal
clipping and console flashes:
```yaml
- label: Launch Custom Diagnostic TUI
  type: script
  action: "diagnostics_tui.py"
  external: false
```
*Plugin requirement:* The python script must implement a `def main(stdscr)`
function taking the active curses screen as its sole argument.
