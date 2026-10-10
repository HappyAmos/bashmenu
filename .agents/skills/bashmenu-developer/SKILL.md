---
name: bashmenu-developer
description: Core developer guidelines for the multi-platform BashMenu
  project. Use when modifying bashmenu.py, bashedit.py, bashmenu.sh,
  menu configurations, themes, or writing tests in the .tests folder.
---

# Skill Name: BashMenu Core Developer

## Intent
- Use this skill when working on, refactoring, or writing tests for
  the BashMenu project.
- Activate when the user asks to modify python scripts (`bashmenu.py`,
  `bashedit.py`), bash scripts (`bashmenu.sh`), configuration files
  (`bashmenu.yml`), menu definitions (`bashmenu.mnu`, `bashmenu.themes`),
  or project documentation.

## Scope & Boundaries
- **CAN:** Develop cross-platform Python and Bash scripts, update Yaml
  configurations, modify Textual-based UI layouts, and update
  documentation or man pages.
- **CAN:** Create or modify test cases located in the `.tests`
  directory.
- **CANNOT:** Introduce syntax or runtime errors.
- **CANNOT:** Guess implementation details or paths if uncertain.

## Project Structure & Architecture
This project is a multi-platform bash menu system wrapped around a Python
Textual interface.
- `install.sh`: Universal POSIX /bin/sh installer with package auto-detection and self-cleanup.
- `uninstall.sh`: Pure POSIX /bin/sh uninstaller removing files, symlinks, and cache.
- `bashmenu.sh`: Main wrapper script with POSIX /bin/sh trampoline and --setup flag. Sets up the environment,
  validates prerequisites, and manages/activates the Python venv.
- `bashmenu.py`: Core menu system interface built using the **Python
  Textual framework** (migrated from ncurses).
- `bashmenu_ui.py`: Centralized Textual UI primitives, modal screens,
  formatting parsers, and theme color conversion helpers.
- `bashedit.py`: Menu editor utility.
- `menuedit.py`: Visual tree editor for `bashmenu.mnu` (invoked via `F4`).
- `scripts/gorillas.py`: Classic QBasic Gorillas game implemented as a Textual TUI.
- `bashmenu.yml`: Main Yaml configuration file (stores active settings
  like `theme:`).
- `bashmenu.mnu`: Yaml-based menu structure definition file.
- `bashmenu.themes`: Contains menu definition files for themes.
- `scripts/`: Directory containing extension scripts, launcher
  wrappers, and plugins.
- `templates/`: Contains code templates for integration into shell RC
  files (e.g., `.bashrc`, `.vimrc`).
- `.tests/`: New centralized folder containing project test files.
- `bashmenu.1` / `bashmenu.md` / `README.md`: Project man page, verbose
  documentation, and GitHub landing page respectively.

## Core UI & Layout Rules
- **Formatting Constraints:** Left and right margins must be exactly
  two characters wide. The top margin is two lines.
- **Dividers:** Must dynamically fit `{window_width}`. Formula:
  `{screen_width}` minus left/right margins, minus the width of the
  border characters.
- **Adaptive Glyph Resolution Scheme (`{nf:[char]:[nerd]:[emoji]}`):**
  Always resolve icon definitions following the strict 4-tier hierarchy:
  1. *Emoji tier*: Selected first if defined and `settings.use_nerd_fonts` is enabled.
  2. *Nerd Font tier*: Selected second if hex token defined (`#`, `$`, `0x`) and Nerd Fonts enabled.
  3. *Character tier*: Selected third if defined (e.g., `{nf:#}` -> `#`) or when Nerd Fonts are disabled.
  4. *Fallback*: Empty string if unconfigured.
- **Icon Slot Width & Text Alignment Invariant:**
  - Every menu option icon slot must occupy exactly **4 columns** of visual width (`vis_w + pad_w = 4`):
    - 2-column wide emojis (`🚀`, `🎮`, `📥`, `🌐`, `❓`, `🚪`): `vis_w = 2, pad_w = 2` (`f"{icon}  "`).
    - 1-column glyphs and text symbols (`󰖟`, `⚙`, `ℹ`, `🌤`, `#`): `vis_w = 1, pad_w = 3` (`f"{icon}   "`).
    - No icon: 4 spaces (`"    "`).
  - All menu item names/descriptions must strictly align vertically at column 11 (`prefix_w = 10` for single-digit shortcuts).
- **Variation Selector Normalization (`\ufe0f`, `\ufe0e`):**
  - Always strip Unicode Variation Selectors (`.replace('\ufe0f', '').replace('\ufe0e', '')`) from resolved icons prior to display width measurement and rendering.
  - Monospace terminal fonts render text symbols (`⚙`, `ℹ`, `🌤`) in single-column cells. Stripping variation selectors guarantees that `rich.cells.cell_len()` and terminal emulator cursor movement remain identical.
- **Menu Inner Textual Buffer & Window Border Protection:**
  - `MainMenuView` must treat all inner rows (options, dividers, status gutter) as an isolated inner textual screen buffer bounded to `avail_w = window_width - 6`.
  - Inner content must be clamped (`truncate(avail_w)`) and padded to `avail_w` before attaching border characters (`"│  "` and `"  │\n"`), ensuring menu lines can never push out, wrap, or displace window borders.
- **Elements:** Must accommodate a border, title, menu text, shortcut
  badges, and a help/status gutter (located just above the bottom
  border).
- **Plugin Buffer Widget:**
  - The plugin display area must be an independent, undecorated Textual
    buffer (`PluginBuffer`) placed at least one line above the gutter.
  - Buffer width must equal `window_width - 6` (margins + borders).
  - Sizing must be dynamic, growing with content up to a max of 10 rows.
  - The widget background and padding spaces must match the active theme's
    background.
  - Strip Unicode Variation Selectors (`\ufe0f`, `\ufe0e`) from external
    plugin text to eliminate terminal cursor drift and border overflow.
- **Textual CSS Rules:**
  - Always prefix Textual CSS variables with `$` (e.g. `$surface`,
    `$surface-darken-1`). Never write bare variable names without `$`.

