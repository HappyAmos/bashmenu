---
name: bashmenu-developer
description: Core developer guidelines for the multi-platform BashMenu
  project. Use when modifying bashmenu.py, bashedit.py, bashmenu.sh,
  menu configurations, themes, or writing tests in the .tests folder.
---

# Skill Name: BashMenu Core Developer

## 1. Intent, Scope & Boundaries
- **Intent:** Activate when developing, refactoring, or writing tests for Python scripts (`bashmenu.py`, `bashmenu_ui.py`, `bashedit.py`, `menuedit.py`, `themeedit.py`), shell scripts (`bashmenu.sh`, `install.sh`, `scripts/*.sh`), configurations (`bashmenu.yml`, `bashmenu.mnu`, `bashmenu.themes`), or documentation.
- **Can:** Update cross-platform Python/Bash code, Yaml configs, Textual UI layouts, unit tests in `.tests/`, and man/markdown documentation.
- **Cannot:** Introduce syntax/runtime errors; guess paths or implementation details (ask for clarification); hardcode absolute user paths (always use expanding macros: `{home}`, `{bashmenu_dir}`, `{scripts_dir}`, `{templates_dir}`, `{cache_dir}`); bind `<F11>` (reserved by window managers for fullscreen; use `<F12>` or alternate unreserved keys).

---

## 2. Core Development Workflow & Invariants
- **Verification & Linting:** Run `ruff check .tests/` and Python files frequently. Run `shellcheck` across shell scripts. Verify Python tests via `python3 -m unittest discover -s .tests -p "test_*.py"` or `pytest`.
- **Directory Invariants:**
  - Tests: All unit/integration tests must reside in `.tests/` (`test_*.py`) and dynamically resolve project root via `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))`. Never place tests in root or `scripts/`.
  - Extension Scripts: Standalone games, plugins, and helper tools must reside in `scripts/`, never in root. Menu actions reference them via `{scripts_dir}/<name>`.
- **Dependencies & Virtualenv Hygiene:** `requirements.txt` must declare `textual`, `rich`, `PyYAML`, and `ruff`. Never remove `ruff`. Keep system prerequisites to a minimum (`python3` + `curl`). Prefer Python standard library (`json`, `urllib.request`) over external CLI tools (`glow`, `jq`, `yq`) for out-of-the-box compatibility on Termux, Raspberry Pi, and Windows (Git Bash/WSL).
- **Sub-Agent Delegation Policy:** Use local `opencode` CLI sparingly and strictly for small, low-risk draft tasks (test case drafts, isolated prototypes). Treat all output as untrusted draft code requiring strict review, linting, and automated test validation.
- **Branching Discipline:** For structural overhauls (cross-platform compatibility, editor re-architecture, dependency reduction), always branch from git (e.g. `feat/<topic>`) and verify all tests and linters pass before merging.

---

## 3. Project Architecture & Components
| File / Directory | Description |
| :--- | :--- |
| `bashmenu.sh` | Main wrapper with POSIX `/bin/sh` trampoline and `--setup` self-healing virtualenv activation. |
| `bashmenu.py` | Core Textual TUI menu system and placeholder interpolation engine. |
| `bashmenu_ui.py`| Centralized UI primitives, modal screens, drop shadow frames, BBCode parsers, and theme color conversion. |
| `menuedit.py` | Visual tree editor for `bashmenu.mnu` (invoked via `F4`). |
| `themeedit.py` | Visual split-screen theme editor with 2D color and CP437 ASCII pickers. |
| `bashedit.py` | Terminal curses text and menu definition editor. |
| `bashmenu.yml` | Main Yaml configuration file (active theme, plugin layout, timeouts). |
| `bashmenu.mnu` | Yaml menu hierarchy using label-as-key `items:` schema. |
| `bashmenu.themes`| Theme palette, window borders, and divider definitions. |
| `scripts/` | Extension scripts (`cheat.sh`/`.py`, `rich.sh`, `pager.sh`, `webopen.sh`, plugins, games). |
| `templates/` | Generic shell RC templates (`.bashrc`, `.vimrc`) free of personal hostnames, IPs, or absolute paths. |
| `.tests/` | Centralized automated test suite. |
| `install.sh` / `uninstall.sh` | Pure POSIX `/bin/sh` installer and uninstaller with package auto-detection and self-cleanup. |

