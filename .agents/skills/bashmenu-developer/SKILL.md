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
- **Mandatory Git Commit & Push on All Changes:**
  - Every completed task, bug fix, feature addition, or refactoring step must conclude by creating a concise, descriptive git commit (`git commit -m "..."`) and pushing directly to GitHub (`git push`).
  - Never leave changes uncommitted or unpushed in the local repository.
  - After pushing to `origin/main`, inspect or verify GitHub Actions CI when appropriate using GitHub CLI (`gh run list`).
- **Configuration Header Preservation Invariant (`bashmenu.yml`):**
  - Never use raw `open(CONFIG_FILE, "w")` with `yaml.dump()` to persist settings to `bashmenu.yml`.
  - Always call `bashmenu.save_config(config)` so that `CONFIG_HEADER` comments, documentation, and placeholder references are cleanly preserved at the top of the file.
- **Verification & Linting:** Run `ruff check .tests/` and Python files frequently. Run `shellcheck *.sh scripts/*.sh` across shell scripts. Verify Python tests via `python3 -m unittest discover -s .tests -p "test_*.py"` and `pytest`.
- **GitHub Actions CI Workflow & Remote Test Verification:**
  - Automated testing and linting is offloaded to GitHub Actions:
    - Python testing & linting: `.github/workflows/python-app.yml` across Python 3.10, 3.11, and 3.12.
    - Shell script linting: `.github/workflows/shellcheck-app.yml`.
  - When testing changes, commit and push to `origin/main`, then track remote CI using GitHub CLI:
    - Query run ID: `gh run list --workflow=python-app.yml --limit 1 --json databaseId -q '.[0].databaseId'` (or `--workflow=shellcheck-app.yml`)
    - Inspect failures: `gh run view <ID> --log-failed`
    - Watch run: `gh run watch <ID>`
    - Invariant: Never run `gh run view` or `gh run watch` without an explicit run ID as interactive prompts hang non-interactive agent shells.
- **Style Cleanups & Dotfile Constraints:**
  - Resolve PEP 8 warnings (`F841` unused variables, `E741` ambiguous variable names like `l`, trailing whitespace) directly in the source code.
  - Do NOT introduce root `.flake8` configuration files unless explicitly requested by the user.
- **Directory Invariants:**
  - Tests: All unit/integration tests must reside in `.tests/` (`test_*.py`) and dynamically resolve project root via `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))`. Never place tests in root or `scripts/`.
  - Extension Scripts: Standalone games, plugins, and helper tools must reside in `scripts/`, never in root. Menu actions reference them via `{scripts_dir}/<name>`.
  - Notebooks: User notebooks and notes must reside in `notebooks/` (`{notebooks_dir}` / `{notebooks}`). `resolve_notebook_path()` checks `notebooks/` first before falling back to root.
- **Dependencies & Virtualenv Hygiene:** `requirements.txt` must declare all runtime and test dependencies (including `Pillow` for wallpaper compositing, `textual`, `rich`, `PyYAML`, `ruff`, `flake8`, and `pytest`). Keep system prerequisites to a minimum (`python3` + `curl`). CI runners install freshly from `requirements.txt`; ensure no test relies on unlisted packages. Prefer Python standard library (`json`, `urllib.request`) over external CLI tools (`glow`, `jq`, `yq`) for out-of-the-box compatibility on Termux, Raspberry Pi, and Windows (Git Bash/WSL).
- **Subprocess Test Environment Isolation:**
  - Tests executing shell scripts or wrapper binaries (`scripts/rich.sh`, `bashmenu.sh`) via `subprocess.run` must explicitly pass `PYTHON_BIN=sys.executable` and prepend `os.path.dirname(sys.executable)` to `PATH` in `env` to ensure multi-version CI runners (e.g. Python 3.10/3.11/3.12 under `pytest-xdist`) invoke the active virtual environment rather than system Python.
- **Unmounted Widget Property Access (`NoActiveAppError`):**
  - In Textual, accessing `widget.app` raises `textual._context.NoActiveAppError` if the widget has not been mounted in an active application.
  - In Python 3.8+, `getattr(widget, "app", None)` only catches `AttributeError`; because `NoActiveAppError` does not inherit from `AttributeError`, unhandled calls crash unmounted widget styling routines (such as isolated unit tests).
  - Invariant: When resolving `app` from an arbitrary widget, always wrap property retrieval:
    ```python
    app = None
    with contextlib.suppress(Exception):
        app = getattr(widget, "app", None)
    ```
