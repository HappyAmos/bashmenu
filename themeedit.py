#!/usr/bin/env python3
"""
themeedit.py - Interactive Visual Theme Creator & Editor for HA Bash Menu.
Features a live real-time split-screen preview canvas with an interactive
property inspector, 256-color picker modal, box-drawing ASCII modal,
theme cloning, and automatic 16/8-color fallback derivation.
"""

__version__ = "0.0.1"
__author__ = "HappyAmos"

import argparse
import contextlib
import copy
import os
import re
from typing import Any, ClassVar

import yaml
from rich.style import Style
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

import bashmenu
import bashmenu_ui
import ymlcheck

# Standard ANSI Color RGB definitions for distance calculation
ANSI_16_RGB = {
    0: ("COLOR_BLACK", (0, 0, 0)),
    1: ("COLOR_RED", (170, 0, 0)),
    2: ("COLOR_GREEN", (0, 170, 0)),
    3: ("COLOR_YELLOW", (170, 85, 0)),
    4: ("COLOR_BLUE", (0, 0, 170)),
    5: ("COLOR_MAGENTA", (170, 0, 170)),
    6: ("COLOR_CYAN", (0, 170, 170)),
    7: ("COLOR_WHITE", (170, 170, 170)),
    8: ("COLOR_GREY", (85, 85, 85)),
    9: ("COLOR_BRIGHT_RED", (255, 85, 85)),
    10: ("COLOR_BRIGHT_GREEN", (85, 255, 85)),
    11: ("COLOR_BRIGHT_YELLOW", (255, 255, 85)),
    12: ("COLOR_BRIGHT_BLUE", (85, 85, 255)),
    13: ("COLOR_BRIGHT_MAGENTA", (255, 85, 255)),
    14: ("COLOR_BRIGHT_CYAN", (85, 255, 255)),
    15: ("COLOR_BRIGHT_WHITE", (255, 255, 255)),
}

# CP437 mapping for decoding extended ASCII codes in bashmenu
UNICODE_TO_CP437: dict[str, int] = {}
for _b in range(256):
    with contextlib.suppress(Exception):
        UNICODE_TO_CP437[bytes([_b]).decode("cp437")] = _b

CP437_CONTROL_GLYPHS: dict[int, str] = {
    0: "·", 1: "☺", 2: "☻", 3: "♥", 4: "♦", 5: "♣", 6: "♠", 7: "•",
    8: "◘", 9: "○", 10: "◙", 11: "♂", 12: "♀", 13: "♪", 14: "♫", 15: "☼",
    16: "►", 17: "◄", 18: "↕", 19: "‼", 20: "¶", 21: "§", 22: "▬", 23: "↨",
    24: "↑", 25: "↓", 26: "→", 27: "←", 28: "∟", 29: "↔", 30: "▲", 31: "▼",
    127: "⌂",
}
for _c, _g in CP437_CONTROL_GLYPHS.items():
    UNICODE_TO_CP437[_g] = _c


def get_cp437_glyph(code: int) -> str:
    """Return visual character representation for CP437 byte code."""
    if code in CP437_CONTROL_GLYPHS:
        return CP437_CONTROL_GLYPHS[code]
    try:
        return bytes([code % 256]).decode("cp437", errors="replace")
    except (ValueError, UnicodeDecodeError, OverflowError):
        return "?"


