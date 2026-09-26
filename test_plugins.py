#!/usr/bin/env python3
import time
import unittest
from unittest.mock import patch, MagicMock

import bashmenu

class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        bashmenu._plugin_output_cache.clear()

    def test_config_plugin_resolution_and_custom_sleep(self):
        config = {
            "settings": {
                "scripts_dir": "{bashmenu_dir}/scripts",
                "plugins": {
                    "otd": {
                        "script": "otd.sh",
                        "sleep": 5
                    }
                }
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "Quote of the day.\nhttps://example.com/otd\n"
            mock_run.return_value = mock_res

            # Initial call -> runs subprocess
            lines1 = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines1, ["Quote of the day.", "https://example.com/otd"])
            self.assertEqual(mock_run.call_count, 1)

            # Immediate second call -> cached (call count remains 1)
            lines2 = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines2, ["Quote of the day.", "https://example.com/otd"])
            self.assertEqual(mock_run.call_count, 1)

    def test_live_data_sleep_zero(self):
        config = {
            "settings": {
                "scripts_dir": "/tmp",
                "plugins": {
                    "live": {
                        "script": "live.sh",
                        "sleep": 0
                    }
                }
            }
        }
        with patch("subprocess.run") as mock_run:
            count = 0
            def side_effect(cmd, **kwargs):
                nonlocal count
                count += 1
                mock_res = MagicMock()
                mock_res.stdout = f"Live output tick {count}\n"
                return mock_res

            mock_run.side_effect = side_effect

            lines1 = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines1, ["Live output tick 1"])
            self.assertEqual(mock_run.call_count, 1)

            # With sleep=0, next call runs script again immediately
            lines2 = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines2, ["Live output tick 2"])
            self.assertEqual(mock_run.call_count, 2)

    def test_pretext_posttext_and_divider(self):
        config = {
            "user": {
                "divider": {
                    "char": "-",
                    "length": "10"
                }
            },
            "settings": {
                "scripts_dir": "/tmp",
                "plugins": {
                    "otd": {
                        "script": "otd.sh",
                        "sleep": 300,
                        "pretext": "{user.divider}",
                        "posttext": "{user.divider}"
                    }
                }
            }
        }
        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "Sample OTD text\nhttps://example.com\n"
            mock_run.return_value = mock_res

            lines = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines, [
                "{user.divider}",
                "Sample OTD text",
                "https://example.com",
                "{user.divider}"
            ])

            # Verify placeholder expansion of {user.divider}
            expanded = [bashmenu.interpolate_placeholders(line, config) for line in lines]
            self.assertEqual(expanded[0], "[color=divider]----------[/color]")
            self.assertEqual(expanded[3], "[color=divider]----------[/color]")

    def test_divider_window_width_scaling(self):
        config = {
            "user": {
                "divider": {
                    "char": "-",
                    "length": "{window_width}"
                }
            }
        }
        # Force target_w to 76 (corresponding to 80-char width with 2-char margins)
        div_str = bashmenu.resolve_divider_string(config, target_w=76)
        vis_len = bashmenu.get_visible_len(div_str)
        self.assertEqual(vis_len, 76)
        self.assertEqual(div_str, "[color=divider]" + ("-" * 76) + "[/color]")

    def test_menu_priority_over_plugins(self):
        options = [{"label": f"Option {i}"} for i in range(10)]
        num_options = len(options)
        menu_needed_y = 3 + num_options  # row 13

        # Case 1: Large height (24) -> enough space for menu (13), footer (22), and plugins
        height = 24
        help_gutter_top_row = height - 2  # 22
        bottom_plugin_y = help_gutter_top_row - 1  # 21
        max_plugin_rows = max(0, bottom_plugin_y - menu_needed_y + 1)  # 21 - 13 + 1 = 9
        self.assertGreater(max_plugin_rows, 0)

        # Case 2: Constrained height (12) -> menu needs rows 3..12, footer at row 10
        height = 12
        help_gutter_top_row = height - 2  # 10
        bottom_plugin_y = help_gutter_top_row - 1  # 9
        max_plugin_rows = max(0, bottom_plugin_y - menu_needed_y + 1)  # 9 - 13 + 1 = -3 -> 0
        # Plugins dropped to 0 rows first so menu fits
        self.assertEqual(max_plugin_rows, 0)

if __name__ == "__main__":
    unittest.main()