## Behavioral Instructions
1. **Brevity First:** Explain all concepts and technical topics as
   briefly as possible while maintaining complete clarity.
2. **Strict Verification:** Always double-check your code. Run the
   `ruff` linting tool frequently on Python files to enforce quality.
3. **No Guessing:** Never assume or guess. If any detail or requirement
   is unclear, stop and ask the user for clarification immediately.
4. **Theme Management:** When handling the theme selection workflow
   (`Main Menu -> Options & Settings -> Bashmenu Settings -> Change
   Theme`), dynamically load defined themes. Upon selection, update the
   `theme:` key inside `bashmenu.yml`.
5. **Theme Color Conversion for Textual CSS:** When passing theme
   backgrounds or colors from Rich Styles to Textual widget styles
   (`widget.styles.background`), never pass raw color names like
   `'color(19)'`. Always convert 8-bit palette indices to hex color
   strings via `color.get_truecolor()`.
6. **Theme Palette Design & Validation:**
   - **Aesthetics & Tone:** When introducing new themes, design cohesive,
     low-fatigue, balanced palettes (such as `tokyo_night`, `nord`, `everforest`).
     Avoid garish, oversaturated, or clashing combinations (e.g., neon red/yellow
     like `hotdog_stand`) unless explicitly requested.
   - **Schema & Depth Constraints:** Always run
     `python3 ymlcheck.py --themes bashmenu.themes` to verify that 16-color mode
     indices remain within `0..15` (or valid `COLOR_*` constants) and 8-color mode
     indices remain within `0..7`. Never use 256-color indices (e.g., `255`) in
     16 or 8-color sections.
7. **Portable Paths & Macro Invariant:** Never hardcode absolute user
   paths (such as `/home/andrew/`) in menu configurations
   (`bashmenu.mnu`), templates, or launcher scripts. Always utilize
   expanding placeholder macros: `{home}`, `{bashmenu_dir}`,
   `{scripts_dir}`, `{templates_dir}`, and `{cache_dir}`.
8. **Dependency & Virtualenv Hygiene & Ruff Invariant:** Because `bashmenu` is built on
   Textual and Rich, `requirements.txt` must always declare `textual`
   and `rich` alongside `PyYAML` and `ruff`. Never remove `ruff` from
   `requirements.txt`. Run `ruff check .tests/` alongside test suites with every
   Python modification. `bashmenu.sh` venv verification commands must validate
   `yaml, ruff, textual, rich` before marking the environment ready. Keep required
   system packages to an absolute minimum (`python3` + `curl`). Never mandate external
   CLI utilities like `glow`, `jq`, or `yq` in root shell scripts; always
   prefer in-house Python standard library fallbacks (`json`, `urllib.request`)
   to guarantee out-of-the-box compatibility on Termux (Android), Raspberry Pi,
   and Windows (Git Bash/WSL).
9. **Test Suite Organization & Import Standard:** All unit and
   integration test scripts must strictly reside inside the `.tests/`
   directory (named `test_*.py`). Never place test scripts in the root
   or scripts directory. Test files in `.tests/` must dynamically resolve the
   project root using `sys.path.insert(0, os.path.abspath(os.path.join(
   os.path.dirname(__file__), "..")))`. Always verify tests using
   `python3 -m unittest discover -s .tests -p "test_*.py"`.
10. **Scripts Directory Invariant:** All extension scripts, standalone
    games, sub-applications, and plugins must reside inside `scripts/`,
    never in the root directory. Action commands in `bashmenu.mnu` that
    launch them must reference them via `{scripts_dir}/<script_name>`.
11. **YAML Validation Modes (`ymlcheck.py`):**
    Running `python3 ymlcheck.py <file>` without flags defaults to verifying
    pure YAML syntax with no schema enforcement. To run schema checks, use:
    - `--themes` / `-t` for `bashmenu.themes`
    - `--config` / `-c` for `bashmenu.yml`
    - `--menu` / `-m` for `bashmenu.mnu`
12. **Template Sanitization & Macro Expansion:**
    All template files under `templates/` must remain completely generic and
    portable. Never commit personal SSH host aliases, personal IPs, or
    hardcoded username paths. Always use expanding placeholders (`{home}`,
    `{bashmenu_dir}`, `{scripts_dir}`). Any personal configuration examples
    must be commented out with clear explanatory notes.
13. **Selection Modals UX Standard:**
    When prompting users to select from a predefined list of choices (such as
    themes, categories, or actions), do not use freeform text inputs
    (`InputModalScreen`). Always prefer an `OptionList`-based modal screen
    (such as `ThemePickerModalScreen`) that indicates the active selection and
    supports keyboard navigation and Enter/Click selection.
14. **Placeholder Dictionary Completeness:**
    Every placeholder documented in `bashmenu_ui.py` (`PLACEHOLDER_SECTIONS`)
    and the user manual must have a corresponding active mapping in
    `interpolate_placeholders()` in `bashmenu.py`. When modifying constants
    or cache durations (such as `_CMD_CACHE_TTL`), update both `bashmenu.md`
    and `bashmenu.1` to maintain synchronization.
15. **Cross-Platform Browser Dispatch Standard (`webopen.sh`):**
    - Browser launcher scripts must support `--gui` / `-g` (graphical) and
      `--tty` / `tty` / `-t` (console/terminal) interface flags.
    - Never pass `"about:blank"` to system openers (`exo-open`, `xdg-open`),
      as desktop openers reject it with "Failed to open URL" errors. When no
      target URL is specified, launch the browser executable or desktop verb
      directly (e.g., `exo-open --launch WebBrowser`, `x-www-browser`).
    - Implement cascading fallbacks across platforms (Termux, macOS, WSL,
      X11/Wayland, Linux console) with graceful failover from GUI to terminal
      browsers (`brow6el`, `links`, `lynx`, `w3m`, `elinks`, `carbonyl`).
16. **Documentation Synchronization Invariant:**
    - Any new script utility, CLI flag, or layout feature must be
      simultaneously updated across `bashmenu.md`, `bashmenu.1` (man page),
      and `README.md`.
    - Man page and markdown docs must maintain lines wrapped under 80
      characters with a dry, professional tone without promotional hype.
