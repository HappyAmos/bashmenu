#!/usr/bin/env python3
"""
test_inactivity.py - Test suite for BashMenu inactivity timeout and screensaver.

Tests inactivity timeout configuration parsing, schema validation, Textual event
interception, timer resets, alternate buffer execution, and screensaver lifecycle.
"""

import asyncio
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bashmenu
import ymlcheck


class TestInactivityTimeout(unittest.TestCase):
    """The `TestInactivityTimeout` class tests the inactivity timer subsystem."""

    def test_inactivity_config_parsing(self):
        """The `test_inactivity_config_parsing` method tests parsing of
        `settings.inactivity_timeout` with valid, invalid, and missing values.
        """
        app = bashmenu.BashMenuApp()

        # 1. Valid milliseconds and command
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 15000,
                    "command": "cmatrix -b",
                }
            }
        }
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 15.0)
        self.assertEqual(cmd, "cmatrix -b")

        # 2. Placeholders inside command are interpolated
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 30000,
                    "command": "{bashmenu_dir}/screensaver.sh",
                }
            }
        }
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 30.0)
        self.assertNotIn("{bashmenu_dir}", cmd)
        self.assertTrue(cmd.endswith("/screensaver.sh"))

        # 3. Missing inactivity_timeout block
        app.config = {"settings": {}}
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        # 4. Zero or negative milliseconds
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 0,
                    "command": "cmatrix",
                }
            }
        }
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        app.config["settings"]["inactivity_timeout"]["milliseconds"] = -5000
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        # 5. Non-numeric milliseconds
        app.config["settings"]["inactivity_timeout"]["milliseconds"] = "not-a-number"
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        # 6. Empty or blank command
        app.config["settings"]["inactivity_timeout"]["milliseconds"] = 5000
        app.config["settings"]["inactivity_timeout"]["command"] = "   "
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        # 7. Unconfigured command (omitted from settings by default)
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 300000,
                }
            }
        }
        sec, cmd = app.get_inactivity_config()
        self.assertEqual(sec, 0.0)
        self.assertEqual(cmd, "")

        # 8. setup_inactivity_timer does nothing when command is unconfigured
        app.setup_inactivity_timer()
        self.assertIsNone(app._inactivity_timer)

    def test_ymlcheck_inactivity_validation(self):
        """The `test_ymlcheck_inactivity_validation` method verifies that
        `ymlcheck.py` schema validation accepts valid configurations and
        reports descriptive errors for invalid inactivity nodes.
        """
        # Valid config
        valid_cfg = {
            "version": "0.0.1",
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 300000,
                    "command": "cmatrix",
                }
            },
        }
        with patch("ymlcheck.load_yaml_raw", return_value=(valid_cfg, None)):
            self.assertTrue(ymlcheck.validate_config_file("dummy.yml"))

        # Valid config without command argument (default)
        valid_cfg_no_cmd = {
            "version": "0.0.1",
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 300000,
                }
            },
        }
        with patch("ymlcheck.load_yaml_raw", return_value=(valid_cfg_no_cmd, None)):
            self.assertTrue(ymlcheck.validate_config_file("dummy.yml"))

        # Invalid: inactivity_timeout is not a dict
        invalid_cfg1 = {
            "settings": {
                "inactivity_timeout": "invalid_string",
            }
        }
        with patch("ymlcheck.load_yaml_raw", return_value=(invalid_cfg1, None)):
            self.assertFalse(ymlcheck.validate_config_file("dummy.yml"))

        # Invalid: milliseconds is not a number
        invalid_cfg2 = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": "five_minutes",
                    "command": "cmatrix",
                }
            }
        }
        with patch("ymlcheck.load_yaml_raw", return_value=(invalid_cfg2, None)):
            self.assertFalse(ymlcheck.validate_config_file("dummy.yml"))

        # Invalid: command is not a string
        invalid_cfg3 = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 10000,
                    "command": 12345,
                }
            }
        }
        with patch("ymlcheck.load_yaml_raw", return_value=(invalid_cfg3, None)):
            self.assertFalse(ymlcheck.validate_config_file("dummy.yml"))

    def test_timer_reset_and_arming(self):
        """The `test_timer_reset_and_arming` method verifies that active timers
        are reset upon receiving input events and stopped when reconfigured.
        """
        app = bashmenu.BashMenuApp()
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 60000,
                    "command": "cmatrix",
                }
            }
        }

        # Mock timer
        mock_timer = MagicMock()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_timer._task = mock_task

        app._inactivity_timer = mock_timer
        app.reset_inactivity_timer()
        mock_timer.reset.assert_called_once()

        # If screensaver is currently active, reset is ignored
        mock_timer.reset.reset_mock()
        app._is_screensaver_active = True
        app.reset_inactivity_timer()
        mock_timer.reset.assert_not_called()
        app._is_screensaver_active = False

        # If timer task is done (expired), reset_inactivity_timer re-arms it
        mock_task.done.return_value = True
        with patch.object(app, "set_timer", return_value=MagicMock()) as mock_set:
            app.reset_inactivity_timer()
            mock_set.assert_called_once_with(
                60.0,
                app._trigger_inactivity_timeout,
                name="inactivity_timeout",
            )

    def test_trigger_inactivity_timeout_execution_and_buffer_isolation(self):
        """The `test_trigger_inactivity_timeout_execution_and_buffer_isolation`
        method verifies alternate buffer escape codes and command execution.
        """
        app = bashmenu.BashMenuApp()
        app.config = {
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 10000,
                    "command": "cmatrix -b",
                }
            }
        }

        # Test execution with can_suspend = True
        mock_driver = MagicMock()
        mock_driver.can_suspend = True
        app._driver = mock_driver

        captured_stdout = io.StringIO()
        with (
            patch("sys.stdout", captured_stdout),
            patch("subprocess.run") as mock_subproc,
            patch.object(app, "suspend", MagicMock()),
            patch.object(app, "setup_inactivity_timer") as mock_rearm,
        ):
            app._trigger_inactivity_timeout()

            # Verify subprocess call
            mock_subproc.assert_called_once_with(
                "cmatrix -b",
                shell=True,
                executable=bashmenu.BASH_BIN,
                check=False,
            )

            # Verify alternate screen buffer sequences written to stdout
            out_str = captured_stdout.getvalue()
            self.assertIn("\x1b[?1049h\x1b[H\x1b[2J", out_str)
            self.assertIn("\x1b[?1049l", out_str)

            # Verify timer was re-armed
            mock_rearm.assert_called_once()
            self.assertFalse(app._is_screensaver_active)

    def test_pilot_inactivity_timeout_flow(self):
        """The `test_pilot_inactivity_timeout_flow` method verifies the async
        Textual pilot lifecycle, timer triggering, and reset upon key events.
        """
        test_cfg = {
            "version": "0.0.1",
            "theme": "matrix",
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 400,  # 0.4s
                    "command": "cmatrix",
                }
            },
        }

        async def run_pilot_check():
            app = bashmenu.BashMenuApp(config=test_cfg)
            with (
                patch("subprocess.run") as mock_subproc,
                patch.object(app, "_trigger_inactivity_timeout", wraps=app._trigger_inactivity_timeout) as mock_trigger,
            ):
                async with app.run_test(size=(80, 24)) as pilot:
                    # Timer should be set
                    self.assertIsNotNone(app._inactivity_timer)

                    # 1. Reset on key event before timeout
                    await asyncio.sleep(0.2)
                    await pilot.press("down")
                    self.assertEqual(mock_trigger.call_count, 0)

                    # 2. Wait 0.2s: should not fire yet because countdown reset to 0.4s
                    await asyncio.sleep(0.2)
                    self.assertEqual(mock_trigger.call_count, 0)

                    # 3. Allow timeout to expire
                    for _ in range(8):
                        if mock_trigger.call_count >= 1:
                            break
                        await asyncio.sleep(0.1)
                    self.assertGreaterEqual(mock_trigger.call_count, 1)
                    mock_subproc.assert_called()

        asyncio.run(run_pilot_check())

    def test_pilot_inactivity_reset_on_mouse_event(self):
        """The `test_pilot_inactivity_reset_on_mouse_event` method verifies that
        mouse events intercept and reset the inactivity countdown.
        """
        test_cfg = {
            "version": "0.0.1",
            "theme": "matrix",
            "settings": {
                "inactivity_timeout": {
                    "milliseconds": 500,
                    "command": "cmatrix",
                }
            },
        }

        async def run_mouse_check():
            app = bashmenu.BashMenuApp(config=test_cfg)
            with (
                patch("subprocess.run"),
                patch.object(app, "reset_inactivity_timer", wraps=app.reset_inactivity_timer) as mock_reset,
            ):
                async with app.run_test(size=(80, 24)) as pilot:
                    # Simulate mouse move / hover
                    await pilot.hover(offset=(10, 5))
                    self.assertGreater(mock_reset.call_count, 0)

        asyncio.run(run_mouse_check())

    def test_refresh_environment_rearms_inactivity_timer(self):
        """The `test_refresh_environment_rearms_inactivity_timer` method verifies
        that refreshing the environment (F5) re-arms the inactivity timer.
        """
        screen = bashmenu.BashMenuScreen()
        mock_app = MagicMock()
        screen._app = mock_app

        mock_mv = MagicMock()
        mock_pb = MagicMock()

        with (
            patch.object(bashmenu.BashMenuScreen, "menu_view", mock_mv),
            patch.object(bashmenu.BashMenuScreen, "plugin_buffer", mock_pb),
            patch("bashmenu.load_config", return_value=({"settings": {}}, "")),
            patch("bashmenu.load_menu", return_value=({"items": []}, "")),
            patch("bashmenu.get_plugin_outputs"),
        ):
            screen.refresh_environment()
            mock_app.setup_inactivity_timer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
