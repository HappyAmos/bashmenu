#!/usr/bin/env python3
"""
theme_from_image.py - Auto-generate HA Bash Menu themes from an image.

Extracts a harmonious color palette using Pillow adaptive color quantization,
evaluates perceptual luminance and saturation to assign semantic roles (background,
borders, accents, text, highlights, buttons), maps colors to standard xterm-256 indices,
and auto-derives 16-color and 8-color fallback tiers.

Can be used as a standalone CLI tool or imported as a module by themeedit.py.
"""

from __future__ import annotations

import argparse
import colorsys
import contextlib
import copy
import os
import re
import sys
from typing import Any

import yaml
from rich._palettes import EIGHT_BIT_PALETTE

# Ensure parent directory is on sys.path for local imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import bashmenu
import themeedit
import ymlcheck

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False


def rgb_to_xterm256(r: int, g: int, b: int) -> int:
    """Find the closest standard xterm-256 color index using Euclidean distance."""
    best_idx = 0
    best_dist = float("inf")
    for i in range(256):
        pal = EIGHT_BIT_PALETTE[i]
        dist = (pal.red - r) ** 2 + (pal.green - g) ** 2 + (pal.blue - b) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = i
            if dist == 0:
                break
    return best_idx


def get_color_luminance(r: int, g: int, b: int) -> float:
    """Calculate perceptual relative luminance (0..255)."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def extract_palette_from_image(
    image_path: str, max_colors: int = 24
) -> list[dict[str, Any]]:
    """
    Extract a list of dominant unique color dictionaries from an image file.

    Returns a list of dicts with keys:
        rgb, h, s, v, lum, 256, count
    """
    if not PIL_AVAILABLE or Image is None:
        raise RuntimeError("Pillow (PIL) is required for image color extraction.")

    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    with Image.open(image_path) as orig:
        img = orig.convert("RGB")
        # Resize to thumbnail size for fast quantization
        img.thumbnail((200, 200))
        quant = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=max_colors)
        pal = quant.getpalette()[: max_colors * 3]
        raw_colors = quant.getcolors() or []

    extracted: list[dict[str, Any]] = []
    seen_256: set[int] = set()

    for count, idx in sorted(raw_colors, reverse=True):
        if idx * 3 + 2 >= len(pal):
            continue
        r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        lum = get_color_luminance(r, g, b)
        c256 = rgb_to_xterm256(r, g, b)

        if c256 not in seen_256:
            seen_256.add(c256)
            extracted.append({
                "rgb": (r, g, b),
                "h": h,
                "s": s,
                "v": v,
                "lum": lum,
                "256": c256,
                "count": count,
            })

    return extracted


def sanitize_theme_name(raw_name: str) -> str:
    """Sanitize arbitrary string into a valid lowercase slug for bashmenu.themes."""
    slug = re.sub(r"[^\w\-]+", "_", raw_name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "image_theme"


def generate_theme_from_image(
    image_path: str,
    theme_name: str | None = None,
    mode: str = "dark",
    set_wallpaper: bool = True,
    background_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a full HA Bash Menu theme dictionary derived from an image.

    Includes 256, 16, and 8 color tiers, marquee, indicator, and window borders.
    """
    colors = extract_palette_from_image(image_path, max_colors=24)
    if not colors:
        raise ValueError("Could not extract any colors from the provided image.")

    is_dark = mode.lower() != "light"

    # 1. Determine Background
    if is_dark:
        dark_cands = [p for p in colors if p["lum"] < 50]
        if dark_cands:
            chosen_bg = min(dark_cands, key=lambda x: x["lum"])
            bg_color = chosen_bg["256"]
            bg_lum = chosen_bg["lum"]
        else:
            bg_color = "COLOR_BLACK"
            bg_lum = 0.0
    else:
        light_cands = [p for p in colors if p["lum"] > 190]
        if light_cands:
            chosen_bg = max(light_cands, key=lambda x: x["lum"])
            bg_color = chosen_bg["256"]
            bg_lum = chosen_bg["lum"]
        else:
            bg_color = 255
            bg_lum = 255.0

    # 2. Score Candidates for Accents (balancing saturation & background contrast)
    scored = []
    for p in colors:
        if p["256"] == bg_color:
            continue
        contrast = abs(p["lum"] - bg_lum) / 100.0
        # Emphasize saturation, but ensure visible contrast with background
        score = (p["s"] * 1.6) + (contrast * 1.2)
        p_copy = dict(p)
        p_copy["score"] = score
        scored.append(p_copy)

    sorted_accents = sorted(scored, key=lambda x: x["score"], reverse=True)
    if not sorted_accents:
        sorted_accents = [dict(colors[0])]

    primary_accent = sorted_accents[0]["256"]

    # Secondary accent: pick distinct hue/luminance if available
    sec_candidates = [
        p for p in sorted_accents
        if p["256"] != primary_accent and (abs(p["h"] - sorted_accents[0]["h"]) > 0.08 or abs(p["lum"] - sorted_accents[0]["lum"]) > 25)
    ]
    if not sec_candidates:
        sec_candidates = [p for p in sorted_accents if p["256"] != primary_accent]
    secondary_accent = sec_candidates[0]["256"] if sec_candidates else primary_accent

    # 3. Determine Borders and Structural Lines (mid-tones)
    if is_dark:
        border_cands = sorted(
            [p for p in colors if 40 <= p["lum"] <= 150 and p["256"] != bg_color],
            key=lambda x: abs(x["lum"] - 85),
        )
    else:
        border_cands = sorted(
            [p for p in colors if 60 <= p["lum"] <= 170 and p["256"] != bg_color],
            key=lambda x: abs(x["lum"] - 110),
        )
    border_color = border_cands[0]["256"] if border_cands else primary_accent

    # Dimmer gutter/whitespace tone
    gutter_cands = sorted(
        [p for p in colors if (25 <= p["lum"] <= 100 if is_dark else 100 <= p["lum"] <= 210) and p["256"] != bg_color and p["256"] != border_color],
        key=lambda x: x["lum"],
    )
    gutter_color = gutter_cands[0]["256"] if gutter_cands else (238 if is_dark else 250)

    # 4. Selection Row & Button Foreground Contrast
    prim_rgb = EIGHT_BIT_PALETTE[primary_accent] if isinstance(primary_accent, int) else None
    if prim_rgb:
        prim_lum = get_color_luminance(prim_rgb.red, prim_rgb.green, prim_rgb.blue)
    else:
        prim_lum = 50.0

    selection_fg = 16 if prim_lum > 135 else 255
    text_fg = 255 if is_dark else 16

    # Error and Success button colors: use image accents if matching hue, else clean ANSI/256
    error_cands = [p for p in colors if (p["h"] >= 0.95 or p["h"] <= 0.06) and p["s"] >= 0.35]
    button_error = error_cands[0]["256"] if error_cands else 196

    success_cands = [p for p in colors if 0.22 <= p["h"] <= 0.44 and p["s"] >= 0.30]
    button_success = success_cands[0]["256"] if success_cands else 40

    # Assemble 256-color palette dictionary
    palette_256: dict[str, Any] = {
        "background": bg_color,
        "title": [primary_accent, -1],
        "border": [border_color, -1],
        "text": [text_fg, -1],
        "highlight": [selection_fg, primary_accent],
        "accent": [secondary_accent, -1],
        "footer": [border_color, -1],
        "shadow": [236, "COLOR_BLACK"],
        "gutter": [gutter_color, -1],
        "selection": [selection_fg, primary_accent],
        "shortcut_key": [secondary_accent, -1],
        "divider": [border_color, -1],
        "button_primary": [selection_fg, primary_accent],
        "button_error": [255, button_error],
        "button_cancel": [text_fg, gutter_color],
        "button_success": [255, button_success],
        "help_text": [secondary_accent, -1],
        "plugin": [secondary_accent, -1],
        "window_close_button": [203, -1],
        "scrollbar": [primary_accent, 236 if is_dark else 250],
        "whitespace": [gutter_color, -1],
    }

    # Automatically derive 16-color and 8-color fallback depths
    palette_16, palette_8 = themeedit.auto_derive_fallback_depths(palette_256)

    # Standard clean window borders and marquee
    full_theme: dict[str, Any] = {
        "marquee": {"char": "\u2022", "gap": 5},
        "indicator": "{nf:@:\uEE90:}",
        "window": {
            "border_horizontal": "\u2500",
            "border_vertical": "\u2502",
            "border_top_left": "\u250C",
            "border_top_right": "\u2510",
            "border_bottom_left": "\u2514",
            "border_bottom_right": "\u2518",
            "left_tee": "\u251C",
            "right_tee": "\u2524",
            "top_tee": "\u252C",
            "bottom_tee": "\u2534",
            "title_left_cap": "[",
            "title_right_cap": "]",
            "gutter_border": "\u2500",
            "gutter_separator": "\u2502",
            "gutter_left_tee": "\u251C",
            "gutter_right_tee": "\u2524",
            "gutter_top_tee": "\u252C",
            "gutter_bottom_tee": "\u2534",
        },
        256: palette_256,
        16: palette_16,
        8: palette_8,
    }

    # Configure background wallpaper if requested
    if set_wallpaper:
        rel_path = image_path
        with contextlib.suppress(Exception):
            rel = os.path.relpath(image_path, bashmenu.BASHMENU_DIR)
            if not rel.startswith(".."):
                rel_path = rel
        bg_dict: dict[str, Any] = {
            "image": rel_path,
            "opacity": 0.85,
            "scaling": "cover",
            "mode": "halfblock",
            "clustering": 0,
            "quantization": 1,
        }
        if background_config and isinstance(background_config, dict):
            for k, v in background_config.items():
                if k != "image":
                    bg_dict[k] = copy.deepcopy(v)
        full_theme["background"] = bg_dict
    elif background_config and isinstance(background_config, dict):
        full_theme["background"] = copy.deepcopy(background_config)

    return full_theme


