import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure SCRIPT_DIR is in sys.path so we can import bashmenu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import bashmenu

class TestToggleDialog(unittest.TestCase):
    def setUp(self):
        self.config = {
            "settings": {
                "toggle_target": False
            }
        }
        self.theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        self.stdscr = MagicMock()
        self.stdscr.getmaxyx.return_value = (24, 80)

    @patch("bashmenu.show_toggle_box")
    @patch("bashmenu.save_config")
    def test_toggle_action_true(self, mock_save, mock_toggle_box):
        # Mock show_toggle_box to return 'true'
        mock_toggle_box.return_value = "true"

        item = {
            "label": "Toggle Feature",
            "type": "toggle",
            "key": "settings.toggle_target",
            "title": "Enable Feature",
            "message": "Do you want to enable the feature?"
        }

        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, [], []
        )

        # Check config updated and saved
        self.assertTrue(self.config["settings"]["toggle_target"])
        mock_save.assert_called_once_with(self.config)

    @patch("bashmenu.show_toggle_box")
    @patch("bashmenu.save_config")
    def test_toggle_action_false(self, mock_save, mock_toggle_box):
        # Mock show_toggle_box to return 'false'
        mock_toggle_box.return_value = "false"
        self.config["settings"]["toggle_target"] = True

        item = {
            "label": "Toggle Feature",
            "type": "toggle",
            "key": "settings.toggle_target",
            "title": "Enable Feature",
            "message": "Do you want to enable the feature?"
        }

        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, [], []
        )

        # Check config updated to False
        self.assertFalse(self.config["settings"]["toggle_target"])
        mock_save.assert_called_once_with(self.config)

    @patch("bashmenu.show_toggle_box")
    @patch("bashmenu.save_config")
    def test_toggle_action_cancel(self, mock_save, mock_toggle_box):
        # Mock show_toggle_box to return None (Cancel)
        mock_toggle_box.return_value = None
        self.config["settings"]["toggle_target"] = True

        item = {
            "label": "Toggle Feature",
            "type": "toggle",
            "key": "settings.toggle_target",
            "title": "Enable Feature",
            "message": "Do you want to enable the feature?"
        }

        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, [], []
        )

        # Value should be unchanged and save not called
        self.assertTrue(self.config["settings"]["toggle_target"])
        mock_save.assert_not_called()

    @patch("bashmenu.run_action_in_window")
    def test_script_external_true(self, mock_run_win):
        # When external is True (or omitted), it should run using subprocess
        item = {
            "label": "Run Command",
            "type": "script",
            "action": "test_script.sh",
            "external": True
        }

        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, [], []
        )

        # Check run_action_in_window was called
        mock_run_win.assert_called_once()

    @patch("importlib.import_module")
    def test_script_external_false(self, mock_import_module):
        # When external is False, it should attempt to import dynamically
        mock_module = MagicMock()
        mock_import_module.return_value = mock_module

        item = {
            "label": "Run Plugin",
            "type": "script",
            "action": "mock_plugin.py",
            "external": False
        }

        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, [], []
        )

        # Check dynamic import attempted
        mock_import_module.assert_called_with("mock_plugin")
        mock_module.main.assert_called_once_with(self.stdscr)


if __name__ == "__main__":
    unittest.main()