---

## 4. Menu UI & Layout Invariants
- **Margins & Inner Buffer Clamping:** Left/right margins are exactly 2 characters; top margin is 2 lines. `MainMenuView` treats rows as an inner buffer bounded to `avail_w = window_width - 6`. Content is truncated and padded to `avail_w` before attaching borders (`"│  "` and `"  │\n"`), preventing wrapped borders.
- **Icon Slot Width & Text Alignment:** Every option icon slot must occupy exactly **4 columns** (`vis_w + pad_w = 4`):
  - 2-column emojis (`🚀`, `🎮`, `🌐`): `vis_w = 2, pad_w = 2` (`f"{icon}  "`).
  - 1-column glyphs/symbols (`󰖟`, `⚙`, `ℹ`, `#`): `vis_w = 1, pad_w = 3` (`f"{icon}   "`).
  - No icon: 4 spaces (`"    "`).
  - Option descriptions strictly align at column 11 (`prefix_w = 10` for single-digit shortcuts).
- **Adaptive Glyph Resolution (`{nf:[char]:[nerd]:[emoji]}`):** Strict 4-tier resolution hierarchy:
  1. *Emoji tier*: Selected if defined and `settings.use_nerd_fonts: true`.
  2. *Nerd Font tier*: Selected if hex token defined (`#`, `$`, `0x`) and Nerd Fonts enabled.
  3. *Character tier*: Selected if defined or if Nerd Fonts disabled.
  4. *Fallback*: Empty string if unconfigured.
- **Variation Selector Normalization:** Always strip Unicode Variation Selectors (`.replace('\ufe0f', '').replace('\ufe0e', '')`) prior to cell width measurement and rendering to prevent cursor drift and border overflow.
- **Status & Help Gutter Constraints (`MainMenuView`):**
  - 50% Width Limit: Neither status gutter (right) nor help gutter (left) may exceed 50% of available width (`max_gutter_w = max(5, avail_w // 2)`).
  - Pipe Delimiter Wrapping: Items between `|` are treated as atomic badges. Status gutter items wrap bottom-up (overflow on line above).
  - Max Height: Maximum 2 rows (`max_lines=2`); excess is discarded.
  - Sizing Formula: `gutter_rows = min(2, max(1, max(len(help_lines), len(status_lines))))`; `total_content_rows = max(1, h - 4 - gutter_rows)`. Total rendered lines strictly equals terminal height `h`.
- **Plugin Buffer & Section Dividers:**
  - `PluginBuffer` is an independent Textual buffer at least 1 line above the gutter, dynamic height up to 10 rows, with theme background matching.
  - Top divider (`divider: true` / `top_divider: true`): Deducts 1 row from `visible_option_rows` so scrolling never overlaps the divider.
  - With `{screen_width}` dividers, `PluginBuffer` expands to `max(20, w - 2)` at `x = 1`, and text lines indent 2 spaces (`"  "`) for menu column alignment.

---

