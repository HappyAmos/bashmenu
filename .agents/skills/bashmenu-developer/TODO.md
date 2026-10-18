
- [ ] BUG: border misalignment in theme editor 'menu editor' tab:
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
- [ ] BUG: Misalignment of borders in Modals & Popups tab of theme editor:
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
- [ ] BUG: Background of plugins still does not appear 'transparent', meaning it does not show the wallpaper behind the text of the plugins:
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
- [ ] CRITICAL BUG: the time is displaying two hours ahead of the actual system time.
- [ ] BUG: {toast:SECONDS:"MESSAGE"} popup toast message was not added to the Placeholders and Macros help popup modal. Are there any other missing Placeholders or Macros from this help screen? Make sure that creating new Placeholders and Macros documentation in the Placeholders & Macros popup reference modal is a requirement in SKILL.md .