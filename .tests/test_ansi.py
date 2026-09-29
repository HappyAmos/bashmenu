#!/usr/bin/env python3
"""
test_ansi.py - Unit tests for ANSI escape code parsing and color rendering in bashmenu.py
"""

import os
import sys
import unittest
from unittest import mock

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bashedit
import bashmenu
import bashmenu_ui
import menuedit


class TestAnsiParsing(unittest.TestCase):
    """
    Test suite for ANSI escape sequence parsing, sanitization, and curses
    color attribute resolution within the bashmenu engine.
    """
    def test_parse_ansi_line_empty(self):
        """Test parsing an empty string."""
        segments = bashmenu.parse_ansi_line("", 0)
        self.assertEqual(segments, [])

    def test_parse_ansi_line_plain_text(self):
        """Test parsing plain text with no escape sequences."""
        segments = bashmenu.parse_ansi_line("Hello World", 42)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "Hello World")
        self.assertEqual(segments[0][1], 42)

    def test_parse_ansi_line_simple_color(self):
        """Test parsing a string with standard standard ANSI color sequences (e.g. Red, Green)."""
        # Red text
        segments = bashmenu.parse_ansi_line("\x1b[31mRedText", 0)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "RedText")
        # In uninitialized curses test environment, attributes resolve to 0
        attr = segments[0][1]
        self.assertEqual(attr, 0)

    def test_parse_ansi_line_multiple_segments(self):
        """Test parsing multiple consecutive styled text segments."""
        line = "\x1b[1;31mBoldRed\x1b[0;32mGreen\x1b[4;34mUnderlineBlue"
        segments = bashmenu.parse_ansi_line(line, 0)
        self.assertEqual(len(segments), 3)
        
        self.assertEqual(segments[0][0], "BoldRed")
        self.assertEqual(segments[1][0], "Green")
        self.assertEqual(segments[2][0], "UnderlineBlue")

    def test_parse_character_set_sequences(self):
        """Test that character set selection sequences like \x1b(B and other non-SGR escape sequences are discarded."""
        line = "\x1b[31mRedText\x1b(B\x1b[0mNormalText"
        segments = bashmenu.parse_ansi_line(line, 42)
        # Should parse into 'RedText' (styled) and 'NormalText' (reset style). The \x1b(B should be fully ignored.
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][0], "RedText")
        self.assertEqual(segments[1][0], "NormalText")

    def test_process_line_to_segments(self):
        """Test expanding tabs, parsing ANSI codes and sanitizing non-printable characters."""
        # \x00 is non-printable and should be filtered, \t should be expanded to 4 spaces, colors preserved
        # 'Hell' is 4 chars, so tab starting at col 4 expands to col 8 (exactly 4 spaces)
        line = "\x1b[35mHell\t\x00World"
        segments = bashmenu.process_line_to_segments(line, 0)
        self.assertEqual(len(segments), 1)
        # Check that tab expanded to 4 spaces and \x00 was removed
        self.assertEqual(segments[0][0], "Hell    World")

    def test_process_line_to_segments_fallback(self):
        """Test that empty or fully-sanitized strings return at least an empty segment with default style."""
        line = "\x1b[35m\x00"
        segments = bashmenu.process_line_to_segments(line, 999)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "")
        self.assertEqual(segments[0][1], 999)

    def test_interpolate_placeholders_ascii(self):
        """Test that {ascii:168} and similar resolve correctly to CP437 equivalents (e.g. ¿)."""
        text = "Hello {ascii:168} World"
        resolved = bashmenu.interpolate_placeholders(text, {})
        self.assertEqual(resolved, "Hello ¿ World")

    def test_interpolate_placeholders_window_dims(self):
        """Test that {window_width} and {window_height} resolve to valid integer strings representing window dimensions."""
        text = "Dims: {window_width}x{window_height}"
        resolved = bashmenu.interpolate_placeholders(text, {})
        self.assertTrue(resolved.startswith("Dims: "))
        self.assertNotIn("{window_width}", resolved)
        self.assertNotIn("{window_height}", resolved)

    def test_interpolate_placeholders_window_dims_dynamic(self):
        """Test that {window_width} updates dynamically when curses dimensions change."""
        with mock.patch("curses.update_lines_cols", lambda: None):
            with mock.patch("curses.COLS", 120), mock.patch("curses.LINES", 40):
                resolved = bashmenu.interpolate_placeholders("{window_width}x{window_height}", {})
                self.assertEqual(resolved, "112x34")

            with mock.patch("curses.COLS", 160), mock.patch("curses.LINES", 50):
                resolved = bashmenu.interpolate_placeholders("{window_width}x{window_height}", {})
                self.assertEqual(resolved, "152x44")

    def test_interpolate_placeholders_new_directives(self):
        """Test that all newly added custom status gutter placeholders resolve properly."""
        placeholders = [
            "{host}",
            "{user-mode}",
            "{version}",
            "{date_time_12}",
            "{date_time_24}",
            "{date}",
            "{time_12}",
            "{time_24}",
            "{battery}",
            "{utc_seconds}",
        ]
        for p in placeholders:
            resolved = bashmenu.interpolate_placeholders(p, {})
            self.assertNotEqual(resolved, p)
            self.assertNotEqual(resolved, "")
            # Ensure basic type expectations or formats
            if p == "{utc_seconds}":
                self.assertTrue(resolved.isdigit())
            elif p == "{date}":
                self.assertRegex(resolved, r"^\d{4}-\d{2}-\d{2}$")

    def test_get_battery_info_caching(self):
        """Test that get_battery_info properly caches results and avoids multiple slower lookups."""
        # Force a fresh fetch by clearing the cache time
        bashmenu._last_battery_time = 0.0
        first_call = bashmenu.get_battery_info()
        
        # Modify the cached value to verify cache-hits return the modified value within the 5s window
        bashmenu._cached_battery = "42%"
        second_call = bashmenu.get_battery_info()
        self.assertEqual(second_call, "42%")

        # Force fresh fetch again
        bashmenu._last_battery_time = 0.0
        third_call = bashmenu.get_battery_info()
        self.assertEqual(third_call, first_call)

    def test_scripts_placeholder_and_resolution(self):
        """Test that {scripts} resolves properly in interpolate_placeholders."""
        resolved = bashmenu.interpolate_placeholders("{scripts}/bsdgames.sh", {})
        self.assertTrue(resolved.endswith("/scripts/bsdgames.sh"))
        self.assertNotIn("{scripts}", resolved)

    def test_formatting_escaping_and_code_spans(self):
        """Test backslash escaping, code block/span tag suppression, and no_formatting flag."""
        from bashmenu_ui import formatting_to_rich_text, strip_formatting_tags

        # Escaped tag test
        escaped_text = r"Use \[b]bold\[/b] tag"
        rt_escaped = formatting_to_rich_text(escaped_text)
        self.assertEqual(rt_escaped.plain, "Use [b]bold[/b] tag")

        # Code span tag suppression test
        code_span_text = "Look at `[b]code[/b]` and [b]bold[/b]"
        rt_code = formatting_to_rich_text(code_span_text)
        self.assertEqual(rt_code.plain, "Look at `[b]code[/b]` and bold")

        # Code block tag suppression test
        code_block_text = "```\n[color=red]red[/color]\n```"
        rt_block = formatting_to_rich_text(code_block_text)
        self.assertEqual(rt_block.plain, "```\n[color=red]red[/color]\n```")

        # no_formatting flag test
        no_fmt_text = "[b]hello[/b] [color=blue]world[/color]"
        rt_no_fmt = formatting_to_rich_text(no_fmt_text, no_formatting=True)
        self.assertEqual(rt_no_fmt.plain, "[b]hello[/b] [color=blue]world[/color]")

        # strip_formatting_tags tests
        stripped = strip_formatting_tags(r"\[b]literal\[/b] and `[u]code[/u]` and [dim]dim[/dim]")
        self.assertEqual(stripped, "[b]literal[/b] and `[u]code[/u]` and dim")

        stripped_no_fmt = strip_formatting_tags("[b]bold[/b]", no_formatting=True)
        self.assertEqual(stripped_no_fmt, "[b]bold[/b]")

    def test_cache_dir_placeholders_and_resolution(self):
        """Test that {cache_dir}, {cache}, and {settings.cache_dir} resolve properly in interpolate_placeholders."""
        config = {"settings": {"cache_dir": "{home}/custom_cache/bashmenu"}}
        resolved_dir = bashmenu.interpolate_placeholders("{cache_dir}/test.txt", config)
        resolved_cache = bashmenu.interpolate_placeholders("{cache}/test.txt", config)
        resolved_setting = bashmenu.interpolate_placeholders("{settings.cache_dir}/test.txt", config)

        expected_prefix = os.path.expanduser("~") + "/custom_cache/bashmenu"
        self.assertTrue(resolved_dir.startswith(expected_prefix))
        self.assertTrue(resolved_cache.startswith(expected_prefix))
        self.assertTrue(resolved_setting.startswith(expected_prefix))
        self.assertEqual(os.environ.get("CACHE_DIR"), expected_prefix)