- **Sub-Agent Delegation Policy:** Use local `opencode` CLI sparingly and strictly for small, low-risk draft tasks (test case drafts, isolated prototypes). Treat all output as untrusted draft code requiring strict review, linting, and automated test validation.
- **Branching Discipline:** For structural overhauls (cross-platform compatibility, editor re-architecture, dependency reduction), always branch from git (e.g. `feat/<topic>`) and verify all tests and linters pass before merging.
- **Textual UI Performance & Responsiveness Invariants:**
  - **CSS Invalidation Cascades:** Calling `DOMNode.remove_class()` / `add_class()` triggers `update_nodes()` across the entire DOM tree, causing up to 100ms+ synchronous lag on large forms. For collapsible sections or dynamic visibility, toggle `widget.display = True/False` directly and update `widget._classes` without invoking Textual's CSS recalculation engine.
  - **Scroll Visibility Animation & Focus Queuing:** `scroll_visible()` defaults to `animate=True` (200ms timer animation), and `Widget.focus()` defers via `call_later` while queuing an animated `scroll_to_center`. In keyboard navigation, focus jumps, and preview element clicks, pass `animate=False` and use `self.set_focus(widget, scroll_visible=False)` with a post-refresh instant scroll to eliminate latency completely.
  - **Immediate Mouse Interaction:** Handle `events.MouseDown` directly rather than waiting for `events.Click` (which only fires after `MouseUp` and is suppressed if the cursor shifts slightly during click) so users get instantaneous feedback without perceptible lag.
  - **Compositing & Render Caching:** In live preview widgets (such as `ThemePreviewWidget`), cache base composited lines (`_cached_base_lines`). On click or highlight flash feedback, clone only the affected line (`flashed[y] = flashed[y].copy(); flashed[y].stylize(...)`) rather than re-rendering background wallpapers or full canvas structures.
  - **Batch Updates:** Wrap compound operations (section expansion + scroll + focus) within `with self.app.batch_update():`.
- **Inline Macro Parameter Syntax & Help Parity:**
  - Macro placeholders may accept colon-separated inline configurations (e.g. `{file_picker:path:{bashmenu_dir}/assets/wallpapers}` or `{toast:3:"Message"}`).
  - When introducing or extending inline placeholder parameters, ensure full documentation parity:
    1. Update the Placeholders and Macros reference modal in `bashmenu_ui.py`.
    2. Update the manpage (`bashmenu.1`) and markdown guide (`bashmenu.md`).
    3. Ensure 6-tier variable interpolation (env, runtime, bashmenu config, system, theme, inline) functions correctly with nested placeholders.
- **Editor Swap File Placement Invariant:**
  - Built-in text editors must colocate temporary swap files (`.<filename>.swp`) directly in the exact directory of the file being edited.
  - Never store editor swap files in `/tmp` or user root; swap files must be cleanly deleted on save or exit, and detected on crash recovery.

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
- **Plugin Background & Divider Uniformity:**
  - In-plugin rows, in-plugin dividers, padding spaces, and top plugin dividers pre-baked on `PrebakedWallpaperCanvas` must explicitly apply `plugin_bg_color` / `plugin_bg_style` when a theme defines a plugin background (e.g. `mountain`).
  - Cells within the plugin domain must never leave `style.bgcolor is None`, as `composite_single_row` will otherwise treat them as transparent and composite them directly over wallpaper half-blocks.
- **50/50 Dual Marquee Partition Contract (`bashmenu.py`):**
  - **With Right-Aligned Bracket Directives (`[...]`):**
    - Available line width (`avail_w`) is strictly split 50/50 around the center:
      - Left partition: constrained from `0` to `center - 2` (`left_part_w = max(prefix_w + 1, center - 2)`).
      - Center margin: exactly 4 spaces (`"    "`) between `center - 2` and `center + 2`.
      - Right partition: constrained from `center + 2` to `avail_w` (`right_part_w = max(3, avail_w - (center + 2))`), right-aligned.
    - *Unselected Items:* Overflowing text in either partition is truncated with a Unicode ellipsis (`…`).
    - *Selected Items:* If the left label, right bracket, or both overflow their respective partitions, marquee scrolling activates simultaneously on both sides after a brief pause delay (4 ticks / 1.0 second).
  - **Without Right-Aligned Bracket Directives:**
    - The option text may utilize the entire available width up to `avail_w` (`label_avail_w = max(5, avail_w - prefix_w)`).
    - *Unselected Items:* Overflowing text truncates with an ellipsis (`…`).
    - *Selected Items:* Overflows marquee across the full available row width.