## 5. Themes, Window Borders & Palette Standards
- **Theme Selection & Conversion:** Selecting a theme updates `theme:` in `bashmenu.yml`. When assigning Rich styles to Textual widget styles (`widget.styles.background`), convert 8-bit palette indices to hex via `color.get_truecolor()`; never pass raw strings like `'color(19)'`. Always prefix Textual CSS variables with `$` (e.g. `$surface`).
- **Depth Constraints & Aesthetics:** Run `python3 ymlcheck.py --themes bashmenu.themes` to validate schemas. 16-color mode indices must stay within `0..15` (or `COLOR_*`), 8-color within `0..7`. Maintain cohesive, low-fatigue palettes (e.g. `tokyo_night`, `nord`, `everforest`).
- **Window Borders (`window:` in `bashmenu.themes`):**
  - Supported keys: `border_horizontal_top`, `border_horizontal_bottom`, `border_vertical_left`, `border_vertical_right` (fallbacks: `border_horizontal`, `border_vertical`), corners (`border_top_left`, `border_top_right`, `border_bottom_left`, `border_bottom_right`), tees (`left_tee`, `right_tee`, `top_tee`, `bottom_tee`), caps (`title_left_cap`, `title_right_cap`), and `shadow_char`.
  - Global Textual Border Sync: `apply_theme_to_textual_borders` synchronizes `textual._border.BORDER_CHARS['thick']`/`['solid']` and clears Textual's box cache (`get_box.cache_clear()`).
- **Dividers (`divider:` in `bashmenu.themes`):**
  - Theme-controlled: Defined strictly in `bashmenu.themes`. Fallback is `char: "{ascii:196}"` and `length: "{window_width}"`.
  - Strict Syntax: Menu items must declare `type: "{divider}"` (or unquoted `{divider}`). Plain `"divider"` is invalid. Dividers only appear if declared in `bashmenu.mnu` or plugin config.
  - Width Modes:
    - `{window_width}`: Inset within borders and 2-space margins (`avail_w = max(20, w - 6)`), framed by standard vertical borders without tees.
    - `{screen_width}`: Full-width border-to-border (`w - 2`), connects directly to `left_tee`/`right_tee` without margin spaces. Foregrounds must match border color.
- **Theme Editor & Contrast Invariants (`bashedit.py`):**
  - When `--display-theme-colors` is active, invert FG/BG if text matches theme background. Fall back to neutral primary 8 (`white` on dark, `black` on light) if both match.
  - Whitespace (`Alt+1`): Stylize non-visible whitespace (`'·'`, `'→'`, `'↵'`) with theme's `whitespace` token (fallback `dim white`). Apply before selection and cursor styles.

---

## 6. Menu Definitions & Visual Editors (`bashmenu.mnu`, `menuedit.py`)
- **Menu Schema (`items:`):**
  - Use `items:` (replaces `options:`) and label-as-key structure:
    ```yaml
    items:
      - '{divider}':
      - Applications:
          icon: '{nf:󰖟}'
          type: submenu
          submenu:
            title: Applications
            items:
              - Web Browser:
                  action: '{scripts_dir}/webopen.sh'
    ```
  - Lean Defaults: Prune default flags (`stream: false`, `masked: false`, `show_whitespace: false`, `refresh: false`, `no_formatting: false`, `external: false`, `alt_buffer: false`, non-editor `tabstop`, duplicate `command` keys).
  - Runtime Normalization: `normalize_menu_items()` canonicalizes labels and dicts, aliasing `items` to `options` internally.
  - Centralized Dump: Use `bashmenu.dump_menu_yaml()` with 2-space indented sequences.
- **Visual Menu Editor (`menuedit.py`):**
  - Property Inspector: Full schema support (`alt_buffer`, `no_formatting`, `start_dir`, `picker`, `on_yes`/`on_no`, flags, extra properties). Uses scrollable `#inspector_panel` (`overflow-y: auto;`) and `#inspector_content` (`height: auto;`).
  - Type Mutation (`Ctrl+T` / `[t]`): Reconfigure item types post-creation. Migrate payloads to target canonical keys (`command`, `script`, `editor` -> `file`, `config`/`toggle` -> `key`, `python`) and prune obsolete keys. Submenu transitions handle container initialization and tree refresh.
  - Help Bar Footer: 2-line vertical container with two 1-line centered horizontal rows:
    - Row 1: `[a] Add`, `[e/ENTER] Edit`, `[t] Type`, `[SPACE] Toggle`, `[d] Delete`, `[m] Move Dn`, `[M] Move Up`.
    - Row 2: `[>] Indent`, `[<] Outdent`, `[CTRL+A] ASCII`, `[CTRL+P] Placeholders`, `[s] Save`, `[ESC/q] Exit`.
  - App Resolution: Always resolve `app_obj = getattr(self, "_app", None) or getattr(self, "app", None)` before `push_screen()` to avoid `NoActiveAppError` in headless tests.

