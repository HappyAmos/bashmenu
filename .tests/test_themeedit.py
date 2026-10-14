#!/usr/bin/env python3
"""
test_themeedit.py - Test suite for BashMenu Visual Theme Editor (themeedit.py).

Verifies ThemePreviewWidget live rendering, 256/16/8 fallback palette auto-derivation,
AsciiPickerModal, ColorPickerModal, SaveThemeModal, and live inspector synchronization.
"""

import asyncio
import os
import shutil
import sys
import tempfile
import unittest

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.text import Text
from textual.widgets import Input

import bashmenu
import bashmenu_ui
import themeedit


class TestThemeEditor(unittest.TestCase):
    """Test suite for themeedit.py functionality and UI components."""

    def test_auto_derive_fallback_depths(self):
        """Verify nearest_ansi_color and auto_derive_fallback_depths generate valid 16 and 8 palettes."""
        palette_256 = {
            "background": "COLOR_BLACK",
            "title": [201, -1],
            "border": [61, -1],
            "text": [255, -1],
            "highlight": [255, 201],
            "selection": [255, 61],
        }

        pal_16, pal_8 = themeedit.auto_derive_fallback_depths(palette_256)

        # Background should map to black
        self.assertEqual(pal_16["background"], "COLOR_BLACK")
        self.assertEqual(pal_8["background"], "COLOR_BLACK")

        # Color pairs must retain length 2 and map to valid ANSI names or -1
        self.assertEqual(len(pal_16["title"]), 2)
        self.assertEqual(pal_16["title"][1], -1)
        self.assertIn("COLOR_", str(pal_16["title"][0]))

        self.assertEqual(len(pal_8["highlight"]), 2)
        self.assertIn("COLOR_", str(pal_8["highlight"][0]))
        self.assertIn("COLOR_", str(pal_8["highlight"][1]))

    def test_theme_preview_widget_rendering(self):
        """Verify ThemePreviewWidget renders title, options, plugin, gutter separator, and drop shadow."""
        sample_theme = {
            "indicator": ">",
            "divider": {"char": "─", "length": "{window_width}"},
            "window": {
                "border_horizontal": "─",
                "border_vertical": "│",
                "border_top_left": "┌",
                "border_top_right": "┐",
                "border_bottom_left": "└",
                "border_bottom_right": "┘",
                "title_left_cap": "[",
                "title_right_cap": "]",
                "gutter_border": "─",
                "gutter_separator": "│",
                "gutter_left_tee": "├",
                "gutter_right_tee": "┤",
                "gutter_top_tee": "┬",
                "gutter_bottom_tee": "┴",
                "shadow_char": "░",
            },
            "256": {
                "background": "COLOR_BLACK",
                "title": [201, -1],
                "border": [61, -1],
                "text": [255, -1],
                "selection": [255, 61],
                "shortcut_key": [201, -1],
                "divider": [61, -1],
                "plugin": [212, -1],
                "gutter": [239, -1],
                "help_text": [117, -1],
                "shadow": [236, "COLOR_BLACK"],
            },
        }

        widget = themeedit.ThemePreviewWidget(sample_theme, theme_name="test_theme")
        rendered = widget.render()
        self.assertIsInstance(rendered, Text)
        plain = rendered.plain

        self.assertIn("Bash Menu", plain)
        self.assertIn("Web Applications", plain)
        self.assertIn("Weather Dashboard", plain)
        self.assertIn("[F1] Help", plain)
        self.assertIn("test_theme", plain)
        self.assertIn("░", plain)  # Drop shadow character present

    def test_theme_editor_app_live_synchronization(self):
        """Verify ThemeEditApp launches, mounts, and updates preview on input change."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # Query preview widget
                preview = screen.query_one("#live_preview", themeedit.ThemePreviewWidget)
                initial_text = preview.render().plain
                self.assertIn("dracula", initial_text)

                # Change an input (e.g. indicator)
                inp = screen.query_one("#prop_indicator", Input)
                inp.value = "◆"
                await pilot.pause()

                updated_text = preview.render().plain
                self.assertIn("◆", updated_text)
                self.assertTrue(screen.is_dirty)

        asyncio.run(_run())

    def test_ascii_picker_modal(self):
        """Verify AsciiPickerModal mounts and selects a glyph."""
        async def _run():
            modal = themeedit.AsciiPickerModal("border_top_left", "┌")
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.push_screen(modal)
                await pilot.pause()

                self.assertIn(modal, app.screen_stack)
                # Dismiss modal with glyph
                modal.dismiss("╭")
                await pilot.pause()
                self.assertNotIn(modal, app.screen_stack)

        asyncio.run(_run())

    def test_color_picker_modal(self):
        """Verify ColorPickerModal mounts, updates preview, and dismisses with color."""
        async def _run():
            modal = themeedit.ColorPickerModal("title", 201, bg_color_val="COLOR_BLACK")
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.push_screen(modal)
                await pilot.pause()

                self.assertIn(modal, app.screen_stack)
                # Dismiss modal with selected color
                modal.dismiss(202)
                await pilot.pause()
                self.assertNotIn(modal, app.screen_stack)

        asyncio.run(_run())

    def test_theme_editor_footer_labels_and_clicks(self):
        """Verify ThemeEditScreen renders bracketed shortcut keys and responds to mouse clicks and F1."""
        import bashmenu_ui

        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # Verify all bracketed keys appear intact
                footer_labels = [lbl.render().plain for lbl in screen.query(".footer_item")]
                self.assertIn("[F1] Help", footer_labels)
                self.assertIn("[c] Pick Color", footer_labels)
                self.assertIn("[a] ASCII/Glyphs", footer_labels)
                self.assertIn("[t] Clone/Base", footer_labels)
                self.assertIn("[d] Derive 16/8", footer_labels)
                self.assertIn("[s] Save", footer_labels)
                self.assertIn("[S] Save As", footer_labels)
                self.assertIn("[r] Reset", footer_labels)
                self.assertIn("[q/ESC] Exit", footer_labels)

                # Test F1 Help shortcut
                await pilot.press("f1")
                await pilot.pause()
                self.assertIsInstance(app.screen, bashmenu_ui.MessageModalScreen)
                self.assertEqual(app.screen.modal_title, "HA Bash Menu Manual")
                app.screen.dismiss()
                await pilot.pause()

                # Test click on lbl_color
                lbl_color = screen.query_one("#lbl_color")
                await pilot.click(lbl_color)
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.ColorPickerModal)
                app.screen.dismiss(None)
                await pilot.pause()

                # Test click on lbl_ascii
                lbl_ascii = screen.query_one("#lbl_ascii")
                await pilot.click(lbl_ascii)
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.AsciiPickerModal)
                app.screen.dismiss(None)
                await pilot.pause()

        asyncio.run(_run())

    def test_themepicker_modal_footer_labels_and_clicks(self):
        """Verify ThemePickerModalScreen renders full key badges and handles footer clicks."""
        import bashmenu_ui

        async def _run():
            class DummyApp(themeedit.App):
                def on_mount(self):
                    self.push_screen(bashmenu_ui.ThemePickerModalScreen())

            app = DummyApp()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                picker = app.screen
                self.assertIsInstance(picker, bashmenu_ui.ThemePickerModalScreen)

                footer_items = [lbl.render().plain for lbl in picker.query(".footer_item")]
                self.assertIn("[ENTER] Select", footer_items)
                self.assertIn("[e] Edit", footer_items)
                self.assertIn("[c] Create", footer_items)
                self.assertIn("[ESC] Cancel", footer_items)

                # Test clicking cancel
                lbl_cancel = picker.query_one("#lbl_ft_cancel")
                await pilot.click(lbl_cancel)
                await pilot.pause()
                self.assertNotIn(picker, app.screen_stack)

        asyncio.run(_run())

    def test_themeedit_esc_clean_exit_and_parent_return(self):
        """Verify ThemeEditScreen exits cleanly on ESC without prompting when unmodified, returning to parent screen."""
        from textual.screen import Screen
        from textual.widgets import Label

        class ParentScreen(Screen):
            def compose(self):
                yield Label("Parent Menu")

        class MockApp(themeedit.App):
            def on_mount(self):
                self.push_screen(ParentScreen())

        async def _run():
            app = MockApp()
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                self.assertIsInstance(app.screen, ParentScreen)

                # Push ThemeEditScreen
                theme_screen = themeedit.ThemeEditScreen()
                app.push_screen(theme_screen)
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.ThemeEditScreen)
                self.assertFalse(theme_screen.is_dirty)

                # Press ESC without edits -> must return directly to ParentScreen without confirm prompt
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, ParentScreen)

                # Now push again, modify a field, and verify it prompts
                theme_screen2 = themeedit.ThemeEditScreen()
                app.push_screen(theme_screen2)
                await pilot.pause()
                inp = theme_screen2.query_one("#prop_indicator", Input)
                inp.value = "◆"
                await pilot.pause()
                self.assertTrue(theme_screen2.is_dirty)

                await pilot.press("escape")
                await pilot.pause()
                import bashmenu_ui
                self.assertIsInstance(app.screen, bashmenu_ui.ConfirmModalScreen)

                # Choose Yes on confirm modal -> exits cleanly to ParentScreen
                btn_yes = app.screen.query_one("#btn_yes")
                await pilot.click(btn_yes)
                await pilot.pause()
                self.assertIsInstance(app.screen, ParentScreen)

        asyncio.run(_run())


    def test_theme_preview_resolves_ascii_placeholders(self):
        """Verify ThemePreviewWidget resolves {ascii:...} placeholders in divider and borders."""
        theme_with_ascii = {
            "indicator": "{ascii:254}",
            "divider": {"char": "{ascii:205}", "length": "{window_width}"},
            "window": {
                "border_horizontal": "{ascii:205}",
                "border_vertical": "{ascii:186}",
                "border_top_left": "{ascii:201}",
                "border_top_right": "{ascii:187}",
                "border_bottom_left": "{ascii:200}",
                "border_bottom_right": "{ascii:188}",
                "title_left_cap": "{ascii:181}",
                "title_right_cap": "{ascii:198}",
                "gutter_border": "{ascii:205}",
                "gutter_separator": "{ascii:186}",
                "gutter_left_tee": "{ascii:204}",
                "gutter_right_tee": "{ascii:185}",
                "gutter_top_tee": "{ascii:203}",
                "gutter_bottom_tee": "{ascii:202}",
                "shadow_char": "░",
            },
            "256": {
                "background": "COLOR_BLACK",
                "title": [201, -1],
                "border": [61, -1],
                "text": [255, -1],
                "selection": [255, 61],
                "shortcut_key": [201, -1],
                "divider": [61, -1],
                "plugin": [212, -1],
                "gutter": [239, -1],
                "help_text": [117, -1],
                "shadow": [236, "COLOR_BLACK"],
            },
        }

        widget = themeedit.ThemePreviewWidget(theme_with_ascii, theme_name="ascii_test")
        plain = widget.render().plain

        # Should NOT contain raw placeholders
        self.assertNotIn("{ascii:205}", plain)
        self.assertNotIn("{ascii:254}", plain)
        # Should contain resolved CP437 characters
        self.assertIn("═", plain)
        self.assertIn("║", plain)
        self.assertIn("╔", plain)
        self.assertIn("■", plain)

    def test_theme_preview_resilient_to_malformed_ascii_macro(self):
        """Verify ThemePreviewWidget renders without layout distortion when malformed macros like {ascii:219s} are present."""
        theme_malformed = {
            "indicator": "{ascii:219s}",
            "divider": {"char": "{ascii:205invalid}", "length": "{window_width}"},
            "window": {
                "border_horizontal": "{ascii:196s}",
                "gutter_separator": "{ascii:219s}",
                "border_top_left": "{invalid_macro}",
                "shadow_char": "{ascii:176s}",
            },
            "256": {
                "background": "COLOR_BLACK",
                "title": [201, -1],
                "border": [61, -1],
                "text": [255, -1],
                "selection": [255, 61],
                "shortcut_key": [201, -1],
                "divider": [61, -1],
                "plugin": [212, -1],
                "gutter": [239, -1],
                "help_text": [117, -1],
                "shadow": [236, "COLOR_BLACK"],
            },
        }

        # 1. bashmenu.interpolate_placeholders should resolve {ascii:219s} cleanly to █
        resolved = bashmenu.interpolate_placeholders("{ascii:219s}", {})
        self.assertEqual(resolved, "█")

        # 2. ThemePreviewWidget should not leak raw macros or distort line widths
        widget = themeedit.ThemePreviewWidget(theme_malformed, theme_name="malformed_test")
        rendered = widget.render()
        lines = rendered.plain.splitlines()

        # Check line widths: Row 0 has 56 columns (no drop shadow), Rows 1-11 have 58 columns
        self.assertEqual(len(lines), 12)
        self.assertEqual(len(lines[0]), 56)
        for i, line in enumerate(lines[1:], start=1):
            self.assertEqual(
                len(line),
                58,
                f"Row {i} width is {len(line)}, expected 58. Line content:\n{line}",
            )

        # Gutter content row (Row 9) must contain █ instead of raw '{ascii:219s}'
        self.assertNotIn("{ascii:219s}", lines[9])
        self.assertIn("█", lines[9])


    def test_ascii_picker_modal_shows_cp437_codes(self):
        """Verify AsciiPickerModal displays recognized CP437 ASCII code numbers and macro format."""
        async def _run():
            modal = themeedit.AsciiPickerModal("test_border", "─")
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                app.push_screen(modal)
                await pilot.pause()
                opt_list = modal.query_one("#glyph_list")
                prompts = [str(opt.prompt) for opt in opt_list._options if hasattr(opt, "prompt")]
                self.assertTrue(any("(ASCII: 196 -> {ascii:196})" in p for p in prompts))
                self.assertTrue(any("(ASCII: 205 -> {ascii:205})" in p for p in prompts))
                self.assertTrue(any("(ASCII: 179 -> {ascii:179})" in p for p in prompts))

        asyncio.run(_run())

    def test_modals_close_button_x_clicks(self):
        """Verify close [X] buttons dismiss AsciiPickerModal, ColorPickerModal, and SaveThemeModal."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                # 1. AsciiPickerModal
                ascii_modal = themeedit.AsciiPickerModal("border", "─")
                app.push_screen(ascii_modal)
                await pilot.pause()
                await pilot.click(ascii_modal.query_one("#btn_close_x"))
                await pilot.pause()
                self.assertNotIn(ascii_modal, app.screen_stack)

                # 2. ColorPickerModal
                color_modal = themeedit.ColorPickerModal("title", 201)
                app.push_screen(color_modal)
                await pilot.pause()
                await pilot.click(color_modal.query_one("#btn_close_x"))
                await pilot.pause()
                self.assertNotIn(color_modal, app.screen_stack)

                # 3. SaveThemeModal
                save_modal = themeedit.SaveThemeModal("my_custom_theme")
                app.push_screen(save_modal)
                await pilot.pause()
                await pilot.click(save_modal.query_one("#btn_close_x"))
                await pilot.pause()
                self.assertNotIn(save_modal, app.screen_stack)

        asyncio.run(_run())

    def test_theme_editor_applies_configured_theme_styles(self):
        """Verify ThemeEditScreen applies configured theme styles and borders to editor UI."""
        import bashmenu_ui

        async def _run():
            screen = themeedit.ThemeEditScreen(
                initial_theme="tokyo_night",
                configured_theme="pacman",
            )
            app = themeedit.ThemeEditApp("tokyo_night")
            async with app.run_test(size=(120, 36)) as pilot:
                app.push_screen(screen)
                await pilot.pause()

                self.assertEqual(screen.configured_theme, "pacman")
                ts = screen.configured_theme_styles
                self.assertIsNotNone(ts)

                # Workspace and screen should have background from configured theme
                bg_style = ts.get("background")
                if bg_style and bg_style.bgcolor:
                    css_bg = bashmenu_ui.parse_css_color(bg_style.bgcolor.name)
                    self.assertEqual(screen.styles.background.hex.lower(), css_bg.lower())

                # Panel borders should use configured border color
                border_style = ts.get("border")
                if border_style and border_style.color:
                    css_border = bashmenu_ui.parse_css_color(border_style.color.name)
                    prev_panel = screen.query_one("#preview_panel")
                    self.assertEqual(prev_panel.styles.border.top[1].hex.lower(), css_border.lower())

                # Header close button should be formatted with theme
                btn_close = screen.query_one("#header #btn_close_x")
                self.assertEqual(btn_close.render().plain, bashmenu_ui.format_close_button_label(ts).plain)

                # Header title cap styling
                borders = ts.get("window_borders") or bashmenu_ui.get_theme_window_borders("pacman")
                l_cap = borders.get("title_left_cap", "[").strip() or "["
                h_title = screen.query_one("#header_title")
                self.assertIn(l_cap, h_title.render().plain)

                # Test header close button click triggers exit
                await pilot.click(btn_close)
                await pilot.pause()
                self.assertNotIn(screen, app.screen_stack)

        asyncio.run(_run())

    def test_theme_picker_modal_edit_and_create_actions(self):
        """Verify ThemePickerModalScreen splits Edit and Create and launches CreateThemePromptModal."""
        import bashmenu_ui

        async def _run():
            modal = bashmenu_ui.ThemePickerModalScreen(current_theme="dracula")
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                app.push_screen(modal)
                await pilot.pause()

                # Verify footer labels
                foot_labels = [lbl.render().plain for lbl in modal.query(".footer_item")]
                self.assertIn("[ENTER] Select", foot_labels)
                self.assertIn("[e] Edit", foot_labels)
                self.assertIn("[c] Create", foot_labels)
                self.assertIn("[ESC] Cancel", foot_labels)

                # Press 'c' to trigger create action
                await pilot.press("c")
                await pilot.pause()

                # Verify CreateThemePromptModal opened
                self.assertIsInstance(app.screen, bashmenu_ui.CreateThemePromptModal)
                prompt_modal = app.screen
                self.assertIn("dracula", prompt_modal.selected_theme)

                # Test 'From Scratch' button
                btn_scratch = prompt_modal.query_one("#btn_scratch")
                await pilot.click(btn_scratch)
                await pilot.pause()

                # Should have launched ThemeEditScreen in is_new mode
                self.assertIsInstance(app.screen, themeedit.ThemeEditScreen)
                new_screen = app.screen
                self.assertTrue(new_screen.is_new)
                self.assertTrue(new_screen.is_dirty)
                # Check header display has file name and Untitled
                hdr_text = new_screen.query_one("#header_title").render().plain
                self.assertIn("bashmenu.themes", hdr_text)
                self.assertIn("[Untitled]", hdr_text)

        asyncio.run(_run())

    def test_save_vs_save_as_distinction(self):
        """Verify Save directly overwrites existing themes, but prompts for untitled/new themes and Save As."""
        async def _run():
            with tempfile.NamedTemporaryFile(suffix=".themes", delete=False) as tmp:
                tmp_path = tmp.name
            real_themes = os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.themes")
            shutil.copyfile(real_themes, tmp_path)

            try:
                # 1. Existing theme: Save directly saves to disk without modal prompt
                screen_existing = themeedit.ThemeEditScreen(
                    initial_theme="dracula",
                    themes_filepath=tmp_path,
                    is_new=False,
                )
                app = themeedit.ThemeEditApp("dracula")
                async with app.run_test(size=(120, 36)) as pilot:
                    app.push_screen(screen_existing)
                    await pilot.pause()

                    # Trigger direct save
                    screen_existing.action_save_theme()
                    await pilot.pause()

                    # Confirmation message modal should appear, NOT SaveThemeModal
                    self.assertIsInstance(app.screen, bashmenu_ui.MessageModalScreen)
                    self.assertEqual(app.screen.modal_title, "Theme Saved")
                    app.screen.dismiss()
                    await pilot.pause()

                    # Trigger Save As: MUST open SaveThemeModal
                    screen_existing.action_save_as_theme()
                    await pilot.pause()
                    self.assertIsInstance(app.screen, themeedit.SaveThemeModal)
                    app.screen.dismiss(None)
                    await pilot.pause()

                    # 2. New / Untitled theme: Save MUST automatically open SaveThemeModal
                    screen_new = themeedit.ThemeEditScreen(
                        themes_filepath=tmp_path,
                        is_new=True,
                    )
                    app.push_screen(screen_new)
                    await pilot.pause()

                    screen_new.action_save_theme()
                    await pilot.pause()
                    self.assertIsInstance(app.screen, themeedit.SaveThemeModal)
                    # Verify input is empty for untitled theme
                    name_input = app.screen.query_one("#input_theme_name")
                    self.assertEqual(name_input.value, "")
                    app.screen.dismiss(None)
                    await pilot.pause()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
