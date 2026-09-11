import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
from pathlib import Path
import sys

# Ensure SCRIPT_DIR is in sys.path so we can import bashmenu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import bashmenu

class TestInjectBlock(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for targets and templates
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)
        
        # Setup config dict for interpolation
        self.config = {
            "theme": "dracula",
            "settings": {
                "custom_value": "hello_world"
            }
        }
        
        # Mock stdscr
        self.stdscr = MagicMock()
        self.theme = {"text": 0, "border": 0, "title": 0, "footer": 0}
        self.menu_stack = []
        self.selected_rows = []

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("bashmenu.show_popup_message")
    def test_missing_paths(self, mock_popup):
        item = {
            "label": "Test Dynamic Block",
            "type": "inject_block"
            # target and template are missing
        }
        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, self.menu_stack, self.selected_rows
        )
        mock_popup.assert_called_once()
        self.assertIn("must be specified", mock_popup.call_args[0][2])

    @patch("bashmenu.show_popup_message")
    def test_missing_template(self, mock_popup):
        target_file = self.test_dir_path / "target.txt"
        item = {
            "label": "Test Dynamic Block",
            "type": "inject_block",
            "target": str(target_file),
            "template": str(self.test_dir_path / "nonexistent.tmpl"),
            "block_id": "test_block"
        }
        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, self.menu_stack, self.selected_rows
        )
        mock_popup.assert_called_once()
        self.assertIn("Template file not found", mock_popup.call_args[0][2])

    @patch("bashmenu.show_confirm_box", return_value="yes")
    @patch("bashmenu.show_popup_message")
    def test_install_new_block(self, mock_popup, mock_confirm):
        target_file = self.test_dir_path / "target.txt"
        template_file = self.test_dir_path / "test.tmpl"
        
        # Create template with interpolation
        template_file.write_text("This is my value: {settings.custom_value}")
        
        item = {
            "label": "Test Dynamic Block",
            "type": "inject_block",
            "target": str(target_file),
            "template": str(template_file),
            "block_id": "test_block"
        }
        
        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, self.menu_stack, self.selected_rows
        )
        
        # Check target content
        self.assertTrue(target_file.exists())
        content = target_file.read_text()
        self.assertIn("# CODEBLOCK:test_block:START", content)
        self.assertIn("This is my value: hello_world", content)
        self.assertIn("# CODEBLOCK:test_block:END", content)
        
        # Verify success message popup
        mock_popup.assert_called_once()
        self.assertIn("successfully installed/updated", mock_popup.call_args[0][2])

    @patch("bashmenu.show_confirm_box")
    @patch("bashmenu.show_popup_message")
    def test_update_existing_block(self, mock_popup, mock_confirm):
        target_file = self.test_dir_path / "target.txt"
        template_file = self.test_dir_path / "test.tmpl"
        
        # Pre-install old block
        target_file.write_text("header\n# CODEBLOCK:test_block:START\nold content\n# CODEBLOCK:test_block:END\nfooter")
        
        # New template
        template_file.write_text("new content")
        
        item = {
            "label": "Test Dynamic Block",
            "type": "inject_block",
            "target": str(target_file),
            "template": str(template_file),
            "block_id": "test_block"
        }
        
        # Mock confirm box to say "yes" (reinstall)
        mock_confirm.return_value = "yes"
        
        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, self.menu_stack, self.selected_rows
        )
        
        content = target_file.read_text()
        self.assertIn("header", content)
        self.assertIn("footer", content)
        self.assertIn("# CODEBLOCK:test_block:START", content)
        self.assertIn("new content", content)
        self.assertIn("# CODEBLOCK:test_block:END", content)
        self.assertNotIn("old content", content)

    @patch("bashmenu.show_confirm_box")
    @patch("bashmenu.show_popup_message")
    def test_uninstall_existing_block(self, mock_popup, mock_confirm):
        target_file = self.test_dir_path / "target.txt"
        template_file = self.test_dir_path / "test.tmpl"
        
        # Pre-install block
        target_file.write_text("header\n# CODEBLOCK:test_block:START\nsome content\n# CODEBLOCK:test_block:END\nfooter")
        
        template_file.write_text("some content")
        
        item = {
            "label": "Test Dynamic Block",
            "type": "inject_block",
            "target": str(target_file),
            "template": str(template_file),
            "block_id": "test_block"
        }
        
        # Mock confirm box to say "no" (uninstall)
        mock_confirm.return_value = "no"
        
        bashmenu.process_item_action(
            item, self.stdscr, self.config, self.theme, self.menu_stack, self.selected_rows
        )
        
        content = target_file.read_text()
        self.assertIn("header", content)
        self.assertIn("footer", content)
        self.assertNotIn("# CODEBLOCK:test_block:START", content)
        self.assertNotIn("some content", content)
        self.assertNotIn("# CODEBLOCK:test_block:END", content)

if __name__ == "__main__":
    unittest.main()
