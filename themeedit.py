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
from typing import Any, ClassVar

import yaml
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

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


class ColorPickerModal(ModalScreen[Any]):
    """Interactive 256-color palette picker with live preview and constants."""

    DEFAULT_CSS = """
    ColorPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    #dialog {
        width: 78;
        height: 27;
        border: thick $accent;
        background: $surface;
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
        color: $accent;
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
        background: $accent;
        color: $text;
    }
    #color_palette_grid {
        height: 12;
        border: solid $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    #preview_bar {
        height: 2;
        margin-top: 1;
        border: solid $accent;
        text-align: center;
    }
    #btn_row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #btn_row Button {
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
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
        self.selected_color = current_val

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(f"Pick Color: [{self.token_name}]", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )
                    yield OptionList(id="color_palette_grid")
                    yield Static(id="preview_bar")
                    with Horizontal(id="btn_row"):
                        yield Button("Select", variant="primary", id="btn_select")
                        yield Button("Inherit (-1)", variant="default", id="btn_inherit")
                        yield Button("Cancel", variant="error", id="btn_cancel")
                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        grid = self.query_one("#color_palette_grid", OptionList)
        options = []
        sel_idx = 0

        # Special option: -1 / Inherit
        options.append(Option(" [-1] Inherit / Transparent", id="-1"))

        # Standard Color Constants
        for name in bashmenu_ui.COLOR_MAP:
            options.append(Option(f" [{name}]", id=name))

        # 256 Numeric Palette
        for i in range(256):
            c_label = f" Color {i:3d}  ■■■■■■"
            options.append(Option(c_label, id=str(i)))

        grid.add_options(options)

        # Highlight currently selected color
        curr_str = str(self.current_val)
        for idx, opt in enumerate(options):
            if str(opt.id) == curr_str:
                sel_idx = idx
                break

        grid.highlighted = sel_idx
        self._update_preview(self.current_val)

    def _update_preview(self, val: Any) -> None:
        p_bar = self.query_one("#preview_bar", Static)
        parsed_c = bashmenu_ui.parse_color_val(val)
        bg_parsed = bashmenu_ui.parse_color_val(self.bg_color_val) or "color(233)"

        txt = Text()
        txt.append(" Sample Text ", style=Style(color=parsed_c or "white", bgcolor=bg_parsed, bold=True))
        txt.append(f"  Token: {val}  (Hex/Parsed: {parsed_c})")
        p_bar.update(txt)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        opt_id = event.option.id
        if opt_id == "-1":
            self.selected_color = -1
        elif opt_id and str(opt_id).isdigit():
            self.selected_color = int(opt_id)
        else:
            self.selected_color = opt_id
        self._update_preview(self.selected_color)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.selected_color)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_select":
            self.dismiss(self.selected_color)
        elif event.button.id == "btn_inherit":
            self.dismiss(-1)
        elif event.button.id == "btn_cancel":
            self.dismiss(None)

    def on_click(self, event: Any) -> None:
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if widget and (getattr(widget, "id", None) == "btn_close_x" or "btn_close_x" in getattr(widget, "classes", [])):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AsciiPickerModal(ModalScreen[str]):
    """Categorized box-drawing and glyph picker modal."""

    DEFAULT_CSS = """
    AsciiPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }
    #dialog {
        width: 74;
        height: 25;
        border: thick $accent;
        background: $surface;
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
        color: $accent;
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
        background: $accent;
        color: $text;
    }
    #glyph_list {
        height: 13;
        border: solid $accent;
    }
    #footer_lbl {
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    GLYPH_CATEGORIES: ClassVar[list[tuple[str, list[str]]]] = [
        ("Single Lines & Corners", ["─", "│", "┌", "┐", "└", "┘", "├", "┤", "┬", "┴", "┼"]),
        ("Rounded Corners", ["╭", "╮", "╰", "╯"]),
        ("Double Lines & Corners", ["═", "║", "╔", "╗", "╚", "╝", "╠", "╣", "╦", "╩", "╬"]),
        ("Heavy & Thick Lines", ["━", "┃", "┏", "┓", "┗", "┛", "┣", "┫", "┳", "┻", "╋"]),
        ("Blocks & Shading", ["░", "▒", "▓", "█", "▀", "▄", "▌", "▐", "■", "▞", "▚"]),
        ("Title Caps & Brackets", ["[", "]", "⟦", "⟧", "(", ")", "<", ">", "{", "}", "╡", "╞", "╢", "╟"]),
        ("Indicators & Pointers", [">", "*", "◆", "▶", "❯", "➜", "➔", "•", "⦿", "󰖟", "⚙", "ℹ"]),
    ]

    def __init__(self, property_name: str, current_char: str):
        super().__init__()
        self.property_name = property_name
        self.current_char = current_char

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label(f"ASCII / Box Glyph Picker: [{self.property_name}]", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(),
                            id="btn_close_x",
                            classes="btn_close_x",
                        )
                    yield OptionList(id="glyph_list")
                    yield Label("[ENTER] Select Character | [ESC] Cancel", id="footer_lbl")
                yield bashmenu_ui.ShadowWidget(id="shadow_right")
            yield bashmenu_ui.ShadowWidget(id="shadow_bottom")

    def on_mount(self) -> None:
        opt_list = self.query_one("#glyph_list", OptionList)
        seen_glyphs = set()
        for cat_name, glyphs in self.GLYPH_CATEGORIES:
            opt_list.add_option(Option(f"── {cat_name} ──", disabled=True))
            for g in glyphs:
                if g in seen_glyphs:
                    continue
                seen_glyphs.add(g)
                cp_code = UNICODE_TO_CP437.get(g)
                if cp_code is not None:
                    prompt = f"  '{g}'   (ASCII: {cp_code} -> {{ascii:{cp_code}}})"
                else:
                    prompt = f"  '{g}'   (Unicode: {ord(g[0]):d} / 0x{ord(g[0]):04x})"
                opt_list.add_option(Option(prompt, id=g))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(str(event.option.id))

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
        border: thick $accent;
        background: $surface;
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
        color: $accent;
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
        background: $accent;
        color: $text;
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

    def __init__(self, current_name: str):
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with bashmenu_ui.ModalFrame(id="modal_frame"):
            with Horizontal(id="dialog_hrow"):
                with Vertical(id="dialog"):
                    with Horizontal(id="title_bar"):
                        yield Label("Save Theme to Disk", id="title")
                        yield Label(
                            bashmenu_ui.format_close_button_label(),
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
# LIVE PREVIEW CANVAS WIDGET
# ==============================================================================


class ThemePreviewWidget(Static):
    """Simulated miniature live preview of BashMenu rendering the active theme."""

    def __init__(self, theme_dict: dict, theme_name: str = "custom", **kwargs):
        super().__init__(**kwargs)
        self.theme_dict = theme_dict
        self.theme_name = theme_name

    def update_theme(self, theme_dict: dict, theme_name: str = "custom") -> None:
        """Update active theme definition and trigger instant re-render."""
        self.theme_dict = theme_dict
        self.theme_name = theme_name
        self.refresh()

    def render(self) -> Text:
        """Render complete simulated BashMenu frame with active borders and styles."""
        w = 56
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

        b_tl = _resolve(borders.get("border_top_left", "┌"))
        b_tr = _resolve(borders.get("border_top_right", "┐"))
        b_bl = _resolve(borders.get("border_bottom_left", "└"))
        b_br = _resolve(borders.get("border_bottom_right", "┘"))
        b_h_top = _resolve(borders.get("border_horizontal_top", borders.get("border_horizontal", "─")))
        b_h_bot = _resolve(borders.get("border_horizontal_bottom", borders.get("border_horizontal", "─")))
        b_v_left = _resolve(borders.get("border_vertical_left", borders.get("border_vertical", "│")))
        b_v_right = _resolve(borders.get("border_vertical_right", borders.get("border_vertical", "│")))
        b_tee_l = _resolve(borders.get("left_tee", "├"))
        b_tee_r = _resolve(borders.get("right_tee", "┤"))
        b_cap_l = _resolve(borders.get("title_left_cap", "["))
        b_cap_r = _resolve(borders.get("title_right_cap", "]"))
        b_gt_border = _resolve(borders.get("gutter_border", "─"))
        b_gt_sep = _resolve(borders.get("gutter_separator", "│"))
        b_gt_l_tee = _resolve(borders.get("gutter_left_tee", "├"))
        b_gt_r_tee = _resolve(borders.get("gutter_right_tee", "┤"))
        b_gt_top_tee = _resolve(borders.get("gutter_top_tee", "┬"))
        b_gt_bot_tee = _resolve(borders.get("gutter_bottom_tee", "┴"))
        shadow_ch = _resolve(borders.get("shadow_char", "░"))

        indicator = _resolve(self.theme_dict.get("indicator", ">")) or ">"

        divider_def = self.theme_dict.get("divider", {})
        if isinstance(divider_def, dict):
            div_char = _resolve(divider_def.get("char", "─")) or "─"
            div_len = divider_def.get("length", "{window_width}")
        else:
            div_char = "─"
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
        out.append_text(top_line)
        out.append("\n")

        # Helper to wrap inner rows with window borders
        def wrap_line(inner_text: Text) -> Text:
            line = Text()
            line.append(b_v_left + "  ", style=b_style)
            line.append_text(inner_text)
            rem = inner_w - len(inner_text.plain)
            if rem > 0:
                line.append(" " * rem, style=text_style)
            line.append("  " + b_v_right, style=b_style)
            line.append(shadow_ch * 2, style=shadow_style)
            return line

        # Row 1: Option 1 (Unselected)
        r1 = Text()
        r1.append("    [1] ", style=key_style)
        r1.append("Web Applications", style=text_style)
        out.append_text(wrap_line(r1))
        out.append("\n")

        # Row 2: Option 2 (Selected with indicator)
        r2 = Text()
        r2.append(f"  {indicator} [2] System Utilities", style=sel_style)
        rem_sel = inner_w - len(r2.plain)
        if rem_sel > 0:
            r2.append(" " * rem_sel, style=sel_style)
        l2 = Text()
        l2.append(b_v_left + "  ", style=b_style)
        l2.append_text(r2)
        l2.append("  " + b_v_right, style=b_style)
        l2.append(shadow_ch * 2, style=shadow_style)
        out.append_text(l2)
        out.append("\n")

        # Row 3: Divider
        if "{screen_width}" in div_len:
            div_row = Text()
            div_row.append(b_tee_l + div_char * (w - 2) + b_tee_r, style=div_style)
            div_row.append(shadow_ch * 2, style=shadow_style)
            out.append_text(div_row)
        else:
            r_div = Text()
            r_div.append(div_char * inner_w, style=div_style)
            out.append_text(wrap_line(r_div))
        out.append("\n")

        # Row 4: Option 3
        r3 = Text()
        r3.append("    [3] ", style=key_style)
        r3.append("Theme Settings", style=text_style)
        out.append_text(wrap_line(r3))
        out.append("\n")

        # Row 5: Plugin Header
        pl_box_w = max(24, inner_w - 6)
        title_pl = " Weather Dashboard "
        dash_len = max(0, pl_box_w - 3 - len(title_pl))
        r_pl_h = Text(f"┌─{title_pl}" + "─" * dash_len + "┐", style=plug_style)
        out.append_text(wrap_line(r_pl_h))
        out.append("\n")

        # Row 6: Plugin Content
        cont_pl = " 72°F Sunny • Orion Up 3d"
        rem_cont = max(0, pl_box_w - 2 - len(cont_pl))
        r_pl_c = Text(f"│{cont_pl}" + " " * rem_cont + "│", style=plug_style)
        out.append_text(wrap_line(r_pl_c))
        out.append("\n")

        # Row 7: Plugin Bottom
        r_pl_b = Text("└" + "─" * (pl_box_w - 2) + "┘", style=plug_style)
        out.append_text(wrap_line(r_pl_b))
        out.append("\n")

        # Row 8: Gutter Top Border
        avail_both = max(4, w - 11)
        left_gw = 23
        right_gw = avail_both - left_gw
        sep_x = 3 + left_gw + 2
        rem_right = w - 2 - sep_x

        gt_line = Text()
        gt_line.append(b_gt_l_tee + b_gt_border * (sep_x - 1), style=b_style)
        gt_line.append(b_gt_top_tee, style=b_style)
        gt_line.append(b_gt_border * rem_right + b_gt_r_tee, style=b_style)
        gt_line.append(shadow_ch * 2, style=shadow_style)
        out.append_text(gt_line)
        out.append("\n")

        # Row 9: Gutter Content Row
        h_part = Text("[F1] Help | [F2] Themes", style=help_style)
        if h_part.cell_len > left_gw:
            h_part.truncate(left_gw)
        h_pad = max(0, left_gw - h_part.cell_len)
        if h_pad > 0:
            h_part.append(" " * h_pad)

        s_part = Text(f"{self.theme_name} | 12:45", style=gutter_style)
        if s_part.cell_len > right_gw:
            s_part.truncate(right_gw)
        s_pad = max(0, right_gw - s_part.cell_len)
        status_cell = Text(" " * s_pad)
        status_cell.append_text(s_part)

        g_content = Text()
        g_content.append(b_v_left + "  ", style=b_style)
        g_content.append_text(h_part)
        g_content.append("  ", style=text_style)
        g_content.append(b_gt_sep, style=b_style)
        g_content.append("  ", style=text_style)
        g_content.append_text(status_cell)
        g_content.append("  " + b_v_right, style=b_style)
        g_content.append(shadow_ch * 2, style=shadow_style)
        out.append_text(g_content)
        out.append("\n")

        # Row 10: Bottom Border
        bot_line = Text()
        bot_line.append(b_bl + b_h_bot * (sep_x - 1), style=b_style)
        bot_line.append(b_gt_bot_tee, style=b_style)
        bot_line.append(b_h_bot * rem_right + b_br, style=b_style)
        bot_line.append(shadow_ch * 2, style=shadow_style)
        out.append_text(bot_line)
        out.append("\n")

        # Row 11: Bottom Drop Shadow
        bot_shadow = Text()
        bot_shadow.append("  " + shadow_ch * w, style=shadow_style)
        out.append_text(bot_shadow)

        return out


# ==============================================================================
# MAIN THEME EDITOR SCREEN
# ==============================================================================


class ThemeEditScreen(Screen):
    """Interactive Split-Screen Theme Editor Screen."""

    DEFAULT_CSS = """
    ThemeEditScreen {
        layout: vertical;
        background: $surface;
    }
    #header {
        dock: top;
        height: 1;
        width: 100%;
        background: $accent;
        color: $surface;
    }
    #header_title {
        width: 1fr;
        text-align: center;
        text-style: bold;
    }
    #workspace {
        height: 1fr;
        width: 100%;
    }
    #preview_panel {
        width: 1fr;
        height: 100%;
        border: solid $accent;
        padding: 1 1;
        align: center middle;
    }
    #inspector_panel {
        width: 1fr;
        height: 100%;
        border: solid $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    .section_header {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 0;
        background: $accent 15%;
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
        background: $surface;
        color: $accent;
    }
    .footer_row {
        height: 1;
        width: 100%;
        align: center middle;
    }
    .footer_item {
        color: $accent;
    }
    .footer_item:hover {
        text-style: underline;
        color: $text;
    }
    .footer_sep {
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("f1", "show_help", "Help"),
        Binding("question_mark", "show_help", "Help", show=False),
        Binding("c", "pick_color", "Color Picker"),
        Binding("a", "pick_ascii", "ASCII Picker"),
        Binding("t", "clone_theme", "Clone Base"),
        Binding("d", "derive_palettes", "Derive 16/8"),
        Binding("s", "save_theme", "Save"),
        Binding("r", "reset_theme", "Reset"),
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

    def __init__(self, initial_theme: str = "tokyo_night", themes_filepath: str | None = None):
        super().__init__()
        self.themes_filepath = themes_filepath or os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.themes")
        self.raw_themes_data = bashmenu_ui.load_themes_file(self.themes_filepath) or {}
        self.theme_name = initial_theme if initial_theme in self.raw_themes_data else "dracula"
        if not self.raw_themes_data:
            # Fallback basic template
            self.raw_themes_data = {"custom": {"window": {}, "256": {"background": "COLOR_BLACK"}}}
            self.theme_name = "custom"

        # Active editable working copy
        self.current_theme = copy.deepcopy(self.raw_themes_data.get(self.theme_name, {}))
        self._ensure_theme_structure()
        self._initial_theme_snapshot = copy.deepcopy(self.current_theme)
        self._initial_theme_name = self.theme_name
        self._force_dirty = False

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
        self.current_theme.setdefault("window", {})
        self.current_theme.setdefault("divider", {"char": "─", "length": "{window_width}"})
        if "256" in self.current_theme and 256 not in self.current_theme:
            self.current_theme[256] = self.current_theme.pop("256")
        if "16" in self.current_theme and 16 not in self.current_theme:
            self.current_theme[16] = self.current_theme.pop("16")
        if "8" in self.current_theme and 8 not in self.current_theme:
            self.current_theme[8] = self.current_theme.pop("8")
        self.current_theme.setdefault(256, {})

        # Fill default window borders if missing
        for k, v in bashmenu_ui.DEFAULT_WINDOW_BORDER.items():
            self.current_theme["window"].setdefault(k, v)

    def on_mount(self) -> None:
        """Initialize mounted state and baseline snapshot after widgets are composed."""
        self._mounted_ready = True
        self._initial_theme_snapshot = copy.deepcopy(self.current_theme)
        self._initial_theme_name = self.theme_name
        self._force_dirty = False
        self._sync_preview()

    def compose(self) -> ComposeResult:
        with Vertical(id="header"):
            yield Label(f"BashMenu Theme Editor — [{self.theme_name}]", id="header_title")

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
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[c] Pick Color", classes="footer_item", id="lbl_color", markup=False)
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[a] ASCII/Glyphs", classes="footer_item", id="lbl_ascii", markup=False)
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[t] Clone/Base", classes="footer_item", id="lbl_clone", markup=False)
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[d] Derive 16/8", classes="footer_item", id="lbl_derive", markup=False)
            with Horizontal(classes="footer_row"):
                yield Label("[s] Save Theme", classes="footer_item", id="lbl_save", markup=False)
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[r] Reset", classes="footer_item", id="lbl_reset", markup=False)
                yield Label("  |  ", classes="footer_sep", markup=False)
                yield Label("[q/ESC] Exit", classes="footer_item", id="lbl_exit", markup=False)

    def _sync_preview(self) -> None:
        """Propagate current theme changes to the preview canvas widget."""
        preview = self.query_one("#live_preview", ThemePreviewWidget)
        preview.update_theme(self.current_theme, theme_name=self.theme_name)
        h_title = self.query_one("#header_title", Label)
        dirty_flag = " *" if self.is_dirty else ""
        h_title.update(f"BashMenu Theme Editor — [{self.theme_name}]{dirty_flag}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle live input changes and synchronize preview instantly."""
        if not getattr(self, "_mounted_ready", False):
            return

        inp_id = event.input.id
        val = event.value.strip()

        if not inp_id:
            return

        if inp_id == "prop_indicator":
            self.current_theme["indicator"] = val
        elif inp_id == "prop_shadow_char":
            self.current_theme["window"]["shadow_char"] = val
        elif inp_id.startswith("prop_divider_"):
            sub_k = inp_id.replace("prop_divider_", "")
            self.current_theme.setdefault("divider", {})[sub_k] = val
        elif inp_id.startswith("prop_"):
            border_k = inp_id.replace("prop_", "")
            self.current_theme["window"][border_k] = val
        elif inp_id.startswith("color_"):
            tok = inp_id.replace("color_", "")
            pal = self.current_theme.setdefault(256, {})
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
            else:
                curr_val = self.current_theme.get("window", {}).get(prop_k, "")

            def _on_ascii_picked(glyph: str | None) -> None:
                if glyph:
                    target_input_id = f"#prop_{prop_k}"
                    with contextlib.suppress(Exception):
                        inp = self.query_one(target_input_id, Input)
                        inp.value = glyph

            self.app.push_screen(AsciiPickerModal(prop_k, curr_val), _on_ascii_picked)

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

            self.app.push_screen(ColorPickerModal(tok, curr_val, bg_color_val=bg_val), _on_color_picked)

    def on_click(self, event: Any) -> None:
        """Handle mouse clicks on interactive footer shortcut items."""
        widget = getattr(event, "widget", None) or getattr(event, "target", None)
        if not widget:
            return
        w_id = getattr(widget, "id", None)
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
        elif w_id == "lbl_save":
            self.action_save_theme()
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

            self.app.push_screen(ColorPickerModal(tok, curr_val, bg_color_val=bg_val), _cb)
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

            self.app.push_screen(ColorPickerModal(tok, curr_val, bg_color_val=bg_val), _cb_def)

    def action_pick_ascii(self) -> None:
        """Trigger box-drawing ASCII modal for focused property or default."""
        focused = self.focused
        if focused and isinstance(focused, Input) and focused.id and focused.id.startswith("prop_"):
            prop_k = focused.id.replace("prop_", "")
            curr_val = focused.value

            def _cb_a(g):
                if g:
                    focused.value = g

            self.app.push_screen(AsciiPickerModal(prop_k, curr_val), _cb_a)
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

            self.app.push_screen(AsciiPickerModal(prop_k, curr_val), _cb_a_def)

    def action_clone_theme(self) -> None:
        """Open theme picker to clone an existing theme as a base."""
        def _on_theme_chosen(theme_key: str | None) -> None:
            if theme_key and theme_key in self.raw_themes_data:
                self.theme_name = f"{theme_key}_custom"
                self.current_theme = copy.deepcopy(self.raw_themes_data[theme_key])
                self._ensure_theme_structure()
                self.is_dirty = True
                self._populate_all_inputs()
                self._sync_preview()

        self.app.push_screen(bashmenu_ui.ThemePickerModalScreen(self.theme_name), _on_theme_chosen)

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

            for k, _ in self.BORDER_PROPERTIES:
                b_val = str(self.current_theme.get("window", {}).get(k, ""))
                self.query_one(f"#prop_{k}", Input).value = b_val

            pal_256 = self._get_pal_256()
            for tok in self.COLOR_TOKENS:
                c_val = str(pal_256.get(tok, -1))
                self.query_one(f"#color_{tok}", Input).value = c_val

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
            )
        )

    def action_reset_theme(self) -> None:
        """Revert working copy to loaded state."""
        if self.theme_name in self.raw_themes_data:
            self.current_theme = copy.deepcopy(self.raw_themes_data[self.theme_name])
            self._ensure_theme_structure()
            self.is_dirty = False
            self._populate_all_inputs()
            self._sync_preview()

    def action_save_theme(self) -> None:
        """Open Save Modal and persist validated theme to bashmenu.themes."""
        def _on_save_confirmed(result: tuple[str, bool] | None) -> None:
            if not result:
                return
            new_name, set_active = result
            self.theme_name = new_name

            # Ensure 16 and 8 fallback tiers exist before saving
            if 16 not in self.current_theme or 8 not in self.current_theme:
                pal_256 = self._get_pal_256()
                p16, p8 = auto_derive_fallback_depths(pal_256)
                self.current_theme[16] = p16
                self.current_theme[8] = p8

            # Save to bashmenu.themes
            try:
                self.raw_themes_data[self.theme_name] = copy.deepcopy(self.current_theme)

                # Validate with ymlcheck before writing to disk
                errs = []
                for k_depth, v_keys in self.current_theme.items():
                    depth_str = str(k_depth)
                    if depth_str == "window":
                        errs.extend(ymlcheck.validate_window_section(v_keys, f"{self.theme_name}.window"))
                    elif depth_str == "divider":
                        errs.extend(ymlcheck.validate_divider_section(v_keys, f"{self.theme_name}.divider"))
                    elif depth_str in ("256", "16", "8"):
                        errs.extend(ymlcheck.validate_depth_section(depth_str, v_keys, self.theme_name))

                if errs:
                    err_msg = "\n".join(f"- {e}" for e in errs)
                    self.app.push_screen(
                        bashmenu_ui.MessageModalScreen(
                            "Theme Validation Error",
                            f"Theme schema issues detected:\n{err_msg}",
                        )
                    )
                    return

                # Serialize cleanly to bashmenu.themes
                with open(self.themes_filepath, "w", encoding="utf-8") as f:
                    yaml.dump(self.raw_themes_data, f, sort_keys=False, default_flow_style=False)

                # Optionally set as active theme in bashmenu.yml
                if set_active:
                    cfg, _ = bashmenu.load_config()
                    cfg["theme"] = self.theme_name
                    cfg_path = os.path.join(bashmenu.BASHMENU_DIR, "bashmenu.yml")
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        yaml.dump(cfg, f, sort_keys=False, default_flow_style=False)

                self.is_dirty = False
                self._sync_preview()
                self.app.push_screen(
                    bashmenu_ui.MessageModalScreen(
                        "Theme Saved",
                        f"Successfully saved theme '{self.theme_name}' to disk!\n"
                        + ("Active theme updated in bashmenu.yml." if set_active else ""),
                    )
                )
            except Exception as e:  # noqa: BLE001
                self.app.push_screen(
                    bashmenu_ui.MessageModalScreen("Save Failed", f"Error saving theme to disk:\n{e}")
                )

        self.app.push_screen(SaveThemeModal(self.theme_name), _on_save_confirmed)

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

    def __init__(self, theme_name: str = "tokyo_night", **kwargs):
        super().__init__(**kwargs)
        self.theme_name = theme_name

    def on_mount(self) -> None:
        self.push_screen(ThemeEditScreen(initial_theme=self.theme_name))


def main() -> None:
    parser = argparse.ArgumentParser(description="BashMenu Theme Editor")
    parser.add_argument("theme", nargs="?", default="tokyo_night", help="Theme name to edit or clone")
    args = parser.parse_args()

    app = ThemeEditApp(theme_name=args.theme)
    app.run()


if __name__ == "__main__":
    main()
