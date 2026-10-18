- [x] Found a new bug in the menuedit.py script. This happened when navigating the menu using the arrow keys. ```
  ╭───────────────────────────────────────────────────────────────── Traceback (most recent call last) ─────────────────────────────────────────────────────────────────╮
│ /home/andrew/github/bashmenu/menuedit.py:2178 in on_tree_node_highlighted                                                                                           │
│                                                                                                                                                                     │
│   2175 │   │   │   │   node.expand()                                                            ╭───────── locals ──────────╮                                       │
│   2176 │                                                                                        │ event = NodeHighlighted() │                                       │
│   2177 │   def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:             │  self = MenuEditScreen()  │                                       │
│ ❱ 2178 │   │   self.update_inspector(event.node.data if event.node else None)                   ╰───────────────────────────╯                                       │
│   2179 │                                                                                                                                                            │
│   2180 │   def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:                                                                                       │
│   2181 │   │   self.update_inspector(event.node.data if event.node else None)                                                                                       │
│                                                                                                                                                                     │
│ /home/andrew/github/bashmenu/menuedit.py:2344 in update_inspector                                                                                                   │
│                                                                                                                                                                     │
│   2341 │   │   preview_str = render_menu_item_preview(item, config=cfg, width=38)                                                                                   │
│   2342 │   │   lines.append(f"[bold cyan]Preview:[/bold cyan]\n{escape(preview_str)}")                                                                              │
│   2343 │   │                                                                                                                                                        │
│ ❱ 2344 │   │   inspector.update("\n\n".join(lines))                                                                                                                 │
│   2345 │                                                                                                                                                            │
│   2346 │   def action_edit_item(self) -> None:                                                                                                                      │
│   2347 │   │   tree = self.query_one("#tree", Tree)                                                                                                                 │
│                                                                                                                                                                     │
│ ╭────────────────────────────────────────────────────────────────── locals ──────────────────────────────────────────────────────────────────╮                      │
│ │      action = '{home}/autoexec.sh'                                                                                                         │                      │
│ │       badge = '[EDT]'                                                                                                                      │                      │
│ │    block_id = None                                                                                                                         │                      │
│ │         cfg = {                                                                                                                            │                      │
│ │               │   'version': '0.0.1',                                                                                                      │                      │
│ │               │   'theme': 'dayscape',                                                                                                     │                      │
│ │               │   'user': {                                                                                                                │                      │
│ │               │   │   'example_boolean': True,                                                                                             │                      │
│ │               │   │   'example_filepath': '{bashmenu_dir}',                                                                                │                      │
│ │               │   │   'example_string': 'A string of text',                                                                                │                      │
│ │               │   │   'localip': '[b]{localip}[/b]',                                                                                       │                      │
│ │               │   │   'postal_code': 49079,                                                                                                │                      │
│ │               │   │   'antigravity': 'cd {dir_picker} && agy -c'                                                                           │                      │
│ │               │   },                                                                                                                       │                      │
│ │               │   'settings': {                                                                                                            │                      │
│ │               │   │   'cache_dir': '{home}/.cache/bashmenu',                                                                               │                      │
│ │               │   │   'check_for_updates': False,                                                                                          │                      │
│ │               │   │   'plugins': {                                                                                                         │                      │
│ │               │   │   │   'type': 'table',                                                                                                 │                      │
│ │               │   │   │   'width': '100%',                                                                                                 │                      │
│ │               │   │   │   'entries': 4,                                                                                                    │                      │
│ │               │   │   │   'headers': '',                                                                                                   │                      │
│ │               │   │   │   'divider': True,                                                                                                 │                      │
│ │               │   │   │   'weather': {'script': "curl -s 'wttr.in/{user.postal_code}?format=4'", 'sleep': 10000},                          │                      │
│ │               │   │   │   'alienware': {'sleep': 15000, 'script': '{scripts_dir}/serverup.sh 192.168.4.46 [b]Alienware[/b]'},              │                      │
│ │               │   │   │   'pi3b': {'sleep': 20000, 'script': '{scripts_dir}/serverup.sh 192.168.4.47 [b]Pi3b[/b]'},                        │                      │
│ │               │   │   │   'halftop': {'sleep': 25000, 'script': '{scripts_dir}/serverup.sh 192.168.4.96 [b]Halftop[/b]'},                  │                      │
│ │               │   │   │   'otd': {                                                                                                         │                      │
│ │               │   │   │   │   'script': 'otd.sh',                                                                                          │                      │
│ │               │   │   │   │   'sleep': 40000,                                                                                              │                      │
│ │               │   │   │   │   'standalone': True,                                                                                          │                      │
│ │               │   │   │   │   'pretext': '{divider}',                                                                                      │                      │
│ │               │   │   │   │   'posttext': '{divider}'                                                                                      │                      │
│ │               │   │   │   }                                                                                                                │                      │
│ │               │   │   },                                                                                                                   │                      │
│ │               │   │   'templates_dir': '{bashmenu_dir}/templates',                                                                         │                      │
│ │               │   │   'scripts_dir': '{bashmenu_dir}/scripts',                                                                             │                      │
│ │               │   │   'ping_target': '1.1.1.1',                                                                                            │                      │
│ │               │   │   'tab_to_spaces': True,                                                                                               │                      │
│ │               │   │   'tabstop': 4,                                                                                                        │                      │
│ │               │   │   'show_menu_shortcuts': True,                                                                                         │                      │
│ │               │   │   'use_nerd_fonts': True,                                                                                              │                      │
│ │               │   │   ... +4                                                                                                               │                      │
│ │               │   }                                                                                                                        │                      │
│ │               }                                                                                                                            │                      │
│ │  extra_keys = []                                                                                                                           │                      │
│ │   flag_name = 'display_theme_colors'                                                                                                       │                      │
│ │       flags = []                                                                                                                           │                      │
│ │        icon = '{nf::#f11e7}'                                                                                                               │                      │
│ │   inspector = Static(id='inspector_content')                                                                                               │                      │
│ │        item = {'type': 'editor', 'action': '{home}/autoexec.sh', 'icon': '{nf::#f11e7}', 'label': 'Edit autoexec.sh [{home}/autoexec.sh]'} │                      │
│ │   item_type = 'editor'                                                                                                                     │                      │
│ │         key = None                                                                                                                         │                      │
│ │  known_keys = {'items', 'picker', 'command', 'file', 'on_yes', 'on_no', 'target', 'label', 'template', 'icon', ... +28}                    │                      │
│ │       lines = [                                                                                                                            │                      │
│ │               │   '[bold magenta][EDT] EDITOR[/bold magenta]',                                                                             │                      │
│ │               │   '[bold white]Title/Label:[/bold white] Edit autoexec.sh [{home}/autoexec.sh]',                                           │                      │
│ │               │   '[bold cyan]Icon/Glyph:[/bold cyan] {nf::#f11e7}',                                                                       │                      │
│ │               │   '[bold yellow]Action/Target:[/bold yellow] {home}/autoexec.sh',                                                          │                      │
│ │               │   '[bold cyan]Preview:[/bold cyan]\n  1.  \U000f11e7   Edit au    [/home/andrew/aut'                                       │                      │
│ │               ]                                                                                                                            │                      │
│ │         msg = None                                                                                                                         │                      │
│ │       on_no = None                                                                                                                         │                      │
│ │      on_yes = None                                                                                                                         │                      │
│ │      picker = None                                                                                                                         │                      │
│ │ preview_str = '  1.  \U000f11e7   Edit au    [/home/andrew/aut'                                                                            │                      │
│ │        self = MenuEditScreen()                                                                                                             │                      │
│ │   start_dir = None                                                                                                                         │                      │
│ │      target = None                                                                                                                         │                      │
│ │    template = None                                                                                                                         │                      │
│ │       title = 'Edit autoexec.sh [{home}/autoexec.sh]'                                                                                      │                      │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯                      │
│                                                                                                                                                                     │
│ /home/andrew/github/bashmenu/.venv/lib/python3.12/site-packages/textual/widgets/_static.py:94 in update                                                             │
│                                                                                                                                                                     │
│   91 │   │   """                                                                                                                                                    │
│   92 │   │                                                                                                                                                          │
│   93 │   │   self.__content = content                                                                                                                               │
│ ❱ 94 │   │   self.__visual = visualize(self, content, markup=self._render_markup)                                                                                   │
│   95 │   │   self.refresh(layout=layout)                                                                                                                            │
│   96                                                                                                                                                                │
│                                                                                                                                                                     │
│ ╭────────────────────────────────────────────── locals ──────────────────────────────────────────────╮                                                              │
│ │ content = '[bold magenta][EDT] EDITOR[/bold magenta]\n\n[bold white]Title/Label:[/bold white]'+221 │                                                              │
│ │  layout = True                                                                                     │                                                              │
│ │    self = Static(id='inspector_content')                                                           │                                                              │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────╯                                                              │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
MarkupError: closing tag '[/home/andrew/aut]' does not match any open tag
```
