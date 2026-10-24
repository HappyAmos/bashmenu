
- [x] FEATURE/UI: Theme editor dropper status bar: display only 256-color codes (no hex/ANSI names), add live "[Top: ▓▓▓]" and "[Bot: ▓▓▓]" foreground-only swatches, and expand #preview_status_bar to 2 rows with evenly distributed badges.
- [x] BUG: Synchronize Menu Editor, Text Editor, and Modals theme colors with Theme Editor mock previews (fix orange $accent header bar / $panel status bar / footer background leak when token bgcolor is -1, and inherit section backgrounds in mock previews).
- [x] BUG: Marquee not working when hovering over overflowing menu items (e.g. "Configure Status Gutter"). Fix screen stack depth check in _tick_marquee and MarqueeLabel._on_tick.
- [x] BUG: Changing a value of the bashmenu.yml config file does not update a menu item that relies on it's value. Initiate line refresh across all placeholder-bearing menu items in the current menu after item action completes.
- [x] CRITICAL BUG: Replace "choice" menu item type completely with "radio" type. Implement true radio-button interface (vertical list, (•)/( ) indicators, standard Select/Cancel buttons, keyboard/mouse nav). Update schema, eliminate "choice" completely, integrate "radio" type with full options configuration and badges into menuedit.py, update documentation, and update tests.
- [x] BUG: When cursor is at the last character at the bottom of the text area editing a "note", particularly when an autocomplete "- [ ]" is created, the window doesn't automatically adjust to the newly added line, forcing the user to arrow down to the next line.
- [x] FEATURE: Add the option to rename a "note" in a notebook. Rename with the keyboard shortcut <m>.
- [x] FEATURE: Pager: add binary choice option to use "default" system $EDITOR or BM's built-in editor.
- [x] RESPONSIVENESS: Theme editor preview item selection lag: significant blocking delay until focus lands on color field in property inspector.
- [x] BUG: border misalignment in theme editor 'menu editor' tab:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Mock Menu  Menu Editor  Modals & Popups                                         │
│━━━━━━━━━━━╸━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│                                                                                 │
│ ┌──[ Menu Editor ]──────────────────────────────────────────────────────[X]──┐░░│
│ │ ▼ Main Menu▀▀▀▀▀▀▀▀▀▀▀▀│ Title: [ My Menu▀▀▀▀]▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▲│░░   │
│ │▀▀▀▶ Applications▀▀▀▀▀▀▀│ Icon:▀▀[ 📁▀▀▀▀▀▀▀▀▀]▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█│░░   │
│ │▀▀▀▀▀• Terminal▀▀▀▀▀▀▀▀▀│ Type:▀▀[ submenu▀▀▀▀]▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█│░░   │
```
- [x] BUG: Misalignment of borders in Modals & Popups tab of theme editor:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Mock Menu  Menu Editor  Modals & Popups                                         │
│━━━━━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│                                                                                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀┌──[ Notice Modal ]───────────────────────[X]──┐░░               │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀│ Are you sure you want to apply these▀▀▀▀▀▲ │░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀│ changes? All pending configurations will █ │░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀│ be persisted to disk immediately.▀▀▀▀▀▀▀▀█ │░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀│ Press [Yes] to proceed, [Cancel] to abort▼ │░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀├────────────────────────────────────────────┤░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀│▀▀▀▀▀▀▀▀ [ Confirm ]    [ Cancel ] ▀▀▀▀▀▀▀▀▀│░░                 │
│ ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀└────────────────────────────────────────────┘░░                 │
```
- [x] BUG: Background of plugins still does not appear 'transparent', meaning it does not show the wallpaper behind the text of the plugins:
```
│▀▀─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────▀▀│
│▀▀┌───────────────────────────────────────┬───────────────────────────────────────┬───────────────────────────────────────┬───────────────────────────────────────┐▀▀│
│▀▀│ 49079: ☀  🌡+59°F 🌬↗14mph              │ Alienware:                            │ Pi3b:                                 │ Halftop:                              │▀▀│
│▀▀│                                       │   192.168.4.46 | UP                   │   192.168.4.47 | UP                   │   192.168.4.96 | DOWN                 │▀▀│
│▀▀└───────────────────────────────────────┴───────────────────────────────────────┴───────────────────────────────────────┴───────────────────────────────────────┘▀▀│
│▀▀─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────▀▀│
│▀▀On This Day:                                                                                                                                                     ▀▀│
│▀▀320 – Pappus of Alexandria, Greek philosopher, observes an eclipse of the Sun and writes a commentary on The Great Astronomer (Almagest).                        ▀▀│
│▀▀https://en.wikipedia.org/wiki/Pappus_of_Alexandria                                                                                                               ▀▀│
│▀▀On This Day courtesy of https://today.zenquotes.io/                                                                                                              ▀▀│
│▀▀─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────▀▀│
```
- [x] CRITICAL BUG: the time is displaying two hours ahead of the actual system time.
- [x] BUG: {toast:SECONDS:"MESSAGE"} popup toast message was not added to the Placeholders and Macros help popup modal. Are there any other missing Placeholders or Macros from this help screen? Make sure that creating new Placeholders and Macros documentation in the Placeholders & Macros popup reference modal is a requirement in SKILL.md .
- [x] BUG: Built-in text editors swap files should be created and deleted in the exact directory where the file being edited is located.
- [x] FEATURE: Notebook editor: If the user has created a checkbox, or is creating a list, or similar related formatting item, when they hit enter, create a new line below the line they pressed enter on, and include the basic formatting for that item. For instance, if the user is creating a list of checkboxes, after they press enter, automatically create the next checkbox "- [ ] ", same for ordered, unordered lists, etc. Better yet, would be faint ghost text with tab to complete. Create a plan and present it to me as an artifact.
- [x] BUG: Toast: Placeholders included in {toast:"{date_time_24_short}"} do not expand.
- [x] FEATURE: Make sure the copy and paste buffer for notes can pass information back to any interface such as the built-in text editor
- [x] BUG: UI: Bashmenu editor property inspector panel is not utilizing as much space as it can for the preview pane:
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│  ── Property Inspector ──                                                        │
│                                                                                  │
│   SCRIPT                                                                         │
│                                                                                  │
│  Title/Label: Search Nerd Font & Emoji [{scripts_dir}/glyphs.sh]                 │
│                                                                                  │
│  Icon/Glyph: {nf::#f422}                                                         │
│                                                                                  │
│  Action/Target: {scripts_dir}/glyphs.sh {param}                                  │
│                                                                                  │
│  Flags: stream=True                                                              │
│                                                                                  │
│  Preview:                                                                        │
│    1.     Search     [/home/andrew/git[---This space could be used.----------]  │
```
- [x] Add a directive to SKILL.md to append .agents/skills/bashmenu-developer/DONE.md with completed TODO.md items, and include a description and summary of what you did.
- [x] BUG: Vertical borders in the preview pane of the theme editor are no longer clickable (outside/window borders).
- [x] REQUEST: Start referencing {bashmenu_dir}/notebook/notes.yml -> notebook -> notes -> TODO update SKILL.md to add this to your workflow after completing tasks. Mark done items in this list as done, and continue writing completion summaries to DONE.md . You will still reference this file (TODO.md) after completing tasks as well.
- [x] BUG: Theme editor -> `<f2>` to Configure Background Wallpaper: "Scaling Mode" has several  options to choose from, but I think only two options are actually implemented (cover, stretch). Please finish implementing the other methods.
- [x] CRITICAL BUG: Theme editor, not sure what exactly caused this crash, but here is the output:
````
[andrew@andrew-Inspiron-3537:~/github/bashmenu$ bm
╭───────────────────────────────────────────────────────────────── Traceback (most recent call last) ─────────────────────────────────────────────────────────────────╮
│ /home/andrew/github/bashmenu/themeedit.py:4890 in on_button_pressed                                                                                                 │
│                                                                                                                                                                     │
│   4887 │   │   │                                                                                ╭──────────────────── locals ────────────────────╮                  │
│   4888 │   │   │   self.app.push_screen(                                                        │   bg_val = 235                                 │                  │
│   4889 │   │   │   │   ColorPickerModal(                                                        │   btn_id = 'btn_color_editor__tab_active'      │                  │
│ ❱ 4890 │   │   │   │   │   tok,                                                                 │ curr_val = [234, -1]                           │                  │
│   4891 │   │   │   │   │   curr_val,                                                            │    event = Pressed()                           │                  │
│   4892 │   │   │   │   │   bg_color_val=bg_val,                                                 │  pal_256 = {                                   │                  │
│   4893 │   │   │   │   │   theme_styles=self.configured_theme_styles,                           │            │   'background': 235,              │                  │
│                                                                                                 │            │   'title': [252, -1],             │                  │
│                                                                                                 │            │   'border': [239, -1],            │                  │
│                                                                                                 │            │   'text': [255, -1],              │                  │
│                                                                                                 │            │   'highlight': [16, 252],         │                  │
│                                                                                                 │            │   'accent': [145, -1],            │                  │
│                                                                                                 │            │   'footer': [239, -1],            │                  │
│                                                                                                 │            │   'shadow': [                     │                  │
│                                                                                                 │            │   │   236,                        │                  │
│                                                                                                 │            │   │   'COLOR_BLACK'               │                  │
│                                                                                                 │            │   ],                              │                  │
│                                                                                                 │            │   'gutter': [66, -1],             │                  │
│                                                                                                 │            │   'selection': [16, 252],         │                  │
│                                                                                                 │            │   ... +12                         │                  │
│                                                                                                 │            }                                   │                  │
│                                                                                                 │      sec = 'editor'                            │                  │
│                                                                                                 │ sec_dict = {'tab_active': [234, -1]}           │                  │
│                                                                                                 │     self = ThemeEditScreen()                   │                  │
│                                                                                                 │  sub_tok = 'tab_active'                        │                  │
│                                                                                                 │      tok = 'editor__tab_active'                │                  │
│                                                                                                 ╰────────────────────────────────────────────────╯                  │
│                                                                                                                                                                     │
│ /home/andrew/github/bashmenu/themeedit.py:570 in __init__                                                                                                           │
│                                                                                                                                                                     │
│    567 │   │                                                                                                                                                        │
│    568 │   │   self.active_tab = "fg"                                                                                                                               │
│    569 │   │   self.view_mode = "grid"                                                                                                                              │
│ ❱  570 │   │   self.theme_colors_list = self._extract_theme_colors()                                                                                                │
│    571 │                                                                                                                                                            │
│    572 │   def _extract_theme_colors(self) -> list[tuple[Any, list[str]]]:                                                                                          │
│    573 │   │   """Extract and group all unique non-inherit colors currently defined in theme pa                                                                     │
│                                                                                                                                                                     │
│ ╭──────────────────────────────────────────────────────────────────────────── locals ─────────────────────────────────────────────────────────────────────────────╮ │
│ │  bg_color_val = 235                                                                                                                                             │ │
│ │   current_val = [234, -1]                                                                                                                                       │ │
│ │          self = ColorPickerModal()                                                                                                                              │ │
│ │ theme_palette = {                                                                                                                                               │ │
│ │                 │   'background': 235,                                                                                                                          │ │
│ │                 │   'title': [252, -1],                                                                                                                         │ │
│ │                 │   'border': [239, -1],                                                                                                                        │ │
│ │                 │   'text': [255, -1],                                                                                                                          │ │
│ │                 │   'highlight': [16, 252],                                                                                                                     │ │
│ │                 │   'accent': [145, -1],                                                                                                                        │ │
│ │                 │   'footer': [239, -1],                                                                                                                        │ │
│ │                 │   'shadow': [236, 'COLOR_BLACK'],                                                                                                             │ │
│ │                 │   'gutter': [66, -1],                                                                                                                         │ │
│ │                 │   'selection': [16, 252],                                                                                                                     │ │
│ │                 │   ... +12                                                                                                                                     │ │
│ │                 }                                                                                                                                               │ │
│ │  theme_styles = {                                                                                                                                               │ │
│ │                 │   'background': Style(bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),                                                          │ │
│ │                 │   'title': Style(color=Color('color(252)', ColorType.EIGHT_BIT, number=252), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),   │ │
│ │                 │   'border': Style(color=Color('color(239)', ColorType.EIGHT_BIT, number=239), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),  │ │
│ │                 │   'text': Style(color=Color('color(255)', ColorType.EIGHT_BIT, number=255), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),    │ │
│ │                 │   'highlight': Style(                                                                                                                         │ │
│ │                 │   │   color=Color('color(16)', ColorType.EIGHT_BIT, number=16),                                                                               │ │
│ │                 │   │   bgcolor=Color('color(252)', ColorType.EIGHT_BIT, number=252)                                                                            │ │
│ │                 │   ),                                                                                                                                          │ │
│ │                 │   'accent': Style(color=Color('color(145)', ColorType.EIGHT_BIT, number=145), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),  │ │
│ │                 │   'footer': Style(color=Color('color(239)', ColorType.EIGHT_BIT, number=239), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),  │ │
│ │                 │   'shadow': Style(                                                                                                                            │ │
│ │                 │   │   color=Color('color(236)', ColorType.EIGHT_BIT, number=236),                                                                             │ │
│ │                 │   │   bgcolor=Color('#000000', ColorType.TRUECOLOR, triplet=ColorTriplet(red=0, green=0, blue=0))                                             │ │
│ │                 │   ),                                                                                                                                          │ │
│ │                 │   'gutter': Style(color=Color('color(66)', ColorType.EIGHT_BIT, number=66), bgcolor=Color('color(235)', ColorType.EIGHT_BIT, number=235)),    │ │
│ │                 │   'selection': Style(                                                                                                                         │ │
│ │                 │   │   color=Color('color(16)', ColorType.EIGHT_BIT, number=16),                                                                               │ │
│ │                 │   │   bgcolor=Color('color(252)', ColorType.EIGHT_BIT, number=252)                                                                            │ │
│ │                 │   ),                                                                                                                                          │ │
│ │                 │   ... +18                                                                                                                                     │ │
│ │                 }                                                                                                                                               │ │
│ │    token_name = 'editor__tab_active'                                                                                                                            │ │
│ ╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                                                                     │
│ /home/andrew/github/bashmenu/themeedit.py:597 in _extract_theme_colors                                                                                              │
│                                                                                                                                                                     │
│    594 │   │   │   │   if c in (-1, "-1", None, ""):                                                                                                                │
│    595 │   │   │   │   │   continue                                                                                                                                 │
│    596 │   │   │   │   tag = token if len(vals) == 1 else (f"{token}(fg)" if idx == 0 else f"{t                                                                     │
│ ❱  597 │   │   │   │   color_usage.setdefault(c, []).append(tag)                                                                                                    │
│    598 │   │   return list(color_usage.items())                                                                                                                     │
│    599 │                                                                                                                                                            │
│    600 │   def _build_palette_option(self, color_val: Any, tokens: list[str]) -> Text:                                                                              │
│                                                                                                                                                                     │
│ ╭──────────────────────────────────────────────────── locals ────────────────────────────────────────────────────╮                                                  │
│ │           c = {'tab_active': [234, -1]}                                                                        │                                                  │
│ │ color_usage = {                                                                                                │                                                  │
│ │               │   235: ['background'],                                                                         │                                                  │
│ │               │   252: [                                                                                       │                                                  │
│ │               │   │   'title(fg)',                                                                             │                                                  │
│ │               │   │   'highlight(bg)',                                                                         │                                                  │
│ │               │   │   'selection(bg)',                                                                         │                                                  │
│ │               │   │   'button_primary(bg)',                                                                    │                                                  │
│ │               │   │   'scrollbar(fg)'                                                                          │                                                  │
│ │               │   ],                                                                                           │                                                  │
│ │               │   239: ['border(fg)', 'footer(fg)', 'divider(fg)'],                                            │                                                  │
│ │               │   255: ['text(fg)', 'button_error(fg)', 'button_cancel(fg)', 'button_success(fg)'],            │                                                  │
│ │               │   16: ['highlight(fg)', 'selection(fg)', 'button_primary(fg)'],                                │                                                  │
│ │               │   145: ['accent(fg)', 'shortcut_key(fg)', 'plugin(fg)'],                                       │                                                  │
│ │               │   236: ['shadow(fg)', 'button_cancel(bg)', 'scrollbar(bg)', 'whitespace(fg)'],                 │                                                  │
│ │               │   'COLOR_BLACK': ['shadow(bg)'],                                                               │                                                  │
│ │               │   66: ['gutter(fg)'],                                                                          │                                                  │
│ │               │   196: ['button_error(bg)'],                                                                   │                                                  │
│ │               │   ... +3                                                                                       │                                                  │
│ │               }                                                                                                │                                                  │
│ │         idx = 0                                                                                                │                                                  │
│ │        self = ColorPickerModal()                                                                               │                                                  │
│ │      source = {                                                                                                │                                                  │
│ │               │   'background': 235,                                                                           │                                                  │
│ │               │   'title': [252, -1],                                                                          │                                                  │
│ │               │   'border': [239, -1],                                                                         │                                                  │
│ │               │   'text': [255, -1],                                                                           │                                                  │
│ │               │   'highlight': [16, 252],                                                                      │                                                  │
│ │               │   'accent': [145, -1],                                                                         │                                                  │
│ │               │   'footer': [239, -1],                                                                         │                                                  │
│ │               │   'shadow': [236, 'COLOR_BLACK'],                                                              │                                                  │
│ │               │   'gutter': [66, -1],                                                                          │                                                  │
│ │               │   'selection': [16, 252],                                                                      │                                                  │
│ │               │   ... +12                                                                                      │                                                  │
│ │               }                                                                                                │                                                  │
│ │         tag = 'editor'                                                                                         │                                                  │
│ │       token = 'editor'                                                                                         │                                                  │
│ │         val = {'tab_active': [234, -1]}                                                                        │                                                  │
│ │        vals = [{'tab_active': [234, -1]}]                                                                      │                                                  │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
TypeError: unhashable type: 'dict'
````