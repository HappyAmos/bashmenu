
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