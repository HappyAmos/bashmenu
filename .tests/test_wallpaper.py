#!/usr/bin/env python3
"""
test_wallpaper.py - Test suite for BashMenu half-block background wallpaper compositing.

Verifies WallpaperCompositor downsampling, caching, tint blending, composite_menu_text
rendering, MainMenuView integration, twilight theme schema validation, and error resilience.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import PropertyMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.style import Style
from rich.text import Text
from textual.geometry import Region, Size

import bashmenu
import bashmenu_ui
import ymlcheck


class TestWallpaperCompositor(unittest.TestCase):
    """Test suite verifying WallpaperCompositor and half-block menu compositing."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.wallpaper_path = os.path.join(cls.test_dir, "assets", "wallpapers", "twilight.png")

    def test_wallpaper_file_exists(self):
        """Verify the twilight wallpaper image exists in assets/wallpapers/."""
        self.assertTrue(
            os.path.exists(self.wallpaper_path),
            f"Expected wallpaper at {self.wallpaper_path}",
        )

    def test_compositor_loading_and_resizing(self):
        """Verify WallpaperCompositor loads image, resizes to (w, h*2), and caches grid."""
        compositor = bashmenu_ui.WallpaperCompositor(
            self.wallpaper_path, opacity=0.35, scaling="cover", base_dir=self.test_dir
        )
        self.assertIsNotNone(compositor._raw_image)

        # Generate grid for 80x24 terminal
        grid = compositor.get_grid(80, 24, (15, 20, 32))
        self.assertIsNotNone(grid)
        self.assertEqual(len(grid), 24)
        self.assertEqual(len(grid[0]), 80)

        # Verify cached grid returned on subsequent call with identical parameters
        grid2 = compositor.get_grid(80, 24, (15, 20, 32))
        self.assertIs(grid, grid2)

    def test_compositor_graceful_missing_file(self):
        """Verify WallpaperCompositor gracefully handles non-existent image paths."""
        compositor = bashmenu_ui.WallpaperCompositor(
            "non_existent_wallpaper_12345.png", opacity=0.35, base_dir=self.test_dir
        )
        self.assertIsNone(compositor._raw_image)
        grid = compositor.get_grid(80, 24, (15, 20, 32))
        self.assertIsNone(grid)

    def test_get_theme_bg_rgb(self):
        """Verify get_theme_bg_rgb extracts RGB triplet from theme styles."""
        styles = {"background": Style(bgcolor="color(235)")}
        rgb = bashmenu_ui.get_theme_bg_rgb(styles)
        self.assertIsInstance(rgb, tuple)
        self.assertEqual(len(rgb), 3)

        # Empty or missing styles fallback
        fallback_rgb = bashmenu_ui.get_theme_bg_rgb({})
        self.assertEqual(fallback_rgb, (15, 20, 32))

    def test_composite_menu_text_transformation(self):
        """Verify composite_menu_text inserts half-blocks into empty space and applies bg to text."""
        compositor = bashmenu_ui.WallpaperCompositor(
            self.wallpaper_path, opacity=0.35, scaling="cover", base_dir=self.test_dir
        )
        grid = compositor.get_grid(80, 24, (15, 20, 32))

        # Create sample menu line with borders, spaces, and text
        raw_text = Text("┌" + "─" * 78 + "┐\n")
        raw_text.append("│  [1] First Option" + " " * 57 + "│\n")
        raw_text.append("└" + "─" * 78 + "┘")

        composited = bashmenu_ui.composite_menu_text(
            raw_text, grid, 80, 3, theme_default_bg=Style(bgcolor="color(235)").bgcolor
        )

        plain = composited.plain
        self.assertIn("▀", plain)
        self.assertIn("First Option", plain)
        self.assertEqual(len(composited.split("\n")), 3)

    def test_main_menu_view_integration(self):
        """Verify MainMenuView renders half-blocks when background is enabled, and none when disabled."""
        cfg, _ = bashmenu.load_config()
        menu, _ = bashmenu.load_menu()

        # 1. Enabled
        cfg["settings"]["background"] = {
            "enabled": True,
            "image": "{bashmenu_dir}/assets/wallpapers/twilight.png",
            "opacity": 0.35,
            "scaling": "cover",
        }
        mv_enabled = bashmenu.MainMenuView(config=cfg, menu_data=menu)
        with patch.object(
            bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)
        ):
            out_enabled = mv_enabled.render()
        self.assertGreater(out_enabled.plain.count("▀"), 500)

        # 2. Disabled
        cfg["settings"]["background"]["enabled"] = False
        mv_disabled = bashmenu.MainMenuView(config=cfg, menu_data=menu)
        with patch.object(
            bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)
        ):
            out_disabled = mv_disabled.render()
        self.assertEqual(out_disabled.plain.count("▀"), 0)

    def test_twilight_theme_schema_validation(self):
        """Verify ymlcheck validates twilight theme and settings.background without errors."""
        themes_path = os.path.join(self.test_dir, "bashmenu.themes")
        config_path = os.path.join(self.test_dir, "bashmenu.yml")

        self.assertTrue(ymlcheck.validate_theme_file(themes_path))
        self.assertTrue(ymlcheck.validate_config_file(config_path))

    def test_theme_specified_background_resolution(self):
        """Verify theme-specified background displays automatically without settings.background in config."""
        cfg, _ = bashmenu.load_config()
        cfg["theme"] = "twilight"
        # Ensure settings.background is completely absent
        cfg.get("settings", {}).pop("background", None)
        menu, _ = bashmenu.load_menu()

        mv = bashmenu.MainMenuView(config=cfg, menu_data=menu)
        with patch.object(
            bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)
        ):
            out = mv.render()

        # Twilight specifies background in theme itself, so half-blocks must render
        self.assertGreater(out.plain.count("▀"), 500)

    def test_theme_without_background_renders_no_halfblocks(self):
        """Verify theme without background (e.g. dracula) renders with zero half-blocks when config is omitted."""
        cfg, _ = bashmenu.load_config()
        cfg["theme"] = "dracula"
        cfg.get("settings", {}).pop("background", None)
        menu, _ = bashmenu.load_menu()

        mv = bashmenu.MainMenuView(config=cfg, menu_data=menu)
        with patch.object(
            bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)
        ):
            out = mv.render()

        self.assertEqual(out.plain.count("▀"), 0)

    def test_settings_enabled_false_overrides_theme_background(self):
        """Verify settings.background.enabled: false suppresses theme-specified background."""
        cfg, _ = bashmenu.load_config()
        cfg["theme"] = "twilight"
        cfg.setdefault("settings", {})["background"] = {"enabled": False}
        menu, _ = bashmenu.load_menu()

        mv = bashmenu.MainMenuView(config=cfg, menu_data=menu)
        with patch.object(
            bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)
        ):
            out = mv.render()

        self.assertEqual(out.plain.count("▀"), 0)

    def test_main_menu_view_render_lines_not_blank(self):
        """Verify Textual's render_lines pipeline for MainMenuView produces non-blank menu content."""
        async def _run():
            app = bashmenu.BashMenuApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                mv = app.screen.query_one(bashmenu.MainMenuView)
                strips = mv.render_lines(Region(0, 0, 80, 24))

                self.assertEqual(len(strips), 24)
                top_line = strips[0].text
                # Top border must contain Bash Menu title and border chars, not just spaces
                self.assertIn("Bash Menu", top_line)
                self.assertNotEqual(top_line.strip(), "")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
