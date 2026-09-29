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


if __name__ == "__main__":
    unittest.main()
