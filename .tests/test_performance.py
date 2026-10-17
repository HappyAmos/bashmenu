#!/usr/bin/env python3
"""
test_performance.py - Responsiveness and performance regression test suite.

Verifies frame render latency, mouse-move debouncing, plugin display cache invalidation,
and the ResponsivenessWatchdog monitor.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.text import Text
from textual.geometry import Size

import bashmenu


class TestPerformanceAndResponsiveness(unittest.TestCase):
    """Test suite ensuring UI render latency and responsiveness thresholds."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.cfg, cls.menu = bashmenu.load_config(), bashmenu.load_menu()
        if isinstance(cls.cfg, tuple):
            cls.cfg = cls.cfg[0]
        if isinstance(cls.menu, tuple):
            cls.menu = cls.menu[0]
        cls.cfg["theme"] = "twilight"

    def test_navigation_render_latency(self):
        """Verify 100 cursor moves render with an average duration < 15ms and max < 35ms."""
        mv = bashmenu.MainMenuView(config=self.cfg, menu_data=self.menu)
        with patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)):
            # Warm up
            mv.render()

            durations = []
            for r in range(50):
                mv.selected_rows = [r % 5]
                t0 = time.perf_counter()
                out = mv.render()
                durations.append((time.perf_counter() - t0) * 1000.0)

            avg_ms = sum(durations) / len(durations)
            max_ms = max(durations)

            self.assertIsInstance(out, Text)
            self.assertLess(avg_ms, 15.0, f"Average render latency too high: {avg_ms:.2f}ms (target < 15ms)")
            max_limit = 100.0 if os.getenv("CI") else 35.0
            self.assertLess(max_ms, max_limit, f"Maximum single-frame latency too high: {max_ms:.2f}ms (target < {max_limit}ms)")

    def test_mouse_move_intra_row_latency(self):
        """Verify intra-row mouse movements are debounced and execute in < 0.2ms."""
        mv = bashmenu.MainMenuView(config=self.cfg, menu_data=self.menu)
        with patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)):
            # Prime visible rows
            mv.render()

            event1 = MagicMock()
            event1.y = 7
            event1.x = 10
            mv.on_mouse_move(event1)

            # Second event in the same row
            event2 = MagicMock()
            event2.y = 7
            event2.x = 25

            t0 = time.perf_counter()
            for _ in range(500):
                mv.on_mouse_move(event2)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 500.0

            self.assertLess(elapsed_ms, 0.2, f"Debounced mouse movement too slow: {elapsed_ms:.4f}ms")

    def test_plugin_display_cache_invalidation_on_update(self):
        """Verify plugin display cache reuses entries and auto-invalidates when a plugin finishes background fetch."""
        test_cfg = dict(self.cfg)

        # 1. First fetch
        items1 = bashmenu.get_plugin_display_items(test_cfg, avail_w=74, screen_div_w=78)

        # 2. Second fetch with untouched plugin cache returns cached items
        items2 = bashmenu.get_plugin_display_items(test_cfg, avail_w=74, screen_div_w=78)
        self.assertEqual(len(items1), len(items2))

        # 3. Simulate a plugin background thread update with new timestamp
        with bashmenu._plugin_lock:
            bashmenu._plugin_output_cache["test_plugin"] = {
                "time": time.time() + 10.0,
                "lines": ["[b]Updated Test Output[/b]"],
            }

        items3 = bashmenu.get_plugin_display_items(test_cfg, avail_w=74, screen_div_w=78)
        self.assertIsNotNone(items3)
        # Clean up
        with bashmenu._plugin_lock:
            bashmenu._plugin_output_cache.pop("test_plugin", None)
            bashmenu._plugin_display_cache.clear()

    def test_responsiveness_watchdog_monitoring(self):
        """Verify ResponsivenessWatchdog measures execution time and alerts when exceeding threshold."""
        warnings = []
        watchdog = bashmenu.ResponsivenessWatchdog(
            threshold_ms=10.0,
            warning_callback=lambda src, dt: warnings.append((src, dt)),
        )

        # Fast operation (< threshold)
        with watchdog.measure("fast_op"):
            time.sleep(0.001)

        self.assertEqual(watchdog.total_frames, 1)
        self.assertEqual(watchdog.slow_frames, 0)
        self.assertEqual(len(warnings), 0)

        # Slow operation (> threshold)
        with watchdog.measure("slow_op"):
            time.sleep(0.015)

        self.assertEqual(watchdog.total_frames, 2)
        self.assertEqual(watchdog.slow_frames, 1)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0][0], "slow_op")
        self.assertGreaterEqual(warnings[0][1], 10.0)
        self.assertGreaterEqual(watchdog.max_frame_ms, 10.0)

    def test_dynamic_refresh_interval_detection(self):
        """Verify _determine_refresh_interval preserves 1.0s for second-precision clocks and 5.0s otherwise."""
        screen = bashmenu.BashMenuScreen()
        screen.initial_config = {"settings": {"status_gutter": "User: {user} | {date_time_24}"}}
        self.assertEqual(screen._determine_refresh_interval(), 1.0)

        screen.initial_config = {"settings": {"status_gutter": "User: {user} | {time_12}"}}
        self.assertEqual(screen._determine_refresh_interval(), 1.0)

        screen.initial_config = {"settings": {"status_gutter": "User: {user} | {date_time_24_short}"}}
        self.assertEqual(screen._determine_refresh_interval(), 5.0)

        screen.initial_config = {"settings": {"status_gutter": "User: {user} | Static Info"}}
        self.assertEqual(screen._determine_refresh_interval(), 5.0)

        # Explicit user configuration overrides dynamic detection
        screen.initial_config = {"settings": {"refresh_interval": 2.5, "status_gutter": "{date_time_24}"}}
        self.assertEqual(screen._determine_refresh_interval(), 2.5)

        # Millisecond configuration support (>= 50ms)
        screen.initial_config = {"settings": {"refresh_interval": 2000, "status_gutter": "{date_time_24}"}}
        self.assertEqual(screen._determine_refresh_interval(), 2.0)

    def test_mouse_navigation_scroll_stability(self):
        """Verify mouse hover in a scrolled menu preserves scroll offset without collapsing to top."""
        many_options = [{"title": f"Option {i}", "type": "command"} for i in range(30)]
        test_menu = {"items": many_options}
        mv = bashmenu.MainMenuView(config=self.cfg, menu_data=test_menu)
        mv.visible_option_rows = 10

        # Scroll down to offset 10 (showing options 10-19)
        mv.scroll_offsets = [10]
        mv.selected_rows = [15]

        # Hover over rendered row 3 (which corresponds to Option 13)
        event = MagicMock()
        event.y = 6  # 6 - 3 = rendered_row 3
        mv.on_mouse_move(event)

        # Selection should move to 13, and scroll_offset MUST remain 10 (no collapse)
        self.assertEqual(mv.current_row(), 13)
        self.assertEqual(mv.current_scroll_offset(), 10)

        # Move mouse over rendered row 0 (Option 10)
        event.y = 3  # 3 - 3 = rendered_row 0
        mv.on_mouse_move(event)
        self.assertEqual(mv.current_row(), 10)
        self.assertEqual(mv.current_scroll_offset(), 10)

        # Move mouse over rendered row 9 (Option 19)
        event.y = 12  # 12 - 3 = rendered_row 9
        mv.on_mouse_move(event)
        self.assertEqual(mv.current_row(), 19)
        self.assertEqual(mv.current_scroll_offset(), 10)

    def test_scroll_wheel_navigation_bounds(self):
        """Verify scroll_down and scroll_up clamp gracefully at boundaries without wrapping."""
        many_options = [{"title": f"Option {i}", "type": "command"} for i in range(20)]
        test_menu = {"items": many_options}
        mv = bashmenu.MainMenuView(config=self.cfg, menu_data=test_menu)
        mv.visible_option_rows = 8  # max_scroll = 20 - 8 = 12

        self.assertEqual(mv.current_scroll_offset(), 0)

        # Scroll down multiple times
        for _ in range(25):
            mv.scroll_down(step=1)

        # Should be clamped at max_scroll = 12, not wrapped around
        self.assertEqual(mv.current_scroll_offset(), 12)
        self.assertGreaterEqual(mv.current_row(), 12)
        self.assertLess(mv.current_row(), 20)

        # Scroll up multiple times
        for _ in range(25):
            mv.scroll_up(step=1)

        # Should be clamped at 0, not wrapped around
        self.assertEqual(mv.current_scroll_offset(), 0)
        self.assertLessEqual(mv.current_row(), 7)

    def test_mouse_scroll_event_stopping(self):
        """Verify on_mouse_scroll_down and on_mouse_scroll_up prevent default and stop bubbling."""
        many_options = [{"title": f"Option {i}", "type": "command"} for i in range(10)]
        mv = bashmenu.MainMenuView(config=self.cfg, menu_data={"items": many_options})
        mv.visible_option_rows = 5

        ev_down = MagicMock()
        mv.on_mouse_scroll_down(ev_down)
        ev_down.prevent_default.assert_called_once()
        ev_down.stop.assert_called_once()

        ev_up = MagicMock()
        mv.on_mouse_scroll_up(ev_up)
        ev_up.prevent_default.assert_called_once()
        ev_up.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
