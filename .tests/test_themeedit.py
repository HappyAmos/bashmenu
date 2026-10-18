#!/usr/bin/env python3
"""
test_themeedit.py - Test suite for BashMenu Visual Theme Editor (themeedit.py).

Verifies ThemePreviewWidget live rendering, 256/16/8 fallback palette auto-derivation,
AsciiPickerModal, ColorPickerModal, SaveThemeModal, and live inspector synchronization.
"""

import asyncio
import copy
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.text import Text
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

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
                modal.dismiss([202, -1])
                await pilot.pause()
                self.assertNotIn(modal, app.screen_stack)

        asyncio.run(_run())

    def test_color_grid_widget_navigation(self):
        """Verify ColorGridWidget arrow navigation and underline on active cell."""
        grid = themeedit.ColorGridWidget(initial_code=0)
        self.assertEqual(grid.cursor_code, 0)

        # Right arrow moves +1
        grid.action_cursor_right()
        self.assertEqual(grid.cursor_code, 1)

        # Down arrow moves +16
        grid.action_cursor_down()
        self.assertEqual(grid.cursor_code, 17)

        # Left arrow moves -1
        grid.action_cursor_left()
        self.assertEqual(grid.cursor_code, 16)

        # Up arrow moves -16
        grid.action_cursor_up()
        self.assertEqual(grid.cursor_code, 0)

        # Render output should have 16 lines
        rendered = grid.render()
        lines = rendered.plain.splitlines()
        self.assertEqual(len(lines), 16)

        # The active cell (0) is underlined in the rendered Text object
        active_found = False
        for span in rendered.spans:
            if getattr(span.style, "underline", False):
                active_found = True
                break
        self.assertTrue(active_found, "Selected color code must be underlined.")

    def test_color_picker_modal_dual_layer_fg_bg(self):
        """Verify ColorPickerModal supports dual FG/BG layers, Tab switching, and swatch names."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                modal = themeedit.ColorPickerModal("title", [201, -1], bg_color_val="COLOR_BLACK")
                app.push_screen(modal)
                await pilot.pause()

                self.assertTrue(modal.is_pair)
                self.assertEqual(modal.fg_val, 201)
                self.assertEqual(modal.bg_val, -1)
                self.assertEqual(modal.active_tab, "fg")

                # Verify tab button labels explicitly indicate Foreground and Background
                btn_fg = modal.query_one("#btn_tab_fg", themeedit.Button)
                btn_bg = modal.query_one("#btn_tab_bg", themeedit.Button)
                self.assertIn("Foreground", str(btn_fg.label))
                self.assertIn("Background", str(btn_bg.label))

                # Switch layer to BG via action
                modal.action_switch_layer()
                self.assertEqual(modal.active_tab, "bg")

                # Change BG color
                grid = modal.query_one("#color_grid", themeedit.ColorGridWidget)
                grid.set_code(61)
                await pilot.pause()
                self.assertEqual(modal.bg_val, 61)

                # Switch back to FG
                modal.action_switch_layer()
                await pilot.pause()
                self.assertEqual(modal.active_tab, "fg")

                # Select constant name via swatch
                btn_swatch = modal.query_one("#swatch_COLOR_RED", themeedit.Button)
                await pilot.click(btn_swatch)
                await pilot.pause()
                self.assertEqual(modal.fg_val, "COLOR_RED")

                # Verify confirm selection returns both layers
                self.assertEqual(modal.selected_color, ["COLOR_RED", 61])

        asyncio.run(_run())

    def test_color_picker_modal_tab_navigation_reaches_all_buttons(self):
        """Verify pressing Tab moves focus from color grid to swatches and action buttons."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                modal = themeedit.ColorPickerModal("title", 201)
                app.push_screen(modal)
                await pilot.pause()

                # Initially color_grid has focus
                grid = modal.query_one("#color_grid", themeedit.ColorGridWidget)
                self.assertTrue(grid.has_focus)

                # Tab through widgets and track focused IDs
                focused_ids = []
                for _ in range(35):
                    await pilot.press("tab")
                    await pilot.pause()
                    w = app.focused
                    if w and getattr(w, "id", None):
                        focused_ids.append(w.id)

                # Verify swatches (standard and extended) and all bottom buttons were reached via Tab
                self.assertIn("swatch_inherit", focused_ids)
                self.assertIn("swatch_COLOR_ORANGE", focused_ids)
                self.assertIn("btn_select", focused_ids)
                self.assertIn("btn_inherit", focused_ids)
                self.assertIn("btn_cancel", focused_ids)

        asyncio.run(_run())

    def test_color_picker_modal_extended_swatches(self):
        """Verify ColorPickerModal renders all bright and extended swatches and clicking updates color and grid."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                modal = themeedit.ColorPickerModal("title", 201)
                app.push_screen(modal)
                await pilot.pause()

                # Verify extended color swatches are rendered
                swatch_orange = modal.query_one("#swatch_COLOR_ORANGE", themeedit.Button)
                swatch_purple = modal.query_one("#swatch_COLOR_PURPLE", themeedit.Button)
                swatch_pink = modal.query_one("#swatch_COLOR_PINK", themeedit.Button)
                swatch_brown = modal.query_one("#swatch_COLOR_BROWN", themeedit.Button)
                swatch_br_red = modal.query_one("#swatch_COLOR_BRIGHT_RED", themeedit.Button)

                self.assertIsNotNone(swatch_orange)
                self.assertIsNotNone(swatch_purple)
                self.assertIsNotNone(swatch_pink)
                self.assertIsNotNone(swatch_brown)
                self.assertIsNotNone(swatch_br_red)

                # Click COLOR_ORANGE and verify FG is set to COLOR_ORANGE and grid code is 208
                await pilot.click(swatch_orange)
                await pilot.pause()
                self.assertEqual(modal.fg_val, "COLOR_ORANGE")
                grid = modal.query_one("#color_grid", themeedit.ColorGridWidget)
                self.assertEqual(grid.cursor_code, 208)

        asyncio.run(_run())

    def test_color_picker_modal_theme_palette_tab(self):
        """Verify ColorPickerModal Theme Palette tab displays in-use colors, supports keyboard navigation and switching."""
        from textual.widgets import OptionList

        async def _run():
            app = themeedit.ThemeEditApp("dayscape")
            async with app.run_test(size=(100, 35)) as pilot:
                pal = app.screen.current_theme.get(256, {})
                modal = themeedit.ColorPickerModal("title", [235, -1], bg_color_val=189, theme_palette=pal)
                app.push_screen(modal)
                await pilot.pause()

                # Verify mode buttons exist
                btn_grid = modal.query_one("#btn_mode_grid", themeedit.Button)
                btn_pal = modal.query_one("#btn_mode_palette", themeedit.Button)
                self.assertIsNotNone(btn_grid)
                self.assertIsNotNone(btn_pal)
                self.assertEqual(modal.view_mode, "grid")

                # Verify OptionList exists and has in-use theme colors
                ol = modal.query_one("#theme_palette_list", OptionList)
                self.assertGreater(ol.option_count, 0)
                self.assertEqual(len(modal.theme_colors_list), ol.option_count)

                # Switch to Theme Palette tab via button click
                await pilot.click(btn_pal)
                await pilot.pause()
                self.assertEqual(modal.view_mode, "palette")
                self.assertEqual(str(modal.query_one("#color_grid").styles.display), "none")
                self.assertEqual(str(ol.styles.display), "block")

                # Initial highlight should match 235 (index 1 in dayscape palette)
                self.assertEqual(ol.highlighted, 1)

                # Move down in palette list to select next color (64)
                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(modal.fg_val, 64)

                # Switch to BG layer and select another color
                await pilot.click(modal.query_one("#btn_tab_bg", themeedit.Button))
                await pilot.pause()
                self.assertEqual(modal.active_tab, "bg")

                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(modal.bg_val, 16)

                # Switch back to 256 Grid view via 'g' key
                await pilot.press("g")
                await pilot.pause()
                self.assertEqual(modal.view_mode, "grid")
                self.assertEqual(str(modal.query_one("#color_grid").styles.display), "block")
                self.assertEqual(str(ol.styles.display), "none")

                # Color grid cursor should be synchronized with active BG color (16)
                grid = modal.query_one("#color_grid", themeedit.ColorGridWidget)
                self.assertEqual(grid.cursor_code, 16)

                # Confirm selection
                modal._confirm()
                await pilot.pause()
                self.assertEqual(modal.selected_color, [64, 16])

        asyncio.run(_run())

    def test_theme_editor_footer_spread_layout(self):
        """Verify update_footer_layout spreads footer items and separators proportionally across screen width."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                screen.update_footer_layout(width=120)
                await pilot.pause()

                footer = screen.query_one("#footer")
                first_row = footer.query(".footer_row").first()
                items = list(first_row.query(".footer_item"))
                seps = list(first_row.query(".footer_sep"))

                # Margins must be applied to items and separators spreading them across 120 width
                has_item_margin = any(it.styles.margin.right > 0 or it.styles.margin.left > 0 for it in items)
                has_sep_margin = any(s.styles.margin.right > 0 or s.styles.margin.left > 0 for s in seps)
                self.assertTrue(has_item_margin or has_sep_margin, "Footer items/separators should have spacing margins applied.")

        asyncio.run(_run())

    def test_ascii_picker_modal_tab_navigation_reaches_all_buttons(self):
        """Verify pressing Tab moves focus from ASCII grid to swatches and action buttons."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                modal = themeedit.AsciiPickerModal("border", "─")
                app.push_screen(modal)
                await pilot.pause()

                # Initially ascii_grid has focus
                grid = modal.query_one("#ascii_grid", themeedit.AsciiGridWidget)
                self.assertTrue(grid.has_focus)

                # Tab through widgets and track focused IDs
                focused_ids = []
                for _ in range(60):
                    await pilot.press("tab")
                    await pilot.pause()
                    w = app.focused
                    if w and getattr(w, "id", None):
                        focused_ids.append(w.id)

                # Verify all bottom buttons were reached via Tab
                self.assertIn("swatch_ascii_196", focused_ids)
                self.assertIn("btn_select", focused_ids)
                self.assertIn("btn_select_macro", focused_ids)
                self.assertIn("btn_cancel", focused_ids)

        asyncio.run(_run())

    def test_theme_preview_occupies_at_least_half_of_preview_pane(self):
        """Verify ThemePreviewWidget occupies >= 50% of preview pane area across resolutions."""
        async def _run():
            for width, height in [(100, 30), (120, 36), (140, 40), (160, 45)]:
                app = themeedit.ThemeEditApp("dracula")
                async with app.run_test(size=(width, height)) as pilot:
                    screen = themeedit.ThemeEditScreen()
                    app.push_screen(screen)
                    await pilot.pause()

                    panel = screen.query_one("#preview_panel")
                    prev = screen.query_one("#live_preview", themeedit.ThemePreviewWidget)
                    rendered = prev.render().plain.splitlines()

                    inner_pw = max(1, panel.size.width - 4)
                    inner_ph = max(1, panel.size.height - 4)
                    panel_area = inner_pw * inner_ph

                    prev_w = max(len(line) for line in rendered)
                    prev_h = len(rendered)
                    prev_area = prev_w * prev_h

                    ratio = prev_area / panel_area
                    self.assertGreaterEqual(
                        ratio,
                        0.50,
                        f"At {width}x{height}, preview ({prev_area}) was {ratio:.1%} of pane ({panel_area}), expected >= 50%",
                    )

        asyncio.run(_run())

    def test_border_character_changes_update_preview(self):
        """Verify that changing border_horizontal and border_vertical updates preview live."""
        async def _run():
            app = themeedit.ThemeEditApp("pacman")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                inp_h = screen.query_one("#prop_border_horizontal", Input)
                inp_v = screen.query_one("#prop_border_vertical", Input)

                # Change horizontal border to '='
                inp_h.value = "="
                await pilot.pause()

                preview = screen.query_one("#live_preview", themeedit.ThemePreviewWidget)
                rendered = preview.render().plain

                self.assertIn("=", rendered, "Preview should update when border_horizontal is changed.")

                # Change vertical border to '#'
                inp_v.value = "#"
                await pilot.pause()

                rendered2 = preview.render().plain
                self.assertIn("#", rendered2, "Preview should update when border_vertical is changed.")

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
                self.assertIn("[F2] Background", footer_labels)
                self.assertIn("[F3] Pick Color", footer_labels)
                self.assertIn("[F4] ASCII/Glyphs", footer_labels)
                self.assertIn("[F5] Reset", footer_labels)
                self.assertIn("[F6] Clone/Base", footer_labels)
                self.assertIn("[F7] Derive 16/8", footer_labels)
                self.assertIn("[F8] Expand All", footer_labels)
                self.assertIn("[F9] From Image", footer_labels)
                self.assertIn("[Ctrl+S] Save", footer_labels)
                self.assertIn("[Ctrl+A] Save As", footer_labels)
                self.assertIn("[ESC/q] Exit", footer_labels)

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


    def test_ascii_grid_widget_navigation(self):
        """Verify AsciiGridWidget arrow navigation and underline on active cell."""
        grid = themeedit.AsciiGridWidget(initial_code=196)
        self.assertEqual(grid.cursor_code, 196)

        # Right arrow moves +1
        grid.action_cursor_right()
        self.assertEqual(grid.cursor_code, 197)

        # Down arrow moves +16
        grid.action_cursor_down()
        self.assertEqual(grid.cursor_code, 213)

        # Left arrow moves -1
        grid.action_cursor_left()
        self.assertEqual(grid.cursor_code, 212)

        # Up arrow moves -16
        grid.action_cursor_up()
        self.assertEqual(grid.cursor_code, 196)

        # Render output should have 16 lines
        rendered = grid.render()
        lines = rendered.plain.splitlines()
        self.assertEqual(len(lines), 16)

        # Active cell is underlined in rendered Text
        active_found = False
        for span in rendered.spans:
            if getattr(span.style, "underline", False):
                active_found = True
                break
        self.assertTrue(active_found, "Selected ASCII code must be underlined.")

    def test_ascii_picker_modal_shows_cp437_codes(self):
        """Verify AsciiPickerModal displays recognized CP437 ASCII code numbers and macro format."""
        async def _run():
            modal = themeedit.AsciiPickerModal("test_border", "─")
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(100, 30)) as pilot:
                app.push_screen(modal)
                await pilot.pause()

                # Preview bar displays initial CP437 code 196 format
                p_bar = modal.query_one("#preview_bar", themeedit.Static)
                self.assertIn("(ASCII: 196 -> {ascii:196})", p_bar.render().plain)

                # Move cursor to 205 ('═')
                grid = modal.query_one("#ascii_grid", themeedit.AsciiGridWidget)
                grid.set_code(205)
                await pilot.pause()
                self.assertIn("(ASCII: 205 -> {ascii:205})", p_bar.render().plain)

                # Move cursor to 179 ('│')
                grid.set_code(179)
                await pilot.pause()
                self.assertIn("(ASCII: 179 -> {ascii:179})", p_bar.render().plain)

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

                # Test exiting from the launched ThemeEditScreen
                # Dirty prompt appears, confirm Yes -> exits cleanly to parent without ScreenError
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, bashmenu_ui.ConfirmModalScreen)
                await pilot.press("y")
                await pilot.pause()
                self.assertNotIn(new_screen, app.screen_stack)

        asyncio.run(_run())

    def test_theme_picker_modal_edit_action_clean_exit(self):
        """Verify ThemePickerModalScreen Edit action launches ThemeEditScreen and exits without ScreenError."""
        from textual.screen import Screen
        from textual.widgets import Label

        import bashmenu_ui

        class ParentScreen(Screen):
            def compose(self):
                yield Label("Parent Menu")

        class MockApp(themeedit.App):
            def on_mount(self):
                self.push_screen(ParentScreen())

        async def _run():
            app = MockApp()
            async with app.run_test(size=(120, 36)) as pilot:
                modal = bashmenu_ui.ThemePickerModalScreen(current_theme="dracula")
                app.push_screen(modal)
                await pilot.pause()

                # Press 'e' to edit dracula theme
                await pilot.press("e")
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.ThemeEditScreen)

                # Exit cleanly from ThemeEditScreen without ScreenError
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, ParentScreen)

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

    def test_click_to_inspect_elements(self):
        """Verify that left-clicking elements on ThemePreviewWidget focuses matching inspector inputs."""

        async def _run():
            app = themeedit.ThemeEditApp()
            async with app.run_test() as pilot:
                screen = app.screen
                preview = screen.query_one("#live_preview", themeedit.ThemePreviewWidget)

                # 1. Click top-left corner (0, 0) -> prop_border_top_left
                await pilot.click(preview, offset=(0, 0))
                self.assertEqual(screen.focused.id, "prop_border_top_left")

                # 2. Click title text -> color_title
                await pilot.click(preview, offset=(preview._last_w // 2, 0))
                self.assertEqual(screen.focused.id, "color_title")

                # 3. Click selected option text (row 2, col 15) -> color_highlight
                await pilot.click(preview, offset=(15, 2))
                self.assertEqual(screen.focused.id, "color_highlight")

                # 4. Click indicator glyph (row 2, col 5) -> prop_indicator
                await pilot.click(preview, offset=(5, 2))
                self.assertEqual(screen.focused.id, "prop_indicator")

                # 5. Click shortcut key (row 1, col 8) -> color_shortcut_key
                await pilot.click(preview, offset=(8, 1))
                self.assertEqual(screen.focused.id, "color_shortcut_key")

                # 6. Click unselected option label (row 1, col 15) -> color_text
                await pilot.click(preview, offset=(15, 1))
                self.assertEqual(screen.focused.id, "color_text")

                # 7. Repeated clicks: Click horizontal border (col 2, row 0)
                await pilot.click(preview, offset=(2, 0))
                self.assertEqual(screen.focused.id, "color_border")
                # Repeated clicks consistently focus the same clicked target without toggling away
                await pilot.click(preview, offset=(2, 0))
                self.assertEqual(screen.focused.id, "color_border")

                # 8. Click panel margin area -> color_background
                panel = screen.query_one("#preview_panel")
                await pilot.click(panel, offset=(0, 0))
                self.assertEqual(screen.focused.id, "color_background")

                # 9. Visual haptic feedback (flash inversion)
                from unittest.mock import patch

                with patch.object(preview, "set_timer") as mock_timer:
                    await pilot.click(preview, offset=(15, 1))
                    self.assertIsNotNone(preview._flash_range)
                    rendered = preview.render()
                    has_reverse = any(span.style and span.style.reverse is True for span in rendered.spans)
                    self.assertTrue(has_reverse)
                    mock_timer.assert_called_once()
                    preview._clear_flash()
                    self.assertIsNone(preview._flash_range)

        asyncio.run(_run())

    def test_background_config_modal_controls_and_dismissal(self):
        """Verify BackgroundConfigModal controls, browse button, and dismissal actions."""
        from textual.widgets import Select

        curr_bg = {
            "image": "assets/wallpapers/twilight.png",
            "opacity": 0.75,
            "scaling": "fit",
            "mode": "quarterblock",
            "clustering": 32,
            "quantization": 64,
        }

        class ModalApp(themeedit.App):
            def __init__(self):
                super().__init__()
                self.modal_result = "unset"

            def on_mount(self):
                def _cb(res):
                    self.modal_result = res

                self.push_screen(themeedit.BackgroundConfigModal(current_background=curr_bg), _cb)

        async def _run():
            app = ModalApp()
            async with app.run_test() as pilot:
                self.assertIsInstance(app.screen, themeedit.BackgroundConfigModal)
                modal = app.screen

                img_inp = modal.query_one("#input_bg_image", Input)
                self.assertEqual(img_inp.value, "assets/wallpapers/twilight.png")

                op_inp = modal.query_one("#input_bg_opacity", Input)
                self.assertEqual(op_inp.value, "0.75")

                sc_sel = modal.query_one("#select_bg_scaling", Select)
                self.assertEqual(sc_sel.value, "fit")

                md_sel = modal.query_one("#select_bg_mode", Select)
                self.assertEqual(md_sel.value, "quarterblock")

                cl_inp = modal.query_one("#input_bg_clustering", Input)
                self.assertEqual(cl_inp.value, "32")

                qu_inp = modal.query_one("#input_bg_quantization", Input)
                self.assertEqual(qu_inp.value, "64")

                # Test Apply button
                btn_apply = modal.query_one("#btn_apply_bg")
                await pilot.click(btn_apply)
                await pilot.pause()
                self.assertEqual(
                    app.modal_result,
                    {
                        "image": "assets/wallpapers/twilight.png",
                        "opacity": 0.75,
                        "scaling": "fit",
                        "mode": "quarterblock",
                        "clustering": 32,
                        "quantization": 64,
                    },
                )

        asyncio.run(_run())

    def test_background_config_modal_remove_and_cancel(self):
        """Verify BackgroundConfigModal remove wallpaper and cancel buttons."""
        class RemoveApp(themeedit.App):
            def __init__(self):
                super().__init__()
                self.modal_result = "unset"

            def on_mount(self):
                def _cb(res):
                    self.modal_result = res

                self.push_screen(
                    themeedit.BackgroundConfigModal(current_background="assets/wallpapers/test.png"),
                    _cb,
                )

        async def _run_remove():
            app = RemoveApp()
            async with app.run_test() as pilot:
                btn_remove = app.screen.query_one("#btn_remove_bg")
                await pilot.click(btn_remove)
                await pilot.pause()
                self.assertEqual(app.modal_result, {})

        asyncio.run(_run_remove())

        class CancelApp(themeedit.App):
            def __init__(self):
                super().__init__()
                self.modal_result = "unset"

            def on_mount(self):
                def _cb(res):
                    self.modal_result = res

                self.push_screen(
                    themeedit.BackgroundConfigModal(current_background="assets/wallpapers/test.png"),
                    _cb,
                )

        async def _run_cancel():
            app = CancelApp()
            async with app.run_test() as pilot:
                btn_cancel = app.screen.query_one("#btn_cancel_bg")
                await pilot.click(btn_cancel)
                await pilot.pause()
                self.assertIsNone(app.modal_result)

        asyncio.run(_run_cancel())

    def test_theme_editor_background_shortcut_and_inspector(self):
        """Verify ThemeEditScreen background shortcut [b] and inspector wallpaper controls."""
        app = themeedit.ThemeEditApp()

        async def _run():
            async with app.run_test() as pilot:
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # Summary input and button exist in inspector
                wp_input = screen.query_one("#prop_wallpaper_image", Input)
                self.assertIsNotNone(wp_input)
                btn_cfg = screen.query_one("#btn_config_background")
                self.assertIsNotNone(btn_cfg)

                # Press 'f2' to open modal
                await pilot.press("f2")
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.BackgroundConfigModal)

                # Cancel modal
                await pilot.press("escape")
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.ThemeEditScreen)

        asyncio.run(_run())

    def test_theme_preview_widget_with_wallpaper(self):
        """Verify ThemePreviewWidget renders safely with background wallpaper configured."""
        sample_theme = {
            "indicator": ">",
            "divider": {"char": "─", "length": "{window_width}"},
            "window": dict(bashmenu_ui.DEFAULT_WINDOW_BORDER),
            "background": {
                "image": "assets/wallpapers/twilight.png",
                "opacity": 0.5,
                "scaling": "cover",
                "mode": "halfblock",
            },
            256: {
                "background": "COLOR_BLACK",
                "title": [201, -1],
                "border": [61, -1],
                "text": [255, -1],
                "highlight": [255, 201],
                "selection": [255, 61],
                "shortcut_key": [201, -1],
                "divider": [61, -1],
                "plugin": [81, -1],
                "gutter": [61, -1],
                "help_text": [81, -1],
                "shadow": [235, "COLOR_BLACK"],
            },
        }
        widget = themeedit.ThemePreviewWidget(sample_theme, theme_name="test_wp")
        rendered = widget.render()
        self.assertIsInstance(rendered, Text)
        self.assertIn("Bash Menu", rendered.plain)

    def test_theme_editor_collapsible_sections(self):
        """Verify ThemeEditScreen collapsible section headers, default collapsed state, F8 shortcut, and auto-expansion."""
        app = themeedit.ThemeEditApp()

        async def _run():
            async with app.run_test() as pilot:
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # 1. Initial default state: all 6 sections are collapsed with '▶'
                hdr_general = screen.query_one("#hdr_general")
                sec_general = screen.query_one("#sec_general")
                self.assertIn("▶", str(hdr_general.render()))
                self.assertTrue(sec_general.has_class("collapsed"))

                lbl_expand_all = screen.query_one("#lbl_expand_all", Label)
                self.assertIn("Expand All", str(lbl_expand_all.render()))

                # 2. Press F8 to expand all sections
                await pilot.press("f8")
                await pilot.pause()
                self.assertFalse(sec_general.has_class("collapsed"))
                self.assertIn("▼", str(hdr_general.render()))
                self.assertIn("Collapse All", str(lbl_expand_all.render()))

                # Verify other sections also expanded
                sec_marquee = screen.query_one("#sec_marquee")
                hdr_marquee = screen.query_one("#hdr_marquee")
                self.assertFalse(sec_marquee.has_class("collapsed"))
                self.assertIn("▼", str(hdr_marquee.render()))

                # 3. Press F8 again to collapse all sections
                await pilot.press("f8")
                await pilot.pause()
                self.assertTrue(sec_general.has_class("collapsed"))
                self.assertIn("▶", str(hdr_general.render()))
                self.assertTrue(sec_marquee.has_class("collapsed"))
                self.assertIn("▶", str(hdr_marquee.render()))
                self.assertIn("Expand All", str(lbl_expand_all.render()))

                # 4. Click single section header to expand
                await pilot.click(hdr_general)
                await pilot.pause()
                self.assertFalse(sec_general.has_class("collapsed"))
                self.assertIn("▼", str(hdr_general.render()))

                # Click again to collapse
                await pilot.click(hdr_general)
                await pilot.pause()
                self.assertTrue(sec_general.has_class("collapsed"))
                self.assertIn("▶", str(hdr_general.render()))

                # 5. Keyboard interaction on focused header: Enter/Space/Left/Right
                hdr_marquee.focus()
                await pilot.press("enter")
                await pilot.pause()
                self.assertFalse(sec_marquee.has_class("collapsed"))
                self.assertIn("▼", str(hdr_marquee.render()))

                await pilot.press("space")
                await pilot.pause()
                self.assertTrue(sec_marquee.has_class("collapsed"))
                self.assertIn("▶", str(hdr_marquee.render()))

                await pilot.press("right")
                await pilot.pause()
                self.assertFalse(sec_marquee.has_class("collapsed"))

                await pilot.press("left")
                await pilot.pause()
                self.assertTrue(sec_marquee.has_class("collapsed"))

                # 6. Auto-expand on focus_inspector_target from collapsed state
                self.assertTrue(sec_general.has_class("collapsed"))
                screen.focus_inspector_target("prop_indicator")
                await pilot.pause()
                self.assertFalse(sec_general.has_class("collapsed"))
                self.assertIn("▼", str(hdr_general.render()))

        asyncio.run(_run())

    def test_generate_theme_from_image_functionality(self):
        """Verify generate_theme_from_image creates valid 256, 16, and 8 color tiers and wallpaper config."""
        import ymlcheck
        from scripts.theme_from_image import generate_theme_from_image

        twilight_img = os.path.join(bashmenu.BASHMENU_DIR, "assets", "wallpapers", "twilight.png")
        if not os.path.isfile(twilight_img):
            self.skipTest("twilight.png wallpaper not found")

        theme = generate_theme_from_image(twilight_img, theme_name="twilight_auto", mode="dark", set_wallpaper=True)
        self.assertIn(256, theme)
        self.assertIn(16, theme)
        self.assertIn(8, theme)
        self.assertIn("marquee", theme)
        self.assertIn("window", theme)
        self.assertIn("background", theme)
        self.assertEqual(theme["background"]["image"], "assets/wallpapers/twilight.png")

        # Validate with ymlcheck validators
        for depth in (256, 16, 8):
            errs = ymlcheck.validate_depth_section(str(depth), theme[depth], "twilight_auto")
            self.assertEqual(errs, [], f"Validation errors in depth {depth}: {errs}")

        # Verify background_config preservation
        custom_bg = {
            "image": "assets/wallpapers/mountain.png",
            "opacity": 0.55,
            "scaling": "stretch",
            "mode": "quarterblock",
            "clustering": 32,
            "quantization": 16,
        }
        theme_custom_bg = generate_theme_from_image(
            twilight_img,
            theme_name="twilight_custom",
            mode="dark",
            set_wallpaper=True,
            background_config=custom_bg,
        )
        self.assertEqual(theme_custom_bg["background"]["image"], "assets/wallpapers/twilight.png")
        self.assertEqual(theme_custom_bg["background"]["opacity"], 0.55)
        self.assertEqual(theme_custom_bg["background"]["scaling"], "stretch")
        self.assertEqual(theme_custom_bg["background"]["mode"], "quarterblock")
        self.assertEqual(theme_custom_bg["background"]["clustering"], 32)
        self.assertEqual(theme_custom_bg["background"]["quantization"], 16)

    def test_theme_from_image_modal_and_f9_shortcut(self):
        """Verify pressing F9 in ThemeEditScreen opens ThemeFromImageModal, generates theme, and preserves background settings."""
        twilight_img = os.path.join(bashmenu.BASHMENU_DIR, "assets", "wallpapers", "twilight.png")
        if not os.path.isfile(twilight_img):
            self.skipTest("twilight.png wallpaper not found")

        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # Configure custom background settings on screen before pressing F9
                screen.current_theme["background"] = {
                    "image": "assets/wallpapers/mountain.png",
                    "opacity": 0.45,
                    "scaling": "stretch",
                    "mode": "halfblock",
                    "clustering": 64,
                    "quantization": 8,
                }

                # Press F9 to open ThemeFromImageModal
                await pilot.press("f9")
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.ThemeFromImageModal)
                modal = app.screen

                # Set image path and theme name
                modal.query_one("#input_image_path", Input).value = twilight_img
                modal.query_one("#input_theme_name", Input).value = "twilight_gen"
                await pilot.pause()

                # Trigger generation
                await pilot.click(modal.query_one("#btn_generate"))
                await pilot.pause()

                # Success modal appears
                self.assertIsInstance(app.screen, bashmenu_ui.MessageModalScreen)
                self.assertEqual(app.screen.modal_title, "Theme Generated")
                app.screen.dismiss()
                await pilot.pause()

                # Verify ThemeEditScreen state updated and background settings preserved
                self.assertEqual(screen.theme_name, "twilight_gen")
                self.assertTrue(screen.is_dirty)
                bg_res = screen.current_theme.get("background", {})
                self.assertEqual(bg_res.get("image"), "assets/wallpapers/twilight.png")
                self.assertEqual(bg_res.get("opacity"), 0.45)
                self.assertEqual(bg_res.get("scaling"), "stretch")
                self.assertEqual(bg_res.get("mode"), "halfblock")
                self.assertEqual(bg_res.get("clustering"), 64)
                self.assertEqual(bg_res.get("quantization"), 8)

        asyncio.run(_run())

    def test_theme_rename_modal_and_inspector_input(self):
        """Verify theme renaming updates ThemeEditScreen state via inspector input and RenameThemeModal."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)
                self.assertEqual(screen.theme_name, "dracula")

                # 1. Test inline input rename in General & Identity
                inp = screen.query_one("#prop_theme_name", Input)
                inp.value = "renamed_theme_inline"
                await pilot.pause()

                self.assertEqual(screen.theme_name, "renamed_theme_inline")
                self.assertTrue(screen.is_dirty)

                # 2. Test modal rename via action_rename_theme
                screen.action_rename_theme()
                await pilot.pause()
                self.assertIsInstance(app.screen, themeedit.RenameThemeModal)
                modal = app.screen
                modal_inp = modal.query_one("#input_rename", Input)
                self.assertEqual(modal_inp.value, "renamed_theme_inline")

                modal_inp.value = "brand_new_name"
                await pilot.click(modal.query_one("#btn_confirm_rename"))
                await pilot.pause()

                # State reflected on screen
                self.assertEqual(screen.theme_name, "brand_new_name")
                self.assertEqual(screen.query_one("#prop_theme_name", Input).value, "brand_new_name")
                self.assertTrue(screen.is_dirty)

        asyncio.run(_run())

    def test_theme_deletion_in_editor(self):
        """Verify deleting a theme prompts confirmation, removes from raw_themes_data, and switches to fallback."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)

                # Add a dummy disposable theme to raw_themes_data
                screen.raw_themes_data["disposable_test_theme"] = copy.deepcopy(screen.current_theme)
                screen.theme_name = "disposable_test_theme"

                # Trigger deletion
                screen.action_delete_theme()
                await pilot.pause()

                self.assertIsInstance(app.screen, bashmenu_ui.ConfirmModalScreen)
                modal = app.screen
                self.assertEqual(modal.modal_title, "Delete Theme")

                # Mock open / write to avoid modifying local repo bashmenu.themes during unit test
                with mock.patch("builtins.open", mock.mock_open()):
                    await pilot.click(modal.query_one("#btn_yes"))
                    await pilot.pause()

                # Verify disposable theme was removed
                self.assertNotIn("disposable_test_theme", screen.raw_themes_data)
                self.assertEqual(screen.theme_name, "dracula")
                self.assertEqual(screen.query_one("#prop_theme_name", Input).value, "dracula")

        asyncio.run(_run())

    def test_theme_picker_delete_theme(self):
        """Verify ThemePickerModalScreen supports deleting a non-active theme with confirmation."""
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                picker = bashmenu_ui.ThemePickerModalScreen(current_theme="dracula")
                app.push_screen(picker)
                await pilot.pause()

                self.assertIn("delete_theme", [b.action for b in picker.BINDINGS])
                # Add dummy theme to picker
                picker.theme_keys.append("temp_to_delete")
                opt_list = picker.query_one("#options_list", OptionList)
                opt_list.add_option(Option("   Temp To Delete"))
                opt_list.highlighted = len(picker.theme_keys) - 1

                picker.action_delete_theme()
                await pilot.pause()

                self.assertIsInstance(app.screen, bashmenu_ui.ConfirmModalScreen)
                confirm_modal = app.screen

                with mock.patch("builtins.open", mock.mock_open()), \
                     mock.patch("bashmenu_ui.load_themes_file", return_value={"dracula": {}, "temp_to_delete": {}}):
                    await pilot.click(confirm_modal.query_one("#btn_yes"))
                    await pilot.pause()

                self.assertNotIn("temp_to_delete", picker.theme_keys)

        asyncio.run(_run())

    def test_generate_from_image_and_save_workflow(self):
        """Verify generating palette from image for an existing theme can be saved directly via Ctrl+S and exits cleanly."""
        async def _run():
            app = themeedit.ThemeEditApp("mountain")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)
                self.assertEqual(screen.theme_name, "mountain")
                self.assertFalse(screen.is_new)
                self.assertFalse(screen.is_dirty)

                # Simulate theme generation result for 'mountain'
                dummy_theme = copy.deepcopy(screen.current_theme)
                dummy_theme[256]["title"] = [214, -1]
                res = {"theme": dummy_theme, "name": "mountain"}

                # Trigger generation callback logic
                screen.current_theme = res["theme"]
                screen.theme_name = res["name"]
                screen.is_new = res["name"] not in screen.raw_themes_data
                screen.is_dirty = True
                screen._populate_all_inputs()
                screen._sync_preview()
                await pilot.pause()

                self.assertFalse(screen.is_new)
                self.assertTrue(screen.is_dirty)
                self.assertIn("mountain", str(screen.query_one("#header_title", Label).render()))

                # Save directly via action_save_theme (Ctrl+S)
                with mock.patch("builtins.open", mock.mock_open()):
                    screen.action_save_theme()
                    await pilot.pause()

                # Verify MessageModalScreen 'Theme Saved' appears, NOT SaveThemeModal
                self.assertIsInstance(app.screen, bashmenu_ui.MessageModalScreen)
                self.assertEqual(app.screen.modal_title, "Theme Saved")
                app.screen.dismiss()
                await pilot.pause()

                # State should now be clean (not dirty, not new)
                self.assertFalse(screen.is_dirty)
                self.assertFalse(screen.is_new)

                # Exiting should not prompt for unsaved changes
                screen.action_exit_editor()
                await pilot.pause()
                self.assertNotIsInstance(app.screen, bashmenu_ui.ConfirmModalScreen)

        asyncio.run(_run())

    def test_action_open_theme_clean_and_dirty_prompts(self):
        """Verify Ctrl+O opens theme picker, prompting to save if dirty."""
        # 1. Verify keybinding
        bindings_dict = {
            b.key: b.action for b in themeedit.ThemeEditScreen.BINDINGS
        }
        self.assertEqual(bindings_dict.get("ctrl+o"), "open_theme")

        # 2. Interactive workflow
        async def _run():
            app = themeedit.ThemeEditApp("dracula")
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause()
                screen = app.screen
                self.assertIsInstance(screen, themeedit.ThemeEditScreen)
                self.assertFalse(screen.is_dirty)

                # A. Clean state: opening another theme loads directly
                screen.action_open_theme()
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, bashmenu_ui.ThemePickerModalScreen
                )
                picker = app.screen
                picker.dismiss("monochrome")
                await pilot.pause()

                self.assertEqual(screen.theme_name, "monochrome")
                self.assertFalse(screen.is_dirty)

                # B. Dirty state: prompts with ConfirmModalScreen
                pal_256 = screen._get_pal_256()
                pal_256["title"] = [99, -1]
                self.assertTrue(screen.is_dirty)

                screen.action_open_theme()
                await pilot.pause()
                self.assertIsInstance(
                    app.screen, bashmenu_ui.ThemePickerModalScreen
                )
                picker = app.screen
                picker.dismiss("dracula")
                await pilot.pause()

                self.assertIsInstance(
                    app.screen, bashmenu_ui.ConfirmModalScreen
                )
                confirm = app.screen
                self.assertEqual(confirm.modal_title, "Unsaved Changes")

                # Selecting "No" discards changes and loads selected theme
                await pilot.click(confirm.query_one("#btn_no"))
                await pilot.pause()
                self.assertEqual(screen.theme_name, "dracula")
                self.assertFalse(screen.is_dirty)

                # C. Dirty state: selecting "Yes" saves and loads
                pal_256 = screen._get_pal_256()
                pal_256["title"] = [88, -1]
                self.assertTrue(screen.is_dirty)

                screen.action_open_theme()
                await pilot.pause()
                picker = app.screen
                picker.dismiss("monochrome")
                await pilot.pause()

                confirm = app.screen
                self.assertIsInstance(confirm, bashmenu_ui.ConfirmModalScreen)
                with mock.patch("builtins.open", mock.mock_open()):
                    await pilot.click(confirm.query_one("#btn_yes"))
                    await pilot.pause()

                # Dismiss saved message modal if present
                if isinstance(app.screen, bashmenu_ui.MessageModalScreen):
                    app.screen.dismiss()
                    await pilot.pause()

                self.assertEqual(screen.theme_name, "monochrome")
                self.assertFalse(screen.is_dirty)

                # D. Dirty state: selecting "Cancel" aborts load
                pal_256 = screen._get_pal_256()
                pal_256["title"] = [77, -1]
                self.assertTrue(screen.is_dirty)

                screen.action_open_theme()
                await pilot.pause()
                picker = app.screen
                picker.dismiss("dracula")
                await pilot.pause()

                confirm = app.screen
                self.assertIsInstance(confirm, bashmenu_ui.ConfirmModalScreen)
                await pilot.click(confirm.query_one("#btn_cancel"))
                await pilot.pause()

                # Theme must remain monochrome and still dirty
                self.assertEqual(screen.theme_name, "monochrome")
                self.assertTrue(screen.is_dirty)

        asyncio.run(_run())

    def test_themeedit_footer_shortcuts_sequential(self):
        """Verify theme editor footer presents function keys sequentially followed by non-function keys."""
        import asyncio

        app = themeedit.ThemeEditApp("dracula")

        async def _run():
            async with app.run_test(size=(120, 40)):
                screen = app.screen
                footer = screen.query_one("#footer")
                rows = list(footer.query(".footer_row"))
                self.assertEqual(len(rows), 2)

                row1_labels = [str(lbl.render()) for lbl in rows[0].query(".footer_item")]
                row2_labels = [str(lbl.render()) for lbl in rows[1].query(".footer_item")]

                # Row 1 must have F1 through F6 in sequential order
                self.assertEqual(row1_labels, [
                    "[F1] Help",
                    "[F2] Background",
                    "[F3] Pick Color",
                    "[F4] ASCII/Glyphs",
                    "[F5] Reset",
                    "[F6] Clone/Base",
                ])

                # Row 2 must have F7 through F9, followed by non-function keys
                self.assertEqual(row2_labels, [
                    "[F7] Derive 16/8",
                    "[F8] Expand All",
                    "[F9] From Image",
                    "[Ctrl+N] New",
                    "[Ctrl+O] Open",
                    "[Ctrl+S] Save",
                    "[Ctrl+A] Save As",
                    "[ESC/q] Exit",
                ])

        asyncio.run(_run())

    def test_ctrl_n_creates_new_theme(self):
        """Verify Ctrl+N shortcut triggers action_new_theme and creates untitled theme."""
        import asyncio

        app = themeedit.ThemeEditApp("dracula")

        async def _run():
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.screen
                self.assertEqual(screen.theme_name, "dracula")
                # Trigger action_new_theme via keyboard binding
                await pilot.press("ctrl+n")
                await pilot.pause()
                self.assertEqual(screen.theme_name, "untitled")
                self.assertTrue(screen.is_new)
                self.assertTrue(screen.is_dirty)
                # Name input should be blank for untitled theme
                name_inp = screen.query_one("#prop_theme_name")
                self.assertEqual(name_inp.value, "")

        asyncio.run(_run())

    def test_highlight_backspace_color_parsing_resilience(self):
        """Verify backspacing inside highlight token input does not freeze compositor or crash."""
        import asyncio

        from textual.widgets import Input

        app = themeedit.ThemeEditApp("dracula")

        async def _run():
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.screen
                highlight_inp = screen.query_one("#color_highlight", Input)
                # Simulate backspacing the closing bracket: '[255, 201]' -> '[255, 201'
                highlight_inp.value = "[255, 201"
                await pilot.pause()
                # App remains responsive and preview render does not crash
                preview = screen.query_one("#live_preview", themeedit.ThemePreviewWidget)
                rendered = preview.render()
                self.assertIsNotNone(rendered)
                self.assertTrue(len(rendered.plain) > 0)

        asyncio.run(_run())

    def test_preview_widget_renders_background_wallpaper(self):
        """Verify ThemePreviewWidget renders half-block wallpaper characters when background is set."""
        theme_def = {
            "indicator": ">",
            "divider": {"char": "─", "length": "{window_width}"},
            "window": dict(bashmenu_ui.DEFAULT_WINDOW_BORDER),
            "background": {
                "image": "assets/wallpapers/twilight.png",
                "opacity": 0.5,
                "scaling": "stretch",
                "mode": "halfblock",
            },
            256: {
                "background": 0,
                "title": [15, -1],
                "border": [15, -1],
                "text": [255, -1],
                "highlight": [16, 15],
                "selection": [15, 19],
                "shortcut_key": [53, -1],
                "divider": [15, -1],
                "plugin": [53, -1],
                "gutter": [238, -1],
                "help_text": [53, -1],
                "shadow": [236, "COLOR_BLACK"],
            },
        }
        preview = themeedit.ThemePreviewWidget(theme_def, theme_name="test_bg_theme")
        rendered = preview.render()
        has_halfblock = ("\u2580" in rendered.plain) or ("\u2584" in rendered.plain)
        self.assertTrue(has_halfblock, "Mock preview should contain composited halfblock characters")


if __name__ == "__main__":
    unittest.main()




