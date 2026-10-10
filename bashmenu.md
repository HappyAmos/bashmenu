# HA Bash Menu Specification & User Manual (v0.0.1)

Welcome to the specification and user manual for HA Bash Menu, a lightweight,
data-driven Textual Text User Interface (TUI) menu engine and configuration
editor for Linux systems.

<details>
<summary><b>Table of Contents</b> (click to expand)</summary>

- [1. Component Overview & Files](#1-component-overview--files)
  - [1.1 Local Manual Pages (Man Pages)](#11-local-manual-pages-man-pages)
- [2. Dynamic Scripts & Templates References](#2-dynamic-scripts--templates-references)
  - [2.1 Provided Utility Scripts (`scripts/`)](#21-provided-utility-scripts-scripts)
  - [2.2 Provided Templates (`templates/`)](#22-provided-templates-templates)
- [3. Keyboard Shortcuts & Navigation Reference](#3-keyboard-shortcuts--navigation-reference)
  - [3.1 Main Menu Engine (`bashmenu.py`)](#31-main-menu-engine-bashmenupy)
  - [3.2 Visual Menu Editor (`menuedit.py`)](#32-visual-menu-editor-menueditpy)
  - [3.3 Built-in Text Editor (`bashedit.py`)](#33-built-in-text-editor-basheditpy)
- [4. Configuration & Schema Specifications](#4-configuration--schema-specifications)
  - [4.1 Settings Store (`bashmenu.yml`)](#41-settings-store-bashmenuyml)
  - [4.2 Menu Structure (`bashmenu.mnu`)](#42-menu-structure-bashmenumnu)
  - [4.3 Color Themes Specification (`bashmenu.themes`)](#43-color-themes-specification-bashmenuthemes)
- [5. Complete Menu Option Types Reference](#5-complete-menu-option-types-reference)
- [6. Dynamic Directives & Variables](#6-dynamic-directives--variables)
  - [6.1 Dynamic Input Directives](#61-dynamic-input-directives)
  - [6.2 System & Path Placeholders](#62-system--path-placeholders)
  - [6.3 Nerd Fonts & Emoji Adaptive Resolution](#63-nerd-fonts--emoji-adaptive-resolution)
  - [6.4 Console Tag Rich Formatting](#64-console-tag-rich-formatting)
- [7. Advanced Integration Use Cases](#7-advanced-integration-use-cases)
  - [7.1 Modular Block Injection (`type: inject_block`)](#71-modular-block-injection-type-inject_block)
  - [7.2 In-Process Python Plugins (`external: false`)](#72-in-process-python-plugins-external-false)
  - [7.3 Multi-Platform Support & Environment Detection](#73-multi-platform-support--environment-detection)
  - [7.4 Background Footer Plugins Architecture & Creation Guide](#74-background-footer-plugins-architecture--creation-guide)

</details>

---

## 1. Component Overview & Files

HA Bash Menu is comprised of modular scripts and configuration files:

| Component / File | Description |
| :--- | :--- |
| `install.sh` | Universal POSIX /bin/sh installer with package auto-detection and self-cleanup. |
| `uninstall.sh` | Pure POSIX /bin/sh uninstaller removing files, symlinks, and cache. |
| `bashmenu.sh` | Launcher shell script with auto-setup and self-healing. |
| `bashmenu.py` | Core Textual TUI application engine and main rendering window. |
| `bashmenu_ui.py` | Shared UI library — modal screens, theme engine, formatting helpers. |
| `bashedit.py` | Built-in Nano-style text editor engine. |
| `menuedit.py` | Interactive TUI visual editor for `bashmenu.mnu` (run via `F4`). |
| `bashmenu.yml` | YAML user settings configuration store. |
| `bashmenu.mnu` | YAML menu layout structure and action definitions. |
| `bashmenu.themes` | YAML color themes for 256, 16, and 8 color modes. |
| `ymlcheck.py` | Command line validator for theme and configuration YAML files. |

### 1.1 Local Manual Pages (Man Pages)

| File | Description |
| :--- | :--- |
| `bashmenu.1` | Exhaustive terminal manual page for HA Bash Menu. |

---

## 2. Dynamic Scripts & Templates References

### 2.1 Provided Utility Scripts (`scripts/`)
These scripts are stored in the `/scripts` directory and can be used directly or as action references:

| Script | Description |
| :--- | :--- |
| `scripts/ascii.sh` | Standard and Extended ASCII viewing utility. |
| `scripts/asteroids.sh` | Asteroids game runner that downloads, compiles, and launches the terminal game. |
| `scripts/bsdgames.sh` | Interactive runner menu for classic BSD games (adventure, atc, battlestar, robots, snake, tetris, etc.). |
| `scripts/cheat.py` | Python CLI cheatsheet search engine supporting exact matches, tags, and full-text search. |
| `scripts/cheat.sh` | Cheatsheet lookup utility wrapper for rich.sh and pager.sh. |
| `scripts/dnsconfig.sh` | Interactive shell script that configures IPv4 and IPv6 DNS server addresses for active network connections using nmcli and systemd-resolved. |
| `scripts/games.sh` | Interactive runner menu for terminal games (ninvaders, pacman4console, nsnake, greed, moon-buggy, nethack, asteroids). |
| `scripts/get_api_key.sh` | Script to securely retrieve and format API keys or credentials. |
| `scripts/getdns.py` | CLI python utility to query and discover currently active upstream system DNS server settings. |
| `scripts/glyphs.sh` | Curses search and preview dialog box utility for selecting Unicode emojis and Nerd Font icons. |
| `scripts/gorillas.py` | QBasic Gorillas clone TUI game implemented as a Textual Screen, launched from the Games submenu. |
| `scripts/hostname.sh` | Hostname and system identity discovery utility reporting hostname, FQDN, kernel, architecture, and OS distribution. |
| `scripts/install_basics.sh` | Cross-platform basic tools installer wrapper. |
| `scripts/install_cheat.sh` | Setup script that installs interactive cheat sheet terminal tools into the local environment. |
| `scripts/install_games.sh` | Cross-platform installer for terminal games (ninvaders, nsnake, greed, moon-buggy, nethack, etc.). |
| `scripts/install_glow.sh` | Installer script for the Glow markdown viewer. |
| `scripts/install_kmscon.sh` | Installer script for the kmscon console emulator, enabling beautiful Unicode and KMS/DRM video support on raw Linux text consoles. |
| `scripts/install_node.sh` | Installer script for Node.js via nvm or system package manager. |
| `scripts/install_scripts.sh` | Deployment script to copy and register utility bash configurations. |
| `scripts/ip_info.sh` | Displays current network interface IP addresses and connection status. |
| `scripts/ncurses_colors.py` | Visual tester for ncurses color support. |
| `scripts/otd.sh` | Shell script fetching a random "On This Day" historical quote/event and link from today.zenquotes.io API using curl and jq. |
| `scripts/pager.sh` | Interactive full-screen terminal text pager supporting ANSI colors, vim/less keys, and link navigation. |
| `scripts/ping.sh` | Cross-platform ping wrapper with unprivileged TCP handshake latency fallback for restricted environments. |
| `scripts/rich.sh` | Markdown file rendering wrapper utilizing Python Rich piped into pager.sh. |
| `scripts/serverup.sh` | Cross-platform server ping and uptime availability check script. |
| `scripts/system_update.sh` | Cross-platform system update wrapper supporting apt, dnf, pacman, pkg, and brew. |
| `scripts/unicode.sh` | Interactive Unicode Block Explorer script. |
| `scripts/webopen.sh` | Cross-platform web browser launcher wrapper script that opens a specified URL, file, or default browser (supporting Linux, macOS, WSL, and Termux). Supports `--gui` / `-g` for graphical browsers and `--tty` / `tty` for terminal browsers (lynx, links, brow6el). |

### 2.2 Provided Templates (`templates/`)
Used as dynamic templates for code generation, settings, or block injections:

| Template | Description |
| :--- | :--- |
| `templates/autoexec.sh.tmpl` | Configurable template for system autoexec shell scripts (used by configure_autoexec plugin). |
| `templates/bash_aliases.tmpl` | Sourced shell alias definitions injected dynamically into user profiles. |

---

## 3. Keyboard Shortcuts & Navigation Reference

### 3.1 Main Menu Engine (`bashmenu.py`)
| Keybinding | Action |
| :--- | :--- |
| `UP` / `DOWN` / `j` / `k` | Navigate highlighted selection row. |
| `0` - `9`, `a` - `z`, `A` - `Z` | Direct option shortcut hotkey jump. |
| `F1` | Display this markdown help manual using the `glow` terminal pager. |
| `F4` | Launch visual menu editor (`menuedit.py`). |
| `F5` | Refresh menu, reload configuration and plugin outputs. |
| `F6` | Toggle option shortcut key badges display. |
| `ENTER` | Execute selected item action. |
| `ESC` | Return to parent submenu or exit application. |

*Note on Intelligent State Retention:* When returning from editors, or scripts with `refresh: true`, the engine traces and preserves your submenu coordinate depth to return you to your exact location, skipping the root menu.

### 3.2 Visual Menu Editor (`menuedit.py`)

| Keybinding | Action |
| :--- | :--- |
| `a` / `Ins` | Insert new menu option node. |
| `e` / `ENTER` | Edit selected node properties or menu header (opens `ItemEditModal`). |
| `E` | Open raw YAML snippet in editor for selected node. |
| `d` / `Del` | Delete selected option node (with confirm box). |
| `m` / `M` | Move selected node down (`m`) or up (`M`). |
| `>` / `.` / `Tab` | Indent item into preceding Submenu folder. |
| `<` / `,` / `Shift+Tab` | Outdent item out to Parent menu list. |
| `t` | Test-run selected menu item action directly. |
| `s` | Save changes to `bashmenu.mnu`. |
| `?` / `h` / `F1` | Display comprehensive General Help modal. |
| `ESC` / `C` | Exit editor or cancel dialogs (prompts if unsaved changes exist). |

*Note on Menu Focus Synchronization & Property Inspector Previews:* When launching `menuedit.py` from `bashmenu.py` (via `F4` or menu item action), the editor tree automatically synchronizes active keyboard focus and selection directly on the item that was selected in `bashmenu.py`, so pressing `e` or `ENTER` immediately opens the `ItemEditModal` dialog for that exact item. The Property Inspector side panel features a real-time visual `Preview:` section for all item types (commands, submenus, scripts, dividers, etc.) showing exactly how the item will appear in the main menu (including resolved Nerd Font/emoji icons, placeholders, and right-aligned shortcut brackets). Additionally, the `ItemEditModal` dialog dynamically updates its preview box in real-time as title or icon fields are edited. Property inspector binary switches match window background styling (`Switch:focus { background: transparent; }`), and the help text footer clearly displays `[ESC / C] Cancel`.

### 3.3 Built-in Text Editor (`bashedit.py`)

| Keybinding | Action |
| :--- | :--- |
| `Ctrl+Q` / `ESC` | Exit editor (prompts save if modified). |
| `Ctrl+O` / `Ctrl+R` / `F5` / `F7` | Open file via file picker modal. |
| `Ctrl+S` / `F2` / `F3` | Save active file. |
| `Alt+S` / `Ctrl+Shift+S` / `F6` | Save As (prompt destination path). |
| `Ctrl+E` / `F4` / `[ + ]` | Create new empty tab document. |
| `Alt+]` / `Ctrl+Tab` | Switch to next tab. |
| `Alt+[` / `Shift+Tab` | Switch to previous tab. |
| `Ctrl+W` | Where Is (search document text). |
| `Shift+Arrows` / `Shift+Home/End` | Select text range (desktop selection). |
| `Ctrl+Left` / `Ctrl+Right` | Move word left / right. |
| `Ctrl+Up` / `Ctrl+Down` | Move paragraph up / down. |
| `Ctrl+X` | Cut line or active selection block. |
| `Ctrl+C` | Copy line or active selection block. |
| `Ctrl+V` | Paste cutbuffer / clipboard text. |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo edit operations. |
| `Ctrl+P` / `Alt+M` | View available placeholders & macros modal. |
| `Ctrl+A` / `F11` | Stream ASCII character table (`ascii.sh`). |
| `Alt+V` / `F10` | Stream terminal colors (`ncurses_colors.py`). |
| `Alt+1` | Toggle whitespace characters visibility. |
| `Ctrl+N` / `Alt+N` | Toggle line numbers gutter display. |
| `F12` | Toggle Markdown rendering for document. |
| `F1` / `Ctrl+G` | View BashEdit keybindings manual modal. |

---

## 4. Configuration & Schema Specifications

### 4.1 Settings Store (`bashmenu.yml`)
The settings file stores nested key-value pairs used throughout the menu.
All entries can be referenced dynamically using the explicit `{app.<key>}`
placeholder namespace (e.g. `{app.theme}`, `{app.settings.tabstop}`,
`{app.user.postal_code}`) or shorthand shortcuts (`{theme}`,
`{settings.<key>}`, `{user.<key>}`).
Example:
```yaml
theme: dracula
user:
  divider:
    char: '{ascii:196}'
    length: '{window_width}'
settings:
  use_nerd_fonts: true
  tabstop: 4
  status_gutter: "{user} | {battery} | {date_time_24}"
  plugins:
    otd:
      script: otd.sh
      sleep: 300
      pretext: '{user.divider}'
      posttext: '{user.divider}'
  dns:
    ipv4:
      primary: 1.1.1.1
```
Any dot-notation key (e.g., `settings.dns.ipv4.primary`, `settings.plugins.otd.sleep`, `user.divider`, or `settings.status_gutter`) can be interpolated
inside menu titles, actions, labels, or template files using brackets.

The `settings.plugins` setting specifies plugin scripts located in the configured `scripts_dir`. Each plugin can be defined as a simple script path or a dictionary with `script`, `sleep`, `pretext`, and `posttext` options:
| Setting | Description |
| :--- | :--- |
| `script` | Script filename or command to execute. |
| `sleep` | Plugin-specific output cache duration in seconds (setting `sleep: 0` will update live data on every frame tick). |
| `pretext` | Text or placeholder rendered immediately before the plugin script output. |
| `posttext` | Text or placeholder rendered immediately after the plugin script output. |

#### Multi-Column Plugin Dashboard Layout:
Plugins can be arranged horizontally into columns spanning the full width of the interface using a declarative `layout` configuration under `settings.plugins`:
```yaml
settings:
  plugins:
    layout:
      type: table
      width: "100%"          # Automatically divides available width equally across columns (e.g. 50/50, 33/33/33)
      entries: 2             # Maximum entries per table row (default: 2)
      headers: ["System", "Weather"]  # Optional column headers
      # rows: [ ["uptime", "weather"] ] # Optional explicit row grouping
    otd:
      script: "otd.sh"
      sleep: 300
      standalone: true       # Renders on its own line stretching across the screen without table borders
      pretext: '{user.divider}'
      posttext: '{user.divider}'
    uptime:
      script: "uptime.sh"
      sleep: 30
    weather:
      script: "curl -s 'wttr.in?format=3'"
      sleep: 300
    disk:
      script: "disk.sh"
      sleep: 60
```
- **Automatic Multi-Table Chunking (`entries: N`)**: When `entries: 2` is set and `rows` is omitted, plugins are automatically grouped into 2-column tables. If a 3rd plugin is encountered, a new table is constructed, spanning the screen on its own or grouping with subsequent plugins.
- **Standalone Plugins (`standalone: true` or `span: full`)**: Full-width plugins (such as quote-of-the-day or system banners) can stretch across the entire screen on their own without table borders, sitting above or below multi-column tables.
- **Asynchronous Execution**: Each plugin continues running asynchronously in its own background worker thread honoring its own `sleep` interval without blocking the user interface. Content within each cell automatically wraps cleanly when lines exceed the column width.

#### Inactivity Timeout & Screensaver (`settings.inactivity_timeout`):
The `settings.inactivity_timeout` configuration enables automated screensaver
execution or command execution when no keyboard or mouse activity is detected
for a configured duration:

```yaml
settings:
  inactivity_timeout:
    milliseconds: 300000     # Duration in milliseconds (e.g. 5 minutes)
    # command: 'cmatrix'     # Optional: command to execute (unconfigured by default)
```

| Setting | Type | Description |
| :--- | :--- | :--- |
| `milliseconds` | Integer / Float | Total inactivity duration before triggering. |
| `command` | String (Optional) | Command to execute in alternate buffer. Unconfigured by default; if omitted, timeout does nothing. |

- **Unconfigured Default**: The timeout directive does not include a command
  argument by default. If `command` is not configured, the timeout function
  does nothing.
- **Countdown Reset**: Any keyboard keystroke, mouse movement, click, or scroll
  action resets the countdown timer back to the beginning.
- **Alternate Buffer Isolation**: The command executes inside an alternate
  screen buffer (`\x1b[?1049h`), ensuring neither the underlying terminal
  command line nor the menu layout is disturbed.
- **Seamless Return**: When the screensaver command exits (e.g. via `q` or
  `Ctrl+C`), the menu interface repaints cleanly and the inactivity countdown is
  re-armed automatically.

Dividers can be defined under `user.divider` (or `settings.divider`) with full specifications including `char` (e.g., `{ascii:196}` or `-`) and `length` (e.g., `{window_width}` or `40`). Using `{user.divider}` or `{divider}` in `pretext` or `posttext` expands to a styled divider line matching the active theme's configured divider color.

The `settings.status_gutter` setting allows customization of the system badges displayed in the bottom right corner (the status gutter). This setting is a string containing text and placeholders separated by pipe symbols (`|`). Neither the status gutter nor the left-aligned help gutter ever exceeds 50% of the screen width. Badges and help action items are delimited by pipe symbols (`|`) and treated as atomic units. When text exceeds 50% of the screen width, overlapping items drop to the next line. Neither gutter ever exceeds two lines, with two lines being the maximum allowed height.

Available status gutter placeholders (badges) include:

| Placeholder | Description |
| :--- | :--- |
| `{user}` / `{username}` | Current system username. |
| `{host}` | System hostname. |
| `{battery}` | Current battery percentage (with a 5-second performance cache). |
| `{date_time_12}` / `{date_time_24}` | Full date and time (includes seconds). |
| `{date_time_12_short}` / `{date_time_24_short}` | Short date and time (excludes seconds; optimal for snappier performance). |
| `{time_12}` / `{time_24}` | Current time (includes seconds). |
| `{time_12_short}` / `{time_24_short}` | Short time (excludes seconds; optimal for snappier performance). |
| `{date}` | Current date (YYYY-MM-DD). |
| `{utc_seconds}` | Current epoch seconds. |

### 4.2 Menu Structure (`bashmenu.mnu`)
The menu structure is defined as a hierarchical list of dictionaries under
a main `options` list. Each option dictionary supports several attributes:

| Attribute | Description |
| :--- | :--- |
| `type` | The action option type (see Section 5 for complete list). |
| `label` | The row label string. Can use bracketed placeholders. |
| `icon` | Icon tag using `{nf:[char]:[nerd-font hex]:[emoji]}` syntax. |
| `action` | Shell command, script, or editor file path. Can use dynamic directives like `{param}`, `{file_picker}`, or `{dir_picker}`. |
| `template` | Source template path for dynamic block injection. |
| `target` | Destination path for dynamic block injection. |
| `block_id` | Unique tag for dynamic block boundary markers. |
| `stream` | `true`\|`false` (Execution Mode: real-time streamed command output window inside TUI). |
| `interactive` | `true`\|`false` (Execution Mode: suspends TUI for full-screen TTY tools without header/footer prompts). |
| `quiet` | `true`\|`false` (Execution Mode: suppresses command headers and press-ENTER prompts). |
| `no_formatting` | `true`\|`false` (disables BBCode rich formatting parser for raw plain text display). |
| `external` | `true`\|`false` (runs scripts in separate shell or process). |
| `user_mode` | `"root"`\|`"user"` (defines execution privilege levels). |
| `key` | YAML dot-notation settings key path in `bashmenu.yml`. |
| `picker` | `"file"`\|`"dir"`\|`"none"` (launches visual configuration chooser). |
| `start_dir` | Default folder path for file/directory picker modals. |
| `masked` | `true`\|`false` (masks password input fields with asterisks). |
| `show_whitespace` | `true`\|`false` (enables spaces/tabs visual indicators). |
| `tab_to_spaces` | `true`\|`false` (converts typed tab keystrokes to spaces). |
| `tabstop` | Tab indents column width as integer. |
| `on_yes` | Nested action executed when "Yes" is selected. |
| `on_no` | Nested action executed when "No" is selected. |
| `message` | Body text prompt string for toggle or confirmation popups. |

### 4.3 Color Themes Specification (`bashmenu.themes`)
Color themes configure the visual palette for the main menu, visual menu editor, text editor, and modal screens. Themes are defined under top-level theme names (`dracula`, `nord`, `cyberpunk`, `gruvbox`, `qbasic`, `pacman`, `industry`, `matrix`, `monochrome`, `synthwave`, `amber_crt`, `hotdog_stand`) for `256`, `16`, and `8` color modes using single-line compact lists `[fg, bg]`.

| Supported Theme Element | Description |
| :--- | :--- |
| `background` | Window background color (`COLOR_BLACK`, int index `0-255`, or `-1`). |
| `title` | Top window title header text color. |
| `border` | Outer frame and panel border line color. |
| `text` | Regular menu item text color. |
| `highlight` | Active selection bar text and background colors. |
| `accent` | Accent highlights, path labels, and prompt titles. |
| `footer` | Help footer line color. |
| `help_text` | Dedicated help text color in the bottom gutter and modal footers. |
| `plugin` | Dedicated text color for background plugin output feeds. |
| `gutter` | Status gutter text color. |
| `selection` | Text selection highlight color. |
| `status_bar` | Status bar header/footer color. |
| `shortcut_key` | Direct selection shortcut hotkey character badge color. |
| `shortcut_label` | Direct selection shortcut hotkey label color. |
| `divider` | Horizontal divider line color. |
| `button_primary` | Modal dialog primary action button color. |
| `button_error` | Modal dialog error/destructive action button color. |
| `button_cancel` | Modal dialog cancel action button color. |
| `button_success` | Modal dialog success action button color. |
| `scrollbar` | Scroll bar thumb (foreground) and track (background) colors. |
| `whitespace` | Non-visible whitespace characters (spaces, tabs, newlines) display color in the text editor. |

*Formatting Rule for Editor Compatibility:* Theme definitions maintain compact single-line flow-style bracket lists (e.g., `title: [201, -1]`). This enables `bashedit.py`'s `--display-theme-colors` feature to accurately parse inline bracketed color values and render live color swatch previews.

#### Window Border & Divider Customization (`window:` and `divider:`)
Themes can optionally override the outer window frame border characters using
a top-level `window:` section, and customize horizontal divider characters
using a top-level `divider:` section. Authors may specify CP437 ASCII macros (e.g.,
`{ascii:205}`, `{ascii:221}`), Unicode characters, or Nerd Font glyphs. Any omitted
keys automatically fall back to standard single-line box drawing characters.

```yaml
pacman:
  indicator: "{nf:):#f0baf:}"
  divider:
    char: "{ascii:205}"                 # ═ (Double horizontal divider)
    length: "{window_width}"
  window:
    border_horizontal_top: "{ascii:223}"    # ▀ (Upper half block)
    border_horizontal_bottom: "{ascii:220}" # ▄ (Lower half block)
    border_vertical_left: "{ascii:221}"     # ▌ (Left half block)
    border_vertical_right: "{ascii:222}"    # ▐ (Right half block)
    border_top_left: "┌"
    border_top_right: "┐"
    border_bottom_left: "└"
    border_bottom_right: "┘"
  256:
    ...
```

| Window Border Attribute | Description | Default Fallback |
| :--- | :--- | :--- |
| `border_horizontal_top` | Top horizontal frame border character. | `border_horizontal` / `─` (`{ascii:196}`) |
| `border_horizontal_bottom` | Bottom horizontal frame border character. | `border_horizontal` / `─` (`{ascii:196}`) |
| `border_vertical_left` | Left vertical frame border character. | `border_vertical` / `│` (`{ascii:179}`) |
| `border_vertical_right` | Right vertical frame border character. | `border_vertical` / `│` (`{ascii:179}`) |
| `border_horizontal` | Shorthand for both top & bottom horizontal frame borders. | `─` (`{ascii:196}`) |
| `border_vertical` | Shorthand for both left & right vertical frame borders. | `│` (`{ascii:179}`) |
| `border_top_left` | Top-left corner frame character. | `┌` (`{ascii:218}`) |
| `border_top_right` | Top-right corner frame character. | `┐` (`{ascii:191}`) |
| `border_bottom_left` | Bottom-left corner frame character. | `└` (`{ascii:192}`) |
| `border_bottom_right` | Bottom-right corner frame character. | `┘` (`{ascii:217}`) |
| `border_tee_top` / `top_tee` | Top horizontal T-junction connector character. | `┬` (`{ascii:194}`) |
| `border_tee_bottom` / `bottom_tee` | Bottom horizontal T-junction connector character. | `┴` (`{ascii:193}`) |
| `border_tee_left` / `left_tee` | Left vertical T-junction connector character. | `├` (`{ascii:195}`) |
| `border_tee_right` / `right_tee` | Right vertical T-junction connector character. | `┤` (`{ascii:180}`) |
| `border_cross` | Grid intersection cross character. | `┼` (`{ascii:197}`) |
| `title_left_cap` | Decorative left cap before the title text in header border. | `[` (bracket) |
| `title_right_cap` | Decorative right cap after the title text in header border. | `]` (bracket) |
| `shadow_char` | Drop shadow shade character for modal dialogs and popups. | `░` (`{ascii:176}`) |

##### Divider Styling, Placement & Width Semantics
Divider styling (`char` glyph, `length`, and color) is defined **strictly in the themes file** (`bashmenu.themes`) as the single source of truth. Individual menu items and plugin declarations simply place a divider using `{divider}` and automatically inherit the active theme's styling.

1. **Theme Definition (`bashmenu.themes`)**: Defined under each theme's `divider:` block (specifying `char` and `length`).
2. **Default Fallback**: If an active theme does not define a `divider:` block, the engine defaults to `char: "{ascii:196}"` of length `{window_width}`.
3. **No Per-Item Style Overrides**: Declared divider options in `bashmenu.mnu` or `bashmenu.yml` do not specify `char` or `length`; their appearance is controlled globally by the active theme.

###### Divider Placement & Strict `{divider}` Recognition
- **Menu Options (`bashmenu.mnu`)**: Dividers are declared strictly using `type: "{divider}"` (or unquoted `type: {divider}`). The plain string `"divider"` is **not** recognized.
- **Divider Presence**: Dividers only appear in a menu if explicitly declared as an item (`type: "{divider}"`). If a menu contains no divider items, **no dividers are rendered** in that menu.
- **Plugins (`bashmenu.yml`)**: Plugin display areas place dividers using `pretext: "{divider}"` or `posttext: "{divider}"`.

###### Divider Widths: `{window_width}` vs `{screen_width}`
- `{window_width}`: Standard shorter divider bounded within window borders and 2-character margins (`avail_w = max(20, w - 6)`). Framed by standard vertical borders (`border_vertical_left`/`border_vertical_right`) with 2-character padding on each side, and **without** border tees.
- `{screen_width}`: Full-width divider running from left border to right border (`w - 2`), overriding all margins. Connects directly to `left_tee` (`border_tee_left`) on the left and `right_tee` (`border_tee_right`) on the right without margin spaces.


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
| `{divider}` | Renders an aesthetic horizontal line separator styled by the theme | *(automatic)* |
| `back` | Navigates back to the preceding menu level| *(automatic)* |
| `exit` | Shuts down the menu interface completely | *(automatic)* |

---

## 6. Dynamic Directives & Variables

### 6.1 Dynamic Input Directives
Dynamic input directives trigger modal dialogs when selected,
substituting the placeholder in the action string prior to execution:

| Directive | Description | Supported Attributes |
| :--- | :--- | :--- |
| `{param}` | Prompts for a single-line parameter value using a text modal. | `title` (modal header), `prompt` (body text), `masked` (mask input with asterisks) |
| `{file_picker}` | Launches a visual file chooser dialog. | `title`, `start_dir` |
| `{file_picker_new}` / `{file_picker:new}` | Launches a visual file chooser dialog that permits creating **new files** (by pressing `n` or `N`). | `title`, `start_dir` |
| `{dir_picker}` | Launches a visual directory chooser dialog. | `title`, `start_dir` |
| `{dir_picker_new}` / `{dir_picker:new}` | Launches a visual directory chooser dialog that permits creating **new folders** (by pressing `n` or `N`). | `title`, `start_dir` |

#### Picker Auto-Starting Folders (Pro Tip):
If you precede `{file_picker}` or `{dir_picker}` with a valid folder path in
the action (e.g., `"{templates_dir}/{file_picker}"` or `"/var/log/{file_picker}"`),
the engine parses the prefix, validates it, and **automatically launches the
visual chooser inside that directory**, completely avoiding double-prefixing.

### 6.2 System & Path Placeholders
These variables are dynamically resolved using active configuration and environment values:

| Placeholder | Description |
| :--- | :--- |
| `{user}` / `{username}` | Current system username. |
| `{host}` / `{hostname}` | System host name. |
| `{user-mode}` | Current privilege mode (`"root"` if running with root/sudo privileges, otherwise `"user"`). |
| `{version}` | Script version (e.g., `0.0.1`). |
| `{home}` | User's absolute home directory path. |
| `{bashmenu_dir}` | Application root directory path. |
| `{templates_dir}` / `{templates}` | Templates folder path (`settings.templates_dir`). |
| `{scripts_dir}` / `{scripts}` | Scripts folder path (`settings.scripts_dir`). |
| `{cache_dir}` / `{cache}` | Cache folder path (`settings.cache_dir`, default `~/.cache/bashmenu`). Sets `$CACHE_DIR`. |
| `{bash_aliases}` | Path to `~/.bash_aliases`. |
| `{bashrc}` | Path to `~/.bashrc`. |
| `{zshrc}` | Path to `~/.zshrc`. |
| `{profile}` | Path to `~/.profile` (falls back to existing `.bash_profile` if `.profile` is absent). |
| `{bash_profile}` | Path to `~/.bash_profile` (falls back to existing `.profile` if `.bash_profile` is absent). |
| `{zprofile}` | Path to `~/.zprofile`. |
| `{shell_profile}` | Path to active user login shell profile. |
| `{vimrc}` | Path to `~/.vimrc`. |
| `{nanorc}` | Path to `~/.nanorc`. |
| `{powershell_profile}` | Path to PowerShell `$PROFILE` script. |
| `{prefix}` | Termux / system installation prefix (`$PREFIX` or `/usr`). |
| `{termux_properties}` | Path to `~/.termux/termux.properties`. |
| `{termux_storage}` | Path to Termux `~/storage` directory. |
| `{appdata}` | Path to Windows `%APPDATA%` directory. |
| `{userprofile}` | Path to Windows `%USERPROFILE%` directory. |
| `{divider}` | Themed horizontal divider line (defaults to `{ascii:196}` of width `{window_width}`). |
| `{date_time_12}` | 12-hour formatted date-time (e.g., `2026-09-15 03:00:00 PM`). |
| `{date_time_12_short}` | Short 12-hour formatted date-time (e.g., `2026-09-15 03:00 PM`). |
| `{date_time_24}` | 24-hour formatted date-time (e.g., `2026-09-15 15:00:00`). |
| `{date_time_24_short}` | Short 24-hour formatted date-time (e.g., `2026-09-15 15:00`). |
| `{date}` | Current date formatted as `YYYY-MM-DD`. |
| `{time_12}` | 12-hour formatted time (e.g., `03:00:00 PM`). |
| `{time_12_short}` | Short 12-hour formatted time (e.g., `03:00 PM`). |
| `{time_24}` | 24-hour formatted time (e.g., `15:00:00`). |
| `{time_24_short}` | Short 24-hour formatted time (e.g., `15:00`). |
| `{battery}` | Current battery percentage (e.g., `84%`, or `N/A` if no battery is detected). Performance-optimized with a 5-second cache to prevent rendering lag. |
| `{theme}` | Active color theme name from `bashmenu.yml` (e.g., `tokyo_night`, `dracula`). |
| `{localip}` | Primary outbound IPv4 address (e.g., `192.168.1.50`). Evaluated on demand via UDP socket probe with TTL cache. |
| `{utc_seconds}` | Current UTC time in seconds since epoch. |
| `{window_width}` | Current active window width in character columns. |
| `{window_height}` | Current active window height in character lines. |
| `{ascii:decimal}` | Prints characters by their decimal code (using CP437 for extended ASCII, e.g. `{ascii:168}` resolves to `¿`). |
| `{app.<key.path>}` / `{<key.path>}` | Resolves any configuration path from `bashmenu.yml` using the explicit `{app.<key>}` namespace (e.g., `{app.theme}`, `{app.settings.tabstop}`, `{app.user.postal_code}`) or shorthand format (e.g., `{settings.cache_dir}`, `{user.editor}`). |
| `{command:shell_cmd}` | Dynamic shell command execution placeholder. Runs `shell_cmd` via system shell, sanitizes and strips trailing whitespace/newlines, and replaces the tag with the command output (supports nested braces, 30.0s cache, and 3.0s execution timeout). |

### 6.3 Nerd Fonts & Emoji Adaptive Resolution
The application resolves icons dynamically according to terminal features and
user configurations using three properties: a fallback ASCII character, a Nerd
Font PUA code point, and a Unicode emoji icon:

```text
{nf:[character]:[nerd-font hex]:[emoji-glyph]}
```

#### Precedence of Evaluation & Display:
The layout engine processes this tag with the following strict hierarchy:
1. **Emoji Icon (Unicode capable)**: If the system is Unicode-capable,
   `settings.use_nerd_fonts` is enabled, and `emoji-glyph` is provided,
   it is chosen and displayed.
2. **Nerd Font Glyph (Nerd Fonts enabled)**: If `settings.use_nerd_fonts`
   is `true` in `bashmenu.yml` and a valid hex code point is provided
   (e.g., `#f0a4`, `$f059f`, `0xef09`), the Nerd Font glyph is displayed.
3. **Fallback Character**: If Nerd Fonts are disabled or no icon/hex is
   defined, the defined character(s) (e.g. `{nf:#}` -> `#`) are displayed.
4. **Fallback**: If all properties are unconfigured, resolves to empty string.

#### Icon Slot Width & Menu Text Alignment:
- Every menu option icon slot occupies a standardized **4-column** visual
  display width (`vis_w + pad_w = 4`):
  - 2-column wide emojis (`🚀`, `🎮`, `📥`, `🌐`, `❓`, `🚪`): `vis_w=2, pad_w=2`.
  - 1-column glyphs and text symbols (`󰖟`, `⚙`, `ℹ`, `🌤`, `#`): `vis_w=1, pad_w=3`.
  - No icon: 4 padding spaces (`"    "`).
- Menu option names and descriptions **always** align vertically at column 11
  (`prefix_w = 10` for single-digit shortcuts), guaranteeing consistent column
  alignment regardless of whether icons are emojis, Nerd Fonts, ASCII, or absent.
- Unicode Variation Selectors (`\ufe0f`, `\ufe0e`) are automatically stripped
  prior to display measurement so that monospace font cell dimensions in terminal
  emulators match layout engine calculations.

*Theme Indicator Syntax:* Uses the exact same bracketed syntax (e.g.,
`indicator: "{nf:[char]:[nerd-font hex]:[emoji-glyph]}"` inside the theme file).

### 6.4 Console Tag Rich Formatting
The application includes a rich formatting parser allowing developers to use inline, nested BBCode-style tags throughout options, headers, status gutters, and prompts.

#### Available Formatting Tags:

| Tag | Description |
| :--- | :--- |
| `[b]text[/b]` | Renders text in **bold** (Rich `Style(bold=True)`). |
| `[u]text[/u]` | Renders text with an **underline** (Rich `Style(underline=True)`). |
| `[dim]text[/dim]` | Renders text with **dimmed** contrast (Rich `Style(dim=True)`). |
| `[reverse]text[/reverse]` | Renders text in **reversed** foreground/background contrast (Rich `Style(reverse=True)`). |
| `[color=color_name]text[/color]` | Renders text in a custom theme color. |
| `[table width=100%][tr][th]Col[/th][/tr][tr][td]Val[/td][/tr][/table]` | Renders an aligned Unicode box-drawing table (`┌─┬─┐`, `│ │ │`, `├─┼─┤`, `└─┴─┘`) with auto-sized or percentage column widths (e.g. 50/50, 33/33/33), bold headers, and in-cell text wrapping. |
| `[list][*]Item 1[*]Item 2[/list]` | Renders an unordered bulleted list (`• Item 1`). Closing `[/*]` tags are optional. |
| `[list=1][*]Item 1[*]Item 2[/list]` | Renders an ordered numbered list (`1. Item 1`, `2. Item 2`). |

#### Theme Colors Available:

| Color Identifier | Target Element / Description |
| :--- | :--- |
| `color=text` | Standard text color of the active theme. |
| `color=border` | Border frame color. |
| `color=title` | Main title header color. |
| `color=highlight` | Selected/highlighted bar colors. |
| `color=footer` | Help footer line color. |
| `color=help_text` | Dedicated help text color in bottom gutter and modal footers. |
| `color=plugin` | Background plugin feed output text color. |
| `color=shortcut_key` | Direct action shortcut character badge color. |
| `color=accent` | Accent indicator/status badge color. |
| `color=divider` | Horizontal line divider color. |

#### Key Features:
* **Nesting Support**: Tags can be nested seamlessly (e.g. `[b]bold text [color=accent]with accented[/color] highlight[/b]`).
* **Visible Width Safety**: Centering, padding, and layout checks automatically ignore tags, ensuring pixel-perfect alignments for any styled text.
* **Code Block & Backtick Tag Suppression**: Formatting tags inside inline code backticks `` `[b]code[/b]` `` and fenced code blocks ```` ```[color=red]code[/color]``` ```` are automatically suppressed and displayed literally as plain text.
* **Backslash Tag Escaping**: Preceding a tag bracket with a backslash `\[tag]` (e.g., `\[b]` or `\[/b]`) escapes the formatting parser, rendering the literal bracketed tag text.
* **`no_formatting` Directive / Flag**: Dialog screens and formatting conversion utilities accept an optional `no_formatting: bool = False` parameter to disable tag processing entirely when displaying raw unformatted text.

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
*Plugin requirement:* The python script must implement a Textual `Screen` subclass
that is pushed via `screen.app.push_screen()`.

### 7.3 Multi-Platform Support & Environment Detection
HA Bash Menu incorporates an environment detection engine in `bashmenu.sh` enabling graceful degradation and multi-platform compatibility without manual configuration.

- **Universal Shebangs:** All `.py` and `.sh` files leverage `#!/usr/bin/env` for maximum portability.
- **Cross-Platform Package Wrappers:** By routing operations through wrappers like `scripts/system_update.sh`, the engine automatically translates dependency installs to the correct local package manager (`apt`, `dnf`, `pacman`, `pkg`, or `brew`), and smartly adds or omits `sudo` depending on whether it is running in standard Linux, macOS, WSL, or containerized user-spaces like Termux.
- **Graceful Degradation:** Features dependent on low-level system daemon frameworks (e.g., `kmscon` or `systemd-resolved` DNS modification) check for Termux/WSL and fail gracefully, rather than crashing with environment errors.

### 7.4 Background Footer Plugins Architecture & Creation Guide

HA Bash Menu features an asynchronous, background-cached plugin architecture for displaying live feeds, status information, or quotes directly above the help footer.

#### How Background Plugins Work:
1. **Asynchronous Daemon Execution**: Plugin scripts run in background daemon threads (`threading.Thread(daemon=True)`) with thread-safe locking (`RLock`). This ensures network requests or slow command calls never freeze or lag the main TUI rendering loop.
2. **In-Memory Caching & Sleep Interval**: The output of each plugin script is cached in memory. The `sleep` setting (default: `300` seconds) controls how long cached output remains valid before spawning a background refresh thread. Setting `sleep: 0` forces live execution on every frame tick.
3. **Responsive Vertical Layout Priority**: Menu navigation options hold top rendering priority. The engine calculates available screen space between the menu options list and help footer (`max_plugin_rows`). On constrained terminal windows, plugin output lines are automatically wrapped, truncated, or hidden so menu navigation remains unhindered.
4. **Pretext & Posttext Wrapping**: Optional `pretext` and `posttext` strings can be rendered before and after script output. These support full placeholder interpolation (including `{user.divider}` or `{divider}` for horizontal rule lines).

#### Creating & Registering a Custom Plugin:

1. **Create the Plugin Script**:
   Write a shell script or executable program placed in `scripts_dir` (e.g. `scripts/my_plugin.sh`):
   ```bash
   #!/usr/bin/env bash
   # Example: scripts/my_plugin.sh
   UPTIME=$(uptime -p | sed 's/up //')
   echo -e "[b]System Uptime:[/b] [color=accent]${UPTIME}[/color]"
   ```
   *Note:* The script can output one or multiple lines, and may include rich BBCode formatting tags (e.g. `[b]`, `[color=accent]`) and placeholders.

2. **Register in `bashmenu.yml`**:
   Add the plugin definition under `settings.plugins` in `bashmenu.yml`:
   ```yaml
   settings:
     plugins:
       uptime_feed:
         script: "my_plugin.sh"
         sleep: 60
         pretext: '{user.divider}'
         posttext: '{user.divider}'
   ```

3. **Supported Plugin Definition Formats**:
   - **Simple String**: `my_plugin: "my_plugin.sh"` (uses default `sleep: 300`).
   - **Full Dictionary**:

     | Property | Description |
     | :--- | :--- |
     | `script` (or `command`, `cmd`, `path`, `file`) | Filename inside `scripts_dir`, absolute path, or shell command string. |
     | `sleep` | Cache duration in seconds (`0` for live refresh). |
     | `pretext` | Header text/divider rendered before script output. |
     | `posttext` | Footer text/divider rendered after script output. |