17. **Terminal Keybinding Collision Invariant (Avoid `<F11>`):**
    Terminal emulators and window managers reserve `<F11>` globally to toggle
    fullscreen mode, intercepting the key before it reaches TUI event loops.
    Never bind `<F11>` for application shortcuts; use `<F12>` or alternate
    unreserved function keys.
18. **Rich & ANSI Terminal Pager Pipeline (`FORCE_COLOR` & `less -R`):**
    When piping Rich or ANSI-styled output into pagers such as `less`, terminal
    color detection is deactivated by Rich because stdout is a pipe. To preserve
    color rendering without printing raw escape codes:
    - Set `export FORCE_COLOR=1` (or pass `--force-terminal`).
    - Pass `-R` (or `-r`) to `less` to interpret raw ANSI color escape sequences.
    - Always resolve script directories portably (using `BASH_SOURCE[0]`) rather
      than hardcoding paths.
    - Standardize markdown document rendering and pagination on
      `{scripts_dir}/rich.sh <file> | {scripts_dir}/pager.sh` rather than
      third-party binary viewers (`glow`).
19. **Menu Editor Schema & Property Inspector Completeness (`menuedit.py`):**
    The visual editor's property inspector (`update_inspector()`) and edit
    modal (`ItemEditModal`) must support the complete `bashmenu.mnu` schema:
    - Explicitly render `alt_buffer`, `no_formatting`, `start_dir`, `picker`,
      `on_yes`, and `on_no`.
    - Track all flags (`stream`, `quiet`, `interactive`, `show_whitespace`,
      `masked`, `refresh`, `external`, `display_theme_colors`).
    - Include an "Extra Properties" fallback for author-defined custom attributes.
    - Ensure `#inspector_panel` uses `overflow-y: auto;` and `#inspector_content`
      uses `height: auto;` for scrollable inspection.
    - **Menu Item Type Mutation & Key Remapping:** Menu items must allow full type
      reconfiguration post-creation. Support type switching both inside
      `ItemEditModal` (`[CTRL+T]`) and directly from tree nodes in `MenuEditScreen` (`[t]`).
    - **Payload Migration & Key Shadowing Prevention:** When an item's type changes,
      migrate the action payload to the target type's canonical primary key
      (`command`, `script`, `editor` -> `file`, `config`/`toggle` -> `key`, `python`)
      and prune obsolete type keys to prevent payload pollution.
    - **Submenu & Divider Transitions:** Converting to `submenu` must initialize
      `submenu: {title: ..., options: []}`; converting from `submenu` to a leaf item
      must prune the container block and trigger `populate_tree()` to refresh tree hierarchy.
      Transitions between `divider` and standard items must dynamically toggle
      section visibility and clean up divider directives (`char`, `length`).
    - **Safe App Instance Resolution:** Always resolve application instances via
      `app_obj = getattr(self, "_app", None) or getattr(self, "app", None)` before
      calling `push_screen()`, preventing `NoActiveAppError` in headless unit test
      harnesses.
20. **Menu Editor Two-Line Help Bar Layout (`menuedit.py`):**
    The visual menu editor's bottom help bar (`#footer`) must be configured
    as a two-line `Vertical` container with `height: 2` containing two
    `Horizontal` rows (`.footer_row` with `height: 1; align: center middle;`):
    - Row 1: Item operations & reordering (`[a] Add`, `[e/ENTER] Edit`, `[t] Type`,
      `[SPACE] Toggle`, `[d] Delete`, `[m] Move Dn`, `[M] Move Up`).
    - Row 2: Hierarchy adjustments, tools, & session control (`[>] Indent`,
      `[<] Outdent`, `[CTRL+A] ASCII`, `[CTRL+P] Placeholders`, `[s] Save`, `[ESC/q] Exit`).
    - Keep interactive widget IDs (`lbl_*`) intact for click handlers and theme styling.
21. **OpenCode Sub-Agent Delegation Policy:**
    When delegating tasks to the local `opencode` CLI:
    - Use sparingly and exclusively for small, low-risk, self-contained jobs
      (e.g., test case drafts, isolated script prototypes).
    - Treat all generated output as untrusted draft code requiring strict review,
      lint verification (`ruff`), and automated test validation before committing.
    - Always display the prompt and review output transparently with the user.
22. **Editor Theme Color Code Inversion & Contrast Invariant (`bashedit.py`):**
    When `--display-theme-colors` is enabled in `bashedit.py` (e.g. editing `bashmenu.themes`):
    - Check if the rendered text color matches the active theme background.
    - If the text color matches the active theme background, invert foreground and background
      styling using the other token in the color pair (`color=css_tok, bgcolor=css_other`).
    - If both foreground and background values of the pair match the current theme background
      (e.g., `[16, 16]` on dark background or `[19, 19]` on `qbasic`), select a neutral primary 8
      color value (`white` on dark backgrounds, `black` on light backgrounds) for contrast.
    - Fall back to the neutral primary 8 color if the paired color lacks adequate contrast.
    - **Whitespace Character Stylization (`whitespace` / `whitespace_color`):**
      * When `show_whitespace` is toggled (`Alt+1`), non-visible whitespace characters (space `'·'`,
        tab `'→'` plus tabstop padding, carriage return `'↵'`, and newline `'↵'`) must be stylized
        using the theme's `whitespace` (or `whitespace_color`) palette token.
      * If no whitespace style is defined, it falls back to a standalone default (`dim white` /
        `Style(color="white", dim=True)`), without falling back to theme gutter or shadow.
      * This ensures whitespace markers appear in a subtle, slightly darker/dimmer shade than
        standard text without competing for contrast.
      * Whitespace styles are applied before selection highlights (`sel_style`) and cursor inversions
        (`reverse bold`), guaranteeing that cursor movement and text selections remain clearly visible.