def save_theme_to_themes_file(
    theme_name: str,
    theme_dict: dict[str, Any],
    themes_path: str | None = None,
    set_active: bool = False,
    config_path: str | None = None,
) -> bool:
    """Save the theme to bashmenu.themes and optionally activate it in bashmenu.yml."""
    target_path = themes_path or bashmenu.BASHMENU_THEMES
    cfg_path = config_path or bashmenu.BASHMENU_CONFIG

    existing_themes: dict[str, Any] = {}
    if os.path.isfile(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            existing_themes = yaml.safe_load(f) or {}

    clean_theme = copy.deepcopy(theme_dict)
    # Validate structure using ymlcheck
    errs = []
    for k_depth, v_keys in clean_theme.items():
        depth_str = str(k_depth)
        if depth_str == "window":
            errs.extend(ymlcheck.validate_window_section(v_keys, f"{theme_name}.window"))
        elif depth_str == "divider":
            errs.extend(ymlcheck.validate_divider_section(v_keys, f"{theme_name}.divider"))
        elif depth_str == "marquee":
            errs.extend(ymlcheck.validate_marquee_section(v_keys, f"{theme_name}.marquee"))
        elif depth_str == "background":
            errs.extend(ymlcheck.validate_theme_background_section(v_keys, f"{theme_name}.background"))
        elif depth_str in ("256", "16", "8"):
            errs.extend(ymlcheck.validate_depth_section(depth_str, v_keys, theme_name))

    if errs:
        raise ValueError(f"Theme validation failed: {'; '.join(errs)}")

    existing_themes[theme_name] = clean_theme

    with open(target_path, "w", encoding="utf-8") as f:
        yaml.dump(existing_themes, f, sort_keys=False, allow_unicode=True)

    if set_active and os.path.isfile(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cfg["theme"] = theme_name
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, sort_keys=False, allow_unicode=True)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-generate a HA Bash Menu theme derived from an image color palette."
    )
    parser.add_argument("image", help="Path to input image file (PNG/JPG)")
    parser.add_argument("-n", "--name", help="Theme identifier (default: based on image filename)")
    parser.add_argument(
        "-m", "--mode", choices=["dark", "light"], default="dark", help="Theme mode (default: dark)"
    )
    parser.add_argument(
        "--no-wallpaper", action="store_true", help="Do not configure image as background wallpaper"
    )
    parser.add_argument(
        "-s", "--save", action="store_true", help="Save directly into bashmenu.themes"
    )
    parser.add_argument(
        "-a", "--set-active", action="store_true", help="Activate theme in bashmenu.yml (implies --save)"
    )
    parser.add_argument("-o", "--output", help="Write YAML output to specific file")
    parser.add_argument(
        "--opacity", type=float, help="Wallpaper opacity (0.0 - 1.0, default: 0.85)"
    )
    parser.add_argument(
        "--scaling", choices=["cover", "stretch", "fit", "center", "tile"], help="Wallpaper scaling mode (default: cover)"
    )
    parser.add_argument(
        "--bg-mode", choices=["halfblock", "quarterblock"], help="Wallpaper rendering mode (default: halfblock)"
    )
    parser.add_argument(
        "--clustering", type=int, help="Color clustering distance (0=none, 16-128)"
    )
    parser.add_argument(
        "--quantization", type=int, help="Palette quantization levels (1=off, 16-256)"
    )

    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"Error: Image file not found: {args.image}", file=sys.stderr)
        return 1

    stem = os.path.splitext(os.path.basename(args.image))[0]
    name = sanitize_theme_name(args.name or stem)

    cli_bg: dict[str, Any] = {}
    if args.opacity is not None:
        cli_bg["opacity"] = args.opacity
    if args.scaling is not None:
        cli_bg["scaling"] = args.scaling
    if args.bg_mode is not None:
        cli_bg["mode"] = args.bg_mode
    if args.clustering is not None:
        cli_bg["clustering"] = args.clustering
    if args.quantization is not None:
        cli_bg["quantization"] = args.quantization

    try:
        theme = generate_theme_from_image(
            args.image,
            theme_name=name,
            mode=args.mode,
            set_wallpaper=not args.no_wallpaper,
            background_config=cli_bg or None,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error extracting theme from image: {exc}", file=sys.stderr)
        return 1

    if args.save or args.set_active:
        try:
            save_theme_to_themes_file(name, theme, set_active=args.set_active)
            print(f"[✓] Theme '{name}' successfully saved to {bashmenu.BASHMENU_THEMES}")
            if args.set_active:
                print(f"[✓] Theme '{name}' activated in {bashmenu.BASHMENU_CONFIG}")
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"Error saving theme: {exc}", file=sys.stderr)
            return 1
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            yaml.dump({name: theme}, f, sort_keys=False, allow_unicode=True)
        print(f"[✓] Theme '{name}' exported to {args.output}")
    else:
        print(yaml.dump({name: theme}, sort_keys=False, allow_unicode=True))

    return 0


if __name__ == "__main__":
    sys.exit(main())