def get_rgb_from_color_idx(idx: int | str) -> tuple[int, int, int]:
    """Calculate RGB triplet from 256-color index or color constant."""
    if isinstance(idx, str):
        if idx in bashmenu_ui.COLOR_MAP:
            hex_c = bashmenu_ui.COLOR_MAP[idx].lstrip("#")
            return tuple(int(hex_c[i : i + 2], 16) for i in (0, 2, 4))
        if idx.isdigit():
            idx = int(idx)
        else:
            return (128, 128, 128)

    if not isinstance(idx, int) or idx < 0:
        return (0, 0, 0)

    if idx < 16:
        return ANSI_16_RGB[idx][1]
    if idx < 232:
        idx -= 16
        b = (idx % 6) * 51
        g = ((idx // 6) % 6) * 51
        r = (idx // 36) * 51
        return (r, g, b)
    # Grayscale ramp 232..255
    gray = 8 + (idx - 232) * 10
    return (gray, gray, gray)


def nearest_ansi_color(val: int | str, max_colors: int = 16) -> str | int:
    """Find closest 16-color or 8-color constant using Euclidean RGB distance."""
    if val == -1 or val == "-1":
        return -1
    if isinstance(val, str) and val in bashmenu_ui.COLOR_MAP:
        return val

    rgb = get_rgb_from_color_idx(val)
    best_dist = float("inf")
    best_name = "COLOR_BLACK"

    limit = 16 if max_colors >= 16 else 8
    for i in range(limit):
        c_name, c_rgb = ANSI_16_RGB[i]
        dist = sum((rgb[k] - c_rgb[k]) ** 2 for k in range(3))
        if dist < best_dist:
            best_dist = dist
            best_name = c_name

    return best_name


def auto_derive_fallback_depths(palette_256: dict) -> tuple[dict, dict]:
    """Automatically derive 16-color and 8-color fallback dictionaries from 256 palette."""
    palette_16 = {}
    palette_8 = {}

    for k, val in palette_256.items():
        if k == "background":
            palette_16[k] = nearest_ansi_color(val, 16)
            palette_8[k] = nearest_ansi_color(val, 8)
        elif isinstance(val, (list, tuple)) and len(val) >= 2:
            fg16 = nearest_ansi_color(val[0], 16)
            bg16 = nearest_ansi_color(val[1], 16)
            fg8 = nearest_ansi_color(val[0], 8)
            bg8 = nearest_ansi_color(val[1], 8)
            palette_16[k] = [fg16, bg16]
            palette_8[k] = [fg8, bg8]
        else:
            palette_16[k] = val
            palette_8[k] = val

    return palette_16, palette_8


# ==============================================================================
# PICKER MODAL SCREENS
# ==============================================================================


# ==============================================================================
# PICKER MODAL SCREENS & WIDGETS
# ==============================================================================

STANDARD_CONST_MAP: dict[str, int] = {
    "COLOR_BLACK": 0,
    "COLOR_RED": 196,
    "COLOR_GREEN": 46,
    "COLOR_YELLOW": 226,
    "COLOR_BLUE": 63,
    "COLOR_MAGENTA": 201,
    "COLOR_CYAN": 51,
    "COLOR_WHITE": 231,
    "COLOR_GREY": 244,
    "COLOR_GRAY": 244,
    "COLOR_BRIGHT_BLACK": 244,
    "COLOR_BRIGHT_RED": 203,
    "COLOR_BRIGHT_GREEN": 82,
    "COLOR_BRIGHT_YELLOW": 227,
    "COLOR_BRIGHT_BLUE": 75,
    "COLOR_BRIGHT_MAGENTA": 207,
    "COLOR_BRIGHT_CYAN": 87,
    "COLOR_BRIGHT_WHITE": 255,
    "COLOR_ORANGE": 208,
    "COLOR_PURPLE": 129,
    "COLOR_PINK": 211,
    "COLOR_BROWN": 130,
}

CODE_TO_CONST: dict[int, str] = {
    0: "COLOR_BLACK",
    196: "COLOR_RED",
    46: "COLOR_GREEN",
    226: "COLOR_YELLOW",
    63: "COLOR_BLUE",
    201: "COLOR_MAGENTA",
    51: "COLOR_CYAN",
    231: "COLOR_WHITE",
    244: "COLOR_GREY",
    203: "COLOR_BRIGHT_RED",
    82: "COLOR_BRIGHT_GREEN",
    227: "COLOR_BRIGHT_YELLOW",
    75: "COLOR_BRIGHT_BLUE",
    207: "COLOR_BRIGHT_MAGENTA",
    87: "COLOR_BRIGHT_CYAN",
    255: "COLOR_BRIGHT_WHITE",
    208: "COLOR_ORANGE",
    129: "COLOR_PURPLE",
    211: "COLOR_PINK",
    130: "COLOR_BROWN",
}


class ColorGridWidget(Widget):
    """Interactive 16x16 2D terminal color palette grid with keyboard navigation."""

    can_focus = True

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("left", "cursor_left", "Left", show=False),
        Binding("right", "cursor_right", "Right", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("home", "cursor_home", "Home", show=False),
        Binding("end", "cursor_end", "End", show=False),
        Binding("pageup", "cursor_page_up", "Page Up", show=False),
        Binding("pagedown", "cursor_page_down", "Page Down", show=False),
        Binding("enter", "select_color", "Select", show=False),
    ]

    class ColorHighlighted(Message):
        """Emitted when highlighted color index changes."""

        def __init__(self, color_code: int) -> None:
            super().__init__()
            self.color_code = color_code

    class ColorSelected(Message):
        """Emitted when Enter is pressed on a color."""

        def __init__(self, color_code: int) -> None:
            super().__init__()
            self.color_code = color_code

    def __init__(self, initial_code: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.cursor_code = max(0, min(255, initial_code))

    def render(self) -> Text:
        grid_text = Text()
        for row in range(16):
            for col in range(16):
                code = row * 16 + col
                is_sel = (code == self.cursor_code)
                code_str = f"{code:4d}"

                if is_sel:
                    # While navigating, the currently selected number code is underlined
                    if code == 0:
                        style = Style(color="color(255)", bgcolor="color(237)", bold=True, underline=True)
                    else:
                        bg = "color(237)" if code != 237 else "color(233)"
                        style = Style(color=f"color({code})", bgcolor=bg, bold=True, underline=True)
                else:
                    if code == 0:
                        style = Style(color="color(242)")
                    else:
                        style = Style(color=f"color({code})")

                grid_text.append(code_str, style=style)
            if row < 15:
                grid_text.append("\n")

        return grid_text

    def set_code(self, code: int, notify: bool = True) -> None:
        """Update cursor code and refresh visual display."""
        if 0 <= code <= 255:
            self.cursor_code = code
            self.refresh()
            if notify:
                self.post_message(self.ColorHighlighted(self.cursor_code))

    def on_click(self, event: Any) -> None:
        x = getattr(event, "x", 0)
        y = getattr(event, "y", 0)
        col = x // 4
        row = y
        if 0 <= col < 16 and 0 <= row < 16:
            code = row * 16 + col
            self.set_code(code)

    def action_cursor_left(self) -> None:
        self.set_code((self.cursor_code - 1) % 256)

    def action_cursor_right(self) -> None:
        self.set_code((self.cursor_code + 1) % 256)

    def action_cursor_up(self) -> None:
        self.set_code((self.cursor_code - 16) % 256)

    def action_cursor_down(self) -> None:
        self.set_code((self.cursor_code + 16) % 256)

    def action_cursor_home(self) -> None:
        self.set_code(0)

    def action_cursor_end(self) -> None:
        self.set_code(255)

    def action_cursor_page_up(self) -> None:
        self.set_code((self.cursor_code - 64) % 256)

    def action_cursor_page_down(self) -> None:
        self.set_code((self.cursor_code + 64) % 256)

    def action_select_color(self) -> None:
        self.post_message(self.ColorSelected(self.cursor_code))


class ColorPickerModal(ModalScreen[Any]):
    """Interactive 2D terminal color palette picker with live preview and constants."""

    DEFAULT_CSS = """
    ColorPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    #dialog {
        width: 80;
        height: 29;
        border: thick #555;
        background: #181818;
        padding: 0 1;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 0;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #eee;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        background: #333;
        color: #fff;
    }
    #tabs_row {
        height: 2;
        width: 100%;
        align: center middle;
        margin-bottom: 0;
    }
    #tabs_row Button, .tab_btn {
        height: 1;
        min-width: 22;
        margin: 0 1;
        padding: 0 1;
        border: none !important;
    }
    #tab_hint {
        color: #888;
        margin-left: 1;
    }
    #tab_single {
        text-align: center;
        text-style: bold;
        color: #ccc;
    }
    #grid_container {
        height: 16;
        width: 100%;
        align: center middle;
    }
    ColorGridWidget {
        width: 64;
        height: 16;
    }
    ColorGridWidget:focus {
        border: none;
    }
    #preview_bar {
        height: 1;
        width: 100%;
        margin-top: 0;
        text-align: center;
    }
    .swatch_row, #swatch_row {
        height: 1;
        width: 100%;
        align: center middle;
        margin-top: 0;
    }
    .swatch_lbl {
        color: #888;
        margin-right: 1;
        width: 10;
    }
    .swatch_row Button, #swatch_row Button, .btn_swatch {
        height: 1;
        min-width: 4;
        padding: 0;
        margin: 0;
        border: none !important;
        background: #252525;
        color: #ccc;
    }
    #swatch_inherit { background: #333333; color: #cccccc; }
    #swatch_COLOR_BLACK { background: #000000; color: #ffffff; }
    #swatch_COLOR_RED { background: #ff0000; color: #ffffff; }
    #swatch_COLOR_GREEN { background: #00ff00; color: #000000; }
    #swatch_COLOR_YELLOW { background: #ffff00; color: #000000; }
    #swatch_COLOR_BLUE { background: #0055ff; color: #ffffff; }
    #swatch_COLOR_MAGENTA { background: #ff00ff; color: #ffffff; }
    #swatch_COLOR_CYAN { background: #00ffff; color: #000000; }
    #swatch_COLOR_WHITE { background: #ffffff; color: #000000; }
    #swatch_COLOR_GREY, #swatch_COLOR_GRAY { background: #808080; color: #ffffff; }
    #swatch_COLOR_BRIGHT_BLACK { background: #555555; color: #ffffff; }
    #swatch_COLOR_BRIGHT_RED { background: #ff5555; color: #ffffff; }
    #swatch_COLOR_BRIGHT_GREEN { background: #55ff55; color: #000000; }
    #swatch_COLOR_BRIGHT_YELLOW { background: #ffff55; color: #000000; }
    #swatch_COLOR_BRIGHT_BLUE { background: #5555ff; color: #ffffff; }
    #swatch_COLOR_BRIGHT_MAGENTA { background: #ff55ff; color: #ffffff; }
    #swatch_COLOR_BRIGHT_CYAN { background: #55ffff; color: #000000; }
    #swatch_COLOR_BRIGHT_WHITE { background: #ffffff; color: #000000; }
    #swatch_COLOR_ORANGE { background: #ff8700; color: #000000; }
    #swatch_COLOR_PURPLE { background: #af00ff; color: #ffffff; }
    #swatch_COLOR_PINK { background: #ff87af; color: #000000; }
    #swatch_COLOR_BROWN { background: #af5f00; color: #ffffff; }
    .btn_swatch:hover {
        text-style: underline bold;
    }
    .btn_swatch:focus {
        text-style: underline bold reverse;
    }
    .tab_btn:focus {
        text-style: underline bold reverse;
    }
    #btn_row {
        height: 3;
        margin-top: 0;
        align: center middle;
    }
    #btn_row Button {
        height: 3;
        min-width: 16;
        margin: 0 1;
    }
    #btn_row Button:focus {
        border: heavy #fff;
        text-style: bold;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm_selection", "Select"),
        Binding("1", "select_fg_tab", "Foreground", show=False),
        Binding("2", "select_bg_tab", "Background", show=False),
        Binding("f", "select_fg_tab", "Foreground", show=False),
        Binding("b", "select_bg_tab", "Background", show=False),
        Binding("i", "action_inherit", "Inherit", show=False),
    ]

    def __init__(
        self,
        token_name: str,
        current_val: Any,
        bg_color_val: Any = None,
        theme_styles: dict | None = None,
    ):
        super().__init__()
        self.token_name = token_name
        self.current_val = current_val
        self.bg_color_val = bg_color_val
        self.theme_styles = theme_styles or {}

        if token_name == "background":
            self.is_pair = False
            self.fg_val = current_val
            self.bg_val = -1
        else:
            self.is_pair = True
            if isinstance(current_val, (list, tuple)):
                self.fg_val = current_val[0] if len(current_val) > 0 else -1
                self.bg_val = current_val[1] if len(current_val) > 1 else -1
            elif isinstance(current_val, str) and current_val.strip().startswith("[") and current_val.strip().endswith("]"):
                try:
                    parsed = yaml.safe_load(current_val)
                    if isinstance(parsed, list):
                        self.fg_val = parsed[0] if len(parsed) > 0 else -1
                        self.bg_val = parsed[1] if len(parsed) > 1 else -1
                    else:
                        self.fg_val = current_val
                        self.bg_val = -1
                except (yaml.YAMLError, ValueError):
                    self.fg_val = current_val
                    self.bg_val = -1
            else:
                self.fg_val = current_val
                self.bg_val = -1

        self.active_tab = "fg"

    @property
    def selected_color(self) -> Any:
        return [self.fg_val, self.bg_val] if self.is_pair else self.fg_val

    @selected_color.setter
    def selected_color(self, val: Any) -> None:
        if self.is_pair:
            if isinstance(val, (list, tuple)):
                self.fg_val = val[0] if len(val) > 0 else -1
                self.bg_val = val[1] if len(val) > 1 else -1
            else:
                if self.active_tab == "fg":
                    self.fg_val = val
                else:
                    self.bg_val = val
        else:
            self.fg_val = val

    def _val_to_code(self, val: Any) -> int:
        if val is None or val == -1 or val == "-1":
            return -1
        if isinstance(val, int) and 0 <= val <= 255:
            return val
        if isinstance(val, str):
            val_clean = val.strip()
            if val_clean in STANDARD_CONST_MAP:
                return STANDARD_CONST_MAP[val_clean]
            if val_clean.isdigit():
                num = int(val_clean)
                if 0 <= num <= 255:
                    return num
        return 0

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(f"Pick Color: [{self.token_name}]", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(self.theme_styles),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )
                    with Horizontal(id="tabs_row"):
                        if self.is_pair:
                            yield Button(f"[1] Foreground: {self.fg_val}", id="btn_tab_fg", classes="tab_btn", variant="primary")
                            yield Button(f"[2] Background: {self.bg_val}", id="btn_tab_bg", classes="tab_btn", variant="default")
                            yield Label("([1] FG | [2] BG)", id="tab_hint")
                        else:
                            yield Label(f"Editing Single Color: {self.token_name}", id="tab_single")

                    with Horizontal(id="grid_container"):
                        init_code = self._val_to_code(self.fg_val)
                        if init_code == -1:
                            init_code = 0
                        yield ColorGridWidget(initial_code=init_code, id="color_grid")

                    yield Static(id="preview_bar")

                    with Horizontal(id="swatch_row", classes="swatch_row"):
                        yield Label("Standard: ", classes="swatch_lbl")
                        yield Button("Black", id="swatch_COLOR_BLACK", classes="btn_swatch")
                        yield Button("Red", id="swatch_COLOR_RED", classes="btn_swatch")
                        yield Button("Green", id="swatch_COLOR_GREEN", classes="btn_swatch")
                        yield Button("Yellow", id="swatch_COLOR_YELLOW", classes="btn_swatch")
                        yield Button("Blue", id="swatch_COLOR_BLUE", classes="btn_swatch")
                        yield Button("Magenta", id="swatch_COLOR_MAGENTA", classes="btn_swatch")
                        yield Button("Cyan", id="swatch_COLOR_CYAN", classes="btn_swatch")
                        yield Button("White", id="swatch_COLOR_WHITE", classes="btn_swatch")

                    with Horizontal(id="swatch_row_bright1", classes="swatch_row"):
                        yield Label("Bright:   ", classes="swatch_lbl")
                        yield Button("Br-Black", id="swatch_COLOR_BRIGHT_BLACK", classes="btn_swatch")
                        yield Button("Br-Red", id="swatch_COLOR_BRIGHT_RED", classes="btn_swatch")
                        yield Button("Br-Green", id="swatch_COLOR_BRIGHT_GREEN", classes="btn_swatch")
                        yield Button("Br-Yellow", id="swatch_COLOR_BRIGHT_YELLOW", classes="btn_swatch")

                    with Horizontal(id="swatch_row_bright2", classes="swatch_row"):
                        yield Label("          ", classes="swatch_lbl")
                        yield Button("Br-Blue", id="swatch_COLOR_BRIGHT_BLUE", classes="btn_swatch")
                        yield Button("Br-Magenta", id="swatch_COLOR_BRIGHT_MAGENTA", classes="btn_swatch")
                        yield Button("Br-Cyan", id="swatch_COLOR_BRIGHT_CYAN", classes="btn_swatch")
                        yield Button("Br-White", id="swatch_COLOR_BRIGHT_WHITE", classes="btn_swatch")

                    with Horizontal(id="swatch_row_ext", classes="swatch_row"):
                        yield Label("Extended: ", classes="swatch_lbl")
                        yield Button("Inherit", id="swatch_inherit", classes="btn_swatch")
                        yield Button("Grey", id="swatch_COLOR_GREY", classes="btn_swatch")
                        yield Button("Orange", id="swatch_COLOR_ORANGE", classes="btn_swatch")
                        yield Button("Purple", id="swatch_COLOR_PURPLE", classes="btn_swatch")
                        yield Button("Pink", id="swatch_COLOR_PINK", classes="btn_swatch")
                        yield Button("Brown", id="swatch_COLOR_BROWN", classes="btn_swatch")

                    with Horizontal(id="btn_row"):
                        yield Button("Select (Enter)", variant="primary", id="btn_select")
                        yield Button("Inherit (-1)", variant="default", id="btn_inherit")
                        yield Button("Cancel (Esc)", variant="error", id="btn_cancel")

                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        ts = self.theme_styles or getattr(self.app, "theme_styles", None) or bashmenu_ui.init_theme_colors()
        self.theme_styles = ts
        bashmenu_ui.apply_modal_theme(self, ts)
        with contextlib.suppress(Exception):
            btn_close = self.query_one("#btn_close_x", Label)
            btn_close.update(bashmenu_ui.format_close_button_label(ts))

        btn_prim = ts.get("button_primary") or ts.get("selection")
        if btn_prim:
            css_p_bg = bashmenu_ui.parse_css_color(btn_prim.bgcolor.name) if btn_prim.bgcolor else None
            css_p_fg = bashmenu_ui.parse_css_color(btn_prim.color.name) if btn_prim.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_select")
                if css_p_bg:
                    b.styles.background = css_p_bg
                if css_p_fg:
                    b.styles.color = css_p_fg

        btn_err = ts.get("button_error") or ts.get("button_cancel")
        if btn_err:
            css_e_bg = bashmenu_ui.parse_css_color(btn_err.bgcolor.name) if btn_err.bgcolor else None
            css_e_fg = bashmenu_ui.parse_css_color(btn_err.color.name) if btn_err.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_cancel")
                if css_e_bg:
                    b.styles.background = css_e_bg
                if css_e_fg:
                    b.styles.color = css_e_fg

        # Explicitly apply vibrant color backgrounds and contrast text to all swatch buttons
        for btn in self.query(".btn_swatch"):
            bid = getattr(btn, "id", "")
            cname = bid.replace("swatch_", "")
            if cname == "inherit":
                btn.styles.background = "#333333"
                btn.styles.color = "#cccccc"
            elif cname in bashmenu_ui.COLOR_MAP:
                hex_c = bashmenu_ui.COLOR_MAP[cname]
                btn.styles.background = hex_c
                if cname in {
                    "COLOR_YELLOW",
                    "COLOR_CYAN",
                    "COLOR_WHITE",
                    "COLOR_BRIGHT_GREEN",
                    "COLOR_BRIGHT_YELLOW",
                    "COLOR_BRIGHT_CYAN",
                    "COLOR_BRIGHT_WHITE",
                    "COLOR_PINK",
                    "COLOR_ORANGE",
                }:
                    btn.styles.color = "#000000"
                else:
                    btn.styles.color = "#ffffff"

        self._sync_tabs_ui()
        self._update_preview()

        # Focus color grid so arrow keys immediately respond
        with contextlib.suppress(Exception):
            self.query_one("#color_grid", ColorGridWidget).focus()

    def _sync_tabs_ui(self) -> None:
        if not self.is_pair:
            return
        with contextlib.suppress(Exception):
            btn_fg = self.query_one("#btn_tab_fg", Button)
            btn_bg = self.query_one("#btn_tab_bg", Button)
            btn_fg.label = f"[1] Foreground: {self.fg_val}"
            btn_bg.label = f"[2] Background: {self.bg_val}"
            if self.active_tab == "fg":
                btn_fg.variant = "primary"
                btn_bg.variant = "default"
            else:
                btn_fg.variant = "default"
                btn_bg.variant = "primary"

    def _update_preview(self) -> None:
        p_bar = self.query_one("#preview_bar", Static)
        parsed_fg = bashmenu_ui.parse_color_val(self.fg_val) or "white"

        if self.bg_val == -1:
            parsed_bg = bashmenu_ui.parse_color_val(self.bg_color_val) or "color(233)"
        else:
            parsed_bg = bashmenu_ui.parse_color_val(self.bg_val) or "color(233)"

        grid = self.query_one("#color_grid", ColorGridWidget)
        curr_code = grid.cursor_code
        const_name = CODE_TO_CONST.get(curr_code)
        const_str = f" ({const_name})" if const_name else ""

        txt = Text()
        if self.token_name == "background":
            bg_only = bashmenu_ui.parse_color_val(self.fg_val) or "color(233)"
            txt.append(" Sample Text ", style=Style(color="white", bgcolor=bg_only, bold=True))
            txt.append(f"  Selected: {self.fg_val}{const_str} (Parsed: {bg_only})")
        else:
            txt.append(" Sample Text ", style=Style(color=parsed_fg, bgcolor=parsed_bg, bold=True))
            layer_label = "FOREGROUND" if self.active_tab == "fg" else "BACKGROUND"
            txt.append(f"  [{layer_label}] Code: {curr_code}{const_str} | FG: {self.fg_val}  BG: {self.bg_val}")

        p_bar.update(txt)

    def on_color_grid_widget_color_highlighted(self, event: ColorGridWidget.ColorHighlighted) -> None:
        code = event.color_code
        if self.active_tab == "fg":
            self.fg_val = code
        else:
            self.bg_val = code

        self._sync_tabs_ui()
        self._update_preview()

    def on_color_grid_widget_color_selected(self, event: ColorGridWidget.ColorSelected) -> None:
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if not btn_id:
            return

        if btn_id == "btn_tab_fg":
            self.action_select_fg_tab()
        elif btn_id == "btn_tab_bg":
            self.action_select_bg_tab()
        elif btn_id == "btn_select":
            self._confirm()
        elif btn_id == "btn_inherit":
            self.action_inherit()
        elif btn_id == "btn_cancel":
            self.dismiss(None)
        elif btn_id.startswith("swatch_"):
            swatch_name = btn_id.replace("swatch_", "")
            if swatch_name == "inherit":
                self.action_inherit()
            else:
                code = STANDARD_CONST_MAP.get(swatch_name, 0)
                grid = self.query_one("#color_grid", ColorGridWidget)
                grid.set_code(code, notify=False)
                grid.focus()
                if self.active_tab == "fg":
                    self.fg_val = swatch_name
                else:
                    self.bg_val = swatch_name
                self._sync_tabs_ui()
                self._update_preview()

    def action_switch_layer(self) -> None:
        if not self.is_pair:
            return
        if self.active_tab == "fg":
            self.action_select_bg_tab()
        else:
            self.action_select_fg_tab()

    def action_select_fg_tab(self) -> None:
        self.active_tab = "fg"
        grid = self.query_one("#color_grid", ColorGridWidget)
        c = self._val_to_code(self.fg_val)
        if c != -1:
            grid.cursor_code = c
            grid.refresh()
        grid.focus()
        self._sync_tabs_ui()
        self._update_preview()

    def action_select_bg_tab(self) -> None:
        if not self.is_pair:
            return
        self.active_tab = "bg"
        grid = self.query_one("#color_grid", ColorGridWidget)
        c = self._val_to_code(self.bg_val)
        if c != -1:
            grid.cursor_code = c
            grid.refresh()
        grid.focus()
        self._sync_tabs_ui()
        self._update_preview()

    def action_inherit(self) -> None:
        if self.active_tab == "fg":
            self.fg_val = -1
        else:
            self.bg_val = -1
        grid = self.query_one("#color_grid", ColorGridWidget)
        grid.focus()
        self._sync_tabs_ui()
        self._update_preview()

    def action_confirm_selection(self) -> None:
        self._confirm()

    def _confirm(self) -> None:
        if self.is_pair:
            self.dismiss([self.fg_val, self.bg_val])
        else:
            self.dismiss(self.fg_val)

    def on_click(self, event: Any) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AsciiGridWidget(Widget):
    """Interactive 16x16 2D CP437 ASCII character grid with keyboard navigation."""

    can_focus = True

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("left", "cursor_left", "Left", show=False),
        Binding("right", "cursor_right", "Right", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("home", "cursor_home", "Home", show=False),
        Binding("end", "cursor_end", "End", show=False),
        Binding("pageup", "cursor_page_up", "Page Up", show=False),
        Binding("pagedown", "cursor_page_down", "Page Down", show=False),
        Binding("enter", "select_glyph", "Select", show=False),
    ]

    class GlyphHighlighted(Message):
        """Emitted when highlighted character index changes."""

        def __init__(self, code: int, glyph: str) -> None:
            super().__init__()
            self.code = code
            self.glyph = glyph

    class GlyphSelected(Message):
        """Emitted when Enter is pressed on a glyph."""

        def __init__(self, code: int, glyph: str) -> None:
            super().__init__()
            self.code = code
            self.glyph = glyph

    def __init__(self, initial_code: int = 196, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cursor_code = max(0, min(255, initial_code))

    def render(self) -> Text:
        grid_text = Text()
        for row in range(16):
            for col in range(16):
                code = row * 16 + col
                glyph = get_cp437_glyph(code)
                is_sel = (code == self.cursor_code)
                cell_str = f" {glyph}  "

                if is_sel:
                    style = Style(color="color(255)", bgcolor="color(237)", bold=True, underline=True)
                else:
                    if 128 <= code <= 255:
                        style = Style(color="color(231)")
                    elif 32 <= code <= 126:
                        style = Style(color="color(250)")
                    else:
                        style = Style(color="color(243)")

                grid_text.append(cell_str, style=style)
            if row < 15:
                grid_text.append("\n")

        return grid_text

    def set_code(self, code: int, notify: bool = True) -> None:
        """Update cursor code and refresh visual display."""
        if 0 <= code <= 255:
            self.cursor_code = code
            self.refresh()
            if notify:
                self.post_message(self.GlyphHighlighted(self.cursor_code, get_cp437_glyph(self.cursor_code)))

    def on_click(self, event: Any) -> None:
        x = getattr(event, "x", 0)
        y = getattr(event, "y", 0)
        col = x // 4
        row = y
        if 0 <= col < 16 and 0 <= row < 16:
            code = row * 16 + col
            self.set_code(code)

    def action_cursor_left(self) -> None:
        self.set_code((self.cursor_code - 1) % 256)

    def action_cursor_right(self) -> None:
        self.set_code((self.cursor_code + 1) % 256)

    def action_cursor_up(self) -> None:
        self.set_code((self.cursor_code - 16) % 256)

    def action_cursor_down(self) -> None:
        self.set_code((self.cursor_code + 16) % 256)

    def action_cursor_home(self) -> None:
        self.set_code(0)

    def action_cursor_end(self) -> None:
        self.set_code(255)

    def action_cursor_page_up(self) -> None:
        self.set_code((self.cursor_code - 64) % 256)

    def action_cursor_page_down(self) -> None:
        self.set_code((self.cursor_code + 64) % 256)

    def action_select_glyph(self) -> None:
        self.post_message(self.GlyphSelected(self.cursor_code, get_cp437_glyph(self.cursor_code)))


QUICK_BORDER_SINGLE: list[tuple[str, int]] = [
    ("─", 196),
    ("│", 179),
    ("┌", 218),
    ("┐", 191),
    ("└", 192),
    ("┘", 217),
    ("├", 195),
    ("┤", 180),
    ("┬", 194),
    ("┴", 193),
    ("┼", 197),
]

QUICK_BORDER_DOUBLE: list[tuple[str, int]] = [
    ("═", 205),
    ("║", 186),
    ("╔", 201),
    ("╗", 187),
    ("╚", 200),
    ("╝", 188),
    ("╠", 204),
    ("╣", 185),
    ("╦", 203),
    ("╩", 202),
    ("╬", 206),
]

QUICK_BORDER_MIXED: list[tuple[str, int]] = [
    ("╒", 213),
    ("╕", 184),
    ("╘", 212),
    ("╛", 190),
    ("╓", 214),
    ("╖", 183),
    ("╙", 211),
    ("╜", 189),
    ("╞", 198),
    ("╡", 181),
    ("╤", 209),
    ("╧", 207),
    ("╪", 216),
    ("╟", 199),
    ("╢", 182),
    ("╥", 210),
    ("╨", 208),
    ("╫", 215),
]

QUICK_BORDER_SHADES: list[tuple[str, int]] = [
    ("░", 176),
    ("▒", 177),
    ("▓", 178),
]

QUICK_BORDER_BLOCKS: list[tuple[str, int]] = [
    ("█", 219),
    ("▄", 220),
    ("▌", 221),
    ("▐", 222),
    ("▀", 223),
]

QUICK_BORDER_SWATCHES: list[tuple[str, int]] = (
    QUICK_BORDER_SINGLE
    + QUICK_BORDER_DOUBLE
    + QUICK_BORDER_MIXED
    + QUICK_BORDER_SHADES
    + QUICK_BORDER_BLOCKS
)


class AsciiPickerModal(ModalScreen[str]):
    """Interactive 2D CP437 ASCII character and box-drawing glyph picker modal."""

    DEFAULT_CSS = """
    AsciiPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    #dialog {
        width: 78;
        height: 27;
        border: thick #555;
        background: #181818;
        padding: 0 1;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 0;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #eee;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        background: #333;
        color: #fff;
    }
    #grid_container {
        height: 16;
        width: 100%;
        align: center middle;
    }
    AsciiGridWidget {
        width: 64;
        height: 16;
    }
    AsciiGridWidget:focus {
        border: none;
    }
    #preview_bar {
        height: 1;
        width: 100%;
        margin-top: 0;
        text-align: center;
    }
    #swatches_container {
        height: 3;
        width: 100%;
        margin-top: 0;
        padding: 0 1;
    }
    .swatch_row {
        height: 1;
        width: 100%;
        align: left middle;
    }
    .swatch_lbl {
        color: #888;
        width: 8;
    }
    .swatch_lbl_sec {
        margin-left: 0;
    }
    .btn_swatch {
        height: 1;
        min-width: 3;
        padding: 0;
        margin: 0;
        border: none !important;
        background: #252525;
        color: #ccc;
    }
    .btn_swatch:hover {
        text-style: underline bold;
        color: #fff;
    }
    .btn_swatch:focus {
        text-style: underline bold reverse;
    }
    #btn_row {
        height: 3;
        margin-top: 0;
        align: center middle;
    }
    #btn_row Button {
        height: 3;
        min-width: 16;
        margin: 0 1;
    }
    #btn_row Button:focus {
        border: heavy #fff;
        text-style: bold;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm_selection", "Select"),
    ]

    def __init__(self, property_name: str, current_char: str, theme_styles: dict | None = None) -> None:
        super().__init__()
        self.property_name = property_name
        self.current_char = current_char
        self.theme_styles = theme_styles or {}

    def _parse_initial_code(self, val: str) -> int:
        if not val:
            return 196
        v = str(val).strip()
        m = re.search(r"\{ascii:\s*(\d+)", v, re.IGNORECASE)
        if m:
            with contextlib.suppress(Exception):
                return int(m.group(1)) % 256
        if v in UNICODE_TO_CP437:
            return UNICODE_TO_CP437[v]
        if len(v) == 1:
            try:
                b = v.encode("cp437")
                return b[0]
            except (UnicodeEncodeError, ValueError, OverflowError):
                return ord(v[0]) % 256
        return 196

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(f"ASCII / Character Picker: [{self.property_name}]", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(self.theme_styles),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )

                    with Horizontal(id="grid_container"):
                        init_code = self._parse_initial_code(self.current_char)
                        yield AsciiGridWidget(initial_code=init_code, id="ascii_grid")

                    yield Static(id="preview_bar")

                    with Vertical(id="swatches_container"):
                        with Horizontal(classes="swatch_row"):
                            yield Label("Single: ", classes="swatch_lbl")
                            for g, c in QUICK_BORDER_SINGLE:
                                yield Button(g, id=f"swatch_ascii_{c}", classes="btn_swatch")
                            yield Label("Shades: ", classes="swatch_lbl swatch_lbl_sec")
                            for g, c in QUICK_BORDER_SHADES:
                                yield Button(g, id=f"swatch_ascii_{c}", classes="btn_swatch")

                        with Horizontal(classes="swatch_row"):
                            yield Label("Double: ", classes="swatch_lbl")
                            for g, c in QUICK_BORDER_DOUBLE:
                                yield Button(g, id=f"swatch_ascii_{c}", classes="btn_swatch")
                            yield Label("Blocks: ", classes="swatch_lbl swatch_lbl_sec")
                            for g, c in QUICK_BORDER_BLOCKS:
                                yield Button(g, id=f"swatch_ascii_{c}", classes="btn_swatch")

                        with Horizontal(classes="swatch_row"):
                            yield Label("Mixed:  ", classes="swatch_lbl")
                            for g, c in QUICK_BORDER_MIXED:
                                yield Button(g, id=f"swatch_ascii_{c}", classes="btn_swatch")

                    with Horizontal(id="btn_row"):
                        yield Button("Select (Enter)", variant="primary", id="btn_select")
                        yield Button("Select Macro", variant="default", id="btn_select_macro")
                        yield Button("Cancel (Esc)", variant="error", id="btn_cancel")

                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        ts = self.theme_styles or getattr(self.app, "theme_styles", None) or bashmenu_ui.init_theme_colors()
        self.theme_styles = ts
        bashmenu_ui.apply_modal_theme(self, ts)
        with contextlib.suppress(Exception):
            btn_close = self.query_one("#btn_close_x", Label)
            btn_close.update(bashmenu_ui.format_close_button_label(ts))

        btn_prim = ts.get("button_primary") or ts.get("selection")
        if btn_prim:
            css_p_bg = bashmenu_ui.parse_css_color(btn_prim.bgcolor.name) if btn_prim.bgcolor else None
            css_p_fg = bashmenu_ui.parse_css_color(btn_prim.color.name) if btn_prim.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_select")
                if css_p_bg:
                    b.styles.background = css_p_bg
                if css_p_fg:
                    b.styles.color = css_p_fg

        btn_err = ts.get("button_error") or ts.get("button_cancel")
        if btn_err:
            css_e_bg = bashmenu_ui.parse_css_color(btn_err.bgcolor.name) if btn_err.bgcolor else None
            css_e_fg = bashmenu_ui.parse_css_color(btn_err.color.name) if btn_err.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_cancel")
                if css_e_bg:
                    b.styles.background = css_e_bg
                if css_e_fg:
                    b.styles.color = css_e_fg

        self._update_preview()
        with contextlib.suppress(Exception):
            self.query_one("#ascii_grid", AsciiGridWidget).focus()

    def _update_preview(self) -> None:
        p_bar = self.query_one("#preview_bar", Static)
        grid = self.query_one("#ascii_grid", AsciiGridWidget)
        code = grid.cursor_code
        glyph = get_cp437_glyph(code)

        txt = Text()
        txt.append(f" Character: '{glyph}' ", style=Style(color="white", bold=True))
        txt.append(f" (ASCII: {code} -> {{ascii:{code}}})  Hex: 0x{code:02X}")
        p_bar.update(txt)

    def on_ascii_grid_widget_glyph_highlighted(self, event: AsciiGridWidget.GlyphHighlighted) -> None:
        self._update_preview()

    def on_ascii_grid_widget_glyph_selected(self, event: AsciiGridWidget.GlyphSelected) -> None:
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if not btn_id:
            return

        if btn_id == "btn_select":
            self._confirm()
        elif btn_id == "btn_select_macro":
            self._confirm(as_macro=True)
        elif btn_id == "btn_cancel":
            self.dismiss(None)
        elif btn_id.startswith("swatch_ascii_"):
            code_str = btn_id.replace("swatch_ascii_", "")
            with contextlib.suppress(ValueError):
                code = int(code_str)
                grid = self.query_one("#ascii_grid", AsciiGridWidget)
                grid.set_code(code)
                grid.focus()
                self._update_preview()

    def action_confirm_selection(self) -> None:
        self._confirm()

    def _confirm(self, as_macro: bool = False) -> None:
        grid = self.query_one("#ascii_grid", AsciiGridWidget)
        code = grid.cursor_code
        if as_macro or str(self.current_char).strip().startswith("{ascii:"):
            self.dismiss(f"{{ascii:{code}}}")
        else:
            self.dismiss(get_cp437_glyph(code))

    def on_click(self, event: Any) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SaveThemeModal(ModalScreen[tuple[str, bool] | None]):
    """Modal for naming and confirming theme save."""

    DEFAULT_CSS = """
    SaveThemeModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    #dialog {
        width: 60;
        height: 20;
        border: thick #555;
        background: #181818;
        padding: 1 2;
    }
    #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 1;
    }
    #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #eee;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        background: #333;
        color: #fff;
    }
    #input_theme_name {
        margin: 1 0;
    }
    #chk_active {
        margin: 1 0;
    }
    #btn_row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    #btn_row Button {
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_name: str, theme_styles: dict | None = None):
        super().__init__()
        self.current_name = "" if current_name == "untitled" else current_name
        self.theme_styles = theme_styles or {}

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label("Save Theme to Disk", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(self.theme_styles),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )
                    yield Label("Theme Identifier / Name (lowercase slug):")
                    yield Input(value=self.current_name, id="input_theme_name", placeholder="e.g. my_cyber_theme")
                    yield Checkbox("Set as active theme in bashmenu.yml", value=True, id="chk_active")
                    with Horizontal(id="btn_row"):
                        yield Button("Save", variant="primary", id="btn_save")
                        yield Button("Cancel", variant="error", id="btn_cancel")
                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        ts = self.theme_styles or getattr(self.app, "theme_styles", None) or bashmenu_ui.init_theme_colors()
        self.theme_styles = ts
        bashmenu_ui.apply_modal_theme(self, ts)
        with contextlib.suppress(Exception):
            btn_close = self.query_one("#btn_close_x", Label)
            btn_close.update(bashmenu_ui.format_close_button_label(ts))
        btn_prim = ts.get("button_primary") or ts.get("selection")
        if btn_prim:
            css_p_bg = bashmenu_ui.parse_css_color(btn_prim.bgcolor.name) if btn_prim.bgcolor else None
            css_p_fg = bashmenu_ui.parse_css_color(btn_prim.color.name) if btn_prim.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_save")
                if css_p_bg:
                    b.styles.background = css_p_bg
                if css_p_fg:
                    b.styles.color = css_p_fg
        btn_err = ts.get("button_error") or ts.get("button_cancel")
        if btn_err:
            css_e_bg = bashmenu_ui.parse_css_color(btn_err.bgcolor.name) if btn_err.bgcolor else None
            css_e_fg = bashmenu_ui.parse_css_color(btn_err.color.name) if btn_err.color else None
            with contextlib.suppress(Exception):
                b = self.query_one("#btn_cancel")
                if css_e_bg:
                    b.styles.background = css_e_bg
                if css_e_fg:
                    b.styles.color = css_e_fg

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            inp = self.query_one("#input_theme_name", Input)
            chk = self.query_one("#chk_active", Checkbox)
            name = inp.value.strip().lower().replace(" ", "_")
            if name:
                self.dismiss((name, chk.value))
            else:
                self.dismiss(None)
        elif event.button.id == "btn_cancel":
            self.dismiss(None)

    def on_click(self, event: Any) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ==============================================================================
# BACKGROUND / WALLPAPER CONFIGURATION MODAL SCREEN
# ==============================================================================


class BackgroundConfigModal(ModalScreen[dict | None]):
    """Interactive modal dialog for configuring wallpaper image and background parameters."""

    DEFAULT_CSS = """
    BackgroundConfigModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    BackgroundConfigModal #dialog {
        width: 76;
        height: 28;
        border: thick #555;
        background: #181818;
        padding: 0 1;
    }
    BackgroundConfigModal #title_bar {
        height: 1;
        width: 100%;
        margin-bottom: 0;
    }
    BackgroundConfigModal #title {
        width: 1fr;
        text-align: center;
        text-style: bold;
        color: #eee;
    }
    BackgroundConfigModal .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    BackgroundConfigModal .btn_close_x:hover {
        background: #333;
        color: #fff;
    }
    BackgroundConfigModal .field_label {
        color: #aaa;
        height: 1;
        margin-top: 1;
    }
    BackgroundConfigModal .field_row {
        height: 1;
        width: 100%;
        margin-bottom: 0;
    }
    BackgroundConfigModal .field_row Input {
        width: 1fr;
        height: 1;
        padding: 0 1;
        border: none;
        background: #252525;
        color: #fff;
    }
    BackgroundConfigModal .field_row Button {
        height: 1;
        min-width: 12;
        margin-left: 1;
        padding: 0 1;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        border-left: none !important;
        border-right: none !important;
    }
    BackgroundConfigModal #btn_browse_bg {
        height: 1;
        min-width: 12;
        margin-left: 1;
        padding: 0 1;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        border-left: none !important;
        border-right: none !important;
        background: #0178d4;
        color: #ffffff;
    }
    BackgroundConfigModal #btn_browse_bg:hover {
        background: #0288d1;
        color: #ffffff;
        text-style: bold underline;
    }
    BackgroundConfigModal #btn_browse_bg:focus {
        background: #0288d1;
        color: #ffffff;
        text-style: bold reverse;
    }
    BackgroundConfigModal .split_row {
        height: 3;
        width: 100%;
        margin-top: 0;
    }
    BackgroundConfigModal .split_col {
        width: 1fr;
        height: 100%;
    }
    BackgroundConfigModal .split_col_left {
        margin-right: 1;
    }
    BackgroundConfigModal .split_col_right {
        margin-left: 1;
    }
    BackgroundConfigModal .split_col Input {
        height: 1;
        padding: 0 1;
        border: none;
        background: #252525;
        color: #fff;
    }
    BackgroundConfigModal .split_col Select {
        height: 1;
        border: none;
        background: #252525;
        color: #fff;
    }
    BackgroundConfigModal .split_col Select > SelectCurrent {
        height: 1;
        border: none !important;
        padding: 0 1;
        background: #252525;
        color: #fff;
    }
    BackgroundConfigModal #btn_row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    BackgroundConfigModal #btn_row Button {
        height: 3;
        min-width: 16;
        margin: 0 1;
    }
    BackgroundConfigModal #btn_row Button:focus {
        border: heavy #fff;
        text-style: bold;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
    ]

    def __init__(
        self,
        current_background: dict | str | None = None,
        theme_styles: dict | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.theme_styles = theme_styles or {}
        if isinstance(current_background, dict):
            self.bg_cfg = copy.deepcopy(current_background)
        elif isinstance(current_background, str):
            self.bg_cfg = {"image": current_background}
        else:
            self.bg_cfg = {}

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label("Configure Background Wallpaper", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(self.theme_styles),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )

                    curr_img = str(self.bg_cfg.get("image", ""))
                    curr_op = str(self.bg_cfg.get("opacity", 0.85))
                    curr_sc = str(self.bg_cfg.get("scaling", "cover"))
                    curr_md = str(self.bg_cfg.get("mode", "halfblock"))
                    curr_cl = str(self.bg_cfg.get("clustering", 0))
                    curr_qu = str(self.bg_cfg.get("quantization", 1))

                    scaling_options = [
                        ("cover (fill window)", "cover"),
                        ("stretch (exact fit)", "stretch"),
                        ("fit (proportional)", "fit"),
                        ("center (original size)", "center"),
                        ("tile (repeat pattern)", "tile"),
                    ]
                    mode_options = [
                        ("halfblock (▀▄ dual-pixel)", "halfblock"),
                        ("quarterblock (▖▗ quad-pixel)", "quarterblock"),
                    ]

                    valid_scaling = [val for _, val in scaling_options]
                    valid_modes = [val for _, val in mode_options]

                    yield Label("Wallpaper Image File:", classes="field_label")
                    with Horizontal(classes="field_row"):
                        yield Input(
                            value=curr_img,
                            placeholder="e.g. assets/wallpapers/twilight.png",
                            id="input_bg_image",
                        )
                        yield Button("Browse...", id="btn_browse_bg", variant="default")

                    with Horizontal(classes="split_row"):
                        with Vertical(classes="split_col split_col_left"):
                            yield Label("Opacity (0.0 to 1.0):", classes="field_label")
                            yield Input(value=curr_op, id="input_bg_opacity", placeholder="0.85")
                        with Vertical(classes="split_col split_col_right"):
                            yield Label("Scaling Mode:", classes="field_label")
                            yield Select[str](
                                options=scaling_options,
                                value=curr_sc if curr_sc in valid_scaling else "cover",
                                id="select_bg_scaling",
                                allow_blank=False,
                            )

                    with Horizontal(classes="split_row"):
                        with Vertical(classes="split_col split_col_left"):
                            yield Label("Rendering Mode:", classes="field_label")
                            yield Select[str](
                                options=mode_options,
                                value=curr_md if curr_md in valid_modes else "halfblock",
                                id="select_bg_mode",
                                allow_blank=False,
                            )
                        with Vertical(classes="split_col split_col_right"):
                            yield Label("Clustering (0=none, 16-128):", classes="field_label")
                            yield Input(value=curr_cl, id="input_bg_clustering", placeholder="0")

                    yield Label("Palette Quantization (1=off, 16-256):", classes="field_label")
                    with Horizontal(classes="field_row"):
                        yield Input(value=curr_qu, id="input_bg_quantization", placeholder="1")

                    with Horizontal(id="btn_row"):
                        yield Button("Apply", variant="primary", id="btn_apply_bg")
                        yield Button("Remove Wallpaper", variant="error", id="btn_remove_bg")
                        yield Button("Cancel", variant="default", id="btn_cancel_bg")

                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        ts = self.theme_styles or getattr(self.app, "theme_styles", None) or bashmenu_ui.init_theme_colors()
        self.theme_styles = ts
        bashmenu_ui.apply_modal_theme(self, ts)
        with contextlib.suppress(Exception):
            btn_close = self.query_one("#btn_close_x", Label)
            btn_close.update(bashmenu_ui.format_close_button_label(ts))
        border_style = ts.get("border") or ts.get("accent")
        if border_style and border_style.color and border_style.color.name:
            css_border = bashmenu_ui.parse_css_color(border_style.color.name)
            if css_border:
                with contextlib.suppress(Exception):
                    self.query_one("#dialog").styles.border = ("thick", css_border)

        btn_prim = ts.get("button_primary") or ts.get("selection")
        if btn_prim:
            css_p_bg = bashmenu_ui.parse_css_color(btn_prim.bgcolor.name) if btn_prim.bgcolor else None
            css_p_fg = bashmenu_ui.parse_css_color(btn_prim.color.name) if btn_prim.color else None
            with contextlib.suppress(Exception):
                for b_id in ["#btn_browse_bg", "#btn_apply_bg"]:
                    b = self.query_one(b_id)
                    if css_p_bg:
                        b.styles.background = css_p_bg
                    if css_p_fg:
                        b.styles.color = css_p_fg

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn_browse_bg":
            start_dir = os.path.join(bashmenu.BASHMENU_DIR, "assets", "wallpapers")
            if not os.path.isdir(start_dir):
                start_dir = os.path.join(os.getcwd(), "assets", "wallpapers")
            if not os.path.isdir(start_dir):
                start_dir = os.getcwd()

            def _on_file_picked(picked_file: str | None) -> None:
                if picked_file:
                    with contextlib.suppress(Exception):
                        rel = os.path.relpath(picked_file, bashmenu.BASHMENU_DIR)
                        if not rel.startswith(".."):
                            picked_file = rel
                    with contextlib.suppress(Exception):
                        inp = self.query_one("#input_bg_image", Input)
                        inp.value = picked_file
                        inp.focus()

            self.app.push_screen(
                bashmenu_ui.FilePickerModalScreen(
                    "Choose Wallpaper Image",
                    start_dir=start_dir,
                    mode="file",
                    theme=self.theme_styles,
                ),
                _on_file_picked,
            )
        elif btn_id == "btn_apply_bg":
            self.action_apply()
        elif btn_id == "btn_remove_bg":
            self.dismiss({})
        elif btn_id == "btn_cancel_bg":
            self.dismiss(None)

    def on_click(self, event: Any) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_apply(self) -> None:
        img_val = self.query_one("#input_bg_image", Input).value.strip()
        if not img_val:
            self.dismiss({})
            return

        opacity_str = self.query_one("#input_bg_opacity", Input).value.strip()
        try:
            opacity_val = max(0.0, min(1.0, float(opacity_str)))
        except ValueError:
            opacity_val = 0.85

        scaling_sel = self.query_one("#select_bg_scaling", Select)
        scaling_val = str(scaling_sel.value) if scaling_sel.value and scaling_sel.value != Select.BLANK else "cover"

        mode_sel = self.query_one("#select_bg_mode", Select)
        mode_val = str(mode_sel.value) if mode_sel.value and mode_sel.value != Select.BLANK else "halfblock"

        clustering_str = self.query_one("#input_bg_clustering", Input).value.strip()
        try:
            clustering_val = max(0, int(clustering_str))
        except ValueError:
            clustering_val = 0

        quantization_str = self.query_one("#input_bg_quantization", Input).value.strip()
        try:
            quantization_val = max(1, int(quantization_str))
        except ValueError:
            quantization_val = 1

        cfg_dict: dict[str, Any] = {
            "image": img_val,
            "opacity": opacity_val,
            "scaling": scaling_val,
            "mode": mode_val,
        }
        if clustering_val > 0:
            cfg_dict["clustering"] = clustering_val
        if quantization_val > 1:
            cfg_dict["quantization"] = quantization_val

        self.dismiss(cfg_dict)


# ==============================================================================
# LIVE PREVIEW CANVAS WIDGET
# ==============================================================================


class ThemePreviewWidget(Static):
    """Simulated miniature live preview of BashMenu rendering the active theme."""

    class ElementClicked(Message):
        """Emitted when an interface element in the preview is clicked."""

        def __init__(self, primary: str, secondary: str = "") -> None:
            super().__init__()
            self.primary = primary
            self.secondary = secondary

    def __init__(self, theme_dict: dict, theme_name: str = "custom", **kwargs):
        super().__init__(**kwargs)
        self.theme_dict = theme_dict
        self.theme_name = theme_name
        self._hit_map: dict[tuple[int, int], tuple[str, str]] = {}
        self._last_w = 56
        self._last_h = 12
        self._flash_range: tuple[int, int, int] | None = None
        self._flash_timer = None

    def _clear_flash(self) -> None:
        """Clear active flash inversion and restore normal appearance."""
        self._flash_range = None
        self._flash_timer = None
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        """Handle mouse click on preview element, flash clicked item, and emit ElementClicked message."""
        pos = (event.x, event.y)
        hit = self._hit_map.get(pos)
        if not hit and (
            0 <= event.x < getattr(self, "_last_w", 56) + 3 and 0 <= event.y <= getattr(self, "_last_h", 12) + 5
        ):
            hit = ("color_background", "color_background")
        if hit:
            # Determine contiguous element range on this row for haptic visual feedback
            target_key = hit[0]
            ey = event.y
            x1 = event.x
            while x1 > 0 and self._hit_map.get((x1 - 1, ey), (None,))[0] == target_key:
                x1 -= 1
            x2 = event.x + 1
            while self._hit_map.get((x2, ey), (None,))[0] == target_key:
                x2 += 1

            self._flash_range = (ey, x1, x2)
            if getattr(self, "_flash_timer", None) is not None:
                with contextlib.suppress(Exception):
                    self._flash_timer.stop()
            self._flash_timer = self.set_timer(0.15, self._clear_flash)
            self.refresh()

            self.post_message(self.ElementClicked(primary=hit[0], secondary=hit[1]))

    def update_theme(self, theme_dict: dict, theme_name: str = "custom") -> None:
        """Update active theme definition and trigger instant re-render."""
        self.theme_dict = theme_dict
        self.theme_name = theme_name
        self._flash_range = None
        self.refresh()

    def render(self) -> Text:
        """Render complete simulated BashMenu frame with active borders and styles."""
        parent = getattr(self, "parent", None)
        if parent and getattr(parent, "size", None) and parent.size.width > 20 and parent.size.height > 10:
            inner_pw = max(40, parent.size.width - 3)
            inner_ph = max(12, parent.size.height - 2)
            w = max(38, inner_pw - 2)
            num_rows = inner_ph
        else:
            w = 56
            num_rows = 12

        self._hit_map.clear()
        self._last_w = w
        self._last_h = num_rows

        def set_hit_range(y_row: int, x_start: int, x_end: int, primary: str, secondary: str = "") -> None:
            sec = secondary or primary
            for x_col in range(max(0, x_start), min(w + 3, x_end)):
                self._hit_map[(x_col, y_row)] = (primary, sec)

        inner_w = w - 6  # Borders (2) + Margins (4)
        t_dict = dict(self.theme_dict)
        if 256 not in t_dict and "256" in t_dict:
            t_dict[256] = t_dict["256"]

        t_data = {self.theme_name: t_dict}
        styles = bashmenu_ui.init_theme_colors(self.theme_name, raw_theme_data=t_data)
        borders = bashmenu_ui.get_theme_window_borders(self.theme_name, raw_theme_data=t_data)

        b_style = styles.get("border", Style(color="blue"))
        t_style = styles.get("title", Style(color="magenta", bold=True))
        text_style = styles.get("text", Style(color="white"))
        sel_style = styles.get("selection", Style(color="white", bgcolor="blue"))
        key_style = styles.get("shortcut_key", Style(color="magenta", bold=True))
        div_style = styles.get("divider", Style(color="blue"))
        plug_style = styles.get("plugin", Style(color="cyan"))
        gutter_style = styles.get("gutter", Style(color="blue"))
        help_style = styles.get("help_text", Style(color="cyan"))
        shadow_style = styles.get("shadow", Style(color="black", dim=True))

        def _resolve(val: Any) -> str:
            if not val:
                return ""
            v = str(val)
            if "{" in v:
                v = bashmenu.interpolate_placeholders(v, self.theme_dict)
                v = bashmenu.resolve_glyph(v, {})
            return v.replace("\ufe0f", "").replace("\ufe0e", "")

        def _resolve_border_char(val: Any, fallback: str = " ") -> str:
            if not val:
                return fallback
            v = _resolve(val)
            if not v:
                return fallback
            if "{" in v:
                m = re.search(r"\{ascii:\s*(\d+)", v, re.IGNORECASE)
                if m:
                    try:
                        code = int(m.group(1))
                        v = bytes([code % 256]).decode("cp437", errors="replace")
                    except (ValueError, OverflowError):
                        v = fallback
                elif v.startswith("{") and v.endswith("}"):
                    return fallback
            if len(v) > 1:
                if v.startswith("{"):
                    return fallback
                return v[0]
            return v if v else fallback

        b_tl = _resolve_border_char(borders.get("border_top_left"), "┌")
        b_tr = _resolve_border_char(borders.get("border_top_right"), "┐")
        b_bl = _resolve_border_char(borders.get("border_bottom_left"), "└")
        b_br = _resolve_border_char(borders.get("border_bottom_right"), "┘")
        b_h_top = _resolve_border_char(borders.get("border_horizontal_top", borders.get("border_horizontal")), "─")
        b_h_bot = _resolve_border_char(borders.get("border_horizontal_bottom", borders.get("border_horizontal")), "─")
        b_v_left = _resolve_border_char(borders.get("border_vertical_left", borders.get("border_vertical")), "│")
        b_v_right = _resolve_border_char(borders.get("border_vertical_right", borders.get("border_vertical")), "│")
        b_tee_l = _resolve_border_char(borders.get("left_tee", borders.get("border_tee_left")), "├")
        b_tee_r = _resolve_border_char(borders.get("right_tee", borders.get("border_tee_right")), "┤")
        b_cap_l = _resolve_border_char(borders.get("title_left_cap"), "[")
        b_cap_r = _resolve_border_char(borders.get("title_right_cap"), "]")
        b_gt_border = _resolve_border_char(borders.get("gutter_border"), "─")
        b_gt_sep = _resolve_border_char(borders.get("gutter_separator"), "│")
        b_gt_l_tee = _resolve_border_char(borders.get("gutter_left_tee"), "├")
        b_gt_r_tee = _resolve_border_char(borders.get("gutter_right_tee"), "┤")
        b_gt_top_tee = _resolve_border_char(borders.get("gutter_top_tee"), "┬")
        b_gt_bot_tee = _resolve_border_char(borders.get("gutter_bottom_tee"), "┴")
        shadow_ch = _resolve_border_char(borders.get("shadow_char"), "░")

        ind_val = self.theme_dict.get("indicator", ">")
        indicator = _resolve(ind_val)
        if "{" in indicator:
            m = re.search(r"\{ascii:\s*(\d+)", indicator, re.IGNORECASE)
            if m:
                try:
                    code = int(m.group(1))
                    indicator = bytes([code % 256]).decode("cp437", errors="replace")
                except (ValueError, OverflowError):
                    indicator = ">"
            elif indicator.startswith("{") and indicator.endswith("}"):
                indicator = ">"
        if not indicator:
            indicator = ">"
        if len(indicator) > 2:
            indicator = indicator[0]

        divider_def = self.theme_dict.get("divider", {})
        if isinstance(divider_def, dict):
            div_char = _resolve_border_char(divider_def.get("char"), "─")
            div_len = str(divider_def.get("length", "{window_width}"))
        else:
            div_char = _resolve_border_char(divider_def, "─")
            div_len = "{window_width}"

        out = Text()

        # Row 0: Top Window Border with Title
        title_text = f" {b_cap_l} Bash Menu {b_cap_r} "
        remain_w = max(0, w - 2 - len(title_text))
        pad_l = remain_w // 2
        pad_r = remain_w - pad_l
        top_line = Text()
        top_line.append(b_tl + b_h_top * pad_l, style=b_style)
        top_line.append(title_text, style=t_style)
        top_line.append(b_h_top * pad_r + b_tr, style=b_style)
        lines: list[Text] = [top_line]

        set_hit_range(0, 0, 1, "prop_border_top_left", "color_border")
        set_hit_range(0, 1, 1 + pad_l, "color_border", "prop_border_horizontal")
        t_pos = 1 + pad_l
        set_hit_range(0, t_pos, t_pos + 1, "color_title", "color_title")
        t_pos += 1
        set_hit_range(0, t_pos, t_pos + len(b_cap_l), "prop_title_left_cap", "color_title")
        t_pos += len(b_cap_l)
        inner_title = " Bash Menu "
        set_hit_range(0, t_pos, t_pos + len(inner_title), "color_title", "prop_title_left_cap")
        t_pos += len(inner_title)
        set_hit_range(0, t_pos, t_pos + len(b_cap_r), "prop_title_right_cap", "color_title")
        t_pos += len(b_cap_r)
        set_hit_range(0, t_pos, 1 + pad_l + len(title_text), "color_title", "color_title")
        set_hit_range(0, 1 + pad_l + len(title_text), w - 1, "color_border", "prop_border_horizontal")
        set_hit_range(0, w - 1, w, "prop_border_top_right", "color_border")

        # Helper to wrap inner rows with window borders
        def wrap_line(inner_text: Text) -> Text:
            line = Text()
            line.append(b_v_left + "  ", style=b_style)
            curr_inner = inner_text.copy()
            if curr_inner.cell_len > inner_w:
                curr_inner.truncate(inner_w)
            line.append_text(curr_inner)
            rem = max(0, inner_w - curr_inner.cell_len)
            if rem > 0:
                line.append(" " * rem, style=text_style)
            line.append("  " + b_v_right, style=b_style)
            line.append(shadow_ch * 2, style=shadow_style)
            return line

        def make_opt_line(num: int, label: str, is_sel: bool) -> tuple[Text, tuple]:
            if is_sel:
                r = Text()
                r.append(f"  {indicator} [{num}] {label}", style=sel_style)
                if r.cell_len > inner_w:
                    r.truncate(inner_w)
                rem_sel = max(0, inner_w - r.cell_len)
                if rem_sel > 0:
                    r.append(" " * rem_sel, style=sel_style)
                line = Text()
                line.append(b_v_left + "  ", style=b_style)
                line.append_text(r)
                line.append("  " + b_v_right, style=b_style)
                line.append(shadow_ch * 2, style=shadow_style)
                return line, ("opt", num, label, True)
            else:
                r = Text()
                r.append(f"    [{num}] ", style=key_style)
                r.append(label, style=text_style)
                return wrap_line(r), ("opt", num, label, False)

        def make_div_line() -> tuple[Text, tuple]:
            if "{screen_width}" in div_len:
                div_row = Text()
                div_row.append(b_tee_l + div_char * (w - 2) + b_tee_r, style=div_style)
                div_row.append(shadow_ch * 2, style=shadow_style)
                return div_row, ("div", True)
            else:
                r_div = Text()
                r_div.append(div_char * inner_w, style=div_style)
                return wrap_line(r_div), ("div", False)

        pl_box_w = max(24, inner_w - 6)
        title_pl = " Weather Dashboard "
        dash_len = max(0, pl_box_w - 3 - len(title_pl))
        r_pl_h = wrap_line(Text(f"┌─{title_pl}" + "─" * dash_len + "┐", style=plug_style))
        r_pl_c1 = wrap_line(
            Text(
                "│ 72°F Sunny • Orion Up 3d"
                + " " * max(0, pl_box_w - 2 - len(" 72°F Sunny • Orion Up 3d"))
                + "│",
                style=plug_style,
            )
        )
        r_pl_c2 = wrap_line(
            Text(
                "│ Humidity 45% • Wind 5mph"
                + " " * max(0, pl_box_w - 2 - len(" Humidity 45% • Wind 5mph"))
                + "│",
                style=plug_style,
            )
        )
        r_pl_b = wrap_line(Text("└" + "─" * (pl_box_w - 2) + "┘", style=plug_style))

        pl_h_item = (r_pl_h, ("pl", pl_box_w))
        pl_c1_item = (r_pl_c1, ("pl", pl_box_w))
        pl_c2_item = (r_pl_c2, ("pl", pl_box_w))
        pl_b_item = (r_pl_b, ("pl", pl_box_w))
        empty_item = (wrap_line(Text("", style=text_style)), ("empty",))

        raw_options = [
            (1, "Web Applications", False),
            (2, "System Utilities", True),
            (3, "Administration Tools", False),
            (4, "Network Diagnostics", False),
            (5, "Theme Settings", False),
            (6, "Security & Firewall", False),
            (7, "Development Tools", False),
            (8, "Backup & Storage", False),
            (9, "Exit to Shell", False),
        ]

        body_slots = num_rows - 5
        if body_slots <= 7:
            min_items = [
                make_opt_line(1, "Web Applications", False),
                make_opt_line(2, "System Utilities", True),
                make_div_line(),
                make_opt_line(3, "Theme Settings", False),
                pl_h_item,
                pl_c1_item,
                pl_b_item,
            ]
            body_items = min_items[:body_slots]
            while len(body_items) < body_slots:
                body_items.append(empty_item)
        else:
            use_c2 = body_slots >= 11
            pl_lines = [pl_h_item, pl_c1_item] + ([pl_c2_item] if use_c2 else []) + [pl_b_item]
            rem_slots = body_slots - len(pl_lines)
            n_opts = max(1, rem_slots - 1)
            opts = raw_options[:min(n_opts, len(raw_options))]
            body_items = []
            div_placed = False
            for idx, (num, label, is_sel) in enumerate(opts):
                if idx == min(2, len(opts) - 1) and not div_placed:
                    body_items.append(make_div_line())
                    div_placed = True
                body_items.append(make_opt_line(num, label, is_sel))
            if not div_placed:
                body_items.insert(min(2, len(body_items)), make_div_line())
            while len(body_items) + len(pl_lines) < body_slots:
                body_items.append(empty_item)
            body_items.extend(pl_lines)

        for idx, (line_item, meta) in enumerate(body_items):
            lines.append(line_item)
            y = 1 + idx
            kind = meta[0]
            if kind == "div" and meta[1]:  # Screen-width divider
                set_hit_range(y, 0, 1, "prop_left_tee", "color_divider")
                set_hit_range(y, 1, w - 1, "color_divider", "prop_divider_char")
                set_hit_range(y, w - 1, w, "prop_right_tee", "color_divider")
                set_hit_range(y, w, w + 2, "color_shadow", "prop_shadow_char")
            else:
                set_hit_range(y, 0, 1, "color_border", "prop_border_vertical")
                set_hit_range(y, 1, 3, "color_background", "color_border")
                set_hit_range(y, w - 3, w - 1, "color_background", "color_border")
                set_hit_range(y, w - 1, w, "color_border", "prop_border_vertical")
                set_hit_range(y, w, w + 2, "color_shadow", "prop_shadow_char")

                if kind == "opt":
                    num, label, is_sel = meta[1], meta[2], meta[3]
                    if is_sel:
                        set_hit_range(y, 3, 5, "color_selection", "color_highlight")
                        ind_len = len(indicator)
                        set_hit_range(y, 5, 5 + ind_len, "prop_indicator", "color_selection")
                        set_hit_range(y, 5 + ind_len, 6 + ind_len, "color_selection", "prop_indicator")
                        sc_start = 6 + ind_len
                        sc_str = f"[{num}]"
                        set_hit_range(y, sc_start, sc_start + len(sc_str), "color_shortcut_key", "color_selection")
                        set_hit_range(y, sc_start + len(sc_str), w - 3, "color_selection", "color_highlight")
                    else:
                        set_hit_range(y, 3, 7, "color_background", "color_text")
                        sc_str = f"[{num}]"
                        set_hit_range(y, 7, 7 + len(sc_str), "color_shortcut_key", "color_text")
                        lbl_start = 7 + len(sc_str) + 1
                        lbl_end = min(w - 3, lbl_start + len(label))
                        set_hit_range(y, lbl_start, lbl_end, "color_text", "color_shortcut_key")
                        set_hit_range(y, lbl_end, w - 3, "color_background", "color_text")
                elif kind == "div":
                    set_hit_range(y, 3, w - 3, "color_divider", "prop_divider_char")
                elif kind == "pl":
                    box_w = meta[1]
                    set_hit_range(y, 3, 3 + box_w, "color_plugin", "color_accent")
                    set_hit_range(y, 3 + box_w, w - 3, "color_background", "color_plugin")
                elif kind == "empty":
                    set_hit_range(y, 3, w - 3, "color_background", "color_text")

        # Gutter Top Border
        avail_both = max(4, w - 11)
        left_gw = max(23, int(avail_both * 0.55)) if w > 56 else 23
        right_gw = avail_both - left_gw
        sep_x = 3 + left_gw + 2
        rem_right = max(0, w - 2 - sep_x)

        gt_line = Text()
        gt_line.append(b_gt_l_tee + b_gt_border * (sep_x - 1), style=b_style)
        gt_line.append(b_gt_top_tee, style=b_style)
        gt_line.append(b_gt_border * rem_right + b_gt_r_tee, style=b_style)
        gt_line.append(shadow_ch * 2, style=shadow_style)
        lines.append(gt_line)

        y_gt = 1 + len(body_items)
        set_hit_range(y_gt, 0, 1, "prop_gutter_left_tee", "color_border")
        set_hit_range(y_gt, 1, sep_x, "prop_gutter_border", "color_gutter")
        set_hit_range(y_gt, sep_x, sep_x + 1, "prop_gutter_top_tee", "color_border")
        set_hit_range(y_gt, sep_x + 1, w - 1, "prop_gutter_border", "color_gutter")
        set_hit_range(y_gt, w - 1, w, "prop_gutter_right_tee", "color_border")
        set_hit_range(y_gt, w, w + 2, "color_shadow", "prop_shadow_char")

        # Gutter Content Row
        help_items = ["[F1] Help", "[F2] Themes"]
        if left_gw >= 38:
            help_items.append("[F4] Edit")
        if hasattr(bashmenu, "format_spread_gutter_line"):
            h_text = bashmenu.format_spread_gutter_line(help_items, left_gw)
        else:
            h_text = " | ".join(help_items)
        h_part = Text(h_text, style=help_style)
        if h_part.cell_len > left_gw:
            h_part.truncate(left_gw)
        h_pad = max(0, left_gw - h_part.cell_len)
        if h_pad > 0:
            h_part.append(" " * h_pad)

        if right_gw >= 24:
            s_text = f"Theme: {self.theme_name} | 12:45"
        else:
            s_text = f"{self.theme_name} | 12:45"
        s_part = Text(s_text, style=gutter_style)
        if s_part.cell_len > right_gw:
            s_part.truncate(right_gw)
        s_pad = max(0, right_gw - s_part.cell_len)
        status_cell = Text(" " * s_pad)
        status_cell.append_text(s_part)

        g_content = Text()
        g_content.append(b_v_left + "  ", style=b_style)
        g_content.append_text(h_part)
        g_content.append("  ", style=text_style)
        g_content.append(b_gt_sep[0] if b_gt_sep else "│", style=b_style)
        g_content.append("  ", style=text_style)
        g_content.append_text(status_cell)
        g_content.append("  " + b_v_right, style=b_style)
        g_content.append(shadow_ch * 2, style=shadow_style)
        lines.append(g_content)

        y_gc = y_gt + 1
        set_hit_range(y_gc, 0, 1, "color_border", "prop_border_vertical")
        set_hit_range(y_gc, 1, 3, "color_background", "color_border")
        set_hit_range(y_gc, 3, 3 + left_gw, "color_help_text", "color_gutter")
        set_hit_range(y_gc, 3 + left_gw, sep_x, "color_background", "color_gutter")
        set_hit_range(y_gc, sep_x, sep_x + 1, "prop_gutter_separator", "color_gutter")
        set_hit_range(y_gc, sep_x + 1, sep_x + 3, "color_background", "color_gutter")
        set_hit_range(y_gc, sep_x + 3, w - 3, "color_gutter", "color_help_text")
        set_hit_range(y_gc, w - 3, w - 1, "color_background", "color_border")
        set_hit_range(y_gc, w - 1, w, "color_border", "prop_border_vertical")
        set_hit_range(y_gc, w, w + 2, "color_shadow", "prop_shadow_char")

        # Bottom Border
        bot_line = Text()
        bot_line.append(b_bl + b_h_bot * (sep_x - 1), style=b_style)
        bot_line.append(b_gt_bot_tee, style=b_style)
        bot_line.append(b_h_bot * rem_right + b_br, style=b_style)
        bot_line.append(shadow_ch * 2, style=shadow_style)
        lines.append(bot_line)

        y_bot = y_gt + 2
        set_hit_range(y_bot, 0, 1, "prop_border_bottom_left", "color_border")
        set_hit_range(y_bot, 1, sep_x, "color_border", "prop_border_horizontal")
        set_hit_range(y_bot, sep_x, sep_x + 1, "prop_gutter_bottom_tee", "color_border")
        set_hit_range(y_bot, sep_x + 1, w - 1, "color_border", "prop_border_horizontal")
        set_hit_range(y_bot, w - 1, w, "prop_border_bottom_right", "color_border")
        set_hit_range(y_bot, w, w + 2, "color_shadow", "prop_shadow_char")

        # Bottom Drop Shadow
        bot_shadow = Text()
        bot_shadow.append("  " + shadow_ch * w, style=shadow_style)
        lines.append(bot_shadow)

        y_sh = y_gt + 3
        set_hit_range(y_sh, 2, 2 + w, "color_shadow", "prop_shadow_char")

        # Apply brief inverted colors to clicked item (haptic feedback)
        if getattr(self, "_flash_range", None):
            fy, fx1, fx2 = self._flash_range
            if 0 <= fy < len(lines):
                lines[fy].stylize(Style(reverse=True), fx1, fx2)

        out = Text()
        for idx, line in enumerate(lines):
            out.append_text(line)
            if idx < len(lines) - 1:
                out.append("\n")

        bg_spec = styles.get("theme_background")
        if isinstance(bg_spec, dict) and bg_spec.get("image"):
            img_path = str(bg_spec.get("image", "")).strip()
            if img_path:
                with contextlib.suppress(Exception):
                    opacity = float(bg_spec.get("opacity", 0.85))
                    scaling = str(bg_spec.get("scaling", "cover"))
                    clustering = int(bg_spec.get("clustering", 0) or 0)
                    quantization = int(bg_spec.get("quantization", 1) or 1)
                    cached_comp = getattr(self, "_wallpaper_compositor", None)
                    if (
                        cached_comp is not None
                        and getattr(cached_comp, "image_path", None) == img_path
                        and getattr(cached_comp, "opacity", None) == opacity
                        and getattr(cached_comp, "scaling", None) == scaling
                        and getattr(cached_comp, "clustering", None) == clustering
                        and getattr(cached_comp, "quantization", None) == quantization
                    ):
                        compositor = cached_comp
                    else:
                        compositor = bashmenu_ui.WallpaperCompositor(
                            img_path,
                            opacity=opacity,
                            scaling=scaling,
                            base_dir=bashmenu.BASHMENU_DIR,
                            clustering=clustering,
                            quantization=quantization,
                        )
                        self._wallpaper_compositor = compositor

                    if compositor and compositor._raw_image:
                        theme_bg_rgb = bashmenu_ui.get_theme_bg_rgb(styles)
                        grid = compositor.get_grid(w + 3, len(lines), theme_bg_rgb=theme_bg_rgb)
                        if grid:
                            out = bashmenu_ui.composite_menu_text(
                                out,
                                grid,
                                w + 3,
                                len(lines),
                                theme_default_bg=theme_bg_rgb,
                            )

        return out


# ==============================================================================
# MAIN THEME EDITOR SCREEN
# ==============================================================================


class ThemeEditScreen(Screen):
    """Interactive Split-Screen Theme Editor Screen."""

    DEFAULT_CSS = """
    ThemeEditScreen {
        layout: vertical;
        background: #121212;
    }
    #header {
        dock: top;
        height: 1;
        width: 100%;
        background: #242424;
        color: #eee;
    }
    #header_title {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    .btn_close_x {
        dock: right;
        width: 3;
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        min-width: 3;
        background: transparent;
    }
    .btn_close_x:hover {
        background: #3a3a3a;
        color: #fff;
    }
    #workspace {
        height: 1fr;
        width: 100%;
    }
    #preview_panel {
        width: 1fr;
        height: 100%;
        border: solid #444;
        padding: 0 0 0 1;
        overflow: hidden;
        align: left middle;
    }
    #inspector_panel {
        width: 1fr;
        height: 100%;
        border: solid #444;
        padding: 0 1;
        overflow-y: auto;
    }
    #inspector_panel > * {
        margin-right: 1;
    }
    .section_header {
        text-style: bold;
        color: #ddd;
        margin-top: 1;
        margin-bottom: 0;
        background: #252525;
        padding: 0 1;
    }
    .prop_row {
        height: 3;
        width: 100%;
        align: left middle;
        margin-bottom: 0;
    }
    .prop_label {
        width: 16;
        text-style: bold;
        color: #ccc;
    }
    .prop_input {
        width: 1fr;
    }
    .btn_prop_action {
        width: 10;
        margin-left: 1;
    }
    #footer {
        dock: bottom;
        height: 2;
        background: #181818;
        color: #bbb;
    }
    .footer_row {
        height: 1;
        width: 100%;
        align: left middle;
    }
    .footer_item {
        padding: 0 0;
        color: #bbb;
    }
    .footer_item:hover {
        text-style: underline;
        color: #fff;
    }
    .footer_sep {
        padding: 0 0;
        color: #555;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("f1", "show_help", "Help"),
        Binding("question_mark", "show_help", "Help", show=False),
        Binding("f2", "configure_background", "Background"),
        Binding("f3", "pick_color", "Color Picker"),
        Binding("f4", "pick_ascii", "ASCII Picker"),
        Binding("f5", "reset_theme", "Reset"),
        Binding("f6", "clone_theme", "Clone Base"),
        Binding("f7", "derive_palettes", "Derive 16/8"),
        Binding("ctrl+s", "save_theme", "Save"),
        Binding("ctrl+a", "save_as_theme", "Save As"),
        Binding("escape", "exit_editor", "Exit"),
        Binding("q", "exit_editor", "Exit", show=False),
    ]

    COLOR_TOKENS: ClassVar[list[str]] = [
        "background",
        "title",
        "border",
        "text",
        "highlight",
        "selection",
        "accent",
        "gutter",
        "shortcut_key",
        "divider",
        "plugin",
        "footer",
        "shadow",
        "help_text",
        "window_close_button",
        "scrollbar",
        "whitespace",
        "button_primary",
        "button_error",
        "button_cancel",
        "button_success",
    ]

    BORDER_PROPERTIES: ClassVar[list[tuple[str, str]]] = [
        ("border_horizontal", "Horiz Border"),
        ("border_vertical", "Vert Border"),
        ("border_top_left", "Top-Left Corner"),
        ("border_top_right", "Top-Right Corner"),
        ("border_bottom_left", "Bot-Left Corner"),
        ("border_bottom_right", "Bot-Right Corner"),
        ("left_tee", "Left Tee (├)"),
        ("right_tee", "Right Tee (┤)"),
        ("top_tee", "Top Tee (┬)"),
        ("bottom_tee", "Bottom Tee (┴)"),
        ("title_left_cap", "Title Left Cap"),
        ("title_right_cap", "Title Right Cap"),
        ("gutter_border", "Gutter Border"),
        ("gutter_separator", "Gutter Separator"),
        ("gutter_left_tee", "Gutter Left Tee"),
        ("gutter_right_tee", "Gutter Right Tee"),
        ("gutter_top_tee", "Gutter Top Tee"),
        ("gutter_bottom_tee", "Gutter Bot Tee"),
    ]

    def __init__(
        self,
        initial_theme: str | None = None,
        themes_filepath: str | None = None,
        configured_theme: str | None = None,
        is_new: bool = False,
        base_theme: str | None = None,
        current_theme: dict | None = None,
        theme_name: str | None = None,
    ):
        super().__init__()
        self.themes_filepath = themes_filepath or os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.themes")
        self.raw_themes_data = bashmenu_ui.load_themes_file(self.themes_filepath) or {}

        cfg, _ = bashmenu.load_config()
        self.configured_theme = configured_theme or cfg.get("theme", "dracula")
        self.configured_theme_styles = bashmenu_ui.init_theme_colors(self.configured_theme)

        self.is_new = is_new
        if current_theme is not None:
            self.theme_name = theme_name or initial_theme or "custom"
            self.current_theme = copy.deepcopy(current_theme)
        elif is_new:
            if base_theme and base_theme in self.raw_themes_data:
                self.theme_name = "untitled"
                self.current_theme = copy.deepcopy(self.raw_themes_data[base_theme])
            else:
                self.theme_name = "untitled"
                if "monochrome" in self.raw_themes_data:
                    self.current_theme = copy.deepcopy(self.raw_themes_data["monochrome"])
                else:
                    self.current_theme = {
                        "indicator": ">",
                        "divider": {"char": "─", "length": "{window_width}"},
                        "window": copy.deepcopy(bashmenu_ui.DEFAULT_WINDOW_BORDER),
                        256: {
                            "background": "COLOR_BLACK",
                            "title": [255, -1],
                            "border": [245, -1],
                            "text": [252, -1],
                            "highlight": ["COLOR_BLACK", 255],
                            "selection": [232, 250],
                            "shortcut_key": [255, -1],
                            "divider": [245, -1],
                            "plugin": [250, -1],
                            "gutter": [239, -1],
                            "help_text": [248, -1],
                            "shadow": [235, "COLOR_BLACK"],
                        },
                    }
        else:
            target_theme = initial_theme or self.configured_theme
            self.theme_name = target_theme if target_theme in self.raw_themes_data else "dracula"
            if not self.raw_themes_data:
                # Fallback basic template
                self.raw_themes_data = {"custom": {"window": {}, "256": {"background": "COLOR_BLACK"}}}
                self.theme_name = "custom"
            self.current_theme = copy.deepcopy(self.raw_themes_data.get(self.theme_name, {}))

        self._ensure_theme_structure()
        self._initial_theme_snapshot = copy.deepcopy(self.current_theme)
        self._initial_theme_name = "" if is_new else self.theme_name
        self._force_dirty = is_new

    @property
    def is_dirty(self) -> bool:
        if getattr(self, "_force_dirty", False):
            return True
        return (
            self.current_theme != getattr(self, "_initial_theme_snapshot", {})
            or self.theme_name != getattr(self, "_initial_theme_name", "")
        )

    @is_dirty.setter
    def is_dirty(self, val: bool) -> None:
        self._force_dirty = val
        if not val:
            self._initial_theme_snapshot = copy.deepcopy(self.current_theme)
            self._initial_theme_name = self.theme_name

    def _ensure_theme_structure(self) -> None:
        """Guarantee all essential theme blocks exist in the working copy."""
        self.current_theme.setdefault("indicator", ">")
        win = self.current_theme.setdefault("window", {})
        self.current_theme.setdefault("divider", {"char": "─", "length": "{window_width}"})
        if "256" in self.current_theme and 256 not in self.current_theme:
            self.current_theme[256] = self.current_theme.pop("256")
        if "16" in self.current_theme and 16 not in self.current_theme:
            self.current_theme[16] = self.current_theme.pop("16")
        if "8" in self.current_theme and 8 not in self.current_theme:
            self.current_theme[8] = self.current_theme.pop("8")
        self.current_theme.setdefault(256, {})

        # Inherit base horizontal & vertical borders if specific directional keys exist
        if "border_horizontal" not in win or not win["border_horizontal"]:
            win["border_horizontal"] = win.get("border_horizontal_top") or win.get("border_horizontal_bottom", "─")
        if "border_vertical" not in win or not win["border_vertical"]:
            win["border_vertical"] = win.get("border_vertical_left") or win.get("border_vertical_right", "│")

        # Synchronize tees aliases before filling defaults
        if "border_tee_left" not in win and "left_tee" in win:
            win["border_tee_left"] = win["left_tee"]
        if "border_tee_right" not in win and "right_tee" in win:
            win["border_tee_right"] = win["right_tee"]
        if "border_tee_top" not in win and "top_tee" in win:
            win["border_tee_top"] = win["top_tee"]
        if "border_tee_bottom" not in win and "bottom_tee" in win:
            win["border_tee_bottom"] = win["bottom_tee"]

        if "left_tee" not in win and "border_tee_left" in win:
            win["left_tee"] = win["border_tee_left"]
        if "right_tee" not in win and "border_tee_right" in win:
            win["right_tee"] = win["border_tee_right"]
        if "top_tee" not in win and "border_tee_top" in win:
            win["top_tee"] = win["border_tee_top"]
        if "bottom_tee" not in win and "border_tee_bottom" in win:
            win["bottom_tee"] = win["border_tee_bottom"]

        # Fill default window borders if missing (excluding directional overrides so base borders work)
        directional_keys = {"border_horizontal_top", "border_horizontal_bottom", "border_vertical_left", "border_vertical_right"}
        for k, v in bashmenu_ui.DEFAULT_WINDOW_BORDER.items():
            if k not in directional_keys:
                win.setdefault(k, v)

    def on_mount(self) -> None:
        """Initialize mounted state, apply configured theme styles, and baseline snapshot."""
        app_theme = getattr(self.app, "theme_name", None)
        if app_theme and (not getattr(self, "configured_theme", None) or self.configured_theme == "dracula"):
            self.configured_theme = app_theme
            self.configured_theme_styles = getattr(self.app, "theme_styles", None) or bashmenu_ui.init_theme_colors(app_theme)
        self.apply_theme()
        self._sync_preview()
        self.update_footer_layout()
        self._mounted_ready = True
        self._initial_theme_snapshot = copy.deepcopy(self.current_theme)
        self._initial_theme_name = "" if getattr(self, "is_new", False) else self.theme_name
        self._force_dirty = getattr(self, "is_new", False)

    def apply_theme(self) -> None:
        """Apply configured theme styles to ThemeEditScreen and its subwidgets."""
        with contextlib.suppress(Exception):
            self.configured_theme_styles = bashmenu_ui.resolve_theme_dict(
                getattr(self, "configured_theme_styles", None) or getattr(self.app, "theme_styles", None), self.app
            )
            t_name = (
                self.configured_theme_styles.get("theme_name")
                if isinstance(self.configured_theme_styles, dict)
                else getattr(self, "configured_theme", "dracula")
            )
            if t_name:
                self.configured_theme = t_name
                bashmenu_ui.apply_theme_to_textual_borders(t_name)

            ts = self.configured_theme_styles
            bg_style = ts.get("background")
            if bg_style and bg_style.bgcolor and bg_style.bgcolor.name:
                css_bg = bashmenu_ui.parse_css_color(bg_style.bgcolor.name)
                if css_bg:
                    with contextlib.suppress(Exception):
                        self.styles.background = css_bg
                    for wid in ["#workspace", "#preview_panel", "#inspector_panel"]:
                        with contextlib.suppress(Exception):
                            self.query_one(wid).styles.background = css_bg

            hdr_style = ts.get("header") or ts.get("title")
            if hdr_style:
                if hdr_style.bgcolor and hdr_style.bgcolor.name:
                    css_hdr_bg = bashmenu_ui.parse_css_color(hdr_style.bgcolor.name)
                    if css_hdr_bg:
                        with contextlib.suppress(Exception):
                            self.query_one("#header").styles.background = css_hdr_bg
                if hdr_style.color and hdr_style.color.name:
                    css_hdr_fg = bashmenu_ui.parse_css_color(hdr_style.color.name)
                    if css_hdr_fg:
                        with contextlib.suppress(Exception):
                            self.query_one("#header_title", Label).styles.color = css_hdr_fg

            with contextlib.suppress(Exception):
                btn_close = self.query_one("#btn_close_x", Label)
                btn_close.update(bashmenu_ui.format_close_button_label(ts))

            border_style = ts.get("border") or ts.get("accent")
            if border_style and border_style.color and border_style.color.name:
                css_border = bashmenu_ui.parse_css_color(border_style.color.name)
                if css_border:
                    for pid in ["#preview_panel", "#inspector_panel"]:
                        with contextlib.suppress(Exception):
                            self.query_one(pid).styles.border = ("solid", css_border)
                    with contextlib.suppress(Exception):
                        for inp in self.query(".prop_input"):
                            inp.styles.border = ("solid", css_border)

            accent_style = ts.get("accent") or ts.get("title") or ts.get("help_text")
            if accent_style and accent_style.color and accent_style.color.name:
                css_accent = bashmenu_ui.parse_css_color(accent_style.color.name)
                if css_accent:
                    with contextlib.suppress(Exception):
                        for sh in self.query(".section_header"):
                            sh.styles.color = css_accent
                            sh.styles.background = f"{css_accent} 15%"

            text_style = ts.get("text")
            if text_style and text_style.color and text_style.color.name:
                css_text = bashmenu_ui.parse_css_color(text_style.color.name)
                if css_text:
                    with contextlib.suppress(Exception):
                        for pl in self.query(".prop_label"):
                            pl.styles.color = css_text
                    with contextlib.suppress(Exception):
                        for inp in self.query(".prop_input"):
                            inp.styles.color = css_text

            btn_style = ts.get("button_primary") or ts.get("selection") or accent_style
            if btn_style:
                css_btn_bg = bashmenu_ui.parse_css_color(btn_style.bgcolor.name) if btn_style.bgcolor else None
                css_btn_fg = bashmenu_ui.parse_css_color(btn_style.color.name) if btn_style.color else None
                with contextlib.suppress(Exception):
                    for btn in self.query(".btn_prop_action"):
                        if css_btn_bg:
                            btn.styles.background = css_btn_bg
                        if css_btn_fg:
                            btn.styles.color = css_btn_fg

            footer_style = ts.get("footer") or ts.get("background")
            if footer_style and footer_style.bgcolor and footer_style.bgcolor.name:
                css_ftr_bg = bashmenu_ui.parse_css_color(footer_style.bgcolor.name)
                if css_ftr_bg:
                    with contextlib.suppress(Exception):
                        self.query_one("#footer").styles.background = css_ftr_bg

            help_style = ts.get("help_text") or ts.get("shortcut_key") or accent_style
            if help_style and help_style.color and help_style.color.name:
                css_help = bashmenu_ui.parse_css_color(help_style.color.name)
                if css_help:
                    with contextlib.suppress(Exception):
                        for item in self.query(".footer_item"):
                            item.styles.color = css_help

            sep_style = ts.get("border") or ts.get("divider") or ts.get("footer")
            if sep_style and sep_style.color and sep_style.color.name:
                css_sep = bashmenu_ui.parse_css_color(sep_style.color.name)
                if css_sep:
                    with contextlib.suppress(Exception):
                        for sep in self.query(".footer_sep"):
                            sep.styles.color = css_sep
                            sep.styles.auto_color = False

            # Scrollbars
            sb_style = ts.get("scrollbar") or border_style or accent_style
            if sb_style:
                css_sb_fg = (
                    bashmenu_ui.parse_css_color(sb_style.color.name)
                    if (sb_style.color and sb_style.color.name)
                    else None
                )
                css_sb_bg = (
                    bashmenu_ui.parse_css_color(sb_style.bgcolor.name)
                    if (sb_style.bgcolor and sb_style.bgcolor.name)
                    else None
                )
                for w in [self, self.query_one("#inspector_panel")]:
                    with contextlib.suppress(Exception):
                        if css_sb_fg:
                            w.styles.scrollbar_color = css_sb_fg
                        if css_sb_bg:
                            w.styles.scrollbar_background = css_sb_bg

            self.update_footer_layout()

    def compose(self) -> ComposeResult:
        file_name = os.path.basename(self.themes_filepath) if self.themes_filepath else "bashmenu.themes"
        theme_disp = self.theme_name if (self.theme_name and not getattr(self, "is_new", False) and self.theme_name != "untitled") else "Untitled"
        dirty_flag = " *" if self.is_dirty else ""
        with Horizontal(id="header"):
            yield Label(
                f"BashMenu Theme Editor — {file_name} [{theme_disp}]{dirty_flag}",
                id="header_title",
                markup=False,
            )
            yield Label(
                bashmenu_ui.format_close_button_label(self.configured_theme_styles),
                id="btn_close_x",
                classes="btn_close_x",
            )

        with Horizontal(id="workspace"):
            with Vertical(id="preview_panel"):
                yield ThemePreviewWidget(
                    self.current_theme, theme_name=self.theme_name, id="live_preview"
                )

            with VerticalScroll(id="inspector_panel"):
                yield Label("▼ General & Identity", classes="section_header")
                with Horizontal(classes="prop_row"):
                    yield Label("Indicator:", classes="prop_label")
                    yield Input(
                        value=str(self.current_theme.get("indicator", ">")),
                        id="prop_indicator",
                        classes="prop_input",
                    )
                    yield Button("ASCII", classes="btn_prop_action", id="btn_ascii_indicator")
                with Horizontal(classes="prop_row"):
                    yield Label("Shadow Char:", classes="prop_label")
                    yield Input(
                        value=str(self.current_theme["window"].get("shadow_char", "░")),
                        id="prop_shadow_char",
                        classes="prop_input",
                    )
                    yield Button("ASCII", classes="btn_prop_action", id="btn_ascii_shadow_char")

                yield Label("▼ Marquee Settings", classes="section_header")
                m_cfg = self.current_theme.get("marquee", {})
                m_char = str(m_cfg.get("char", " ")) if isinstance(m_cfg, dict) else " "
                m_gap = str(m_cfg.get("gap", 4)) if isinstance(m_cfg, dict) else "4"
                with Horizontal(classes="prop_row"):
                    yield Label("Marquee Char:", classes="prop_label")
                    yield Input(
                        value=m_char,
                        id="prop_marquee_char",
                        classes="prop_input",
                    )
                    yield Button("ASCII", classes="btn_prop_action", id="btn_ascii_marquee_char")
                with Horizontal(classes="prop_row"):
                    yield Label("Gap Spaces:", classes="prop_label")
                    yield Input(
                        value=m_gap,
                        id="prop_marquee_gap",
                        classes="prop_input",
                    )

                yield Label("▼ Window & Gutter Borders", classes="section_header")
                for key, label_text in self.BORDER_PROPERTIES:
                    val = str(self.current_theme["window"].get(key, ""))
                    with Horizontal(classes="prop_row"):
                        yield Label(f"{label_text}:", classes="prop_label")
                        yield Input(value=val, id=f"prop_{key}", classes="prop_input")
                        yield Button("ASCII", classes="btn_prop_action", id=f"btn_ascii_{key}")

                yield Label("▼ Divider Settings", classes="section_header")
                div_char = str(self.current_theme.get("divider", {}).get("char", "─"))
                div_len = str(self.current_theme.get("divider", {}).get("length", "{window_width}"))
                with Horizontal(classes="prop_row"):
                    yield Label("Divider Char:", classes="prop_label")
                    yield Input(value=div_char, id="prop_divider_char", classes="prop_input")
                    yield Button("ASCII", classes="btn_prop_action", id="btn_ascii_divider_char")
                with Horizontal(classes="prop_row"):
                    yield Label("Length Mode:", classes="prop_label")
                    yield Input(value=div_len, id="prop_divider_length", classes="prop_input")

                yield Label("▼ Wallpaper & Background", classes="section_header")
                bg_data = self.current_theme.get("background")
                bg_img = ""
                if isinstance(bg_data, dict):
                    bg_img = str(bg_data.get("image", ""))
                elif isinstance(bg_data, str):
                    bg_img = bg_data
                with Horizontal(classes="prop_row"):
                    yield Label("Wallpaper:", classes="prop_label")
                    yield Input(
                        value=bg_img,
                        placeholder="(None / disabled)",
                        id="prop_wallpaper_image",
                        classes="prop_input",
                    )
                    yield Button("Config", classes="btn_prop_action", id="btn_config_background")

                yield Label("▼ 256-Color Palette Tokens", classes="section_header")
                pal_256 = self.current_theme.get(256) or self.current_theme.get("256") or {}
                for tok in self.COLOR_TOKENS:
                    tok_val = pal_256.get(tok, -1)
                    val_str = str(tok_val)
                    with Horizontal(classes="prop_row"):
                        yield Label(f"{tok}:", classes="prop_label")
                        yield Input(value=val_str, id=f"color_{tok}", classes="prop_input")
                        yield Button("Color", classes="btn_prop_action", id=f"btn_color_{tok}")

        with Vertical(id="footer"):
            with Horizontal(classes="footer_row"):
                yield Label("[F1] Help", classes="footer_item", id="lbl_help", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[F2] Background", classes="footer_item", id="lbl_background", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[F3] Pick Color", classes="footer_item", id="lbl_color", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[F4] ASCII/Glyphs", classes="footer_item", id="lbl_ascii", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[F5] Reset", classes="footer_item", id="lbl_reset", markup=False)
            with Horizontal(classes="footer_row"):
                yield Label("[F6] Clone/Base", classes="footer_item", id="lbl_clone", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[F7] Derive 16/8", classes="footer_item", id="lbl_derive", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[Ctrl+S] Save", classes="footer_item", id="lbl_save", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[Ctrl+A] Save As", classes="footer_item", id="lbl_save_as", markup=False)
                yield Label("|", classes="footer_sep", markup=False)
                yield Label("[ESC/q] Exit", classes="footer_item", id="lbl_exit", markup=False)

    def _sync_preview(self) -> None:
        """Propagate current theme changes to the preview canvas widget."""
        preview = self.query_one("#live_preview", ThemePreviewWidget)
        preview.update_theme(self.current_theme, theme_name=self.theme_name)
        h_title = self.query_one("#header_title", Label)
        dirty_flag = " *" if self.is_dirty else ""
        borders = getattr(self, "configured_theme_styles", {}).get("window_borders") or bashmenu_ui.get_theme_window_borders(getattr(self, "configured_theme", "dracula"))
        l_cap = borders.get("title_left_cap", "[").strip() or "["
        r_cap = borders.get("title_right_cap", "]").strip() or "]"
        file_name = os.path.basename(self.themes_filepath) if self.themes_filepath else "bashmenu.themes"
        theme_disp = self.theme_name if (self.theme_name and not getattr(self, "is_new", False) and self.theme_name != "untitled") else "Untitled"
        h_title.update(f"{l_cap} BashMenu Theme Editor — {file_name} [{theme_disp}]{dirty_flag} {r_cap}")

    def update_footer_layout(self, width: int | None = None) -> None:
        """Distribute footer keyboard shortcut labels and pipe separators equally across both footer rows."""
        w = width
        if w is None or w <= 0:
            if hasattr(self, "size") and self.size and self.size.width:
                w = self.size.width
            elif hasattr(self, "app") and self.app and hasattr(self.app, "size") and self.app.size:
                w = self.app.size.width
            else:
                w = 80

        with contextlib.suppress(Exception):
            footer = self.query_one("#footer")
            rows = list(footer.query(".footer_row"))
            for row in rows:
                items = list(row.query(".footer_item"))
                seps = list(row.query(".footer_sep"))
                if not items:
                    continue
                num_items = len(items)
                if num_items == 1:
                    items[0].styles.margin = (0, 0, 0, 0)
                    continue

                item_lens = []
                for it in items:
                    t = str(it.renderable) if hasattr(it, "renderable") else ""
                    item_lens.append(len(t) if t else len(getattr(it, "content", "")))

                tot_text = sum(item_lens) + len(seps)
                num_gaps = num_items - 1
                rem = max(0, w - tot_text)
                base_gap = rem // num_gaps
                extra = rem % num_gaps

                for i, it in enumerate(items):
                    if i < num_gaps:
                        total_gap = base_gap + (1 if i < extra else 0)
                        left_gap = total_gap // 2
                        right_gap = total_gap - left_gap
                        it.styles.margin = (0, left_gap, 0, 0)
                        if i < len(seps):
                            seps[i].styles.margin = (0, right_gap, 0, 0)
                    else:
                        it.styles.margin = (0, 0, 0, 0)

    def on_resize(self, event: events.Resize) -> None:
        """Handle screen resize, refresh preview canvas dimensions, and distribute footer spacing."""
        self._sync_preview()
        w = None
        if event is not None and hasattr(event, "size") and event.size:
            w = event.size.width
        self.update_footer_layout(width=w)

    @on(ThemePreviewWidget.ElementClicked)
    def on_preview_element_clicked(self, message: ThemePreviewWidget.ElementClicked) -> None:
        """Handle element click from live preview canvas and focus corresponding inspector property."""
        self.focus_inspector_target(message.primary)

    @on(events.Click, "#preview_panel")
    def on_preview_panel_clicked(self, event: events.Click) -> None:
        """Handle click in preview panel margin area and select background color."""
        if event.widget and getattr(event.widget, "id", None) == "preview_panel":
            self.focus_inspector_target("color_background")

    def focus_inspector_target(self, target_id: str) -> None:
        """Scroll to and focus an inspector input widget by element ID."""
        try:
            inp = self.query_one(f"#{target_id}", Input)
            inp.scroll_visible()
            inp.focus()
            clean_name = target_id.replace("color_", "Color: ").replace("prop_", "Border: ").replace("_", " ").title()
            with contextlib.suppress(Exception):
                self.notify(f"Inspecting {clean_name}", title="Theme Element", timeout=1.5)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                elem = self.query_one(f"#{target_id}")
                elem.scroll_visible()
                elem.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle live input changes and synchronize preview instantly."""
        if not getattr(self, "_mounted_ready", False):
            return

        inp_id = event.input.id
        val = event.value.strip()

        if not inp_id:
            return

        if inp_id == "prop_indicator":
            if str(self.current_theme.get("indicator", "")) == val:
                return
            self.current_theme["indicator"] = val
        elif inp_id == "prop_shadow_char":
            win = self.current_theme.setdefault("window", {})
            if str(win.get("shadow_char", "")) == val:
                return
            win["shadow_char"] = val
        elif inp_id.startswith("prop_divider_"):
            sub_k = inp_id.replace("prop_divider_", "")
            div = self.current_theme.setdefault("divider", {})
            if str(div.get(sub_k, "")) == val:
                return
            div[sub_k] = val
        elif inp_id.startswith("prop_marquee_"):
            sub_k = inp_id.replace("prop_marquee_", "")
            mq = self.current_theme.setdefault("marquee", {})
            if not isinstance(mq, dict):
                mq = {}
                self.current_theme["marquee"] = mq
            if sub_k == "gap":
                try:
                    num_val = int(val)
                except ValueError:
                    num_val = 4
                if mq.get("gap") == num_val:
                    return
                mq["gap"] = num_val
            else:
                if str(mq.get("char", " ")) == val:
                    return
                mq["char"] = val
            self.is_dirty = True
            self._sync_preview()
            return
        elif inp_id == "prop_wallpaper_image":
            val_clean = val.strip()
            curr_bg = self.current_theme.get("background")
            if not val_clean:
                if "background" in self.current_theme or "wallpaper" in self.current_theme:
                    self.current_theme.pop("background", None)
                    self.current_theme.pop("wallpaper", None)
                    self.is_dirty = True
                    self._sync_preview()
                return
            if isinstance(curr_bg, dict):
                if curr_bg.get("image") == val_clean:
                    return
                curr_bg["image"] = val_clean
            elif isinstance(curr_bg, str):
                if curr_bg == val_clean:
                    return
                self.current_theme["background"] = {
                    "image": val_clean,
                    "opacity": 0.85,
                    "scaling": "cover",
                    "mode": "halfblock",
                }
            else:
                self.current_theme["background"] = {
                    "image": val_clean,
                    "opacity": 0.85,
                    "scaling": "cover",
                    "mode": "halfblock",
                }
            self.is_dirty = True
            self._sync_preview()
            return
        elif inp_id.startswith("prop_"):
            border_k = inp_id.replace("prop_", "")
            win = self.current_theme.setdefault("window", {})
            if str(win.get(border_k, "")) == val:
                return
            win[border_k] = val
            if border_k == "border_horizontal":
                win["border_horizontal_top"] = val
                win["border_horizontal_bottom"] = val
            elif border_k == "border_vertical":
                win["border_vertical_left"] = val
                win["border_vertical_right"] = val
            elif border_k == "left_tee":
                win["border_tee_left"] = val
            elif border_k == "right_tee":
                win["border_tee_right"] = val
            elif border_k == "top_tee":
                win["border_tee_top"] = val
            elif border_k == "bottom_tee":
                win["border_tee_bottom"] = val
        elif inp_id.startswith("color_"):
            tok = inp_id.replace("color_", "")
            pal = self._get_pal_256()
            if str(pal.get(tok, "")) == val:
                return
            try:
                # Parse python/yaml lists e.g. [201, -1] or scalar 233
                parsed = yaml.safe_load(val)
                pal[tok] = parsed
            except Exception:  # noqa: BLE001
                pal[tok] = val

        self._sync_preview()

    def _get_pal_256(self) -> dict:
        pal = self.current_theme.get(256)
        if pal is None:
            pal = self.current_theme.get("256")
        if pal is None:
            pal = self.current_theme.setdefault(256, {})
        return pal

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if not btn_id:
            return

        if btn_id.startswith("btn_ascii_"):
            prop_k = btn_id.replace("btn_ascii_", "")
            curr_val = ""
            if prop_k == "indicator":
                curr_val = self.current_theme.get("indicator", "")
            elif prop_k == "divider_char":
                curr_val = self.current_theme.get("divider", {}).get("char", "")
            elif prop_k == "marquee_char":
                curr_val = str(self.current_theme.get("marquee", {}).get("char", " "))
            else:
                curr_val = self.current_theme.get("window", {}).get(prop_k, "")

            def _on_ascii_picked(glyph: str | None) -> None:
                if glyph:
                    target_input_id = f"#prop_{prop_k}"
                    with contextlib.suppress(Exception):
                        inp = self.query_one(target_input_id, Input)
                        inp.value = glyph

            self.app.push_screen(
                AsciiPickerModal(prop_k, curr_val, theme_styles=self.configured_theme_styles),
                _on_ascii_picked,
            )

        elif btn_id == "btn_config_background":
            self.action_configure_background()

        elif btn_id.startswith("btn_color_"):
            tok = btn_id.replace("btn_color_", "")
            pal_256 = self._get_pal_256()
            curr_val = pal_256.get(tok, -1)
            bg_val = pal_256.get("background", "COLOR_BLACK")

            def _on_color_picked(chosen: Any) -> None:
                if chosen is not None:
                    target_input_id = f"#color_{tok}"
                    with contextlib.suppress(Exception):
                        inp = self.query_one(target_input_id, Input)
                        inp.value = str(chosen)

            self.app.push_screen(
                ColorPickerModal(tok, curr_val, bg_color_val=bg_val, theme_styles=self.configured_theme_styles),
                _on_color_picked,
            )

    def on_click(self, event: Any) -> None:
        """Handle mouse clicks on interactive footer shortcut items and header close button."""
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if not widget:
            return
        w_id = getattr(widget, "id", None)
        if w_id == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", []):
            self.action_exit_editor()
            return
        if w_id == "lbl_help":
            self.action_show_help()
        elif w_id == "lbl_color":
            self.action_pick_color()
        elif w_id == "lbl_ascii":
            self.action_pick_ascii()
        elif w_id == "lbl_clone":
            self.action_clone_theme()
        elif w_id == "lbl_derive":
            self.action_derive_palettes()
        elif w_id == "lbl_background":
            self.action_configure_background()
        elif w_id == "lbl_save":
            self.action_save_theme()
        elif w_id == "lbl_save_as":
            self.action_save_as_theme()
        elif w_id == "lbl_reset":
            self.action_reset_theme()
        elif w_id == "lbl_exit":
            self.action_exit_editor()

    def action_show_help(self) -> None:
        """Display the HA Bash Menu manual modal (F1 / ? shortcut)."""
        help_path = os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.md")
        help_text = "Help manual file not found."
        if os.path.exists(help_path):
            with open(help_path, "r", encoding="utf-8") as f:
                help_text = f.read()
        self.app.push_screen(
            bashmenu_ui.MessageModalScreen(
                "HA Bash Menu Manual",
                help_text,
                theme=self.configured_theme_styles,
                is_help=True,
                is_markdown=True,
            )
        )

    def action_pick_color(self) -> None:
        """Trigger color picker modal for focused color token or default."""
        focused = self.focused
        if focused and isinstance(focused, Input) and focused.id and focused.id.startswith("color_"):
            tok = focused.id.replace("color_", "")
            pal_256 = self._get_pal_256()
            curr_val = pal_256.get(tok, -1)
            bg_val = pal_256.get("background", "COLOR_BLACK")

            def _cb(c):
                if c is not None:
                    focused.value = str(c)

            self.app.push_screen(
                ColorPickerModal(tok, curr_val, bg_color_val=bg_val, theme_styles=self.configured_theme_styles),
                _cb,
            )
            return

        # Default fallback to color_background
        with contextlib.suppress(Exception):
            inp = self.query_one("#color_background", Input)
            inp.focus()
            tok = "background"
            pal_256 = self._get_pal_256()
            curr_val = pal_256.get(tok, -1)
            bg_val = pal_256.get("background", "COLOR_BLACK")

            def _cb_def(c):
                if c is not None:
                    inp.value = str(c)

            self.app.push_screen(
                ColorPickerModal(tok, curr_val, bg_color_val=bg_val, theme_styles=self.configured_theme_styles),
                _cb_def,
            )

    def action_pick_ascii(self) -> None:
        """Trigger box-drawing ASCII modal for focused property or default."""
        focused = self.focused
        if focused and isinstance(focused, Input) and focused.id and focused.id.startswith("prop_"):
            prop_k = focused.id.replace("prop_", "")
            curr_val = focused.value

            def _cb_a(g):
                if g:
                    focused.value = g

            self.app.push_screen(
                AsciiPickerModal(prop_k, curr_val, theme_styles=self.configured_theme_styles),
                _cb_a,
            )
            return

        # Default fallback to prop_border_top_left
        with contextlib.suppress(Exception):
            inp = self.query_one("#prop_border_top_left", Input)
            inp.focus()
            prop_k = "border_top_left"
            curr_val = inp.value

            def _cb_a_def(g):
                if g:
                    inp.value = g

            self.app.push_screen(
                AsciiPickerModal(prop_k, curr_val, theme_styles=self.configured_theme_styles),
                _cb_a_def,
            )

    def action_clone_theme(self) -> None:
        """Open theme picker to clone an existing theme as a base."""
        def _on_theme_chosen(theme_key: str | None) -> None:
            if theme_key and theme_key in self.raw_themes_data:
                self.theme_name = f"{theme_key}_custom"
                self.current_theme = copy.deepcopy(self.raw_themes_data[theme_key])
                self._ensure_theme_structure()
                self.is_new = True
                self.is_dirty = True
                self._populate_all_inputs()
                self._sync_preview()

        self.app.push_screen(
            bashmenu_ui.ThemePickerModalScreen(self.theme_name, theme=self.configured_theme_styles),
            _on_theme_chosen,
        )

    def _populate_all_inputs(self) -> None:
        """Reflect current_theme values across all inspector input fields."""
        with contextlib.suppress(Exception):
            self.query_one("#prop_indicator", Input).value = str(self.current_theme.get("indicator", ">"))
            self.query_one("#prop_shadow_char", Input).value = str(
                self.current_theme.get("window", {}).get("shadow_char", "░")
            )
            div_char = str(self.current_theme.get("divider", {}).get("char", "─"))
            div_len = str(self.current_theme.get("divider", {}).get("length", "{window_width}"))
            self.query_one("#prop_divider_char", Input).value = div_char
            self.query_one("#prop_divider_length", Input).value = div_len

            m_cfg = self.current_theme.get("marquee", {})
            m_char = str(m_cfg.get("char", " ")) if isinstance(m_cfg, dict) else " "
            m_gap = str(m_cfg.get("gap", 4)) if isinstance(m_cfg, dict) else "4"
            self.query_one("#prop_marquee_char", Input).value = m_char
            self.query_one("#prop_marquee_gap", Input).value = m_gap

            bg_data = self.current_theme.get("background")
            bg_img = ""
            if isinstance(bg_data, dict):
                bg_img = str(bg_data.get("image", ""))
            elif isinstance(bg_data, str):
                bg_img = bg_data
            self.query_one("#prop_wallpaper_image", Input).value = bg_img

            for k, _ in self.BORDER_PROPERTIES:
                b_val = str(self.current_theme.get("window", {}).get(k, ""))
                self.query_one(f"#prop_{k}", Input).value = b_val

            pal_256 = self._get_pal_256()
            for tok in self.COLOR_TOKENS:
                c_val = str(pal_256.get(tok, -1))
                self.query_one(f"#color_{tok}", Input).value = c_val

    def action_configure_background(self) -> None:
        """Open the background and wallpaper configuration dialog (b shortcut)."""
        curr_bg = self.current_theme.get("background")
        self.app.push_screen(
            BackgroundConfigModal(current_background=curr_bg, theme_styles=self.configured_theme_styles),
            self._on_background_configured,
        )

    def _on_background_configured(self, result: dict[str, Any] | None) -> None:
        """Handle background configuration result from modal."""
        if result is None:
            return
        if result:
            self.current_theme["background"] = result
        else:
            self.current_theme.pop("background", None)
            self.current_theme.pop("wallpaper", None)

        self.is_dirty = True
        img_val = result.get("image", "") if result else ""
        with contextlib.suppress(Exception):
            self.query_one("#prop_wallpaper_image", Input).value = img_val
        self._sync_preview()

    def action_derive_palettes(self) -> None:
        """Calculate closest 16-color and 8-color fallback palettes from 256."""
        pal_256 = self._get_pal_256()
        pal_16, pal_8 = auto_derive_fallback_depths(pal_256)
        self.current_theme[16] = pal_16
        self.current_theme[8] = pal_8
        self.is_dirty = True
        self.app.push_screen(
            bashmenu_ui.MessageModalScreen(
                "Palettes Derived",
                "Successfully calculated and synchronized 16-color and 8-color\n"
                "fallback tiers from the active 256 palette.",
                theme=self.configured_theme_styles,
            )
        )

    def action_reset_theme(self) -> None:
        """Revert working copy to loaded state."""
        if getattr(self, "is_new", False) or self.theme_name == "untitled":
            self.current_theme = copy.deepcopy(getattr(self, "_initial_theme_snapshot", {}))
            self._ensure_theme_structure()
            self.is_dirty = True
            self._populate_all_inputs()
            self._sync_preview()
        elif self.theme_name in self.raw_themes_data:
            self.current_theme = copy.deepcopy(self.raw_themes_data[self.theme_name])
            self._ensure_theme_structure()
            self.is_dirty = False
            self._populate_all_inputs()
            self._sync_preview()

    def action_save_theme(self) -> None:
        """Save theme. If untitled or new, prompt for name (Save As); otherwise save directly to disk."""
        if (
            getattr(self, "is_new", False)
            or not self.theme_name
            or self.theme_name == "untitled"
            or self.theme_name not in self.raw_themes_data
        ):
            self.action_save_as_theme()
            return

        self._save_theme_to_disk(self.theme_name, set_active=False)

    def action_save_as_theme(self) -> None:
        """Open Save Modal and persist validated theme to bashmenu.themes under a new or chosen name."""
        def _on_save_confirmed(result: tuple[str, bool] | None) -> None:
            if not result:
                return
            new_name, set_active = result
            self._save_theme_to_disk(new_name, set_active=set_active)

        suggested_name = "" if (getattr(self, "is_new", False) or self.theme_name == "untitled") else self.theme_name
        self.app.push_screen(
            SaveThemeModal(suggested_name, theme_styles=self.configured_theme_styles),
            _on_save_confirmed,
        )

    def _save_theme_to_disk(self, target_name: str, set_active: bool = False) -> None:
        """Serialize validated theme to bashmenu.themes and update state."""
        # Ensure 16 and 8 fallback tiers exist before saving
        if 16 not in self.current_theme or 8 not in self.current_theme:
            pal_256 = self._get_pal_256()
            p16, p8 = auto_derive_fallback_depths(pal_256)
            self.current_theme[16] = p16
            self.current_theme[8] = p8

        try:
            self.raw_themes_data[target_name] = copy.deepcopy(self.current_theme)

            # Validate with ymlcheck before writing to disk
            errs = []
            for k_depth, v_keys in self.current_theme.items():
                depth_str = str(k_depth)
                if depth_str == "window":
                    errs.extend(ymlcheck.validate_window_section(v_keys, f"{target_name}.window"))
                elif depth_str == "divider":
                    errs.extend(ymlcheck.validate_divider_section(v_keys, f"{target_name}.divider"))
                elif depth_str == "marquee":
                    errs.extend(ymlcheck.validate_marquee_section(v_keys, f"{target_name}.marquee"))
                elif depth_str == "background":
                    errs.extend(ymlcheck.validate_theme_background_section(v_keys, f"{target_name}.background"))
                elif depth_str in ("256", "16", "8"):
                    errs.extend(ymlcheck.validate_depth_section(depth_str, v_keys, target_name))

            if errs:
                err_msg = "\n".join(f"- {e}" for e in errs)
                self.app.push_screen(
                    bashmenu_ui.MessageModalScreen(
                        "Theme Validation Error",
                        f"Theme schema issues detected:\n{err_msg}",
                        theme=self.configured_theme_styles,
                    )
                )
                return

            # Serialize cleanly to bashmenu.themes
            with open(self.themes_filepath, "w", encoding="utf-8") as f:
                yaml.dump(self.raw_themes_data, f, sort_keys=False, default_flow_style=False)

            # Optionally set as active theme in bashmenu.yml
            if set_active:
                cfg, _ = bashmenu.load_config()
                cfg["theme"] = target_name
                cfg_path = os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.yml")
                with open(cfg_path, "w", encoding="utf-8") as f:
                    yaml.dump(cfg, f, sort_keys=False, default_flow_style=False)
                self.configured_theme = target_name
                self.configured_theme_styles = bashmenu_ui.init_theme_colors(self.configured_theme)
                self.apply_theme()

            self.theme_name = target_name
            self.is_new = False
            self.is_dirty = False
            self._sync_preview()
            self.app.push_screen(
                bashmenu_ui.MessageModalScreen(
                    "Theme Saved",
                    f"Successfully saved theme '{target_name}' to disk!\n"
                    + ("Active theme updated in bashmenu.yml." if set_active else ""),
                    theme=self.configured_theme_styles,
                )
            )
        except Exception as e:  # noqa: BLE001
            self.app.push_screen(
                bashmenu_ui.MessageModalScreen(
                    "Save Failed",
                    f"Error saving theme to disk:\n{e}",
                    theme=self.configured_theme_styles,
                )
            )

    def action_exit_editor(self) -> None:
        """Safely exit application, checking for unsaved changes."""
        def _safe_exit() -> None:
            if len(self.app.screen_stack) > 1:
                try:
                    self.dismiss(None)
                except Exception:  # noqa: BLE001
                    self.app.pop_screen()
            else:
                self.app.exit()

        if self.is_dirty:
            def _on_confirm(choice: str) -> None:
                if choice == "yes":
                    _safe_exit()

            self.app.push_screen(
                bashmenu_ui.ConfirmModalScreen(
                    "Unsaved Changes",
                    "You have unsaved changes. Are you sure you want to exit without saving?",
                    theme=self.configured_theme_styles,
                ),
                _on_confirm,
            )
        else:
            _safe_exit()


# ==============================================================================
# APPLICATION ENTRYPOINT
# ==============================================================================


class ThemeEditApp(App):
    """Textual App Wrapper for ThemeEditScreen."""

    TITLE = "BashMenu Theme Editor"

    def __init__(self, theme_name: str | None = None, **kwargs):
        super().__init__(**kwargs)
        cfg, _ = bashmenu.load_config()
        self.configured_theme = cfg.get("theme", "dracula")
        self.theme_name = theme_name or self.configured_theme
        self.theme_styles = bashmenu_ui.init_theme_colors(self.configured_theme)

    def on_mount(self) -> None:
        bashmenu_ui.apply_theme_to_textual_borders(self.configured_theme)

        def _on_app_exit(_res: Any = None) -> None:
            self.exit()

        self.push_screen(
            ThemeEditScreen(
                initial_theme=self.theme_name,
                configured_theme=self.configured_theme,
            ),
            _on_app_exit,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="BashMenu Theme Editor")
    parser.add_argument("theme", nargs="?", default=None, help="Theme name to edit or clone")
    args = parser.parse_args()

    app = ThemeEditApp(theme_name=args.theme)
    app.run()


if __name__ == "__main__":
    main()