23. **Headless Execution & Shell Script Source Guarding:**
    Main shell scripts (`bashmenu.sh`) must provide source guards
    (`if [[ "${BASH_SOURCE[0]}" == "${0}" ]]`) and non-interactive inspection flags
    (`--check-env`, `--help`, `--version`) that exit cleanly (0 on success) without
    launching the TUI.
24. **Branching Discipline for Substantial Refactors:**
    When performing extensive structural overhauls (cross-platform compatibility,
    dependency elimination, or editor re-architecture), always branch from git
    (e.g., `feat/<topic>`) and verify all test suites and linters pass before merging.
25. **Markdown Documentation Standards (Tables & Collapsible TOC):**
    - Description lists across documentation (options, flags, parameters, fields) must be
      formatted as GitHub-Flavored Markdown tables rather than indented/unaligned bullet lists.
    - Long-form markdown documentation (such as `bashmenu.md`) should feature a collapsible
      `<details><summary><b>Table of Contents</b> (click to expand)</summary>...</details>`
      block with anchor links for major sections.
    - Code block fences must always have an empty line before them to prevent markdown
      renderers (like Rich) from inlining the code block into the preceding line.
26. **Rich Hyperlink Rendering & Terminal Capabilities (`scripts/rich.sh`):**
    - To render clean terminal hyperlinks (OSC 8) without polluting text with raw anchor URLs:
      * Pass `-y` (`--hyperlinks`) to `rich.markdown`.
      * Rich suppresses colors and hyperlinks if `TERM` is `dumb` or unset. Shell wrappers
        must ensure `TERM` is upgraded to `xterm-256color` and `COLORTERM=truecolor` when
        `TERM` is unset, `dumb`, or `unknown`.
27. **Textual Modal Performance vs. Widget Overkill (`bashmenu_ui.py`):**
    - Avoid using Textual's built-in `Markdown` widget for large documentation documents.
      Textual's `Markdown` decomposes the document into a tree of individual DOM widgets
      (e.g., 784 widgets for `bashmenu.md`), leading to severe CPU overhead (~5-second lag
      on modal mount and choppy scrolling).
    - Use `Static` containing `rich.markdown.Markdown(text, hyperlinks=True)` instead. It
      renders the entire document as a single native widget (under 0.1s load time, smooth
      60 FPS scrolling).
    - Textual's Click events automatically populate `event.style.link` and
      `widget.get_style_at(x, y)` from Rich's rendered styles. Use this to handle link clicks
      directly.
    - For internal anchor links (`#...`), compute/cache line offsets on-demand via
      `Console.render_lines()` and scroll the container (`scroller.scroll_to(y=...)`).
    - If using Textual's `Markdown` widget anywhere, always pass `open_links=False` to prevent
      Textual's default `open_links=True` from unconditionally launching the system web
      browser on internal `#anchor` clicks.
28. **Terminal Pager Standards & Spool Location (`scripts/pager.sh`):**
    - Temporary spools must strictly reside inside `${CACHE_DIR:-${HOME}/.cache/bashmenu}/spool`
      without falling back to `/tmp`. An immediate `trap 'cleanup' EXIT INT TERM HUP`
      must be installed upon spool creation to guarantee spool deletion on all exit paths.
    - The bottom status bar must use a balanced 3-segment row:
      * Left: Position and line range (`TOP  1-23/100`).
      * Center: Centered badge displaying `[ filename.ext ]` (for files) or `[ <stdin> ]`
        (for piped streams).
      * Right: Alert messages or key hints, dynamically condensed or suppressed on narrow
        terminals to prevent badge overlap while guaranteeing line width equals `COLS`.
    - Main invocation must be guarded with `if [ "${BASH_SOURCE[0]}" = "${0}" ]; then main "$@"; fi`
      to enable safe sourcing in automated tests.
    - Support interactive link selection (`l` / `o`), normalized heading jumps (`#...`),
      forward searching (`/`, `n`, `N`), and safe character grabbing (`grab_char`).
29. **Macro Interpolation Performance & Lazy Probes (`bashmenu.py`):**
    - `interpolate_placeholders()` must short-circuit immediately if `not text or "{" not in text`,
      bypassing regexes and string replacements for plain labels, dividers, and icons.
    - Expensive system probes (such as sysfs battery scanning in `get_battery_info()` and
      outbound socket probing in `get_primary_ip()`) must only be evaluated if their specific
      placeholder token (`"{battery}"`, `"{localip}"`) is present in the target string.
    - Never execute network socket probes (`get_primary_ip()`) at module import time.
30. **Sub-Editor Lazy-Loading Standard (`bashmenu.py`):**
    - Heavy standalone editors (`bashedit.py`, `menuedit.py`) must never be imported at
      module top-level in `bashmenu.py`.
    - Always import them on-demand inside their respective execution actions
      (`action_open_editor`, `action_menu_editor`, `run_curses_editor`), saving ~150ms
      of cold-start module import time.
31. **Self-Healing Launcher Fast-Path (`bashmenu.sh`):**
    - Use pure POSIX `awk`/`grep` as Layer 1 in `yaml_get()` for simple scalar settings
      (`settings.cache_dir`, `settings.check_for_updates`) to eliminate ~200ms of Python
      subshell bootstrap latency.
    - Maintain a `.venv/.ready` stamp created upon successful environment verification.
    - On normal launches without setup flags, bypass tool inspection loops and directly
      execute Python.
    - The fast path must self-heal (remove `.ready` and drop into full recovery setup) if:
      * `requirements.txt` is newer than `.ready` (`requirements.txt -nt .ready`).
      * A required system binary (`curl`, `python3`) is missing.
      * Python fails to execute or exits due to broken virtualenv dependencies.
      * The user explicitly invokes `--setup`.
32. **ShellCheck Linting Protocol (`shellcheck`):**
    - Frequently run `shellcheck` across all project shell scripts (`bashmenu.sh`,
      `install.sh`, `uninstall.sh`, and `scripts/*.sh`).
    - When lint warnings or potential POSIX/bash portability pitfalls are detected,
      inspect the scripts, present the findings and proposed fixes clearly to the user,
      and make repairs only upon explicit user approval.