---

## 7. Textual Component Architecture & Modals
- **Classic Drop Shadow Geometry (`ModalFrame`, `ShadowWidget`):**
  - 2-cell right shadow (`start_y + 1` to `start_y + box_h`) and 1-row bottom shadow (`start_x + 2` to `start_x + box_w + 2`).
  - Uses `window.shadow_char` (default `░`) and theme `shadow: [fg, bg]`. Dimmed backdrop at 60%.
  - Wrap `#dialog` in `ModalFrame(id="modal_frame")` and `Horizontal(id="dialog_hrow")` with right and bottom `ShadowWidget`. Direct child IDs remain queryable.
  - Expanded help modals (`is_help=True`): Sized to 95% width/height with `#dialog_hrow` at `1fr 1fr` and `#dialog` at `1fr 100%`.
- **Selection Modals Standard:** When selecting from predefined lists, avoid freeform inputs (`InputModalScreen`). Always prefer `OptionList`-based modals (`ThemePickerModalScreen`) or 2D grid pickers.
- **Interactive 16×16 2D Pickers (`ColorGridWidget`, `AsciiGridWidget`):**
  - For 256-entry domains (colors and CP437 ASCII 0–255), use 16×16 grids with arrow navigation (±1, ±16), Home/End, PgUp/PgDn (±64), and Enter.
  - Active cells must display bold + underline (`underline=True, bold=True`). Mouse clicks resolve via `col = event.x // cell_width; row = event.y`.
  - ASCII Modal Tabs & Swatches: Group characters into range tabs modeled after `scripts/ascii.sh`: `[1] Extended (128-255)`, `[2] Standard (32-126)`, `[3] All (0-255)`. Quick swatches for box borders (`─`, `│`, `═`, `║`, `┌`, `┐`, `└`, `┘`, `█`, `░`) and ANSI colors.
  - Event Decoupling: Grid `set_code(code, notify=True)` must accept `notify=False`. Pass `notify=False` when clicking swatches to prevent highlight events from overwriting named constants (`"COLOR_RED"`).
- **Tab Key Navigation & Modal Button Sizing:**
  - Never bind `tab` at the screen level (`Binding("tab", ...)`). Let Textual's default focus traversal handle <kbd>Tab</kbd> and <kbd>Shift+Tab</kbd> across tabs, grid, swatches, and action buttons.
  - Standard Button Sizing: Button variants apply 2-line borders. Never use `height: 1` or `border: none` on action buttons. Always use standard `#btn_row` styling: `#btn_row { height: 3; margin-top: 1; align: center middle; }` and `#btn_row Button { height: 3; min-width: 16; margin: 0 1; }`.
  - Provide distinct `:focus` styling for `.btn_swatch:focus`, `.tab_btn:focus`, and `#btn_row Button:focus`.
- **Split-Screen Preview Maximization (`ThemePreviewWidget`):**
  - `#preview_panel` must use `padding: 0; overflow: hidden;`.
  - Compute `w = max(38, parent.size.width - 4)` and `num_rows = max(12, parent.size.height - 2)`. Pad body slots with options, dividers, plugin cards, and bordered spacer rows to fill 100% of pane interior.
- **Textual Modal Performance (Rich Static over Markdown Widget):**
  - Avoid Textual's built-in `Markdown` widget for large docs (decomposes into hundreds of DOM widgets causing multi-second lag).
  - Use `Static` wrapping `rich.markdown.Markdown(text, hyperlinks=True)` for single-widget rendering (<0.1s load, 60 FPS). Intercept clicks via `event.style.link`.
  - If using Textual's `Markdown` widget, always pass `open_links=False` to prevent external browser launches on `#anchor` links.

