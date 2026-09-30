#!/usr/bin/env python3
import os
import sys
import unittest

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bashmenu
import bashmenu_ui
import ymlcheck


class TestImprovements(unittest.TestCase):
    def test_date_time_12_short_interpolation(self):
        config = bashmenu.load_config()[0]
        text = "Current: {date_time_12_short}"
        result = bashmenu.interpolate_placeholders(text, config)
        self.assertNotIn("{date_time_12_short}", result)
        self.assertTrue("AM" in result or "PM" in result)

    def test_file_picker_allow_new(self):
        fp = bashmenu_ui.FilePickerModalScreen("Test Picker", mode="file", allow_new=True)
        self.assertTrue(fp.allow_new)
        # Bindings should include 'n'
        binding_keys = [b.key for b in fp.BINDINGS]
        self.assertIn("n", binding_keys)

    def test_theme_picker_modal(self):
        tp = bashmenu_ui.ThemePickerModalScreen(current_theme="dracula")
        self.assertEqual(tp.current_theme, "dracula")
        binding_keys = [b.key for b in tp.BINDINGS]
        self.assertIn("escape", binding_keys)

    def test_ymlcheck_modes(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        theme_path = os.path.join(base_dir, "bashmenu.themes")
        config_path = os.path.join(base_dir, "bashmenu.yml")
        menu_path = os.path.join(base_dir, "bashmenu.mnu")

        self.assertTrue(ymlcheck.validate_yaml_syntax(config_path))
        self.assertTrue(ymlcheck.validate_yaml_syntax(menu_path))
        self.assertTrue(ymlcheck.validate_theme_file(theme_path))
        self.assertTrue(ymlcheck.validate_config_file(config_path))
        self.assertTrue(ymlcheck.validate_menu_file(menu_path))

    def test_bashedit_character_input(self):
        import asyncio

        import textual.keys as k
        from textual.app import App

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_input_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")

                # Specifically test period and letter f (which were previously blocked by event.key.startswith('f'))
                for test_char in [".", "f", "F", " ", "/", "-", "a", "Z", "0", "@"]:
                    ed.lines = [""]
                    ed.cursor_x = 0
                    ed.cursor_y = 0
                    key_name = k._character_to_key(test_char)
                    await pilot.press(key_name)
                    self.assertEqual(ed.lines[0], test_char, f"Character '{test_char}' (key '{key_name}') was blocked!")

        asyncio.run(run_input_checks())

    def test_bashedit_mouse_scroll_and_page_nav(self):
        import asyncio

        from textual.app import App
        from textual.events import MouseScrollDown, MouseScrollUp

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_scroll_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")
                ed.lines = [f"Line {i}" for i in range(100)]
                ed.top_line = 0
                ed.cursor_y = 0

                # Test mouse wheel scroll down
                ed.post_message(
                    MouseScrollDown(ed, x=10, y=5, delta_x=0, delta_y=1, button=4, shift=False, meta=False, ctrl=False)
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 3)

                # Test mouse wheel scroll up
                ed.post_message(
                    MouseScrollUp(ed, x=10, y=5, delta_x=0, delta_y=-1, button=5, shift=False, meta=False, ctrl=False)
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 0)

                # Test pagedown and pageup keys
                await pilot.press("pagedown")
                self.assertTrue(ed.top_line > 0)
                await pilot.press("pageup")
                self.assertEqual(ed.top_line, 0)

        asyncio.run(run_scroll_checks())

    def test_theme_submenu_divider(self):
        sub = bashmenu.build_dynamic_theme_submenu()
        self.assertIn("options", sub)
        options = sub["options"]
        self.assertTrue(len(options) > 2)
        # First item must be a divider
        first_item = options[0]
        self.assertEqual(first_item.get("type"), "divider")
        self.assertEqual(first_item.get("length"), "{window_width}")
        # Second item must be a theme item
        second_item = options[1]
        self.assertIn("set_theme", second_item)

    def test_f1_help_markdown(self):
        import asyncio

        from rich.markdown import Markdown
        from textual.app import App

        class TestApp(App):
            def on_mount(self):
                self.push_screen(bashmenu.BashMenuScreen())

        async def run_f1_check():
            app = TestApp()
            async with app.run_test() as pilot:
                await pilot.press("f1")
                modal = app.screen
                self.assertIsInstance(modal, bashmenu_ui.MessageModalScreen)
                msg_widget = modal.query_one("#message")
                self.assertIsInstance(msg_widget.content, Markdown)

        asyncio.run(run_f1_check())

    def test_bashedit_f12_markdown_toggle(self):
        import asyncio

        from textual.app import App
        from textual.events import MouseScrollDown, MouseScrollUp
        from textual.widgets import Label

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_markdown_toggle_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")
                lbl_md = screen.query_one("#lbl_markdown", Label)

                # 1. Legend label verification
                self.assertIsNotNone(lbl_md)
                self.assertEqual(str(lbl_md.render()), "F12 MD")

                # Set up sample markdown lines
                ed.lines = ["# Title", "", "A paragraph of markdown text.", ""] + [
                    f"- Item {i}" for i in range(50)
                ]
                self.assertFalse(ed.show_markdown)
                self.assertFalse(screen.tabs[screen.active_tab_idx].show_markdown)

                # 2. Press F12 to enable Markdown rendering
                await pilot.press("f12")
                await pilot.pause()
                self.assertTrue(ed.show_markdown)
                self.assertTrue(screen.tabs[screen.active_tab_idx].show_markdown)
                status_lbl = screen.query_one("#editor_status", Label)
                self.assertIn("Markdown rendering enabled", str(status_lbl.render()))

                # 3. Test scrolling in Markdown mode
                ed.top_line = 0
                ed.post_message(
                    MouseScrollDown(
                        ed, x=10, y=5, delta_x=0, delta_y=1, button=4, shift=False, meta=False, ctrl=False
                    )
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 3)

                ed.post_message(
                    MouseScrollUp(
                        ed, x=10, y=5, delta_x=0, delta_y=-1, button=5, shift=False, meta=False, ctrl=False
                    )
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 0)

                # 4. In Markdown preview mode, typing keys does not mutate lines
                initial_lines = list(ed.lines)
                await pilot.press("a")
                await pilot.pause()
                self.assertEqual(ed.lines, initial_lines)
                self.assertIn("Markdown preview active", str(status_lbl.render()))

                # 5. Press F12 again to disable Markdown rendering
                await pilot.press("f12")
                await pilot.pause()
                self.assertFalse(ed.show_markdown)
                self.assertFalse(screen.tabs[screen.active_tab_idx].show_markdown)
                self.assertIn("Markdown rendering disabled", str(status_lbl.render()))

                # 6. Regular editing resumes
                ed.lines = [""]
                ed.cursor_x = 0
                ed.cursor_y = 0
                await pilot.press("x")
                await pilot.pause()
                self.assertEqual(ed.lines[0], "x")

                # 7. Clicking lbl_markdown toggles markdown
                screen.action_toggle_markdown()
                self.assertTrue(ed.show_markdown)

        asyncio.run(run_markdown_toggle_checks())


if __name__ == "__main__":
    unittest.main()