- **Microsecond Dynamic Compositing Invariant:**
  - Marquee animation ticks (250ms interval) must **NEVER** invalidate or recalculate the entire `PrebakedWallpaperCanvas` or background wallpaper grid.
  - Only the single active row line region (`Region(0, active_y, w, 1)`) is refreshed via Textual.
  - Dynamically composite the marqueeing raw line against the wallpaper grid for row `active_y` via `canvas.composite_dynamic_line(active_y, raw_active)`, leaving all static lines, borders, dividers, gutters, and unselected rows cached.

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
- **Theme-Configurable Marquee (`marquee:` in `bashmenu.themes`):**
  - Supported keys under `marquee:`:
    - `char`: Separator string or character repeated between cycles of scrolling text (e.g. `"~"`, `"•"`, `"»"`, `"·"`, `"-"`, `" "` or Nerd Font glyphs).
    - `gap`: Number of times `char` is repeated to form the spacer between loop cycles (integer >= 0, default `5`).
  - Fallback Standard: If a theme omits the `marquee:` section or if an unknown theme is queried, fall back strictly to 5 bullets (`char: "•"`, `gap: 5`).
  - Validation (`ymlcheck.py`): `validate_marquee_section()` enforces that `char` is a string and `gap` is a non-negative integer.
  - Theme Editor (`themeedit.py`):
    - Inspector exposes `prop_marquee_char` (with `btn_ascii_marquee_char` launching `AsciiPickerModal`) and `prop_marquee_gap`.
    - Modifying inputs dynamically synchronizes the live preview and sets the dirty state.
    - Saving persists the validated `marquee:` mapping to disk.
- **CP437 ASCII Macro Interpolation Invariant (`{ascii:NNN}`):**
  - Theme properties for borders, indicators, and marquee characters may specify CP437 byte codes using `{ascii:NNN}` macros (e.g. `{ascii:216}`, `{ascii:196}`).
  - Any code reading theme glyphs (`init_theme_colors`, `get_theme_marquee_config`, `MainMenuView._render_option_row`) must pass the string through `bashmenu_ui.parse_ascii_val()` (or equivalent regex replacement `r"\{ascii:\s*(\d+)\s*\}"`) before displaying or formatting.
  - Raw `{ascii:NNN}` strings must NEVER appear in the user-facing menu options, indicators, or status lines.
- **Theme Renaming, Deletion & Direct Save Invariants (`themeedit.py`):**
  - **Renaming:** Themes can be renamed in-place via `#prop_theme_name`, the adjacent `[Rename]` button, or <kbd>Ctrl+R</kbd> (`RenameThemeModal`). Updating the theme slug synchronizes the header title, live preview, and sets `is_dirty = True`.
  - **Direct Save Invariant (<kbd>Ctrl+S</kbd>):** If `self.theme_name` is set to any valid name (existing or newly named via F9/Rename), <kbd>Ctrl+S</kbd> must immediately serialize and save to disk via `_save_theme_to_disk()`. It must NEVER divert to "Save As" unless the theme is truly untitled (`not self.theme_name or self.theme_name == "untitled"`). Only <kbd>Ctrl+A</kbd> opens "Save As". `SaveThemeModal` must pre-fill `self.theme_name` as suggested name and submit on <kbd>Enter</kbd> (`on_input_submitted`).
  - **Deletion:** Themes can be deleted from `bashmenu.themes` via `#btn_delete_theme` / <kbd>Ctrl+D</kbd> in `themeedit.py`, or via <kbd>d</kbd> / <kbd>Delete</kbd> in `ThemePickerModalScreen` (`bashmenu_ui.py`). Prompts confirmation via `ConfirmModalScreen`. Invariants: Never allow deleting the only remaining theme; if deleting the currently active theme, safely fall back to another theme (e.g. `dracula`) and update `bashmenu.yml`.
  - **Image Palette Generation (`scripts/theme_from_image.py`, <kbd>F9</kbd>):**
    - Generates 256, 16, and 8 color tiers from wallpaper images using Pillow adaptive palette extraction and perceptual luminance sorting. In `action_theme_from_image`, `self.is_new` must be set based on `new_name not in self.raw_themes_data` so existing themes aren't falsely flagged as unnamable/unsaved new themes.
    - **Background Settings Preservation Invariant:** When deriving colors from an image in `themeedit.py` or via `generate_theme_from_image(..., background_config=...)`, all existing wallpaper background parameters (`opacity`, `scaling`, `mode`, `clustering`, `quantization`, `enabled`) from the active theme must be preserved, updating only `image` to the newly resolved path.
