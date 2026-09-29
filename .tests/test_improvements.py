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


if __name__ == "__main__":
    unittest.main()