---

## 8. Performance & Rendering Engines
- **Pre-Baked TrueColor Wallpaper Canvas (`settings.background`, `PrebakedWallpaperCanvas`):**
  - Half-block (`▀`) TrueColor compositing using pure standard ANSI escape sequences. Never introduce Sixel, Kitty, or iTerm2 dependencies.
  - Sub-Millisecond Assembly: Pre-bake static borders, margins, divider rules, and option variants (selected and unselected) into memory on load/resize.
  - Content Blank Row Integrity: Pre-bake static blank rows (`3` to `3 + target_blank_rows`) and fall back to `_static_lines.get(y)` when `opt_idx >= num_options`.
  - Gutter Caching: Cache rendered gutter lines (`raw_hg_lines`) against `gutter_key` so status formatting only runs on second ticks.
  - Differential Redraws: When scroll offset is unchanged, refresh only modified rows (`Region(0, y, w, 1)`), cutting stdout bytes from ~36 KB to ~600 bytes. Clock/plugin ticks refresh only bottom status lines (`Region(0, max(0, h - 3), w, 2)`).
  - Wallpapers must be pre-processed without Floyd-Steinberg dithering (`+dither`, `--nofs`).
- **Macro Interpolation & Probing (`bashmenu.py`):**
  - Short-circuit `interpolate_placeholders()` immediately if `not text or "{" not in text`.
  - Expensive system probes (`get_battery_info()`, `get_primary_ip()`) must only evaluate if their placeholder (`"{battery}"`, `"{localip}"`) is present. Never probe network sockets at module import time.
- **Sub-Editor Lazy Loading:** Heavy standalone editors (`bashedit.py`, `menuedit.py`) must never be imported at top level; import on-demand inside actions.
- **Inactivity Timeout & Screensaver (`settings.inactivity_timeout`):**
  - Configured with `milliseconds` and optional `command`. No default command in `bashmenu.yml` (dormant unless configured).
  - Intercept `events.Key` and `events.MouseEvent` in `BashMenuApp.on_event` to reset timer via `timer.reset()`.
  - Run screensavers in alternate screen buffer (`\x1b[?1049h\x1b[H\x1b[2J`) inside `with self.suspend():`. Restore primary buffer (`\x1b[?1049l`) in `finally`, repaint UI via `self.refresh(layout=True)`, and re-arm timer. Verify `can_suspend` before suspending for headless test safety.

---

## 9. Shell Scripts, CLI Tools & Utilities
- **Script Header Standard:** Every shell script must begin with:
  ```bash
  #!/usr/bin/env bash
  # ==============================================================================
  # SCRIPT: <script_name>.sh
  # DESCRIPTION: <Brief, dry, and concise summary>
  # ==============================================================================
  ```
  Python scripts in `scripts/` must feature a top-level module docstring.
- **Self-Healing Launcher (`bashmenu.sh`):**
  - Layer 1 POSIX `awk`/`grep` parser for scalar settings.
  - `.venv/.ready` stamp bypasses tool inspection on normal launches. Fast-path self-heals (re-runs setup) if `requirements.txt -nt .ready`, prerequisites are missing, Python fails, or `--setup` is passed.
  - Source guards: Guard entry points with `if [[ "${BASH_SOURCE[0]}" == "${0}" ]]`. Non-interactive flags (`--check-env`, `--help`, `--version`) exit 0 without launching TUI.
- **Cross-Platform Browser Dispatch (`webopen.sh`):**
  - Support `--gui` (`-g`) and `--tty` (`-t`). Never pass `"about:blank"` to system openers (`exo-open`, `xdg-open`). Fall back gracefully across GUI and terminal browsers (`brow6el`, `links`, `lynx`, `w3m`, `elinks`, `carbonyl`).