- **Theme Editor & Contrast Invariants (`bashedit.py`):**
  - When `--display-theme-colors` is active, invert FG/BG if text matches theme background. Fall back to neutral primary 8 (`white` on dark, `black` on light) if both match.
  - Whitespace (`Alt+1`): Stylize non-visible whitespace (`'·'`, `'→'`, `'↵'`) with theme's `whitespace` token (fallback `dim white`). Apply before selection and cursor styles.
- **Editor Mouse Navigation & Text Selection (`bashedit.py`):**
  - Gutter & Viewport Geometry: Calculate content column as `content_x = int(event.x) - lineno_width`. If `content_x < 0` (clicked gutter), position at column 0. Clicks beyond text clamp to `len(line)` (whitespace past EOL). Clicks below document clamp to `len(lines) - 1`.
  - Tabstop Mapping: When translating visual columns to buffer character indices, use `_display_col_to_char_idx()` to resolve expanded tabs against `tabstop`.
  - Selection Chains & Modifiers: Single left-click resets `mark_active = False`. Shift+Click anchors or extends `mark_active`. Double-click (`event.chain == 2`) selects word bounds (`[a-zA-Z0-9_]`, whitespace, or punctuation). Triple-click (`event.chain >= 3`) selects the entire row (`mark_x = 0`, `cursor_x = len(line)`).
  - Event Stopping: Consume click events in `EditorWidget.on_click()` with `event.stop()` so parent screen handlers do not trigger unintended actions, while preserving parent delegation for unhandled clicks.

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
  - Type Mutation (`Ctrl+T` / `[t]`): Reconfigure item types post-creation. Migrate payloads to target canonical keys (`command`, `script`, `editor` -> `file`, `config`/`toggle`/`radio` -> `key`, `python`) and prune obsolete keys. Submenu transitions handle container initialization and tree refresh.
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
- **Theme Editor Keybinding & Inspector Standards (`themeedit.py`):**
  - Standardized function key map for theme editor:
    - `F1`: Help
    - `F2`: Background wallpaper configuration modal
    - `F3`: Color Picker modal
    - `F4`: ASCII / Glyphs modal
    - `F5`: Reset current theme to disk
    - `F6`: Clone / Base theme
    - `F7`: Derive 16/8-color fallback palettes
    - `F8`: Toggle expand/collapse all property inspector sections
    - `F9`: Auto-generate theme palette from image (`ThemeFromImageModal`)
    - `Ctrl+R`: Rename theme (`RenameThemeModal`)
    - `Ctrl+D`: Delete theme (confirmation prompt)
    - `Ctrl+N`: Create new theme ('untitled')
    - `Ctrl+O`: Open existing theme to load (prompts if unsaved changes exist)
    - `Ctrl+S`: Save theme directly to disk
    - `Ctrl+A`: Save As new theme
    - `Esc` / `q`: Exit theme editor
  - **Inspector Section Collapsing:** Section headers (`.section_header`) toggle the `.collapsed` class on their corresponding `.section_body`. Inspector sections default to collapsed (`classes="section_body collapsed"`). Pressing `F8` toggles expand/collapse all.
- **Main Menu Global Keybindings (`BashMenuScreen`):**
  - `F1`: Help manual modal
  - `F2`: Theme selector modal
  - `F3`: Text editor (`bashedit.py`)
  - `F4`: Menu editor (`menuedit.py`)
  - `F5`: Hot reload (menu, configs, plugins)
  - `F6`: Direct shortcut badges toggle
  - `F7`: Status gutter configuration modal
  - `F8`: Visual Theme Editor (`themeedit.py`)
  - `Esc`: Back / Exit
  - Gutter click handler (`_handle_gutter_click`) must support mouse clicks for all function key actions and prioritize compound phrases (e.g. `f8`/`themeedit`) before generic matches (`theme`).
