import unittest
import os
import sys

# Ensure SCRIPT_DIR is in sys.path so we can import bashmenu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import bashmenu

class TestInterpolatePlaceholders(unittest.TestCase):
    def setUp(self):
        self.config = {
            "theme": "dracula",
            "settings": {
                "custom_value": "hello_world"
            }
        }

    def test_lowercase_placeholders(self):
        # Test default lowercase built-ins
        text = "Hello {user}, home is {home}, script is in {bashmenu_dir}"
        result = bashmenu.interpolate_placeholders(text, self.config)
        self.assertNotIn("{user}", result)
        self.assertNotIn("{home}", result)
        self.assertNotIn("{bashmenu_dir}", result)
        self.assertIn(bashmenu.USERNAME, result)
        self.assertIn(bashmenu.USER_HOME, result)
        self.assertIn(bashmenu.BASHMENU_DIR, result)

    def test_uppercase_placeholders(self):
        # Test uppercase variations
        text = "Hello {USER}, home is {HOME}, script is in {BASHMENU_DIR}"
        result = bashmenu.interpolate_placeholders(text, self.config)
        self.assertNotIn("{USER}", result)
        self.assertNotIn("{HOME}", result)
        self.assertNotIn("{BASHMENU_DIR}", result)
        self.assertIn(bashmenu.USERNAME, result)
        self.assertIn(bashmenu.USER_HOME, result)
        self.assertIn(bashmenu.BASHMENU_DIR, result)

    def test_mixedcase_placeholders(self):
        # Test mixedcase variations
        text = "Hello {UsEr}, home is {HoMe}, script is in {BaShMeNu_DiR}"
        result = bashmenu.interpolate_placeholders(text, self.config)
        self.assertNotIn("{UsEr}", result)
        self.assertNotIn("{HoMe}", result)
        self.assertNotIn("{BaShMeNu_DiR}", result)
        self.assertIn(bashmenu.USERNAME, result)
        self.assertIn(bashmenu.USER_HOME, result)
        self.assertIn(bashmenu.BASHMENU_DIR, result)

    def test_config_value_with_dynamic_variables(self):
        # Test that dynamic variables within config settings expand whether upper or lower case
        cfg = {
            "settings": {
                "upper_path": "{BASHMENU_DIR}/templates",
                "lower_path": "{bashmenu_dir}/scripts",
            }
        }
        res_upper = bashmenu.interpolate_placeholders("{settings.upper_path}", cfg)
        res_lower = bashmenu.interpolate_placeholders("{settings.lower_path}", cfg)
        self.assertEqual(res_upper, f"{bashmenu.BASHMENU_DIR}/templates")
        self.assertEqual(res_lower, f"{bashmenu.BASHMENU_DIR}/scripts")

    def test_dot_notation_case_sensitivity(self):
        # Dot-notation keys from config should remain case-sensitive as they reference dict keys
        text = "Value: {settings.custom_value}"
        result = bashmenu.interpolate_placeholders(text, self.config)
        self.assertEqual(result, "Value: hello_world")

        text_wrong = "Value: {settings.CUSTOM_VALUE}"
        result_wrong = bashmenu.interpolate_placeholders(text_wrong, self.config)
        self.assertEqual(result_wrong, "Value: {settings.CUSTOM_VALUE}")

    def test_nerd_font_placeholders(self):
        # Nerd Font parsing check with use_nerd_fonts False
        config_no_nf = {"settings": {"use_nerd_fonts": False}}
        text = "{nf:fallback_char:A} Help"
        result = bashmenu.interpolate_placeholders(text, config_no_nf)
        self.assertEqual(result, "fallback_char Help")

        # Nerd Font parsing check with use_nerd_fonts True
        config_nf = {"settings": {"use_nerd_fonts": True}}
        text = "{nf:fallback_char:A} Help"
        result = bashmenu.interpolate_placeholders(text, config_nf)
        self.assertEqual(result, "A Help")

    def test_raw_theme_indicators(self):
        # Verify raw theme indicators of form nf:FALLBACK:GLYPH
        config_no_nf = {"settings": {"use_nerd_fonts": False}}
        config_nf = {"settings": {"use_nerd_fonts": True}}
        
        indicator_text = "nf:>:\uf0a4"
        self.assertEqual(bashmenu.interpolate_placeholders(indicator_text, config_no_nf), ">")
        self.assertEqual(bashmenu.interpolate_placeholders(indicator_text, config_nf), "\uf0a4")

        # Test with hex codes starting with #
        indicator_hex = "nf:>:#f0a4"
        self.assertEqual(bashmenu.interpolate_placeholders(indicator_hex, config_no_nf), ">")
        self.assertEqual(bashmenu.interpolate_placeholders(indicator_hex, config_nf), "\uf0a4")

    def test_hex_glyph_resolution(self):
        # Verify bracketed hex glyph resolution
        config_no_nf = {"settings": {"use_nerd_fonts": False}}
        config_nf = {"settings": {"use_nerd_fonts": True}}

        text = "{nf:>:#f07c0}"
        self.assertEqual(bashmenu.interpolate_placeholders(text, config_no_nf), ">")
        self.assertEqual(bashmenu.interpolate_placeholders(text, config_nf), chr(0xf07c0))

    def test_extracted_menu_icons(self):
        # Verify that all extracted icons in bashmenu.mnu are parsed correctly
        config_nf_false = {"settings": {"use_nerd_fonts": False}}
        config_nf_true = {"settings": {"use_nerd_fonts": True}}

        # Test application icon
        icon_raw = "{nf::\U0001F3AE}"
        self.assertEqual(bashmenu.interpolate_placeholders(icon_raw, config_nf_false), "")
        self.assertEqual(bashmenu.interpolate_placeholders(icon_raw, config_nf_true), "\U0001F3AE")

        # Test exit icon
        icon_raw_exit = "{nf::\U0001F6AA}"
        self.assertEqual(bashmenu.interpolate_placeholders(icon_raw_exit, config_nf_false), "")
        self.assertEqual(bashmenu.interpolate_placeholders(icon_raw_exit, config_nf_true), "\U0001F6AA")

    def test_display_width_resolution(self):
        # Verify get_display_width calculations for ASCII, standard emojis, and emojis with variation selectors
        self.assertEqual(bashmenu.get_display_width(""), 0)
        self.assertEqual(bashmenu.get_display_width("abc"), 3)
        self.assertEqual(bashmenu.get_display_width("🎮"), 2)
        # Emojis with variation selector-16 \uFE0F
        self.assertEqual(bashmenu.get_display_width("\u2699\uFE0F"), 2)
        self.assertEqual(bashmenu.get_display_width("\u2139\uFE0F"), 2)


if __name__ == "__main__":
    unittest.main()