33. **Documentation Parity & Macro Registry Invariant:**
    - There must always be 100% parity across all project documentation and modal
      help screens whenever placeholders, macros, directives, or attributes are
      introduced, updated, or modified.
    - Full synchronization must strictly encompass all six documentation tiers:
      1. `bashmenu_ui.py`: `PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT`
         (displayed in `bashedit.py` via `^P`/`Alt+M` and `menuedit.py` via `^P`/`F4`).
      2. `menuedit.py`: `ITEM_EDIT_HELP_TEXT` (modal item property inspector guide
         invoked via `F1`/`?`).
      3. `bashedit.py`: `action_help_manual` (`F1`/`Ctrl+G`/`Alt+H`) keybinding help list.
      4. `bashmenu.py`: `action_help` in-app help modal (`F1`, which renders `bashmenu.md`).
      5. `bashmenu.md`: Complete Markdown reference documentation (Sections 6.1 and 6.2).
      6. `bashmenu.1`: Linux system man page (`DYNAMIC DIRECTIVES & SYSTEM PLACEHOLDERS`).
    - Every dynamic input directive (`{param}`, `{file_picker}`, `{file_picker_new}`,
      `{dir_picker}`, `{dir_picker_new}`) and all supported attributes (`title`, `prompt`,
      `masked: true/false`, `start_dir`) must be documented in all six tiers.
    - All directory aliases (`{scripts}`, `{templates}`, `{cache}`) must be documented
      alongside canonical paths (`{scripts_dir}`, `{templates_dir}`, `{cache_dir}`).
    - Hardware and network placeholders (`{battery}`, `{localip}`) must be documented with
      their caching characteristics and on-demand evaluation behavior.
    - Configuration placeholders support the explicit namespace `{app.<key>}` (e.g. `{app.theme}`,
      `{app.settings.tabstop}`, `{app.user.postal_code}`) in addition to shorthand forms
      (`{theme}`, `{settings.<key>}`, `{user.<key>}`). `bashmenu.yml` includes a documented
      header comment preserved across `save_config()` writes.
    - Every newly added macro must include automated assertion coverage in
      `.tests/test_improvements.py` (`test_placeholder_documentation_parity`).
34. **Theme Window Border & Divider Customization (`window:` and `divider:` in `bashmenu.themes`):**
    - Themes can optionally define an outer window frame character override dictionary
      under a top-level `window:` key, and a horizontal divider specification under `divider:`.
    - Supported window keys: `border_horizontal_top`, `border_horizontal_bottom`,
      `border_vertical_left`, `border_vertical_right` (with `border_horizontal` and
      `border_vertical` as shorthands/fallbacks), `border_top_left`, `border_top_right`,
      `border_bottom_left`, `border_bottom_right`, `border_tee_top`, `border_tee_bottom`,
      `border_tee_left`, `border_tee_right`, `left_tee`, `right_tee`, `top_tee`, `bottom_tee`,
      `border_cross`, `title_left_cap`, `title_right_cap`, and `shadow_char` (also accepts
      `window_*` / `window_border_*` prefix).
    - Omitted keys seamlessly fall back to default box drawing characters (`┌─┐│└┘`, tees, and brackets `[` / `]`).
    - Values are resolved through `interpolate_placeholders` and `resolve_glyph`,
      supporting CP437 ASCII macros (e.g. `{ascii:223}` for top half block `▀`, `{ascii:220}`
      for bottom half block `▄`, `{ascii:221}` for left half block `▌`, `{ascii:222}` for right
      half block `▐`, and `{ascii:181}`/`{ascii:198}` for `╡ Title ╞`). Unicode Variation Selectors
      (`\ufe0f`, `\ufe0e`) must be stripped prior to measurement.
    - `ymlcheck.py` enforces that `window:` and `divider:` are valid sections and validates all
      child properties.
    - Global Textual border synchronization: `apply_theme_to_textual_borders` in `bashmenu_ui.py`
      synchronizes `textual._border.BORDER_CHARS['thick']` and `['solid']` and clears Textual's
      box cache (`get_box.cache_clear()`), ensuring all modal dialogs across `bashmenu_ui.py`
      and panel borders in `menuedit.py` dynamically honor the active theme's borders.
    - **Divider Styling, Placement & Width Semantics**: Dividers are strictly independent
      of window borders (`window.border_horizontal` must never bleed into or override dividers).
      Divider styling (`char` glyph, `length`, and color) is defined **strictly in the themes file**
      (`bashmenu.themes`) as the single source of truth.
      1. *Theme Definition (`bashmenu.themes`)*: Defined under each theme's `divider:` block.
      2. *Default Fallback*: If not defined by the active theme, defaults to `char: "{ascii:196}"` and `length: "{window_width}"`.
      3. *Strict `{divider}` Syntax*: Menu items must declare dividers strictly using `type: "{divider}"`
         (or unquoted `type: {divider}`). Plain `"divider"` is **not** recognized.
    - **Divider Presence**: Dividers only appear in a menu if explicitly declared as an option (`type: "{divider}"`)
      in `bashmenu.mnu`. If no dividers are declared in `bashmenu.mnu`, no dividers are rendered in that menu.
      Plugins in `bashmenu.yml` place dividers using `pretext: "{divider}"` or `posttext: "{divider}"`.
    - **Divider Width Modes**:
      * `{window_width}`: Standard shorter divider bounded within window borders and 2-space margins
        (`avail_w = max(20, w - 6)`). Framed by standard vertical borders (`border_vertical_left`/
        `border_vertical_right`) with 2 spaces on each side, and **without** border tees.
      * `{screen_width}`: Full-width divider running from left border to right border (`w - 2`),
        overriding all margins. Connects directly to `left_tee` (`border_tee_left`) on the left and
        `right_tee` (`border_tee_right`) on the right without margin spaces. Themes defining
        `{screen_width}` dividers must set the divider foreground color to match the border color.
    - **Dynamic PluginBuffer Geometry & Text Alignment**:
      * When a theme defines `{screen_width}` dividers, `PluginBuffer` dynamically expands to
        `screen_div_w = max(20, w - 2)` and shifts left to `x = 1` (immediately inside the border).
      * Plugin dividers (`pretext: "{divider}"` / `posttext: "{divider}"`) seamlessly span border-to-border.
      * Regular plugin text lines are indented with 2 leading spaces (`"  "`), maintaining strict visual
        alignment with menu option columns.
