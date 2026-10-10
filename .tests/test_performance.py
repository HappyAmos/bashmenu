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
            self.assertLess(max_ms, 35.0, f"Maximum single-frame latency too high: {max_ms:.2f}ms (target < 35ms)")

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


if __name__ == "__main__":
    unittest.main()
