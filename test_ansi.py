#!/usr/bin/env python3
"""
test_ansi.py - Unit tests for ANSI escape code parsing and color rendering in bashmenu.py
"""

import os
import sys
import unittest
from unittest import mock

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bashmenu


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
        # Emojis with \uFE0F variation selector-16 calculate display width 2
        self.assertEqual(bashmenu.resolve_glyph("\u2699\uFE0F"), "\u2699\uFE0F")
        self.assertEqual(bashmenu.resolve_glyph("\u2139\uFE0F"), "\u2139\uFE0F")
        self.assertEqual(bashmenu.resolve_glyph("\U0001F326\uFE0F"), "\U0001F326\uFE0F")
        self.assertEqual(bashmenu.get_display_width("\u2699\uFE0F"), 2)
        self.assertEqual(bashmenu.get_display_width("\u2139\uFE0F"), 2)
        self.assertEqual(bashmenu.get_display_width("\U0001F326\uFE0F"), 2)


import bashedit


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


if __name__ == "__main__":
    unittest.main()