35. **Menu Definition Schema (`bashmenu.mnu`) & Serialization Standards**:
    - **`items:` Key Hierarchy**: `items:` replaces `options:` across all menu files and submenus.
    - **Label-as-Key Item Structure**: Each menu entry is declared with its label as the parent key:
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
    - **Lean Defaults Invariant**: Prune redundant default flags when authoring and serializing:
      omit `stream: false`, `masked: false`, `show_whitespace: false`, `refresh: false`,
      `no_formatting: false`, `external: false`, `alt_buffer: false`, non-editor `tabstop`,
      and duplicate `command` keys.
    - **Runtime Normalization (`normalize_menu_items`)**:
      `normalize_menu_items()` in `bashmenu.py` canonicalizes both new label-as-key items and
      legacy dicts into internal dictionary representations (`label`, `type`, `action`, `submenu`),
      and aliases `items` into `options` for internal UI compatibility.
    - **Strict Divider Representation**: Dividers are represented as scalar `'{divider}'` or
      single-key mapping `'- \'{divider}\':'`. Plain `"divider"` is never recognized.
    - **Centralized Serialization (`dump_menu_yaml`)**:
      Both `bashmenu.py` and `menuedit.py` serialize menu data via `bashmenu.dump_menu_yaml()`,
      utilizing `IndentedDumper` to ensure clean 2-space indented sequences under `items:`.
    - **Validation (`ymlcheck.py`)**: `ymlcheck.py -m <file>` validates `items:` blocks,
      ensuring valid label keys, proper submenu recursion, and strict `{divider}` syntax.
36. **Modal Drop Shadow Architecture (`ModalFrame` & `ShadowWidget`):**
    - **Classic DOS/TUI Drop Shadow Geometry**:
      Modal dialogs are framed with an authentic 2-cell right shadow and 1-row bottom shadow:
      * Right shadow: 2 columns wide, offset 1 row down from top (`y = start_y + 1` to `start_y + box_h`).
      * Bottom shadow: 1 row high, offset 2 columns right from left edge (`x = start_x + 2` to `start_x + box_w + 2`).
    - **Theme Integration & Shading Character**:
      * The shadow character is retrieved from `window.shadow_char` or `DEFAULT_WINDOW_BORDER` (default `░`).
      * Foreground and background colors are applied from each theme's `shadow: [fg, bg]` definition.
      * Modals also apply a dimmed screen backdrop (`screen.styles.background = f"{css_shadow} 60%"`).
    - **Widget Hierarchy & Selector Invariants**:
      * Modals wrap their `#dialog` inside `ModalFrame(id="modal_frame")` and `Horizontal(id="dialog_hrow")`,
        placing `ShadowWidget(id="shadow_right")` beside `#dialog` and `ShadowWidget(id="shadow_bottom")`
        beneath.
      * All widget IDs (`#dialog`, `#title`, `#message`, `#buttons`, `#btn_ok`, `#scroll_container`,
        `#form_scroll`) remain direct query targets via `screen.query_one()`.
    - **Dynamic Resizing & Geometry Syncing**:
      * `ModalFrame.sync_shadows()` reads `dialog.outer_size` and dynamically syncs `shadow_right.styles.height`
        to `outer_size.height - 1` and `shadow_bottom.styles.width` to `outer_size.width`.
      * Size changes are reactively observed via `watch(dialog, "size")` and `on_resize()`.
    - **Universal Modal Coverage (Including Help Screens)**:
      * All modal dialogs without exception render drop shadows.
      * For expanded help modals (`is_help=True`, `MessageModalScreen.help_modal`), `#modal_frame` is sized
        to `95% width` and `95% height` with `#dialog_hrow` at `1fr 1fr` and `#dialog` at `1fr 100%`,
        ensuring full-screen documentation (main menu `F1`, editor manual `F1`/`Ctrl+G`, placeholder
        reference `Ctrl+P`/`F4`, item properties guide `F1`) displays clean drop shadows without overflowing
        the terminal viewport.
37. **Status and Help Gutter Wrapping & 50% Width Invariant (`MainMenuView`):**
    - **50% Width Limit**: Neither the status gutter (right-aligned) nor the help
      gutter (left-aligned) should ever exceed 50% of the screen width
      (`max_gutter_w = max(5, avail_w // 2)`).
    - **Pipe Delimiter Wrapping (`wrap_gutter_items`)**: Both gutters treat text
      between pipe symbols (`|`) as atomic single words/badges. When adding an item
      exceeds 50% width, overlapping text drops to the next line. Status gutter items
      wrap bottom-up, filling the bottom row first with as many badges as fit, and placing
      overflow on the line above (anchoring single-line status gutters to the bottom row).
    - **Two-Line Maximum Height**: Neither gutter should ever exceed two lines.
      Two lines is the maximum height allowed for the gutters (`max_lines=2`). Overflow
      beyond two lines is discarded.
    - **Dynamic Row Allocation & Screen Height Preservation**:
      * `gutter_rows = min(2, max(1, max(len(help_lines), len(status_lines))))`.
      * `total_content_rows = max(1, h - 4 - gutter_rows)`.
      * Total rendered lines strictly equals terminal height `h`.
