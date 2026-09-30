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
- `bashmenu.sh`: Main Bash wrapper script. Sets up the environment,
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
- **Icon & Glyph Spacing:** When an icon or glyph is present on a menu
  option, separate it from the label text with exactly two spaces
  (`f"{icon_resolved}  "`). Ensure prefix width measurements include
  both spaces so label truncation remains aligned.
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
6. **Theme Palette Validation:** When updating or adding themes to
   `bashmenu.themes`, always run `python3 ymlcheck.py --themes bashmenu.themes`
   to verify that 16-color mode indices remain within `0..15` (or valid
   `COLOR_*` constants) and 8-color mode indices remain within `0..7`.
   Never use 256-color indices (e.g., `255`) in 16 or 8-color sections.
7. **Portable Paths & Macro Invariant:** Never hardcode absolute user
   paths (such as `/home/andrew/`) in menu configurations
   (`bashmenu.mnu`), templates, or launcher scripts. Always utilize
   expanding placeholder macros: `{home}`, `{bashmenu_dir}`,
   `{scripts_dir}`, `{templates_dir}`, and `{cache_dir}`.
8. **Dependency & Virtualenv Hygiene:** Because `bashmenu` is built on
   Textual and Rich, `requirements.txt` must always declare `textual`
   and `rich` alongside `PyYAML` and `ruff`. `bashmenu.sh` venv
   verification commands must validate `yaml, ruff, textual, rich`
   before marking the environment ready.
9. **Test Suite Organization & Import Standard:** All unit and
   integration test scripts must strictly reside inside the `.tests/`
   directory (named `test_*.py`). Never place test scripts in the root
   directory. Test files in `.tests/` must dynamically resolve the
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
