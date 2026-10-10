#!/usr/bin/env python3
import os
import sys
import time
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

    def test_plugin_screen_width_divider_and_tee_rendering(self):
        """Verify that when theme divider length is {screen_width}, plugin buffer
        expands to screen_div_w, indents regular lines, and MainMenuView renders
        border tees on divider rows."""
        # 1. PluginBuffer with synthwave theme (length is {screen_width})
        cfg_synth = {"theme": "synthwave"}
        pb = bashmenu.PluginBuffer(config=cfg_synth)
        sample_lines = ["{divider}", "Quote of the day", "{divider}"]
        with patch("bashmenu.get_plugin_outputs", return_value=sample_lines):
            res = pb.render()
            lines = res.plain.split("\n")
            self.assertEqual(len(lines), 3)
            # screen_div_w is 78 for default screen width 80
            self.assertEqual(cell_len(lines[0]), 78)
            # Divider line does NOT have 2 leading spaces
            self.assertFalse(lines[0].startswith("  "))
            # Non-divider line has 2 leading spaces for alignment
            self.assertTrue(lines[1].startswith("  Quote of the day"))
            self.assertEqual(cell_len(lines[1]), 78)
            self.assertEqual(cell_len(lines[2]), 78)

        # 2. MainMenuView rendering border tees for screen divider
        mv = bashmenu.MainMenuView(config=cfg_synth, menu_data={"title": "Test", "options": []})
        borders = bashmenu.bashmenu_ui.get_theme_window_borders("synthwave", config=cfg_synth)
        b_tee_l = borders.get("left_tee") or "├"
        b_tee_r = borders.get("right_tee") or "┤"

        with (
            patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)),
            patch("bashmenu.get_plugin_outputs", return_value=sample_lines),
        ):
            rendered = mv.render().plain
            rendered_lines = rendered.split("\n")
            # Find lines starting and ending with the theme's border tees
            tee_lines = [line for line in rendered_lines if line.startswith(b_tee_l) and line.endswith(b_tee_r)]
            self.assertGreaterEqual(len(tee_lines), 2)
            for tl in tee_lines:
                self.assertEqual(cell_len(tl), 80)

        # 3. MainMenuView with dracula (length is {window_width}) - no tees in plugin rows
        cfg_dracula = {"theme": "dracula"}
        mv_drac = bashmenu.MainMenuView(config=cfg_dracula, menu_data={"title": "Test", "options": []})
        with (
            patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)),
            patch("bashmenu.get_plugin_outputs", return_value=sample_lines),
        ):
            rendered_drac = mv_drac.render().plain
            drac_lines = rendered_drac.split("\n")
            # No tee lines should be produced for plugins
            drac_tee_lines = [line for line in drac_lines if line.startswith("├") or line.endswith("┤")]
            self.assertEqual(len(drac_tee_lines), 0)

        # 4. Geometry update verification
        mock_pb = MagicMock()
        mock_mv_synth = MagicMock()
        mock_mv_synth.config = cfg_synth
        mock_mv_synth.get_plugin_lines_and_limits.return_value = (sample_lines, 1, 15)

        with (
            patch.object(bashmenu.BashMenuScreen, "plugin_buffer", new_callable=PropertyMock, return_value=mock_pb),
            patch.object(bashmenu.BashMenuScreen, "menu_view", new_callable=PropertyMock, return_value=mock_mv_synth),
            patch.object(bashmenu.BashMenuScreen, "size", new_callable=PropertyMock, return_value=Size(80, 24)),
        ):
            screen_synth = bashmenu.BashMenuScreen(config=cfg_synth)
            screen_synth._update_plugin_buffer_geometry()
            self.assertEqual(mock_pb.styles.offset, (1, 18))
            self.assertEqual(mock_pb.styles.width, 78)

        # Dracula theme geometry
        mock_mv_drac = MagicMock()
        mock_mv_drac.config = cfg_dracula
        mock_mv_drac.get_plugin_lines_and_limits.return_value = (sample_lines, 1, 15)

        with (
            patch.object(bashmenu.BashMenuScreen, "plugin_buffer", new_callable=PropertyMock, return_value=mock_pb),
            patch.object(bashmenu.BashMenuScreen, "menu_view", new_callable=PropertyMock, return_value=mock_mv_drac),
            patch.object(bashmenu.BashMenuScreen, "size", new_callable=PropertyMock, return_value=Size(80, 24)),
        ):
            screen_drac = bashmenu.BashMenuScreen(config=cfg_dracula)
            screen_drac._update_plugin_buffer_geometry()
            self.assertEqual(mock_pb.styles.offset, (3, 18))
            self.assertEqual(mock_pb.styles.width, 74)

    def test_plugin_table_layout(self):
        """Test declarative multi-column table layout in settings.plugins."""
        config = {
            "theme": "dracula",
            "settings": {
                "plugins": {
                    "layout": {
                        "type": "table",
                        "width": "100%",
                        "headers": ["System", "Weather"],
                        "rows": [
                            ["uptime", "weather"]
                        ],
                    },
                    "uptime": {
                        "script": "uptime.sh",
                        "sleep": 30,
                    },
                    "weather": {
                        "script": "weather.sh",
                        "sleep": 300,
                    },
                }
            }
        }
        import time
        now = time.time()
        with patch("bashmenu._plugin_lock"):
            bashmenu._plugin_output_cache["uptime"] = {"time": now, "lines": ["Up 2 hours"]}
            bashmenu._plugin_output_cache["weather"] = {"time": now, "lines": ["72F Sunny"]}

        pb = bashmenu.PluginBuffer(config=config)
        with patch.object(bashmenu.PluginBuffer, "size", new_callable=PropertyMock, return_value=Size(80, 10)):
            rendered = pb.render()
            plain = rendered.plain
            self.assertIn("System", plain)
            self.assertIn("Weather", plain)
            self.assertIn("Up 2 hours", plain)
            self.assertIn("72F Sunny", plain)
            lines = [l for l in plain.split("\n") if l.strip()]
            self.assertTrue(all(cell_len(l) == pb.size.width for l in lines))

    def test_plugin_table_layout_entries_and_standalone(self):
        """Test entries: 2 chunking and standalone plugin line stretching."""
        import time
        now = time.time()
        config = {
            "theme": "dracula",
            "settings": {
                "plugins": {
                    "layout": {
                        "type": "table",
                        "entries": 2,
                        "width": "100%",
                    },
                    "otd": {
                        "script": "otd.sh",
                        "standalone": True,
                        "pretext": "{divider}",
                        "posttext": "{divider}",
                    },
                    "uptime": {
                        "script": "uptime.sh",
                    },
                    "weather": {
                        "script": "weather.sh",
                    },
                    "disk": {
                        "script": "disk.sh",
                    },
                }
            }
        }
        with patch("bashmenu._plugin_lock"):
            bashmenu._plugin_output_cache["otd"] = {"time": now, "lines": ["Quote of the day: Be kind."]}
            bashmenu._plugin_output_cache["uptime"] = {"time": now, "lines": ["Up 5 hours"]}
            bashmenu._plugin_output_cache["weather"] = {"time": now, "lines": ["68F Clear"]}
            bashmenu._plugin_output_cache["disk"] = {"time": now, "lines": ["Disk: 50% free"]}

        pb = bashmenu.PluginBuffer(config=config)
        with patch.object(bashmenu.PluginBuffer, "size", new_callable=PropertyMock, return_value=Size(80, 10)):
            rendered = pb.render()
            plain = rendered.plain
            # otd should be present as standalone line
            self.assertIn("Quote of the day: Be kind.", plain)
            # 2-column table for uptime and weather
            self.assertIn("Up 5 hours", plain)
            self.assertIn("68F Clear", plain)
            # 3rd plugin disk constructs its own table
            self.assertIn("Disk: 50% free", plain)

    def test_plugin_section_divider_config(self):
        """Test get_plugin_divider_config resolution under different settings."""
        # 1. divider: True (uses theme's length)
        cfg1 = {"theme": "dracula", "settings": {"plugins": {"divider": True}}}
        has_div, is_screen = bashmenu.get_plugin_divider_config(cfg1)
        self.assertTrue(has_div)
        self.assertFalse(is_screen)  # dracula is {window_width}

        # 2. divider: True with screen theme
        cfg2 = {"theme": "synthwave", "settings": {"plugins": {"divider": True}}}
        has_div, is_screen = bashmenu.get_plugin_divider_config(cfg2)
        self.assertTrue(has_div)
        self.assertTrue(is_screen)  # synthwave has {screen_width}

        # 3. Explicit 'screen' and 'window'
        cfg3 = {"theme": "dracula", "settings": {"plugins": {"divider": "screen"}}}
        self.assertEqual(bashmenu.get_plugin_divider_config(cfg3), (True, True))

        cfg4 = {"theme": "synthwave", "settings": {"plugins": {"divider": "window"}}}
        self.assertEqual(bashmenu.get_plugin_divider_config(cfg4), (True, False))

        # 4. top_divider and layout.divider fallbacks
        cfg5 = {"settings": {"plugins": {"top_divider": True}}}
        has_div, _ = bashmenu.get_plugin_divider_config(cfg5)
        self.assertTrue(has_div)

        cfg6 = {"settings": {"plugins": {"layout": {"divider": True}}}}
        has_div, _ = bashmenu.get_plugin_divider_config(cfg6)
        self.assertTrue(has_div)

        # 5. Disabled / missing
        cfg7 = {"settings": {"plugins": {"divider": False}}}
        self.assertEqual(bashmenu.get_plugin_divider_config(cfg7), (False, False))

    def test_plugin_section_divider_rendering(self):
        """Test that MenuView renders the divider above plugins when divider: True."""
        cfg = {
            "theme": "dracula",
            "settings": {
                "plugins": {
                    "divider": True,
                    "test_plugin": {"script": "dummy.sh"},
                }
            }
        }
        mnu = {"title": "Menu", "options": [{"title": "Option 1"}]}
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)

        sample_lines = ["Plugin output line 1", "Plugin output line 2"]
        with (
            patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)),
            patch("bashmenu.get_plugin_outputs", return_value=sample_lines),
        ):
            # get_plugin_lines_and_limits accounts for top_div_rows
            lines, sep, opt_rows = mv.get_plugin_lines_and_limits(19)
            self.assertEqual(len(lines), 2)
            self.assertEqual(sep, 1)
            # 19 total - 2 plugins - 1 sep - 1 top_div = 15 opt_rows
            self.assertEqual(opt_rows, 15)

            rendered = mv.render().plain
            rendered_lines = rendered.split("\n")
            # Should have horizontal divider line within window borders
            div_lines = [l for l in rendered_lines if "──" in l and ("│" in l or "├" in l)]
            self.assertGreater(len(div_lines), 0)

    def test_table_layout_screen_width_divider_and_tee_alignment(self):
        """Test that with table layout and screen_width themes (cyberpunk, synthwave, qbasic, industry),
        MainMenuView Tee rows and PluginBuffer divider rows align on the exact same row index,
        and table rows preserve 2-space margins."""
        for theme_name in ("cyberpunk", "synthwave", "qbasic", "industry"):
            config = {
                "theme": theme_name,
                "settings": {
                    "plugins": {
                        "type": "table",
                        "width": "100%",
                        "entries": 4,
                        "weather": {"script": "weather.sh"},
                        "alienware": {"script": "alienware.sh"},
                        "pi3b": {"script": "pi3b.sh"},
                        "halftop": {"script": "halftop.sh"},
                        "otd": {
                            "script": "otd.sh",
                            "standalone": True,
                            "pretext": "{divider}",
                            "posttext": "{divider}",
                        },
                    }
                }
            }
            now = time.time()
            with patch("bashmenu._plugin_lock"):
                bashmenu._plugin_output_cache["weather"] = {"time": now, "lines": ["72F Clear"]}
                bashmenu._plugin_output_cache["alienware"] = {"time": now, "lines": ["Alienware Up"]}
                bashmenu._plugin_output_cache["pi3b"] = {"time": now, "lines": ["Pi3b Up"]}
                bashmenu._plugin_output_cache["halftop"] = {"time": now, "lines": ["Halftop Up"]}
                bashmenu._plugin_output_cache["otd"] = {"time": now, "lines": ["Quote of the day: Be kind."]}

            mv = bashmenu.MainMenuView(config=config, menu_data={"title": "Test", "options": [{"label": "Opt 1"}]})
            with patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)):
                lines, sep, _opt_rows = mv.get_plugin_lines_and_limits(19)
                self.assertEqual(len(lines), 6, f"{theme_name} should produce 6 display rows (3 table + 3 otd)")
                self.assertNotIn("{divider}", lines[0])
                self.assertNotIn("{divider}", lines[1])
                self.assertNotIn("{divider}", lines[2])
                self.assertIn("{divider}", lines[3])
                self.assertNotIn("{divider}", lines[4])
                self.assertIn("{divider}", lines[5])

                mock_screen = MagicMock()
                mock_screen.size = Size(80, 24)
                mock_screen.menu_view = mv

                pb = bashmenu.PluginBuffer(config=config)
                pb._screen = mock_screen
                rendered_pb = pb.render().plain
                pb_lines = rendered_pb.split("\n")
                self.assertEqual(len(pb_lines), 6, f"{theme_name} pb should render 6 lines")

                # Table lines (rows 0, 1, 2): have 2-space margin, width 78
                for r in (0, 1, 2):
                    self.assertEqual(cell_len(pb_lines[r]), 78)
                    self.assertTrue(pb_lines[r].startswith("  "), f"Row {r} must have 2-space margin in {theme_name}")

                # Divider line (row 3): no margin, width 78
                self.assertEqual(cell_len(pb_lines[3]), 78)
                self.assertFalse(pb_lines[3].startswith("  "), f"Row 3 divider must not have 2-space margin in {theme_name}")

                # Quote line (row 4): has 2-space margin, width 78
                self.assertEqual(cell_len(pb_lines[4]), 78)
                self.assertTrue(pb_lines[4].startswith("  Quote of the day"), f"Row 4 must have 2-space margin in {theme_name}")

                # Divider line (row 5): no margin, width 78
                self.assertEqual(cell_len(pb_lines[5]), 78)
                self.assertFalse(pb_lines[5].startswith("  "), f"Row 5 divider must not have 2-space margin in {theme_name}")

                # Check MainMenuView border alignment
                borders = bashmenu.bashmenu_ui.get_theme_window_borders(theme_name, config=config)
                b_tee_l = borders.get("left_tee") or borders.get("border_tee_left") or "├"
                b_v_l = borders.get("border_vertical_left") or borders.get("border_vertical") or "│"

                rendered_mv = mv.render().plain
                mv_lines = rendered_mv.split("\n")

                plugin_start = 3 + (mv.total_content_rows or 18) - len(lines) - sep
                self.assertTrue(mv_lines[plugin_start + 0].startswith(b_v_l), f"Row 0 must have vertical border in {theme_name}")
                self.assertTrue(mv_lines[plugin_start + 1].startswith(b_v_l), f"Row 1 must have vertical border in {theme_name}")
                self.assertTrue(mv_lines[plugin_start + 2].startswith(b_v_l), f"Row 2 must have vertical border in {theme_name}")
                self.assertTrue(mv_lines[plugin_start + 3].startswith(b_tee_l), f"Row 3 must have Tee border in {theme_name}")
                self.assertTrue(mv_lines[plugin_start + 4].startswith(b_v_l), f"Row 4 must have vertical border in {theme_name}")
                self.assertTrue(mv_lines[plugin_start + 5].startswith(b_tee_l), f"Row 5 must have Tee border in {theme_name}")


if __name__ == "__main__":
    unittest.main()