- **Interactive 16×16 2D Pickers (`ColorGridWidget`, `AsciiGridWidget`):**
  - For 256-entry domains (colors and CP437 ASCII 0–255), use 16×16 grids with arrow navigation (±1, ±16), Home/End, PgUp/PgDn (±64), and Enter.
  - Active cells must display bold + underline (`underline=True, bold=True`). Mouse clicks resolve via `col = event.x // cell_width; row = event.y`.
  - Direct 2D Grid Access: Avoid unnecessary range tabs in picker modals; keep navigation centered directly on the 16×16 grid.
  - Quick Swatches & Palettes: Provide visual quick-pick buttons for borders (`Single`, `Double`, `Mixed`, `Shades`, `Blocks`) and standard/bright/extended ANSI colors. Avoid `Select` dropdowns for visual tokens where 1-click visual recognition is essential.
  - Event Decoupling: Grid `set_code(code, notify=True)` must accept `notify=False`. Pass `notify=False` when clicking swatches to prevent highlight events from overwriting named constants (`"COLOR_RED"`).
  - **Theme Editor Color Picker Palette Tab (`ColorPickerModal`):**
    - **80-Column Safe Mode Switcher:** Maintains strict 80-column dialog width using `#mode_row`:
      - `[G] 256 Color Grid` (`ColorGridWidget`): 16×16 full terminal color spectrum.
      - `[T] Theme Palette (<count>)` (`OptionList`): All colors currently in use throughout the active theme.
    - **In-Use Color Grouping:** Groups all non-inherit colors defined across the theme palette, rendering:
      - Formatted color swatch badge (`[  <code/name>  ]`) with dynamic luminance-calculated contrast foreground (`#000000` for luminance $> 130$, `#ffffff` otherwise).
      - Comma-separated list of tokens currently using that color (e.g. `border(fg), footer(fg), divider(fg)`).
    - **OptionList Construction:** Textual `OptionList.add_option()` does not take an `id=` keyword argument; items must be wrapped in `Option(prompt, id=...)` (`from textual.widgets.option_list import Option`).
    - **Keyboard & Navigation Shortcuts:** Support `g` (256 Grid), `t` (Theme Palette), `1`/`f` (Foreground layer), `2`/`b` (Background layer), `i` (Inherit `-1`), and arrow keys for real-time live preview updates.
- **Modal Geometry & Button Box Model Standards (80-Column Safe):**
  - Terminal Geometry Bounds: All modal dialogs must fit standard 80-column terminals:
    - Width: `#dialog` width must not exceed `78` columns (`80` columns with right shadow).
    - Height: `#dialog` height must not exceed `27` to `29` rows to prevent vertical clipping on standard 80×24 / 80×28 / 80×30 terminals.
  - Textual Button Width Invariant: Textual's `Button.get_content_width` adds 2 cells to label text by default. For dense button rows (like swatch rows), set `.btn_swatch { padding: 0; margin: 0; min-width: 3; }` so that button width equals `len(label) + 2`.
  - Row Length Limit: Keep all horizontal swatch rows $\le 66$ columns. Split long button groups (e.g. Bright colors) across two clean rows of 4 buttons so labels like `Br-Magenta` are fully spelled out rather than truncated.
  - Preview Bar Sizing: Single-line status or preview bars inside modals must use `height: 1; border: none;` without dynamic borders, ensuring content is not squashed by border edges.
  - **Modal Container Text Color & Light Theme Legibility Invariant (`apply_modal_theme`):**
    - Whenever applying dynamic theme background (`dialog.styles.background = css_bg`), `apply_modal_theme` must explicitly apply the theme's text color directly to the container: `dialog.styles.color = css_text`.
    - In Textual, child widgets (labels, markdown paragraphs, checkboxes) without explicit styles inherit their foreground from the container. Without `dialog.styles.color`, Textual defaults to dark-mode stylesheet `$text = #e0e0e0` (light grey). On light themes like `dayscape` (`#d7d7ff`), light-grey text against a light background yields ~1.1:1 contrast (illegible unless selected).
    - Notes containing markdown task lists (`- [ ]`, `- [x]`) fragment into `.markdown_block` and `Checkbox` widgets and omit `#message` entirely. Style queries must explicitly target `#message, .markdown_block, Checkbox, .markdown_checkbox`.