38. **BBCode Rich Tags, Tables, and Lists (`bashmenu_ui.py`):**
    - **Formatting Tags**: Supports bracketed BBCode tags:
      * Inline styling: `[b]...[/b]`, `[u]...[/u]`, `[dim]...[/dim]`, `[reverse]...[/reverse]`, `[color=...]...[/color]`.
      * Structural tables: `[table]...[/table]`, `[tr]...[/tr]`, `[th]...[/th]`, `[td]...[/td]`. Renders tables using Unicode box-drawing borders (`┌─┬─┐`, `│ │ │`, `├─┼─┤`, `└─┴─┘`).
      * Table width & column distribution: `[table width=100%]` (or `width=full`) automatically divides available width equally across columns (e.g. 50/50 for 2 cols, 33/33/33 for 3 cols, 25/25/25/25 for 4 cols). Explicit integer widths (`width=60`) are also supported.
      * In-cell text wrapping: When column widths are constrained, cell text automatically wraps at word boundaries, increasing row height dynamically without breaking border alignment. When no width is defined, columns auto-fit to the longest string. Headers (`[th]`) are automatically bolded.
      * Structural lists: Unordered `[list][*]...[/list]` (bullet glyphs `• `), ordered `[list=1][*]...[/list]` (numbers `1. `, `2. `), and alphabetical `[list=a][*]...[/list]`. Closing `[/*]` tags are optionally accepted.
    - **Declarative Plugin Dashboard Layout (`settings.plugins.layout`)**:
      * Supports `type: table`, `width: "100%"`, `entries: N` (default 2), `headers: [...]`, and optional explicit `rows: [["plugin_a", "plugin_b"]]` under `settings.plugins` in `bashmenu.yml` to render plugins in a multi-column dashboard.
      * Multi-table chunking: If `entries: 2` is set and a 3rd plugin is encountered, a new table is constructed, spanning the screen on its own or grouping with subsequent plugins.
      * Standalone plugins: Plugins configured with `standalone: true` or `span: full` (e.g. Quote of the Day or system banners) render on their own line stretching across the screen without table borders.
      * Each plugin retains its own independent `sleep` interval and background thread polling without blocking the TUI.
    - **Backtick Suppression & Escaping**: Tags inside inline backticks (`` `[b]code[/b]` ``) or fenced code blocks are automatically suppressed and rendered literally. Backslash prefixing (`\[table]`) escapes parsing.
    - **`no_formatting` Flag**: Passing `no_formatting=True` to formatting conversion functions bypasses BBCode processing entirely.
39. **Cheat CLI Cheatsheet Manager (`scripts/cheat.sh`, `scripts/cheat.py`, `.cheat.yml`):**
    - **Architecture & Role:** `cheat` is a lightweight command-line cheatsheet manager that searches, lists, and displays Markdown cheatsheet files. It acts as an intelligent wrapper around `scripts/rich.sh` (which renders Markdown via Python Rich) and `scripts/pager.sh` (for interactive ANSI scrolling, link jumping, and reloading).
    - **Configuration (`.cheat.yml`):**
      * Stored in `scripts/.cheat.yml` (auto-generated with `dir: ~/cheat` if missing).
      * The `dir` key defines the root directory where Markdown cheatsheets are located (expands `~` portably).
    - **Search & Resolution Hierarchy (`cheat <query>`):**
      * *Priority 1a:* Exact relative path lookup (`<root>/<query>.md`).
      * *Priority 1b:* Filename stem or relative path match across all `.md` files (case-insensitive, `.md` suffix stripped).
      * *Priority 2:* YAML frontmatter tag match. Parses frontmatter headers (`--- ... ---`), supporting both YAML lists (`tags: [git, vcs, undo]`) and comma-separated strings (`tags: git, vcs, undo`). Matches if `<query>` is in the extracted tags (e.g. `cheat bash` matches `bash.md` or any cheatsheet tagged with `bash`).
      * *Priority 3:* Full-text content match across markdown file bodies.
    - **Display Pipeline (`display_markdown`):**
      * Once matched, dispatches to `scripts/rich.sh <file_path>`, passing through `scripts/pager.sh` with interactive ANSI paging, terminal width auto-detection, and `--reload-cmd`.
      * Gracefully falls back to stdout printing if `rich.sh` is unavailable.
    - **List & Search Modes (`-l` / `--list`, `-s` / `--search`):**
      * `cheat -l`: Lists all available cheatsheet files and their frontmatter tags in two neatly aligned columns: relative path on the left and `[tag1, tag2]` on the right.
      * `cheat -l <query>` / `cheat -s <query>`: Filters and lists only matching files and their tags.
    - **Environment & Launcher (`scripts/cheat.sh`):**
      * Resolves symlinks canonically using `BASH_SOURCE[0]`, sets `LC_ALL=en_US.UTF-8`, enters the script directory with `pushd`/`popd`, activates `.venv` if present, and dispatches to `cheat.py`.
40. **Script Header Standardization & Complete Documentation Parity (`scripts/`):**
    - **Standardized Header Banners:** Every shell script inside `scripts/` (and root
      launchers like `bashmenu.sh`) must feature a standardized comment banner at the top:
      ```bash
      #!/usr/bin/env bash
      # ==============================================================================
      # SCRIPT: <script_name>.sh
      # DESCRIPTION: <Brief, dry, and concise summary of utility functionality>
      # ==============================================================================
      ```
      The `SCRIPT:` name must strictly match the actual filename on disk. Python scripts
      in `scripts/` must feature a comprehensive top-level module docstring (`"""..."""`)
      explaining script purpose, dependencies, and command-line usage.
    - **Universal 3-Tier Documentation Registration:** Whenever any script utility is
      introduced or modified, it must be documented simultaneously across all three
      documentation tiers:
      1. `bashmenu.md`: Section 1 (Component Table for root scripts) or Section 2.1
         (`Provided Utility Scripts (scripts/)` table).
      2. `bashmenu.1`: Under `COMPONENT FILES` or `.SS Provided Utility Scripts (scripts/)`
         with `.TP` and `.I scripts/<name>`.
      3. `README.md`: Under `Component Directory` or relevant quick-start references.
    - **Tone & Formatting Constraints:** Descriptions must remain dry, professional, and
      free of promotional hype. Man page and markdown table lines should remain wrapped
      under 80 characters where applicable.
    - **Automated Parity Verification:** When new scripts are added, ensure unit tests in
      `.tests/test_improvements.py` assert that all non-hidden executable scripts in
      `scripts/` have corresponding documentation entries in both `bashmenu.md` and
      `bashmenu.1`.