class TestNerdFontWidth(unittest.TestCase):
    """
    Test suite for PUA Nerd Font glyph width calculation and auto-detection.
    """
    def test_is_pua_glyph(self):
        """Test detection of Private Use Area characters."""
        self.assertTrue(bashmenu.is_pua_glyph("\uf07c"))  # Folder glyph
        self.assertTrue(bashmenu.is_pua_glyph("\ue7f0"))  # Python glyph
        self.assertFalse(bashmenu.is_pua_glyph("A"))
        self.assertFalse(bashmenu.is_pua_glyph("1"))

    def test_get_nerd_font_width_explicit_config(self):
        """Test explicit nerd_font_width settings (1 vs 2)."""
        config_1 = {"settings": {"nerd_font_width": 1}}
        config_2 = {"settings": {"nerd_font_width": 2}}

        self.assertEqual(bashmenu.get_nerd_font_width(config_1), 1)
        self.assertEqual(bashmenu.get_nerd_font_width(config_2), 2)
        self.assertEqual(bashmenu.get_char_width("\uf07c", config_1), 1)
        self.assertEqual(bashmenu.get_char_width("\uf07c", config_2), 2)

    def test_get_nerd_font_width_auto_kitty(self):
        """Test auto-detection in Kitty terminal environment."""
        config_auto = {"settings": {"nerd_font_width": "auto"}}
        with mock.patch.dict(os.environ, {"KITTY_WINDOW_ID": "12345", "TERM": "xterm-kitty"}):
            self.assertEqual(bashmenu.get_nerd_font_width(config_auto), 1)
            self.assertEqual(bashmenu.get_char_width("\uf07c", config_auto), 1)
            self.assertEqual(bashmenu.get_display_width("\uf07c Icon", config_auto), 6)

    def test_get_nerd_font_width_auto_standard(self):
        """Test auto-detection in standard terminal environment."""
        config_auto = {"settings": {"nerd_font_width": "auto"}}
        with mock.patch.dict(os.environ, {"KITTY_WINDOW_ID": "", "TERM": "xterm-256color"}, clear=True):
            self.assertEqual(bashmenu.get_nerd_font_width(config_auto), 1)
            self.assertEqual(bashmenu.get_char_width("\uf07c", config_auto), 1)
            self.assertEqual(bashmenu.get_display_width("\uf07c Icon", config_auto), 6)

    def test_shortcut_badge_display_width(self):
        """Test that shortcut key badges like '[b]' are calculated as 3 columns wide."""
        self.assertEqual(bashmenu.get_display_width("[b]"), 3)
        self.assertEqual(bashmenu.get_display_width("[0]"), 3)

    def test_emoji_variation_selector_display_width(self):
        """Test display width calculations and glyph resolution for emojis with Variation Selector-16 (\uFE0F)."""
        # East Asian Wide emojis have width 2
        self.assertEqual(bashmenu.get_display_width("\U0001F680"), 2)
        self.assertEqual(bashmenu.get_display_width("\U0001F310"), 2)
        # Emojis with \uFE0F variation selector-16 calculate display width matching terminal cell grid
        self.assertEqual(bashmenu.resolve_glyph("\u2699\uFE0F"), "\u2699\uFE0F")
        self.assertEqual(bashmenu.resolve_glyph("\u2139\uFE0F"), "\u2139\uFE0F")
        self.assertEqual(bashmenu.resolve_glyph("\U0001F326\uFE0F"), "\U0001F326\uFE0F")
        self.assertGreaterEqual(bashmenu.get_display_width("\u2699\uFE0F"), 1)
        self.assertGreaterEqual(bashmenu.get_display_width("\u2139\uFE0F"), 1)
        self.assertGreaterEqual(bashmenu.get_display_width("\U0001F326\uFE0F"), 1)