- **Tab Key Navigation & Modal Button Sizing:**
  - Never bind `tab` at the screen level (`Binding("tab", ...)`). Let Textual's default focus traversal handle <kbd>Tab</kbd> and <kbd>Shift+Tab</kbd> across tabs, grid, swatches, and action buttons.
  - Standard Action Button Sizing: Button variants apply 2-line borders. Never use `height: 1` or `border: none` on bottom dialog action buttons. Always use standard `#btn_row` styling: `#btn_row { height: 3; margin-top: 0; align: center middle; }` and `#btn_row Button { height: 3; min-width: 16; margin: 0 1; }`.
  - Provide distinct `:focus` styling for `.btn_swatch:focus`, `.tab_btn:focus`, and `#btn_row Button:focus`.
  - **Button Semantic Alias Resolution (`apply_button_theme`):**
    - Theme definitions in `bashmenu.themes` specify button colors under `button_primary`, `button_error`, `button_cancel`, and `button_success`.
    - When modal screens or helper components request semantic aliases, `apply_button_theme` must resolve fallbacks (`button_danger -> button_error` and `button_default -> button_cancel`) before falling back to `button_primary`. This prevents action buttons (like Delete or Cancel) from unintentionally taking on primary highlight colors.
- **Split-Screen Preview Maximization (`ThemePreviewWidget`):**
  - `#preview_panel` must use `padding: 0; overflow: hidden;`.
  - Compute `w = max(38, parent.size.width - 4)` and `num_rows = max(12, parent.size.height - 2)`. Pad body slots with options, dividers, plugin cards, and bordered spacer rows to fill 100% of pane interior.
- **Textual Modal Performance (Rich Static over Markdown Widget):**
  - Avoid Textual's built-in `Markdown` widget for large docs (decomposes into hundreds of DOM widgets causing multi-second lag).
  - Use `Static` wrapping `rich.markdown.Markdown(text, hyperlinks=True)` for single-widget rendering (<0.1s load, 60 FPS). Intercept clicks via `event.style.link`.
  - If using Textual's `Markdown` widget, always pass `open_links=False` to prevent external browser launches on `#anchor` links.
- **Reusable Marquee Engine & `MarqueeLabel` Widget (`bashmenu_ui.py`):**
  - Centralized Primitives: `format_marquee_spacer()`, `get_theme_marquee_config()`, `get_marquee_slice()`, and `MarqueeTracker`.
  - Polymorphic Widget: `MarqueeLabel` subclasses Textual's `Label` and automatically activates an interval timer (0.25s) with a 4-tick pause delay whenever its content exceeds the widget's visual width (`cell_len(text) > size.width`).
  - Drop-in Compatibility: Because `MarqueeLabel` inherits from `Label`, queries such as `query_one(..., Label)` and methods like `.update(text)` work seamlessly across screens and modals without type mismatches.
  - Applied across:
    - `FilePickerModalScreen` (`#path_label`): smoothly scrolls deep file paths.
    - `bashedit.py` (`#editor_header`): marquees long file paths in narrow Netbook terminal windows.
    - `menuedit.py` (`render_menu_item_preview`): synchronizes preview rendering with 50/50 partition and theme marquee rules.