41. **Inactivity Timeout & Screensaver Architecture (`settings.inactivity_timeout`):**
    - **Configuration & Lean Default Invariant:**
      * Configured under `settings.inactivity_timeout` with `milliseconds` (integer/float) and optional `command` (string).
      * **No Default Command Invariant:** The default configuration in `bashmenu.yml` must **not** include a `command` argument (specifying only `milliseconds: 300000`). If `command` is omitted, `null`, or empty, the timeout subsystem must remain dormant (no timer task scheduled).
    - **Textual Event Interception & Countdown Resets:**
      * `BashMenuApp.on_event` must intercept all `events.Key` and `events.MouseEvent` (`MouseMove`, `MouseDown`, `MouseUp`, `Click`, `MouseScrollDown`, `MouseScrollUp`) before event dispatch, resetting countdown timers via `timer.reset()` with zero allocations.
    - **Alternate Screen Buffer & Subprocess Isolation:**
      * Executed screensavers or idle scripts must run inside an alternate terminal screen buffer (`\x1b[?1049h\x1b[H\x1b[2J`) with Textual suspended (`with self.suspend():`).
      * Always restore the primary screen buffer (`\x1b[?1049l`) in a `finally` block, catch `KeyboardInterrupt` gracefully, repaint the UI via `self.refresh(layout=True)`, and re-arm the inactivity countdown upon exit so terminal lines and menu layout remain undisturbed.
    - **Headless & ScreenStack Safety Patterns:**
      * Before invoking `self.suspend()`, verify `hasattr(self, "_driver") and self._driver and getattr(self._driver, "can_suspend", False)` to support headless pilot testing.
      * Avoid bare `self.screen` queries when screens may be unmounted; wrap lookups with `contextlib.suppress(Exception)` and check `getattr(self, "_screen_stack", None)` to prevent `ScreenStackError`.
      * Always resolve application instances via `app_obj = getattr(self, "_app", None) or getattr(self, "app", None)` before calling `setup_inactivity_timer()`, preventing `NoActiveAppError` in headless test harnesses.
42. **TrueColor Half-Block Wallpaper Compositing & Pre-Baked Canvas (`settings.background`, `PrebakedWallpaperCanvas`):**
    - **Architecture & Terminal Standard Invariant:**
      * Half-block (`▀`) TrueColor compositing blends wallpaper graphics with text using ANSI escape codes. Strictly maintain pure standard terminal text compatibility; **never** introduce Sixel, Kitty Graphics Protocol, or iTerm2 escape dependencies.
    - **In-Memory Pre-Baked Canvas (`PrebakedWallpaperCanvas`):**
      * **Sub-Millisecond Assembly Invariant:** Navigation (arrow keys, scrolling, number shortcuts) must assemble frames in under 1 ms without executing dynamic string formatting, regex matching, icon width measurement, or pixel math.
      * **Pre-Baking Lifecycle:** Pre-bake static borders, margins, divider rules, and plugin placeholder rows on menu load or resize. Pre-bake both unselected (`is_selected=False`) and selected (`is_selected=True`) variants of visible menu options in memory.
      * **Content Blank Row Integrity:** When warming the canvas, pre-bake static blank rows (`│ ... │`) across all content rows (`3` to `3 + target_blank_rows`). In `assemble_frame()`, fall back to `_static_lines.get(y)` whenever `opt_idx >= num_options` to ensure exact window width and border integrity on menus with few options.
      * **Gutter Formatting Caching:** Cache rendered gutter lines (`raw_hg_lines`) against `gutter_key` so status and help text formatting only runs when the timestamp second ticks, avoiding redundant Rich text creation during rapid arrow key navigation.
    - **Differential Line & Status Decoupling:**
      * `set_current_row()` calculates visible screen row coordinates and issues `self.refresh(Region(0, y_old, w, 1), Region(0, y_new, w, 1))` when scrolling offset is unchanged, cutting terminal stdout bytes from ~36 KB down to ~600 bytes.
      * Periodic clock and plugin ticks must refresh only the bottom two status lines (`Region(0, max(0, h - 3), w, 2)`), decoupled from main wallpaper redraws.
    - **Horizontal Span Clustering & Quantization (`clustering`):**
      * Natural photographic wallpapers contain smooth micro-gradients that cause Rich to emit 24-bit escape codes for every individual cell, saturating the PTY buffer.
      * Built-in `clustering` (default `64`, range `0`–`128`) clusters adjacent cells with imperceptible color differences into unified Rich style runs.
      * Wallpapers must be pre-processed without Floyd-Steinberg dithering (`+dither` in ImageMagick, `--nofs` in `pngquant`) to prevent checkerboard stippling from defeating span aggregation.



## Documentation Guidelines
1. **Project Man Page:** Document the core functionality of the
   BashMenu project. Be verbose and detailed as possible. Include
   any arguments or parameters, return values, and expected behavior,
   if applicable. The language in the man page should be concise,
   simple, and clear. Keep lines wrapped under 80 characters, and keep
   the tone dry, no extraneous adjectives.
2. **Project Documentation:** Document the core functionality of the
   BashMenu project. Be verbose and detailed as possible. Include
   any arguments or parameters, return values, and expected behavior,
   if applicable. Explain the purpose and functionality of each
   configuration file, including `bashmenu.yml`, `bashmenu.mnu`,
   and `bashmenu.themes`. Explain the role and usage of {placeholder} 
   expanding macros. Be sure to include example usage of each
   placeholder. Be sure to document the usage of bbcode, with
   examples. Keep lines wrapped under 80 characters. in both the
   man page and markdown documentation. Keep the tone of the 
   documentation professional, dry, with no extraneous adjectives.
   For instance, don't describe an interface as "beautiful" or "cool,"
   just describe what it does. Don't oversell what the interface
   does.
3. **Code Documentation:** When writing code, include docstrings
   and comments to explain the purpose and behavior of each function,
   class, or module. Keep lines wrapped under 80 characters.
   Be sure no spaghetti code exists without proper comments and or
   docstrings. Docstrings should be written in the third person
   (e.g., "The `my_function` function does X.") and text lines should
   be wrapped under 80 characters. In-line comments can exceed 80
   characters for total line length, but should be brief when possible.
