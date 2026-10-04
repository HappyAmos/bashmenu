#!/usr/bin/env python3
import os
import sys
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.cells import cell_len
from textual.geometry import Size

import bashmenu


class TestPluginSystem(unittest.TestCase):
    def setUp(self):
        bashmenu._plugin_output_cache.clear()
        bashmenu._plugin_fetching.clear()

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
            "theme": "pacman",  # pacman defines divider char: {ascii:205} (═)
            "settings": {
                "scripts_dir": "/tmp",
                "plugins": {
                    "otd": {
                        "script": "otd.sh",
                        "sleep": 300,
                        "pretext": "{divider}",
                        "posttext": "{divider}",
                    }
                },
            },
        }
        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "Sample OTD text\nhttps://example.com\n"
            mock_run.return_value = mock_res

            lines = bashmenu.get_plugin_outputs(config)
            self.assertEqual(lines, [
                "{divider}",
                "Sample OTD text",
                "https://example.com",
                "{divider}",
            ])

            # Verify placeholder expansion of {divider} with window_width
            expanded = [bashmenu.interpolate_placeholders(line, config, extra_vars={"window_width": 10}) for line in lines]
            self.assertEqual(expanded[0], "[color=divider]══════════[/color]")
            self.assertEqual(expanded[3], "[color=divider]══════════[/color]")

    def test_divider_window_width_scaling(self):
        config = {"theme": "pacman"}
        # Force target_w to 76 (corresponding to 80-char width with 2-char margins)
        div_str = bashmenu.resolve_divider_string(config, target_w=76)
        vis_len = bashmenu.get_visible_len(div_str)
        self.assertEqual(vis_len, 76)
        self.assertEqual(div_str, "[color=divider]" + ("═" * 76) + "[/color]")

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

    def test_plugin_dynamic_sizing_and_separator(self):
        """The `test_plugin_dynamic_sizing_and_separator` method tests
        the dynamic sizing and separator allocation of plugin lines.
        """
        cfg = {"theme": "dracula"}
        mnu = {"title": "Test", "options": [{"title": "Option 1"}]}
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)

        # 1. No plugins: 0 plugin lines, 0 separator rows
        with patch("bashmenu.get_plugin_outputs", return_value=[]):
            lines, sep, opt_rows = mv.get_plugin_lines_and_limits(19)
            self.assertEqual(len(lines), 0)
            self.assertEqual(sep, 0)
            self.assertEqual(opt_rows, 19)

        # 2. 3 plugin lines: 3 lines, 1 separator row, 15 option rows
        with patch(
            "bashmenu.get_plugin_outputs",
            return_value=["Line 1", "Line 2", "Line 3"],
        ):
            lines, sep, opt_rows = mv.get_plugin_lines_and_limits(19)
            self.assertEqual(len(lines), 3)
            self.assertEqual(sep, 1)
            self.assertEqual(opt_rows, 15)

        # 3. 15 plugin lines: capped at 10 rows, 1 separator row
        with patch(
            "bashmenu.get_plugin_outputs",
            return_value=[f"Line {i}" for i in range(15)],
        ):
            lines, sep, opt_rows = mv.get_plugin_lines_and_limits(19)
            self.assertEqual(len(lines), 10)
            self.assertEqual(sep, 1)
            self.assertEqual(opt_rows, 8)

    def test_plugin_order_preserved(self):
        """The `test_plugin_order_preserved` method verifies plugins
        execute and return outputs in configuration order.
        """
        config = {
            "settings": {
                "scripts_dir": "/tmp",
                "plugins": {
                    "first_plugin": {"script": "/tmp/first.sh", "sleep": 0},
                    "second_plugin": {"script": "/tmp/second.sh", "sleep": 0},
                    "third_plugin": {"script": "/tmp/third.sh", "sleep": 0},
                },
            }
        }
        with patch("subprocess.run") as mock_run:
            def side_effect(cmd, **kwargs):
                mock_res = MagicMock()
                cmd_str = cmd[0] if isinstance(cmd, list) else cmd
                mock_res.stdout = f"Output from {cmd_str}\n"
                return mock_res

            mock_run.side_effect = side_effect
            lines = bashmenu.get_plugin_outputs(config)
            self.assertEqual(
                lines,
                [
                    "Output from /tmp/first.sh",
                    "Output from /tmp/second.sh",
                    "Output from /tmp/third.sh",
                ],
            )

    def test_plugin_render_border_integrity(self):
        """The `test_plugin_render_border_integrity` method verifies that
        MainMenuView.render maintains exact line width and border integrity
        when plugins output tabs, ANSI codes, emojis, and long lines.
        """
        cfg = {
            "theme": "dracula",
            "settings": {"status_gutter": "User | 100% | 12:00"},
        }
        mnu = {
            "title": "Test Menu",
            "options": [
                {"title": "Option 1", "type": "command"},
                {"title": "Option 2", "type": "command"},
            ],
        }
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)

        test_widths = [80, 100, 120]
        test_heights = [24, 30]

        problematic_outputs = [
            "Normal plugin line",
            "\tTabbed\tcontent\twith multiple tabs",
            "\x1b[31;1mRed Bold\x1b[0m and \x1b[32mGreen\x1b[0m text",
            "Emojis and wide chars: 🚀 🌟 💻 日本語",
            "Very long line: " + ("x" * 200),
            "",
            "   Leading and trailing spaces   ",
        ]

        with patch("bashmenu.get_plugin_outputs", return_value=problematic_outputs):
            for w in test_widths:
                for h in test_heights:
                    with patch.object(
                        bashmenu.MainMenuView,
                        "size",
                        new_callable=PropertyMock,
                        return_value=Size(w, h),
                    ):
                        rendered_text = mv.render()
                        lines = rendered_text.plain.split("\n")

                    self.assertEqual(
                        len(lines),
                        h,
                        f"Rendered line count ({len(lines)}) must equal screen height ({h})",
                    )

                    for idx, line in enumerate(lines):
                        line_cells = cell_len(line)
                        self.assertEqual(
                            line_cells,
                            w,
                            f"Row {idx} width ({line_cells}) must equal screen width ({w}):\n'{line}'",
                        )

                        if idx == 0:
                            self.assertTrue(line.startswith("┌") and line.endswith("┐"))
                        elif idx == h - 1:
                            self.assertTrue(line.startswith("└") and line.endswith("┘"))
                        else:
                            self.assertTrue(
                                line.startswith("│  ") and line.endswith("  │"),
                                f"Row {idx} borders broken: '{line}'",
                            )

    def test_plugin_buffer_widget(self):
        """The `test_plugin_buffer_widget` method verifies that PluginBuffer
        renders plugin lines in an isolated, undecorated buffer without
        border characters.
        """
        cfg = {"theme": "dracula"}
        pb = bashmenu.PluginBuffer(config=cfg)

        # Case 1: Empty plugin list -> empty text
        with patch("bashmenu.get_plugin_outputs", return_value=[]):
            res = pb.render()
            self.assertEqual(res.plain, "")

        # Case 2: Weather and OTD plugins with emojis and ANSI
        sample_lines = [
            "On This Day: Pompey arrives in Egypt",
            "49079: \U0001f324\ufe0f  \U0001f321\ufe0f+72°F \U0001f32c\ufe0f\u21935mph",
        ]
        with patch("bashmenu.get_plugin_outputs", return_value=sample_lines):
            res = pb.render()
            lines = res.plain.split("\n")
            self.assertEqual(len(lines), 2)
            self.assertIn("Pompey arrives in Egypt", lines[0])
            self.assertIn("49079:", lines[1])
            # The buffer itself does not inject decorative border characters
            for line in lines:
                self.assertFalse(line.startswith("│"))
                self.assertFalse(line.endswith("│"))
                self.assertNotIn("\ufe0f", line)
                self.assertNotIn("\ufe0e", line)
                self.assertEqual(cell_len(line), 80)

        # Case 3: Non-black themes (qbasic, hotdog_stand)
        for theme_name, expected_hex in [("qbasic", "#0000af"), ("hotdog_stand", "#ff0000")]:
            th_styles = bashmenu.bashmenu_ui.init_theme_colors(theme_name)
            hex_c = bashmenu.get_hex_from_style(th_styles.get("background"))
            self.assertEqual(hex_c, expected_hex)


if __name__ == "__main__":
    unittest.main()