class TestBashEditThemeColors(unittest.TestCase):
    """Test suite for bashedit --display-theme-colors feature."""

    def test_get_line_color_spans(self):
        ed = bashedit.EditorWidget(display_theme_colors=True)
        spans = ed.get_line_color_spans("title: [201, -1]")
        self.assertEqual(len(spans), 2)
        start, end, style = spans[0]
        self.assertEqual(start, 8)
        self.assertEqual(end, 11)
        self.assertEqual(style.color.name, "#ff00ff")

    def test_get_line_color_spans_tokens(self):
        ed = bashedit.EditorWidget(display_theme_colors=True)
        spans = ed.get_line_color_spans("background: [COLOR_BLACK, -1]")
        self.assertEqual(len(spans), 2)
        _start, _end, style = spans[0]
        self.assertIn(style.color.name, ["#000000", "black"])

    def test_outside_brackets_ignored(self):
        ed = bashedit.EditorWidget(display_theme_colors=True)
        spans = ed.get_line_color_spans("background: COLOR_BLACK")
        self.assertEqual(len(spans), 0)
        spans_256 = ed.get_line_color_spans("256:")
        self.assertEqual(len(spans_256), 0)

    def test_help_manual_and_view_colors_flag(self):
        screen_with_flag = bashedit.BashEditScreen(display_theme_colors=True)
        self.assertTrue(screen_with_flag.display_theme_colors_flag)

        screen_without_flag = bashedit.BashEditScreen(display_theme_colors=False)
        self.assertFalse(screen_without_flag.display_theme_colors_flag)

    @mock.patch("bashmenu.get_plugin_outputs", lambda config: [])
    def test_f1_help_modal_press_without_markup_error(self):
        import asyncio

        from textual.app import App

        import bashmenu

        class TestApp(App):
            def on_mount(self):
                self.push_screen(bashmenu.BashMenuScreen())

        async def run_test():
            app = TestApp()
            async with app.run_test() as pilot:
                await pilot.pause(0.1)
                await pilot.press("f1")
                await pilot.pause(0.2)
                self.assertEqual(type(app.screen).__name__, "MessageModalScreen")

        asyncio.run(run_test())


