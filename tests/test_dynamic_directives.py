import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock curses before importing anything that might use it
sys.modules["curses"] = MagicMock()

import bashmenu

class TestDynamicDirectives(unittest.TestCase):
    def setUp(self):
        self.stdscr = MagicMock()
        self.config = {
            "theme": "dracula",
            "settings": {
                "templates_dir": "templates",
                "scripts_dir": "scripts"
            }
        }
        self.theme = {"text": 0, "border": 0}

    @patch("bashmenu.show_input_box")
    def test_resolve_param_directive(self, mock_input):
        # Setup mock to return a value
        mock_input.return_value = "my_value"
        
        selected_item = {
            "title": "Test Title",
            "prompt": "Test Prompt:",
            "masked": False
        }
        action_str = "some_command {param}"
        
        result = bashmenu.resolve_dynamic_directives(
            self.stdscr, action_str, selected_item, self.config, self.theme
        )
        
        self.assertEqual(result, "some_command my_value")
        mock_input.assert_called_once_with(
            self.stdscr, "Test Title", "Test Prompt:", "", self.theme, False
        )

    @patch("bashmenu.show_input_box")
    def test_resolve_param_directive_cancelled(self, mock_input):
        # Setup mock to return None (user pressed ESC)
        mock_input.return_value = None
        
        selected_item = {}
        action_str = "some_command {param}"
        
        result = bashmenu.resolve_dynamic_directives(
            self.stdscr, action_str, selected_item, self.config, self.theme
        )
        
        self.assertIsNone(result)

    @patch("bashmenu.show_file_picker")
    def test_resolve_file_picker_directive(self, mock_picker):
        mock_picker.return_value = "/path/to/file.txt"
        
        selected_item = {
            "title": "My File Picker",
            "start_dir": "~/projects"
        }
        action_str = "process_file {file_picker}"
        
        result = bashmenu.resolve_dynamic_directives(
            self.stdscr, action_str, selected_item, self.config, self.theme
        )
        
        self.assertEqual(result, "process_file /path/to/file.txt")
        # Ensure it was called with the interpolated path
        mock_picker.assert_called_once()
        args, kwargs = mock_picker.call_args
        self.assertEqual(kwargs.get("mode"), "file")

    @patch("bashmenu.show_file_picker")
    def test_resolve_dir_picker_directive(self, mock_picker):
        mock_picker.return_value = "/path/to/dir"
        
        selected_item = {
            "title": "My Dir Picker",
            "start_dir": "/tmp"
        }
        action_str = "process_dir {dir_picker}"
        
        result = bashmenu.resolve_dynamic_directives(
            self.stdscr, action_str, selected_item, self.config, self.theme
        )
        
        self.assertEqual(result, "process_dir /path/to/dir")
        mock_picker.assert_called_once()
        args, kwargs = mock_picker.call_args
        self.assertEqual(kwargs.get("mode"), "dir")

    @patch("bashmenu.resolve_dynamic_directives")
    @patch("bashmenu.run_action_in_window")
    def test_process_item_action_with_param(self, mock_run, mock_resolve):
        mock_resolve.return_value = "echo hello_world"
        
        selected_item = {
            "type": "command",
            "action": "echo {param}",
            "label": "Echo Command"
        }
        
        menu_stack = []
        selected_rows = []
        
        bashmenu.process_item_action(
            selected_item, self.stdscr, self.config, self.theme, menu_stack, selected_rows
        )
        
        mock_resolve.assert_called_once()
        mock_run.assert_called_once_with(
            self.stdscr, "echo hello_world", "Echo Command", self.theme, stream=False
        )

    @patch("bashmenu.resolve_dynamic_directives")
    @patch("bashmenu.run_action_in_window")
    def test_process_item_action_cancelled(self, mock_run, mock_resolve):
        # Resolve returns None (user cancelled)
        mock_resolve.return_value = None
        
        selected_item = {
            "type": "command",
            "action": "echo {param}",
            "label": "Echo Command"
        }
        
        menu_stack = []
        selected_rows = []
        
        res = bashmenu.process_item_action(
            selected_item, self.stdscr, self.config, self.theme, menu_stack, selected_rows
        )
        
        self.assertEqual(res, (None, self.theme, self.config))
        mock_run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
