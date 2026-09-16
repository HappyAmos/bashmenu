#!/usr/bin/env python3
"""
test_ansi.py - Unit tests for ANSI escape code parsing and color rendering in bashmenu.py
"""

import unittest
import sys
import os

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bashmenu


class TestAnsiParsing(unittest.TestCase):
    """
    Test suite for ANSI escape sequence parsing, sanitization, and curses
    color attribute resolution within the bashmenu engine.
    """
    def test_parse_ansi_line_empty(self):
        """Test parsing an empty string."""
        segments = bashmenu.parse_ansi_line("", 0)
        self.assertEqual(segments, [])

    def test_parse_ansi_line_plain_text(self):
        """Test parsing plain text with no escape sequences."""
        segments = bashmenu.parse_ansi_line("Hello World", 42)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "Hello World")
        self.assertEqual(segments[0][1], 42)

    def test_parse_ansi_line_simple_color(self):
        """Test parsing a string with standard standard ANSI color sequences (e.g. Red, Green)."""
        # Red text
        segments = bashmenu.parse_ansi_line("\x1b[31mRedText", 0)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "RedText")
        # In uninitialized curses test environment, attributes resolve to 0
        attr = segments[0][1]
        self.assertEqual(attr, 0)

    def test_parse_ansi_line_multiple_segments(self):
        """Test parsing multiple consecutive styled text segments."""
        line = "\x1b[1;31mBoldRed\x1b[0;32mGreen\x1b[4;34mUnderlineBlue"
        segments = bashmenu.parse_ansi_line(line, 0)
        self.assertEqual(len(segments), 3)
        
        self.assertEqual(segments[0][0], "BoldRed")
        self.assertEqual(segments[1][0], "Green")
        self.assertEqual(segments[2][0], "UnderlineBlue")

    def test_parse_character_set_sequences(self):
        """Test that character set selection sequences like \x1b(B and other non-SGR escape sequences are discarded."""
        line = "\x1b[31mRedText\x1b(B\x1b[0mNormalText"
        segments = bashmenu.parse_ansi_line(line, 42)
        # Should parse into 'RedText' (styled) and 'NormalText' (reset style). The \x1b(B should be fully ignored.
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][0], "RedText")
        self.assertEqual(segments[1][0], "NormalText")

    def test_process_line_to_segments(self):
        """Test expanding tabs, parsing ANSI codes and sanitizing non-printable characters."""
        # \x00 is non-printable and should be filtered, \t should be expanded to 4 spaces, colors preserved
        # 'Hell' is 4 chars, so tab starting at col 4 expands to col 8 (exactly 4 spaces)
        line = "\x1b[35mHell\t\x00World"
        segments = bashmenu.process_line_to_segments(line, 0)
        self.assertEqual(len(segments), 1)
        # Check that tab expanded to 4 spaces and \x00 was removed
        self.assertEqual(segments[0][0], "Hell    World")

    def test_process_line_to_segments_fallback(self):
        """Test that empty or fully-sanitized strings return at least an empty segment with default style."""
        line = "\x1b[35m\x00"
        segments = bashmenu.process_line_to_segments(line, 999)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0][0], "")
        self.assertEqual(segments[0][1], 999)

    def test_interpolate_placeholders_ascii(self):
        """Test that {ascii:168} and similar resolve correctly to CP437 equivalents (e.g. ¿)."""
        text = "Hello {ascii:168} World"
        resolved = bashmenu.interpolate_placeholders(text, {})
        self.assertEqual(resolved, "Hello ¿ World")

    def test_interpolate_placeholders_window_dims(self):
        """Test that {window_width} and {window_height} resolve to valid integer strings representing window dimensions."""
        text = "Dims: {window_width}x{window_height}"
        resolved = bashmenu.interpolate_placeholders(text, {})
        self.assertTrue(resolved.startswith("Dims: "))
        self.assertNotIn("{window_width}", resolved)
        self.assertNotIn("{window_height}", resolved)

    def test_interpolate_placeholders_new_directives(self):
        """Test that all newly added custom status gutter placeholders resolve properly."""
        placeholders = [
            "{host}",
            "{user-mode}",
            "{version}",
            "{date_time_12}",
            "{date_time_24}",
            "{date}",
            "{time_12}",
            "{time_24}",
            "{battery}",
            "{utc_seconds}",
        ]
        for p in placeholders:
            resolved = bashmenu.interpolate_placeholders(p, {})
            self.assertNotEqual(resolved, p)
            self.assertNotEqual(resolved, "")
            # Ensure basic type expectations or formats
            if p == "{utc_seconds}":
                self.assertTrue(resolved.isdigit())
            elif p == "{date}":
                self.assertRegex(resolved, r"^\d{4}-\d{2}-\d{2}$")

    def test_get_battery_info_caching(self):
        """Test that get_battery_info properly caches results and avoids multiple slower lookups."""
        import time
        # Force a fresh fetch by clearing the cache time
        bashmenu._last_battery_time = 0.0
        first_call = bashmenu.get_battery_info()
        
        # Modify the cached value to verify cache-hits return the modified value within the 5s window
        bashmenu._cached_battery = "42%"
        second_call = bashmenu.get_battery_info()
        self.assertEqual(second_call, "42%")

        # Force fresh fetch again
        bashmenu._last_battery_time = 0.0
        third_call = bashmenu.get_battery_info()
        self.assertEqual(third_call, first_call)


if __name__ == "__main__":
    unittest.main()