- **Visual Menu Editor In-Place Sibling Reordering & Debounced Auto-Save Invariant (`menuedit.py`):**
  - In `action_move_up` and `action_move_down`: Never call `self.populate_tree()` to reorder siblings. `populate_tree()` calls `tree.clear()`, destroying all DOM nodes, resetting expansion/collapse states across the menu, and causing a visible full-screen blink/flash.
  - Reorder siblings in-place directly in `node.parent._children`, then call `tree._invalidate()`, `tree._build()`, `tree.select_node(node)`, and `tree.scroll_to_node(node)`. Fall back to `populate_tree()` only if `node.parent` is absent or the node is not found in `_children`.
  - Never run synchronous YAML serialization (`bashmenu.dump_menu_yaml()`) and disk write on every keystroke (`~61ms` per call). Debounce autosaves via `self.set_timer(0.35, self._save_menu_quietly)` and flush immediately on manual save (`action_save_menu`), exit (`action_exit_editor`), or screen unmount (`on_unmount`). If unmounted or not running an active application loop, execute the write immediately without scheduling timers.

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
- **Status Gutter Clock & Refresh Granularity (`_determine_refresh_interval`):**
  - Second-precision tokens (`{date_time_24}`, `{date_time_12}`, `{time_24}`, `{time_12}`, `{seconds}`, `%S`): automatically sets periodic refresh to `1.0` second.
  - Minute-precision tokens (`{date_time_24_short}`, `{time_24_short}`, `{date}`) or static badges: automatically throttles periodic refresh to `5.0` seconds to conserve CPU and battery.
  - User Override: Users can explicitly configure `settings.refresh_interval` (or `settings.status_refresh_rate`) in `bashmenu.yml` (in seconds, e.g. `1.0`, or milliseconds, e.g. `1000`). Validated in `ymlcheck.py`.
- **CI Virtualization & Performance Test Resilience:**
  - Timing assertions in performance tests must account for shared virtualized runners and CPU scheduling jitter under parallel test workers (`pytest -n auto`).
  - Use `os.getenv("CI")` to scale single-frame spike limits (e.g. `100ms` in CI vs `35ms` local) while keeping average latency targets strict (`< 15ms`).

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
  - Balanced 3-segment status bar: Left line range (`TOP 1-23/100`), center badge `[ filename.ext ]` or `[ <stdin> ]`, right key hints (`h/? help`).
  - **Multibyte Box Drawing Invariant:** Never use `tr " " "─"` to generate repeated box borders; `tr` operates on single bytes and corrupts multibyte UTF-8 characters (`\xe2\x94\x80`). Use pure bash string repetition loops (`for (( i=0; i<len; i++ )); do bar="${bar}─"; done`).
  - **Function Key Decoding:** In raw terminal input parsing, decode `F1` from both `ESC O P` (`c2='O', c3='P'`) and `ESC [ 11 ~` (`body="11~"`).
  - **Centered Popup Modals:** Centered floating overlays (`show_help_modal`) must compute `box_w = min(COLS - 6, 74)` and `box_h = min(ROWS - 4, 22)`, draw non-destructively over visible viewport rows, handle internal scrolling (`scroll_top`, `max_scroll`), respect `-c`/`--no-color` (`STRIP_COLORS`), and repaint the underlying document via `render` on dismissal.
  - Awk Collation Portability: In scripts utilizing byte-oriented regex patterns with high-bit octal escapes (`/[\300-\377]/`), GNU Awk (`gawk`) in UTF-8 locales produces `Invalid collation character` errors. Always force `LC_ALL=C` on the Awk execution pipeline (e.g. `LC_ALL=C BAR_LINE="${BAR_LINE}" awk ...`) to guarantee byte-oriented collation across `gawk` and `mawk`.
- **Cheatsheet CLI (`scripts/cheat.sh`, `scripts/cheat.py`, `.cheat.yml`):**
  - Root directory defined in `scripts/.cheat.yml` (`dir: ~/cheat`).
  - Search hierarchy: 1a. Exact relative path -> 1b. Filename stem -> 2. YAML frontmatter tags -> 3. Full-text body.
  - List/Search flags: `cheat -l` (lists files and tags in 2 columns), `cheat -s <query>` (filtered search). Dispatches to `rich.sh` and `pager.sh`.
