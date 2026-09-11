import unittest
from unittest.mock import MagicMock, patch
import os
import subprocess
import sys
import curses

# Ensure SCRIPT_DIR is in sys.path so we can import bashmenu and menuedit
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import bashmenu
import menuedit

class TestConfigPicker(unittest.TestCase):
    def test_default_config_keys(self):
        """Verify templates and scripts are defined in DEFAULT_CONFIG."""
        self.assertIn("templates", bashmenu.DEFAULT_CONFIG)
        self.assertIn("scripts", bashmenu.DEFAULT_CONFIG)
        self.assertEqual(bashmenu.DEFAULT_CONFIG["templates"], "templates")
        self.assertEqual(bashmenu.DEFAULT_CONFIG["scripts"], "scripts")

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_script_action_pick_default(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify scripts picker defaults to subdirectory scripts path when config is missing/relative."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [10]  # Choose [PICK]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        menuedit.select_script_action(stdscr, "script.sh", None, theme)
        
        expected_dir = os.path.abspath(os.path.join(menuedit.SCRIPT_DIR, "scripts"))
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Script File", start_dir=expected_dir, mode="file", default_val="script.sh", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_script_action_pick_custom_abs(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify scripts picker resolves absolute directory path specified in config."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        config = {"scripts": "/absolute/path/to/my_scripts"}
        menuedit.select_script_action(stdscr, "script.sh", config, theme)
        
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Script File", start_dir="/absolute/path/to/my_scripts", mode="file", default_val="script.sh", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_script_action_pick_custom_rel(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify scripts picker resolves relative directory path specified in config relative to SCRIPT_DIR."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        config = {"scripts": "custom_scripts_dir"}
        menuedit.select_script_action(stdscr, "script.sh", config, theme)
        
        expected_dir = os.path.abspath(os.path.join(menuedit.SCRIPT_DIR, "custom_scripts_dir"))
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Script File", start_dir=expected_dir, mode="file", default_val="script.sh", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_editor_target_pick_inject_block_default(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify templates picker defaults to subdirectory templates path when config is missing/relative."""
        mock_win = MagicMock()
        # Navigate down 4 times to target [PICK], then press Enter
        mock_win.getch.side_effect = [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, 10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        menuedit.select_editor_target(stdscr, "templates/block.tmpl", "inject_block", "template", None, theme)
        
        expected_dir = os.path.abspath(os.path.join(menuedit.SCRIPT_DIR, "templates"))
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Target File", start_dir=expected_dir, mode="file", default_val="templates/block.tmpl", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_editor_target_pick_inject_block_custom_abs(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify templates picker resolves absolute directory path specified in config."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, 10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        config = {"templates": "/absolute/path/to/my_templates"}
        menuedit.select_editor_target(stdscr, "templates/block.tmpl", "inject_block", "template", config, theme)
        
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Target File", start_dir="/absolute/path/to/my_templates", mode="file", default_val="templates/block.tmpl", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_editor_target_pick_inject_block_custom_rel(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify templates picker resolves relative directory path specified in config relative to SCRIPT_DIR."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, 10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        config = {"templates": "custom_templates_dir"}
        menuedit.select_editor_target(stdscr, "templates/block.tmpl", "inject_block", "template", config, theme)
        
        expected_dir = os.path.abspath(os.path.join(menuedit.SCRIPT_DIR, "custom_templates_dir"))
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Target File", start_dir=expected_dir, mode="file", default_val="templates/block.tmpl", theme=theme
        )

    @patch("curses.newwin")
    @patch("bashmenu.show_file_picker")
    @patch("bashmenu.draw_shadow")
    def test_select_editor_target_pick_editor_type(self, mock_draw_shadow, mock_show_file_picker, mock_newwin):
        """Verify templates/scripts default configuration does not apply to non-inject_block types (like editor)."""
        mock_win = MagicMock()
        mock_win.getch.side_effect = [curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN, 10]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        menuedit.select_editor_target(stdscr, "file.txt", "editor", "action", None, theme)
        
        mock_show_file_picker.assert_called_once_with(
            stdscr, "Select Target File", start_dir="~", mode="file", default_val="file.txt", theme=theme
        )

    def test_wrap_detail_lines_short(self):
        """Verify that short lines are not wrapped."""
        details = ["Label : Short text", "Type  : script"]
        wrapped = menuedit.wrap_detail_lines(details, prop_w=30)
        self.assertEqual(wrapped, details)

    def test_wrap_detail_lines_no_colon(self):
        """Verify that long lines without colons are wrapped correctly."""
        details = ["This is a very long line without any colons but it still needs to be wrapped properly"]
        wrapped = menuedit.wrap_detail_lines(details, prop_w=20)
        # Verify all lines are within prop_w (20)
        for line in wrapped:
            self.assertTrue(len(line) <= 20)
        self.assertTrue(len(wrapped) > 1)

    def test_wrap_detail_lines_with_colon_indent(self):
        """Verify that long lines with colons wrap and indent the value part."""
        details = ["action    : /home/andrew/scripts/get_api_key.sh --key-name my_super_secret_api_key"]
        # Prefix length is 12 ("action    : ")
        wrapped = menuedit.wrap_detail_lines(details, prop_w=40)
        
        self.assertTrue(len(wrapped) > 1)
        # First line should start with the prefix
        self.assertTrue(wrapped[0].startswith("action    : "))
        # Subsequent lines should start with 12 spaces of indentation
        for line in wrapped[1:]:
            self.assertTrue(line.startswith(" " * 12))
            self.assertTrue(len(line) <= 40)

    def test_wrap_detail_lines_very_narrow_fallback(self):
        """Verify fallback when available width is too small."""
        details = ["action    : some_extremely_long_value"]
        # If prop_w is 13, prefix length is 12, so avail_w = 1.
        # This is < 10, so it should fallback to wrapping the whole line without prefix/indent.
        wrapped = menuedit.wrap_detail_lines(details, prop_w=13)
        for line in wrapped:
            self.assertTrue(len(line) <= 13)

    @patch("shutil.which")
    def test_get_clipboard_tool(self, mock_which):
        """Verify get_clipboard_tool prioritizes xclip over xsel."""
        # Case 1: both exist
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ["xclip", "xsel"] else None
        self.assertEqual(menuedit.get_clipboard_tool(), "xclip")
        
        # Case 2: only xsel exists
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd == "xsel" else None
        self.assertEqual(menuedit.get_clipboard_tool(), "xsel")
        
        # Case 3: neither exists
        mock_which.side_effect = lambda cmd: None
        self.assertIsNone(menuedit.get_clipboard_tool())

    @patch("subprocess.run")
    def test_copy_to_clipboard_xclip(self, mock_run):
        """Verify copy_to_clipboard runs correct xclip commands."""
        with patch("menuedit.CLIPBOARD_TOOL", "xclip"):
            res = menuedit.copy_to_clipboard("test_value")
            self.assertTrue(res)
            mock_run.assert_called_once_with(
                ["xclip", "-selection", "clipboard"],
                input="test_value",
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    @patch("subprocess.run")
    def test_copy_to_clipboard_xsel(self, mock_run):
        """Verify copy_to_clipboard runs correct xsel commands."""
        with patch("menuedit.CLIPBOARD_TOOL", "xsel"):
            res = menuedit.copy_to_clipboard("test_value")
            self.assertTrue(res)
            mock_run.assert_called_once_with(
                ["xsel", "--clipboard", "--input"],
                input="test_value",
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    @patch("curses.newwin")
    @patch("menuedit.copy_to_clipboard")
    @patch("bashmenu.draw_shadow")
    def test_edit_item_properties_yank(self, mock_draw_shadow, mock_copy, mock_newwin):
        """Verify pressing Y on a valid field copies to clipboard and triggers feedback."""
        mock_win = MagicMock()
        # Press 'y' to copy, then press ESC (27) to close
        mock_win.getch.side_effect = [ord('y'), 27]
        mock_win.getmaxyx.return_value = (10, 80)
        mock_newwin.return_value = mock_win
        
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        
        item_dict = {
            "label": "Test Item",
            "type": "command",
            "action": "echo hello"
        }
        config = {}
        theme = {"text": 0, "border": 0, "title": 0, "footer": 0, "highlight": 0}
        
        mock_copy.return_value = True
        
        with patch("menuedit.CLIPBOARD_TOOL", "xclip"):
            menuedit.edit_item_properties(stdscr, item_dict, config, theme)
            
            # The first selected field is "label", so it should copy "Test Item"
            mock_copy.assert_called_once_with("Test Item")

if __name__ == "__main__":
    unittest.main()