- **Terminal Pager Pipeline (`scripts/pager.sh`, `scripts/rich.sh`):**
  - Pipe Rich output via `FORCE_COLOR=1` and `less -R`. Standardize markdown viewing on `{scripts_dir}/rich.sh <file> | {scripts_dir}/pager.sh`. Pass `-y` (`--hyperlinks`) to `rich.markdown`.
  - Spools: Must reside strictly in `${CACHE_DIR:-${HOME}/.cache/bashmenu}/spool` with an immediate `trap 'cleanup' EXIT INT TERM HUP`.
  - Balanced 3-segment status bar: Left line range (`TOP 1-23/100`), center badge `[ filename.ext ]` or `[ <stdin> ]`, right key hints.
- **Cheatsheet CLI (`scripts/cheat.sh`, `scripts/cheat.py`, `.cheat.yml`):**
  - Root directory defined in `scripts/.cheat.yml` (`dir: ~/cheat`).
  - Search hierarchy: 1a. Exact relative path -> 1b. Filename stem -> 2. YAML frontmatter tags -> 3. Full-text body.
  - List/Search flags: `cheat -l` (lists files and tags in 2 columns), `cheat -s <query>` (filtered search). Dispatches to `rich.sh` and `pager.sh`.
- **BBCode Rich Formatting (`bashmenu_ui.py`):**
  - Bracketed tags: `[b]`, `[u]`, `[dim]`, `[reverse]`, `[color=...]`.
  - Tables: `[table]`, `[tr]`, `[th]`, `[td]` with Unicode borders. `width=100%` distributes columns equally with word-boundary cell wrapping.
  - Lists: `[list][*]`, `[list=1][*]`, `[list=a][*]`. Backticks and backslashes escape formatting. `no_formatting=True` flag bypasses processing.
  - Declarative Plugin Layout (`settings.plugins.layout` / `settings.plugins`): Multi-column tables (`type: table`), auto-grouping by `entries: N`, standalone plugins (`standalone: true` / `span: full`), individual sleep intervals, and pretext/posttext dividers.
- **YAML Validation Tool (`ymlcheck.py`):**
  - `ymlcheck.py <file>` validates syntax without schema checks.
  - `--themes` (`-t`) validates `bashmenu.themes` (palette depths, window, divider).
  - `--config` (`-c`) validates `bashmenu.yml`.
  - `--menu` (`-m`) validates `bashmenu.mnu` (items structure, dividers).

---

## 10. Documentation Standards & 6-Tier Parity
- **Tone & Formatting Constraints:** Maintain a professional, dry tone without promotional adjectives. Format lists as GitHub-Flavored Markdown tables with collapsible `<details><summary><b>Table of Contents</b></summary></details>`. Wrap documentation lines under 80 characters. Precede code block fences with an empty line. Docstrings must be in the third person.
- **Universal 6-Tier Parity Invariant:** Every placeholder, macro, directive, and attribute must be 100% synchronized across all six documentation tiers:
  1. `bashmenu_ui.py`: `PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT` (`^P`/`Alt+M` in editor).
  2. `menuedit.py`: `ITEM_EDIT_HELP_TEXT` (`F1`/`?` inspector guide).
  3. `bashedit.py`: `action_help_manual` (`F1`/`Ctrl+G`/`Alt+H` manual).
  4. `bashmenu.py`: `action_help` modal (`F1`, renders `bashmenu.md`).
  5. `bashmenu.md`: Reference documentation (Sections 1, 2.1, 6.1, 6.2).
  6. `bashmenu.1`: Linux system man page.
- **Scripts Documentation:** Every executable script in `scripts/` must be registered in `bashmenu.md`, `bashmenu.1`, and `README.md`. Verified by automated assertions in `.tests/test_improvements.py`.
- **Directory Aliases & Macro Parity:** Document aliases (`{scripts}`, `{templates}`, `{cache}`, `{notebooks}`) alongside canonical forms (`{scripts_dir}`, `{templates_dir}`, `{cache_dir}`, `{notebooks_dir}`). Document config namespaces (`{app.<key>}` alongside `{theme}`, `{settings.<key>}`).