- **CLI Executable Symlinks & Target Directory Resolution (`install.sh` / `bashmenu.sh`):**
  - The installer and launcher expose first-class CLI commands: `bm`, `cheat`, `rich`, and `bmpager`.
  - Resolution Hierarchy (`get_install_bin_dir`):
    1. `$BASHMENU_BIN_DIR` (custom environment override).
    2. `$PREFIX/bin` (Termux environments).
    3. `/usr/local/bin` (when running as `root`, `id -u == 0`).
    4. `$HOME/.local/bin` (standard user binary directory).
    5. `/usr/local/bin` (fallback if no `$HOME` is defined and directory is writable).
  - `uninstall.sh` removes all four symlinks during uninstallation.
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
- **What To Document:** Every script must document its purpose, usage, and configuration options. This directive includes .py, and .sh files. Be sure to document every function, macro, def, directive, and attribute. There should be no undocumented spaghetti code. Keep documentation up-to-date, lines under 80 characters (except inline code documentation or comments), be brief, but clear and precise about what the code does.
- **Tone & Formatting Constraints:** Maintain a professional, dry tone without promotional adjectives. Format lists as GitHub-Flavored Markdown tables with collapsible `<details><summary><b>Table of Contents</b></summary></details>`. Wrap documentation lines under 80 characters. Precede code block fences with an empty line. Docstrings must be in the third person.
- **Universal 6-Tier Parity Invariant:** Every placeholder, macro, directive, and attribute must be 100% synchronized across all six documentation tiers:
  1. `bashmenu_ui.py`: `PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT` (`^P`/`Alt+M` in editor).
  2. `menuedit.py`: `ITEM_EDIT_HELP_TEXT` (`F1`/`?` inspector guide).
  3. `bashedit.py`: `action_help_manual` (`F1`/`Ctrl+G`/`Alt+H` manual).
  4. `bashmenu.py`: `action_help` modal (`F1`, renders `bashmenu.md`).
  5. `bashmenu.md`: Reference documentation (Sections 1, 2.1, 6.1, 6.2).
  6. `bashmenu.1`: Linux system man page.
- **Scripts Documentation:** Every executable script in `scripts/` must be registered in `bashmenu.md`, `bashmenu.1`, and `README.md`. Verified by automated assertions in `.tests/test_improvements.py`.
- **Placeholders & Macros Popup Reference Modal Requirement:** Whenever a new placeholder, directive, or macro (such as `{toast:...}`) is introduced or modified, it is a strict requirement to document it in `bashmenu_ui.py` (`PLACEHOLDER_SECTIONS` and `PLACEHOLDER_HELP_TEXT`) so it is immediately available to users in the Placeholders and Macros popup reference modal (`^P`/`Alt+M` in editor).
- **Directory Aliases & Macro Parity:** Document aliases (`{scripts}`, `{templates}`, `{cache}`, `{notebooks}`) alongside canonical forms (`{scripts_dir}`, `{templates_dir}`, `{cache_dir}`, `{notebooks_dir}`). Document config namespaces (`{app.<key>}` alongside `{theme}`, `{settings.<key>}`).

---

## 11. Additional Directives
- **Continuation Directive:** When you are done working on a task, check both `.agents/skills/bashmenu-developer/TODO.md` and `{bashmenu_dir}/notebooks/notes.yml` (`notebook -> notes -> TODO`) for additional tasks, bugs, features, or improvements to work on as soon as you finish. Both documents utilize standard markdown checkboxes (`- [ ]`). When you are done working on a task, check off the item (`- [x]`) in its respective file (`TODO.md` and/or `notebooks/notes.yml`), append completion summaries to `.agents/skills/bashmenu-developer/DONE.md`, and inform the user that the task is complete with a description of what you discovered and how you resolved it. If you encounter something you need feedback on, pause and ask the user for guidance.
- **Pending Task Marker:** When actively working on an item from `TODO.md` or `{bashmenu_dir}/notebooks/notes.yml`, immediately mark the item with `PENDING:` directly after the checkbox (e.g. `- [ ] PENDING: BUG: ...`). When completed, mark it as `- [x] BUG: ...` (removing `PENDING:`).
- **Self Organization & Shared Notes:** If you are given multiple tasks, register them in `.agents/skills/bashmenu-developer/TODO.md` (or cross-reference shared tasks in `notebooks/notes.yml`), prioritizing them by precedence. Check them off in both files as completed.
- **Precedence:** `CRITICAL BUG` has the highest precedence, followed by `BUG`, then `RESPONSIVENESS`, `UI`, `FEATURE`, `REQUEST` and finally `RESEARCH`.
- **Done Log Directive (`DONE.md`):** Whenever a task, bug fix, or improvement from `TODO.md` or `notebooks/notes.yml` is completed, append the completed item to `.agents/skills/bashmenu-developer/DONE.md` along with a concise description and summary of the root cause, what was changed/implemented, and tests executed.
- **Clean Up:** If new TODO's have been added, old completed TODO's may be removed from the file. The goal is to leave the old ones in there until the user has seen them visually, which they will have done if they added a new TODO item.