class TestThemeProperties(unittest.TestCase):
    """Test suite for help_text and plugin theme properties."""

    def test_init_theme_colors_includes_help_text_and_plugin(self):
        import bashmenu_ui
        styles = bashmenu_ui.init_theme_colors("dracula")
        self.assertIn("help_text", styles)
        self.assertIsNotNone(styles["help_text"])
        self.assertIn("plugin", styles)
        self.assertIsNotNone(styles["plugin"])

    def test_all_themes_have_help_text_and_plugin_properties(self):
        import bashmenu_ui
        themes_data = bashmenu_ui.load_themes_file()
        self.assertTrue(len(themes_data) > 0)
        for theme_name, theme_def in themes_data.items():
            for mode in (256, 16, 8):
                if mode in theme_def:
                    self.assertIn("help_text", theme_def[mode], f"Theme {theme_name} mode {mode} missing help_text")
                    self.assertIn("plugin", theme_def[mode], f"Theme {theme_name} mode {mode} missing plugin")


class TestMenuEditTreeSelection(unittest.TestCase):
    def test_get_active_title_chain_and_node_matching(self):
        import bashmenu
        import menuedit

        fake_screen = type("FakeScreen", (), {})()
        fake_mv = type("FakeMenuView", (), {})()
        fake_mv.menu_stack = [
            {"options": [{"label": "System Information", "type": "submenu"}]},
            {"options": [{"label": "Display CPU Information [lscpu]", "type": "command"}]},
        ]
        fake_mv.selected_rows = [0, 0]
        fake_screen.menu_view = fake_mv

        chain = bashmenu._get_active_title_chain(fake_screen)
        self.assertEqual(chain, ["System Information", "Display CPU Information [lscpu]"])

        scr = menuedit.MenuEditScreen(title_chain=chain)
        mock_root = type("MockNode", (), {})()
        mock_root.data = {"title": "Root"}

        mock_child1 = type("MockNode", (), {})()
        mock_child1.data = {"label": "System Information"}
        mock_child1.children = []

        mock_child2 = type("MockNode", (), {})()
        mock_child2.data = {"label": "Display CPU Information [lscpu]"}
        mock_child2.children = []

        mock_root.children = [mock_child1]
        mock_child1.children = [mock_child2]

        matched = scr._find_node_by_chain(mock_root, chain)
        self.assertEqual(matched, mock_child2)

    @mock.patch("bashmenu.get_plugin_outputs", lambda config: [])
    def test_menuedit_screen_focus_on_selected_item(self):
        import asyncio

        from textual.app import App

        import bashmenu

        class TestApp(App):
            def on_mount(self):
                self.push_screen(bashmenu.BashMenuScreen())

        async def run_test():
            app = TestApp()
            async with app.run_test() as pilot:
                await pilot.pause(0.1)
                screen = app.screen
                mv = screen.menu_view
                opts = mv.current_menu()["options"]
                sys_info_idx = next(i for i, o in enumerate(opts) if "System Information" in str(o.get("label")))
                mv.set_current_row(sys_info_idx)
                screen.action_select_option()
                await pilot.pause(0.05)

                curr_opts = app.screen.menu_view.current_menu()["options"]
                cpu_idx = next(i for i, o in enumerate(curr_opts) if "Display CPU Information" in str(o.get("label")))
                app.screen.menu_view.set_current_row(cpu_idx)

                await pilot.press("f4")
                await pilot.pause(0.2)

                editor_screen = app.screen
                tree = editor_screen.query_one("#tree")
                self.assertIsNotNone(tree.cursor_node)
                data_title = tree.cursor_node.data.get("title") or tree.cursor_node.data.get("label")
                self.assertIn("Display CPU Information", str(data_title))

                await pilot.press("e")
                await pilot.pause(0.1)
                modal_screen = app.screen
                self.assertEqual(type(modal_screen).__name__, "ItemEditModal")

        asyncio.run(run_test())

    def test_item_edit_modal_execution_modes(self):
        import menuedit

        # Test Standard Terminal Mode initial detection and save
        item_std = {"title": "Test Item", "interactive": True, "quiet": False}
        modal_std = menuedit.ItemEditModal(item_std)
        # Check initial index
        self.assertEqual(modal_std.selected_mode_idx, 0) # default init before compose
        
        # Test saved values directly via mock/test logic
        # Standard Terminal Mode
        item1 = {"title": "Test Item"}
        m1 = menuedit.ItemEditModal(item1)
        m1.selected_mode_idx = 2
        # Mock query_one
        class DummyInput:
            value = "test"
        class DummyCheckbox:
            def __init__(self, val=True):
                self.value = val

        class DummyContainer:
            selected_mode_idx = 2

        def dummy_query_one(selector, type_or_id=None):
            if "exec_mode_container" in selector or selector == ExecModeContainer_cls:
                c = DummyContainer()
                c.selected_mode_idx = 2
                return c
            if "chk" in selector:
                return DummyCheckbox(True)
            return DummyInput()

        ExecModeContainer_cls = menuedit.ExecModeContainer
        m1.query_one = dummy_query_one
        m1.dismiss = lambda item: None
        m1.perform_save()

        self.assertFalse(m1.item.get("stream"))
        self.assertTrue(m1.item.get("interactive"))
        self.assertFalse(m1.item.get("quiet"))
        self.assertTrue(m1.item.get("alt_buffer"))

        # Interactive Mode
        m2 = menuedit.ItemEditModal(item1)
        def dummy_query_one_inter(selector, type_or_id=None):
            if "exec_mode_container" in selector or selector == ExecModeContainer_cls:
                c = DummyContainer()
                c.selected_mode_idx = 1
                return c
            if "chk" in selector:
                return DummyCheckbox(True)
            return DummyInput()
        m2.query_one = dummy_query_one_inter
        m2.dismiss = lambda item: None
        m2.perform_save()

        self.assertFalse(m2.item.get("stream"))
        self.assertTrue(m2.item.get("interactive"))
        self.assertTrue(m2.item.get("quiet"))
        self.assertTrue(m2.item.get("alt_buffer"))

        # Stream Mode
        m3 = menuedit.ItemEditModal(item1)
        def dummy_query_one_stream(selector, type_or_id=None):
            if "exec_mode_container" in selector or selector == ExecModeContainer_cls:
                c = DummyContainer()
                c.selected_mode_idx = 0
                return c
            if "chk" in selector:
                return DummyCheckbox(True)
            return DummyInput()
        m3.query_one = dummy_query_one_stream
        m3.dismiss = lambda item: None
        m3.perform_save()

        self.assertTrue(m3.item.get("stream"))
        self.assertFalse(m3.item.get("interactive"))
        self.assertTrue(m3.item.get("quiet"))

    def test_menuedit_move_item_preserves_focus(self):
        import menuedit

        menu_data = {
            "title": "Root Menu",
            "options": [
                {"title": "Item A", "type": "command"},
                {"title": "Item B", "type": "command"},
                {"title": "Item C", "type": "command"},
            ],
        }
        screen = menuedit.MenuEditScreen(menu_file_path="/tmp/fake.mnu")
        screen.menu_data = menu_data

        class DummyTree:
            def __init__(self):
                self.root = type("RootNode", (), {"data": menu_data, "label": "", "expand": lambda *a, **kw: None, "parent": None})()
                self.cursor_node = None
                self.selected_node = None

            def clear(self):
                self.root.children = []

            def focus(self):
                pass

            def select_node(self, node):
                self.selected_node = node
                self.cursor_node = node

            def scroll_to_node(self, node):
                pass

            def refresh(self):
                pass

        dummy_tree = DummyTree()
        dummy_tree.root.children = []

        def mock_build_branch(parent_node, opts):
            for item in opts:
                child = type("ChildNode", (), {"data": item, "parent": parent_node, "children": [], "expand": lambda *a, **kw: None, "add": lambda l, data: None})()
                parent_node.children.append(child)

        screen.query_one = lambda selector, type_or_id=None: dummy_tree
        screen._build_tree_branch = mock_build_branch
        screen.call_after_refresh = lambda fn, *args: fn(*args)
        screen._save_menu_quietly = lambda: None
        screen.update_inspector = lambda item: None

        screen.populate_tree(target_item=menu_data["options"][1])
        self.assertEqual(dummy_tree.cursor_node.data["title"], "Item B")

        # Test Indent Item B under Item A
        dummy_tree.cursor_node = type("ChildNode", (), {"data": menu_data["options"][1], "parent": dummy_tree.root, "children": [], "expand": lambda *a, **kw: None})()
        screen.action_indent_item()
        self.assertEqual(screen.menu_data["options"][0]["type"], "submenu")
        self.assertEqual(len(screen.menu_data["options"][0]["submenu"]["options"]), 1)
        self.assertEqual(screen.menu_data["options"][0]["submenu"]["options"][0]["title"], "Item B")

        # Test Outdent
        sub_item = screen.menu_data["options"][0]["submenu"]["options"][0]
        sub_node = type("ChildNode", (), {"data": sub_item, "parent": type("ParentNode", (), {"data": screen.menu_data["options"][0], "parent": dummy_tree.root})(), "children": []})()
        dummy_tree.cursor_node = sub_node
        screen.action_outdent_item()
        self.assertEqual(len(screen.menu_data["options"]), 3)

    def test_divider_handling(self):
        import menuedit

        # Test ItemEditModal save for divider
        item_div = {"type": "divider", "char": "-", "length": "80"}
        modal = menuedit.ItemEditModal(item_div)
        class DummyInput:
            def __init__(self, val):
                self.value = val
        def mock_query(selector, type_or_id=None):
            if "inp_char" in selector:
                return DummyInput("#")
            if "inp_length" in selector:
                return DummyInput("{window_width}")
            return DummyInput("")
        modal.query_one = mock_query
        modal.dismiss = lambda item: None
        modal.perform_save()

        self.assertEqual(modal.item, {"type": "divider", "char": "#", "length": "{window_width}"})

        # Test indenting under divider is disallowed
        menu_data = {
            "title": "Root Menu",
            "options": [
                {"type": "divider", "char": "-", "length": "80"},
                {"title": "Item A", "type": "command"},
            ],
        }
        screen = menuedit.MenuEditScreen(menu_file_path="/tmp/fake.mnu")
        screen.menu_data = menu_data
        class DummyTree:
            def __init__(self):
                self.root = type("RootNode", (), {"data": menu_data, "parent": None})()
                self.cursor_node = type("ChildNode", (), {"data": menu_data["options"][1], "parent": self.root})()
            def clear(self): pass
            def focus(self): pass
            def select_node(self, node): pass
            def scroll_to_node(self, node): pass
            def refresh(self): pass

        screen.query_one = lambda selector, type_or_id=None: DummyTree()
        screen._save_menu_quietly = lambda: None
        screen.populate_tree = lambda **kw: None

        screen.action_indent_item()
        # Item A should NOT be indented under divider
        self.assertEqual(screen.menu_data["options"][0]["type"], "divider")
        self.assertEqual(len(screen.menu_data["options"]), 2)

        # Test live divider preview update
        updated_preview = []
        class DummyPreviewBox:
            def update(self, content):
                updated_preview.append(content)

        def mock_query_preview(*args, **kwargs):
            selector = str(args[0]) if args else ""
            if "inp_char" in selector:
                return DummyInput("{ascii:196}")
            if "inp_length" in selector:
                return DummyInput("{window_width}")
            if "lbl_divider_preview" in selector:
                return DummyPreviewBox()
            return DummyInput("")

        modal_prev = menuedit.ItemEditModal({"type": "divider", "char": "{ascii:196}", "length": "{window_width}"})
        modal_prev.query_one = mock_query_preview
        modal_prev.update_divider_preview()
        self.assertEqual(len(updated_preview), 1)
        self.assertTrue(updated_preview[0].startswith("─"))

        # Test inspector divider preview
        inspector_content = []
        class DummyInspector:
            def update(self, content):
                inspector_content.append(content)
        screen.query_one = lambda *a, **kw: DummyInspector()
        screen.update_inspector(screen.menu_data["options"][0])
        self.assertEqual(len(inspector_content), 1)
        self.assertIn("Preview:", inspector_content[0])

        # Test ASCII lookup action
        pushed_screens = []
        class DummyApp:
            def __init__(self):
                self.config = {}
            def push_screen(self, screen):
                pushed_screens.append(screen)

        modal_prev._app = DummyApp()
        modal_prev.action_lookup_ascii()
        self.assertEqual(len(pushed_screens), 1)
        self.assertEqual(type(pushed_screens[0]).__name__, "StreamOutputModalScreen")

        # Test placeholders lookup action
        pushed_screens_ph = []
        class DummyAppPh:
            def __init__(self):
                self.config = {}
            def push_screen(self, screen):
                pushed_screens_ph.append(screen)

        modal_prev._app = DummyAppPh()
        modal_prev.action_show_placeholders()
        self.assertEqual(len(pushed_screens_ph), 1)
        self.assertEqual(type(pushed_screens_ph[0]).__name__, "MessageModalScreen")


