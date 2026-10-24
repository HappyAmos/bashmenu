"""Unit tests for Radio menu item type and dynamic placeholder refresh."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from textual.app import App

import bashmenu
import bashmenu_ui
import menuedit
import ymlcheck


class TestRadioModalScreen(unittest.IsolatedAsyncioTestCase):
    """Test the RadioModalScreen widget and interactions."""

    async def test_radio_modal_preselects_current_value(self):
        """Verify RadioModalScreen pre-selects the radio button matching current_value."""
        results = []

        class TestApp(App):
            def on_mount(self):
                screen = bashmenu_ui.RadioModalScreen(
                    "Test Radio",
                    "Select an option:",
                    choices=[("opt_a", "Option A"), ("opt_b", "Option B"), ("opt_c", "Option C")],
                    current_value="opt_b",
                )
                self.push_screen(screen, lambda res: results.append(res))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Press enter directly without changing selection; should submit pre-selected 'opt_b'
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(results, ["opt_b"])

    async def test_radio_modal_number_shortcut_and_submit(self):
        """Verify number shortcuts switch selection and enter submits."""
        results = []

        class TestApp(App):
            def on_mount(self):
                screen = bashmenu_ui.RadioModalScreen(
                    "Test Radio",
                    "Select an option:",
                    choices=[("opt_a", "Option A"), ("opt_b", "Option B"), ("opt_c", "Option C")],
                    current_value="opt_a",
                )
                self.push_screen(screen, lambda res: results.append(res))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Switch to option 3 using key '3'
            await pilot.press("3")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(results, ["opt_c"])

    async def test_radio_modal_cancel_returns_none(self):
        """Verify pressing escape dismisses the modal with None."""
        results = []

        class TestApp(App):
            def on_mount(self):
                screen = bashmenu_ui.RadioModalScreen(
                    "Test Radio",
                    "Select an option:",
                    choices=[("opt_a", "Option A"), ("opt_b", "Option B")],
                )
                self.push_screen(screen, lambda res: results.append(res))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(results, [None])


class TestMenuPlaceholdersRefresh(unittest.TestCase):
    """Test dynamic placeholder invalidation and refresh on MainMenuView."""

    def test_refresh_menu_placeholders_updates_canvas(self):
        """Verify that modifying a config setting updates placeholder-bearing options in canvas."""
        config = {
            "theme": "dracula",
            "settings": {
                "test_key": "initial_value",
                "use_nerd_fonts": True,
            },
        }
        menu_data = {
            "title": "Main Menu [{settings.test_key}]",
            "items": [
                {
                    "title": "Item [{settings.test_key}]",
                    "type": "radio",
                    "key": "settings.test_key",
                    "options": [
                        {"label": "Val 1", "value": "val1"},
                        {"label": "Val 2", "value": "val2"},
                    ],
                },
                {
                    "title": "Static Item",
                    "type": "command",
                    "command": "echo static",
                },
            ],
        }

        menu_view = bashmenu.MainMenuView(config=config, menu_data=menu_data)
        menu_view._size = MagicMock(width=80, height=24)

        # Pre-render to build canvas
        menu_view._render_menu_buffer(assemble=True)
        canvas = menu_view._canvas
        self.assertIsNotNone(canvas)

        # Check initial unselected raw line contains initial_value
        initial_raw = canvas._raw_option_lines.get((0, False))
        self.assertIsNotNone(initial_raw)
        self.assertIn("initial_value", initial_raw.plain)

        # Mutate config value
        config["settings"]["test_key"] = "updated_value"
        menu_view.config = config

        # Refresh placeholders
        menu_view.refresh_menu_placeholders()

        # Check updated unselected raw line contains updated_value
        updated_raw = canvas._raw_option_lines.get((0, False))
        self.assertIsNotNone(updated_raw)
        self.assertIn("updated_value", updated_raw.plain)
        self.assertNotIn("initial_value", updated_raw.plain)

        # Verify header title line 0 also updated
        static_top = canvas._static_lines.get(0)
        self.assertIsNotNone(static_top)
        self.assertIn("updated_value", static_top.plain)


class TestMenuEditRadioIntegration(unittest.TestCase):
    """Test Visual Menu Editor integration for radio type."""

    def test_radio_badge_and_type_detection(self):
        """Verify radio type badge and item type detection."""
        self.assertEqual(menuedit.TYPE_BADGES.get("radio"), "[RAD]")
        type_keys = [k for k, _ in menuedit.ITEM_TYPES]
        self.assertIn("radio", type_keys)

        modal = menuedit.ItemEditModal(
            {"title": "Pager Editor", "type": "radio", "key": "settings.pager_editor", "options": []}
        )
        self.assertEqual(modal._detect_item_type(modal.item), "radio")
        self.assertIn("Configuration Key", modal.get_action_label_text())

    def test_radio_options_parsing_in_save(self):
        """Verify ItemEditModal parses Label = Value lines into options list."""
        item = {
            "title": "Pager Editor [{settings.pager_editor}]",
            "type": "radio",
            "key": "settings.pager_editor",
            "options": [
                {"label": "Default ($EDITOR)", "value": "default"},
                {"label": "Built-in (BashEdit)", "value": "builtin"},
            ],
        }
        modal = menuedit.ItemEditModal(item)

        class MockApp(App):
            def on_mount(self):
                self.push_screen(modal)

        app = MockApp()

        async def _test():
            async with app.run_test() as pilot:
                await pilot.pause()
                text_area = modal.query_one("#inp_radio_options", bashmenu_ui.TextArea)
                self.assertIn("Default ($EDITOR) = default", text_area.text)
                self.assertIn("Built-in (BashEdit) = builtin", text_area.text)

                # Edit text area content
                text_area.text = "Nano = nano\nVim = vim\nCustom Option"
                modal.perform_save()
                await pilot.pause()

                saved = modal.item
                self.assertEqual(saved["type"], "radio")
                self.assertEqual(
                    saved["options"],
                    [
                        {"label": "Nano", "value": "nano"},
                        {"label": "Vim", "value": "vim"},
                        {"label": "Custom Option", "value": "Custom Option"},
                    ],
                )

        import asyncio
        asyncio.run(_test())


class TestYmlCheckRadioValidation(unittest.TestCase):
    """Test ymlcheck.py schema rules for radio items and elimination of choice."""

    def test_choice_is_invalid(self):
        """Verify choice is rejected by ymlcheck as unknown type."""
        self.assertNotIn("choice", ymlcheck.VALID_OPTION_TYPES)
        self.assertNotIn("config_choice", ymlcheck.VALID_OPTION_TYPES)

    def test_radio_is_valid_type(self):
        """Verify radio is in VALID_OPTION_TYPES and validates options."""
        self.assertIn("radio", ymlcheck.VALID_OPTION_TYPES)
        errors = []
        ymlcheck._validate_menu_items(
            [{"Pager Editor": {"type": "radio", "key": "settings.pager_editor", "options": [{"value": "a", "label": "A"}]}}],
            "items",
            errors,
        )
        self.assertEqual(errors, [])

    def test_radio_missing_options_or_key_reports_error(self):
        """Verify radio requires key and non-empty options."""
        errors_no_key = []
        ymlcheck._validate_menu_items(
            [{"Pager Editor": {"type": "radio", "options": ["a", "b"]}}],
            "items",
            errors_no_key,
        )
        self.assertTrue(any("requires a 'key' property" in e for e in errors_no_key))

        errors_no_opts = []
        ymlcheck._validate_menu_items(
            [{"Pager Editor": {"type": "radio", "key": "settings.test", "options": []}}],
            "items",
            errors_no_opts,
        )
        self.assertTrue(any("requires a non-empty 'options' list" in e for e in errors_no_opts))


if __name__ == "__main__":
    unittest.main()