class TestMouseSupportAndCloseButtons(unittest.TestCase):
    """Test suite for mouse interaction handlers and top-right modal close buttons."""

    def test_modal_close_buttons(self):
        """Verify modal screens instantiate top-right btn_close_x close button."""
        dismissed = []

        class DummyModal(bashmenu_ui.MessageModalScreen):
            def dismiss(self, result=None):
                dismissed.append(result)

        modal = DummyModal("Title", "Message")
        label = bashmenu_ui.Label("[X]", id="btn_close_x", classes="btn_close_x")
        class DummyEvent:
            widget = label
            target = label
        modal.on_click(DummyEvent())
        self.assertEqual(len(dismissed), 1)

    def test_main_menu_view_mouse_click(self):
        """Verify MainMenuView handles left-click and right-click on menu options."""
        cfg = {"theme": "dracula"}
        mnu = {"title": "Test", "options": [{"title": "Option 1", "type": "command"}]}
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)

        executed_actions = []

        class DummyScreen:
            def action_select_option(self):
                executed_actions.append("select")

            def action_edit_menu(self):
                executed_actions.append("edit")

        mv._screen = DummyScreen()

        class DummyClickEvent:
            def __init__(self, y, button):
                self.y = y
                self.button = button

        # Row 3 corresponds to Option 1
        mv.on_click(DummyClickEvent(3, 1))
        self.assertEqual(executed_actions, ["select"])

        mv.on_click(DummyClickEvent(3, 3))
        self.assertEqual(executed_actions, ["select", "edit"])

    def test_main_menu_view_mouse_move(self):
        """Verify MainMenuView updates current row highlight on mouse hover."""
        cfg = {"theme": "dracula"}
        mnu = {
            "title": "Test",
            "options": [
                {"title": "Option 1", "type": "command"},
                {"title": "Option 2", "type": "command"},
            ],
        }
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)
        self.assertEqual(mv.current_row(), 0)

        class DummyMoveEvent:
            def __init__(self, y):
                self.y = y

        # Move mouse over Option 2 (Row 4)
        mv.on_mouse_move(DummyMoveEvent(4))
        self.assertEqual(mv.current_row(), 1)

        # Move mouse over Option 1 (Row 3)
        mv.on_mouse_move(DummyMoveEvent(3))
        self.assertEqual(mv.current_row(), 0)

    def test_menuedit_footer_click(self):
        """Verify MenuEditScreen handles clicks on interactive footer labels."""
        screen = menuedit.MenuEditScreen()
        screen.menu_data = {"options": []}

        actions_called = []
        screen.action_add_item = lambda: actions_called.append("add")
        screen.action_save_menu = lambda: actions_called.append("save")
        screen.action_exit_editor = lambda: actions_called.append("exit")
        screen.action_move_down = lambda: actions_called.append("move_down")
        screen.action_move_up = lambda: actions_called.append("move_up")
        screen.action_indent_item = lambda: actions_called.append("indent")
        screen.action_outdent_item = lambda: actions_called.append("outdent")

        class DummyWidget:
            def __init__(self, wid):
                self.id = wid

        class DummyClickEvent:
            def __init__(self, widget):
                self.widget = widget
                self.target = widget

        class DummyTree:
            def is_ancestor_of(self, w):
                return False

        screen.query_one = lambda *a, **kw: DummyTree()

        screen.on_click(DummyClickEvent(DummyWidget("lbl_add")))
        self.assertIn("add", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_move_down")))
        self.assertIn("move_down", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_move_up")))
        self.assertIn("move_up", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_indent")))
        self.assertIn("indent", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_outdent")))
        self.assertIn("outdent", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_save")))
        self.assertIn("save", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_exit")))
        self.assertIn("exit", actions_called)

    def test_menuedit_tree_click_no_crash(self):
        """Verify MenuEditScreen.on_click on tree nodes focuses tree and doesn't raise AttributeError."""
        screen = menuedit.MenuEditScreen()
        screen.action_edit_item = lambda: None

        class DummyNode:
            def __init__(self):
                self.data = {"type": "command", "title": "Test Item"}

        focus_called = []
        class DummyTree:
            root = "ROOT"
            cursor_node = DummyNode()

            def __init__(self):
                self.ancestors = []

            def get_node_at_line(self, line):
                return DummyNode()

            def select_node(self, node):
                pass

            def focus(self):
                focus_called.append(True)

        dummy_tree = DummyTree()
        dummy_tree.ancestors = [dummy_tree]

        class DummyInspector:
            def update(self, val):
                pass

        def mock_query(selector, *args, **kwargs):
            if selector == "#inspector_content":
                return DummyInspector()
            return dummy_tree

        screen.query_one = mock_query

        class DummyClickEvent:
            widget = dummy_tree
            target = dummy_tree
            y = 1
            button = 1
            chain = 1
            style = mock.Mock(meta={"line": 1})

        screen.on_click(DummyClickEvent())
        self.assertTrue(len(focus_called) > 0)

    def test_bashedit_footer_click(self):
        """Verify BashEditScreen handles clicks on interactive footer labels."""
        screen = bashedit.BashEditScreen()

        actions_called = []
        screen.action_save_file = lambda: actions_called.append("save")
        screen.action_open_file = lambda: actions_called.append("open")
        screen.action_exit_editor = lambda: actions_called.append("exit")

        class DummyWidget:
            def __init__(self, wid):
                self.id = wid

        class DummyClickEvent:
            def __init__(self, widget):
                self.widget = widget
                self.target = widget

        screen.on_click(DummyClickEvent(DummyWidget("lbl_save")))
        self.assertIn("save", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_open")))
        self.assertIn("open", actions_called)

        screen.on_click(DummyClickEvent(DummyWidget("lbl_exit")))
        self.assertIn("exit", actions_called)

    def test_menuedit_close_button_click(self):
        """Verify MenuEditScreen on_click handles close button click without AttributeError."""
        screen = menuedit.MenuEditScreen()
        actions_called = []
        screen.action_exit_editor = lambda: actions_called.append("exit")

        class DummyWidget:
            def __init__(self, wid):
                self.id = wid
                self.ancestors = []

        class DummyClickEvent:
            def __init__(self, widget):
                self.widget = widget
                self.target = widget

        class DummyTree:
            cursor_node = None

        screen.query_one = lambda selector, *args, **kwargs: DummyTree()
        screen.on_click(DummyClickEvent(DummyWidget("btn_close_x")))
        self.assertIn("exit", actions_called)


class TestWindowCloseButton(unittest.TestCase):
    """Unit tests for themeable window close button formatting [X]."""

    def test_init_theme_colors_window_close_button_fallback(self):
        styles = bashmenu_ui.init_theme_colors("dracula")
        self.assertIn("window_close_button", styles)
        self.assertIsInstance(styles["window_close_button"], bashmenu_ui.Style)

    def test_format_close_button_label(self):
        theme_styles = {
            "border": bashmenu_ui.Style(color="blue"),
            "window_close_button": bashmenu_ui.Style(color="red", bold=True),
        }
        text_obj = bashmenu_ui.format_close_button_label(theme_styles)
        self.assertEqual(str(text_obj), "[X]")
        self.assertEqual(len(text_obj.spans), 3)
        self.assertEqual(text_obj.spans[0].style, theme_styles["border"])
        self.assertEqual(text_obj.spans[1].style, theme_styles["window_close_button"])
        self.assertEqual(text_obj.spans[2].style, theme_styles["border"])

    def test_all_12_themes_have_window_close_button(self):
        raw_themes = bashmenu_ui.load_themes_file()
        expected_themes = [
            "dracula",
            "nord",
            "cyberpunk",
            "gruvbox",
            "qbasic",
            "pacman",
            "industry",
            "matrix",
            "monochrome",
            "synthwave",
            "amber_crt",
            "hotdog_stand",
        ]
        for tname in expected_themes:
            self.assertIn(tname, raw_themes, f"Theme {tname} missing in bashmenu.themes")
            t_def = raw_themes[tname]
            for tier in [256, 16, 8]:
                self.assertIn(tier, t_def, f"Tier {tier} missing in theme {tname}")
                self.assertIn(
                    "window_close_button",
                    t_def[tier],
                    f"window_close_button missing in theme {tname} tier {tier}",
                )


class TestBashEditTabs(unittest.TestCase):
    """Unit tests for multi-document tab management in bashedit.py."""

    def test_editor_tab_init(self):
        tab = bashedit.EditorTab(file_path="test.sh", lines=["echo hi"])
        self.assertEqual(tab.file_path, "test.sh")
        self.assertEqual(tab.lines, ["echo hi"])
        self.assertFalse(tab.modified)

    def test_bashedit_screen_tabs_init(self):
        screen = bashedit.BashEditScreen(file_path="test.txt")
        self.assertEqual(len(screen.tabs), 1)
        self.assertEqual(screen.active_tab_idx, 0)
        self.assertEqual(screen.tabs[0].file_path, "test.txt")

    def test_bashedit_new_tab_and_switch(self):
        screen = bashedit.BashEditScreen()
        screen.action_new_tab(file_path="doc2.py", lines=["print(123)"])
        self.assertEqual(len(screen.tabs), 2)
        self.assertEqual(screen.active_tab_idx, 1)
        self.assertEqual(screen.file_path, "doc2.py")

        screen.action_prev_tab()
        self.assertEqual(screen.active_tab_idx, 0)

        screen.action_next_tab()
        self.assertEqual(screen.active_tab_idx, 1)

    def test_bashedit_close_single_tab(self):
        screen = bashedit.BashEditScreen(file_path="test.txt")
        screen.action_close_tab(0)
        self.assertEqual(len(screen.tabs), 1)
        self.assertIsNone(screen.tabs[0].file_path)


if __name__ == "__main__":
    unittest.main()







