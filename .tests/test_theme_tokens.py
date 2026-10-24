#!/usr/bin/env python3
"""
test_theme_tokens.py - Unit tests for granular theme color tokens across
Menu Editor, Text Editor, and Modals, background inheritance, and single-color tokens.
"""

import os
import sys
import unittest
from unittest import mock

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.color import Color
from rich.style import Style
from textual.widgets import Button, Input, Label

import bashedit
import bashmenu_ui
import menuedit
import themeedit


class TestThemeTokens(unittest.TestCase):
    """Test suite for granular theme color tokens and background inheritance."""

    def test_is_single_color_token(self):
        """Verify is_single_color_token identifies single-color tokens vs pair tokens."""
        # Single-color tokens
        self.assertTrue(themeedit.is_single_color_token("background"))
        self.assertTrue(themeedit.is_single_color_token("editor_tab_bar"))
        self.assertTrue(themeedit.is_single_color_token("editor__tab_bar"))
        self.assertTrue(themeedit.is_single_color_token("tab_bar"))
        self.assertTrue(themeedit.is_single_color_token("editor_background"))
        self.assertTrue(themeedit.is_single_color_token("editor__background"))
        self.assertTrue(themeedit.is_single_color_token("menu_editor_background"))
        self.assertTrue(themeedit.is_single_color_token("modals_background"))

        # Pair tokens
        self.assertFalse(themeedit.is_single_color_token("editor_line_number"))
        self.assertFalse(themeedit.is_single_color_token("line_number"))
        self.assertFalse(themeedit.is_single_color_token("gutter"))
        self.assertFalse(themeedit.is_single_color_token("editor_eof_tilde"))
        self.assertFalse(themeedit.is_single_color_token("eof_tilde"))
        self.assertFalse(themeedit.is_single_color_token("editor_tab_active"))
        self.assertFalse(themeedit.is_single_color_token("editor_tab_inactive"))
        self.assertFalse(themeedit.is_single_color_token("editor_tab_close"))
        self.assertFalse(themeedit.is_single_color_token("editor_tab_add"))
        self.assertFalse(themeedit.is_single_color_token("menu_editor_tree_guide"))
        self.assertFalse(themeedit.is_single_color_token("menu_editor_label"))
        self.assertFalse(themeedit.is_single_color_token("menu_editor_input"))
        self.assertFalse(themeedit.is_single_color_token("modals_input"))
        self.assertFalse(themeedit.is_single_color_token("modals_footer"))
        self.assertFalse(themeedit.is_single_color_token("modals_border"))

    def test_color_picker_modal_is_pair(self):
        """Verify ColorPickerModal dynamically sets is_pair based on token name."""
        picker_tab_bar = themeedit.ColorPickerModal(token_name="tab_bar", current_val="COLOR_BLACK")
        self.assertFalse(picker_tab_bar.is_pair)

        picker_bg = themeedit.ColorPickerModal(token_name="editor_background", current_val=0)
        self.assertFalse(picker_bg.is_pair)

        picker_line_no = themeedit.ColorPickerModal(token_name="editor_line_number", current_val=[244, -1])
        self.assertTrue(picker_line_no.is_pair)

        picker_gutter = themeedit.ColorPickerModal(token_name="gutter", current_val=[238, -1])
        self.assertTrue(picker_gutter.is_pair)

    def test_init_theme_colors_sub_palettes(self):
        """Verify init_theme_colors builds editor, menu_editor, and modals sub-palettes."""
        raw_theme = {
            "background": "COLOR_BLACK",
            "title": [201, -1],
            "border": [61, -1],
            "text": [255, -1],
            "selection": [255, 61],
            "gutter": [238, -1],
            "footer": [245, -1],
        }

        styles = bashmenu_ui.init_theme_colors("test_custom", raw_theme_data={"test_custom": raw_theme})

        # Check sub-palette structures exist
        self.assertIn("editor", styles)
        self.assertIn("menu_editor", styles)
        self.assertIn("modals", styles)

        editor_styles = styles["editor"]
        menu_styles = styles["menu_editor"]
        mod_styles = styles["modals"]

        # Default fallback for editor
        self.assertIn("line_number", editor_styles)
        self.assertIn("eof_tilde", editor_styles)
        self.assertIn("tab_bar", editor_styles)
        self.assertIn("tab_active", editor_styles)
        self.assertIn("tab_inactive", editor_styles)
        self.assertIn("tab_close", editor_styles)
        self.assertIn("tab_add", editor_styles)

        # Invariant: spec[1] == -1 or "inherit" must have bgcolor=None so canvas background is inherited
        # line_number falls back to gutter [238, -1]
        self.assertIsNone(editor_styles["line_number"].bgcolor)
        self.assertIsNone(editor_styles["eof_tilde"].bgcolor)

        # Default fallback for menu_editor
        self.assertIn("tree_guide", menu_styles)
        self.assertIn("label", menu_styles)
        self.assertIn("input", menu_styles)
        self.assertIn("button_save", menu_styles)
        self.assertIn("button_delete", menu_styles)

        # Default fallback for modals
        self.assertIn("background", mod_styles)
        self.assertIn("border", mod_styles)
        self.assertIn("title", mod_styles)
        self.assertIn("text", mod_styles)
        self.assertIn("input", mod_styles)
        self.assertIn("footer", mod_styles)
        self.assertIn("scrollbar", mod_styles)

    def test_init_theme_colors_custom_overrides(self):
        """Verify explicit editor/menu_editor/modals overrides in theme dict are respected."""
        raw_theme = {
            "background": "COLOR_BLACK",
            "title": [201, -1],
            "border": [61, -1],
            "text": [255, -1],
            "gutter": [238, -1],
            "editor": {
                "line_number": [196, 234],
                "tab_bar": "COLOR_BLUE",
                "eof_tilde": [100, -1],
            },
            "menu_editor": {
                "tree_guide": [45, -1],
                "label": [220, -1],
            },
            "modals": {
                "background": "COLOR_WHITE",
                "input": [16, 250],
            },
        }

        styles = bashmenu_ui.init_theme_colors("test_custom_override", raw_theme_data={"test_custom_override": raw_theme})

        editor_styles = styles["editor"]
        self.assertEqual(editor_styles["line_number"].color.name, "color(196)")
        self.assertEqual(editor_styles["line_number"].bgcolor.name, "color(234)")
        self.assertIsNone(editor_styles["eof_tilde"].bgcolor)

        menu_styles = styles["menu_editor"]
        self.assertEqual(menu_styles["tree_guide"].color.name, "color(45)")
        self.assertEqual(menu_styles["label"].color.name, "color(220)")

        mod_styles = styles["modals"]
        self.assertEqual(mod_styles["input"].color.name, "color(16)")
        self.assertEqual(mod_styles["input"].bgcolor.name, "color(250)")

    def test_bashedit_editor_widget_render_tokens(self):
        """Verify EditorWidget render uses line_number and eof_tilde tokens without background mismatch."""
        custom_theme = {
            "background": Style(color="white", bgcolor="black"),
            "text": Style(color="white"),
            "gutter": Style(color="grey42", bgcolor=None),
            "editor": {
                "line_number": Style(color="yellow", bgcolor=None),
                "eof_tilde": Style(color="cyan", bgcolor=None),
                "cursor_line": Style(bold=True),
            },
        }
        ed = bashedit.EditorWidget(lines=["print('hello')"], theme=custom_theme)

        rendered = ed.render()
        text_lines = rendered.split("\n")
        self.assertGreaterEqual(len(text_lines), 2)

        # Line 1 should have line number ' 1 '
        self.assertIn(" 1 ", text_lines[0].plain)
        # Remaining lines should have '~'
        self.assertTrue(any("~" in line.plain for line in text_lines[1:]))

    def test_apply_modal_theme_with_modals_tokens(self):
        """Verify apply_modal_theme applies modals sub-palette styles to dialog, inputs, and footers."""
        dialog = mock.MagicMock()
        dialog.styles = mock.MagicMock()
        title = mock.MagicMock(spec=Label)
        title.styles = mock.MagicMock()
        title.renderable = "Test Title"
        inp = mock.MagicMock(spec=Input)
        inp.styles = mock.MagicMock()

        def fake_query_one(selector, *args):
            if selector == "#dialog":
                return dialog
            if selector == "#title":
                return title
            msg = f"Not found: {selector}"
            raise KeyError(msg)

        def fake_query(selector_cls):
            if selector_cls is Input:
                return [inp]
            return []

        screen = mock.MagicMock()
        screen.query_one.side_effect = fake_query_one
        screen.query.side_effect = fake_query

        custom_theme = {
            "background": Style(bgcolor=Color.parse("color(0)")),
            "border": Style(color=Color.parse("color(61)")),
            "title": Style(color=Color.parse("color(201)")),
            "text": Style(color=Color.parse("color(255)")),
            "modals": {
                "background": Style(bgcolor=Color.parse("color(235)")),
                "border": Style(color=Color.parse("color(196)")),
                "title": Style(color=Color.parse("color(46)")),
                "input": Style(color=Color.parse("color(250)"), bgcolor=Color.parse("color(236)")),
                "footer": Style(color=Color.parse("color(240)")),
            },
        }

        bashmenu_ui.apply_modal_theme(screen, theme=custom_theme)

        # Verify modal background was set to #dialog using modals.background (color 235)
        self.assertEqual(dialog.styles.background, bashmenu_ui.parse_css_color("color(235)"))
        # Verify title color was set using modals.title (color 46)
        self.assertEqual(title.styles.color, bashmenu_ui.parse_css_color("color(46)"))
        # Verify input was styled using modals.input
        self.assertEqual(inp.styles.color, bashmenu_ui.parse_css_color("color(250)"))
        self.assertEqual(inp.styles.background, bashmenu_ui.parse_css_color("color(236)"))

    def test_apply_button_theme_with_modals_tokens(self):
        """Verify apply_button_theme uses modals overrides when available."""
        custom_theme = {
            "button_primary": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(21)")),
            "button_error": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(196)")),
            "button_cancel": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(240)")),
            "modals": {
                "button_confirm": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(46)")),
                "button_danger": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(160)")),
                "button_cancel": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(236)")),
            },
        }

        btn_confirm = mock.MagicMock(spec=Button)
        btn_confirm.styles = mock.MagicMock()
        bashmenu_ui.apply_button_theme(btn_confirm, theme=custom_theme, button_type="button_confirm")
        self.assertEqual(btn_confirm.styles.background, bashmenu_ui.parse_css_color("color(46)"))

        btn_danger = mock.MagicMock(spec=Button)
        btn_danger.styles = mock.MagicMock()
        bashmenu_ui.apply_button_theme(btn_danger, theme=custom_theme, button_type="button_danger")
        self.assertEqual(btn_danger.styles.background, bashmenu_ui.parse_css_color("color(160)"))

        btn_cancel = mock.MagicMock(spec=Button)
        btn_cancel.styles = mock.MagicMock()
        bashmenu_ui.apply_button_theme(btn_cancel, theme=custom_theme, button_type="button_cancel")
        self.assertEqual(btn_cancel.styles.background, bashmenu_ui.parse_css_color("color(236)"))

    def test_bashedit_tab_styles_application(self):
        """Verify _apply_tab_styles correctly styles tab bar and tab classes."""
        screen = mock.MagicMock()
        tab_bar = mock.MagicMock()
        tab_bar.styles = mock.MagicMock()
        screen.query_one.return_value = tab_bar

        tab_active = mock.MagicMock()
        tab_active.styles = mock.MagicMock()
        tab_inactive = mock.MagicMock()
        tab_inactive.styles = mock.MagicMock()
        tab_close = mock.MagicMock()
        tab_close.styles = mock.MagicMock()
        tab_add = mock.MagicMock()
        tab_add.styles = mock.MagicMock()

        def fake_query(selector):
            if selector == ".editor_tab_active":
                return [tab_active]
            if selector == ".editor_tab":
                return [tab_inactive]
            if selector == ".editor_tab_close":
                return [tab_close]
            if selector == ".editor_tab_add":
                return [tab_add]
            return []

        screen.query.side_effect = fake_query

        custom_theme = {
            "editor": {
                "tab_bar": Style(bgcolor=Color.parse("color(234)")),
                "tab_active": Style(color=Color.parse("color(255)"), bgcolor=Color.parse("color(61)")),
                "tab_inactive": Style(color=Color.parse("color(245)"), bgcolor=Color.parse("color(238)")),
                "tab_close": Style(color=Color.parse("color(196)")),
                "tab_add": Style(color=Color.parse("color(46)")),
            }
        }

        screen.theme_styles = custom_theme
        bashedit.BashEditScreen._apply_tab_styles(screen)

        self.assertEqual(tab_bar.styles.background, bashmenu_ui.parse_css_color("color(234)"))
        self.assertEqual(tab_active.styles.color, bashmenu_ui.parse_css_color("color(255)"))
        self.assertEqual(tab_active.styles.background, bashmenu_ui.parse_css_color("color(61)"))
        self.assertEqual(tab_inactive.styles.color, bashmenu_ui.parse_css_color("color(245)"))
        self.assertEqual(tab_close.styles.color, bashmenu_ui.parse_css_color("color(196)"))
        self.assertEqual(tab_add.styles.color, bashmenu_ui.parse_css_color("color(46)"))
        # Close and add buttons with bgcolor=None fall back to tab_bar background
        self.assertEqual(tab_close.styles.background, bashmenu_ui.parse_css_color("color(234)"))
        self.assertEqual(tab_add.styles.background, bashmenu_ui.parse_css_color("color(234)"))

    def test_init_theme_colors_editor_gutter_fallback(self):
        """Verify editor.gutter is used as fallback for line_number and eof_tilde before top-level gutter."""
        raw_theme = {
            "background": "COLOR_BLACK",
            "gutter": [238, -1],
            "editor": {
                "gutter": [214, 235],
            },
        }
        styles = bashmenu_ui.init_theme_colors("test_ed_gutter", raw_theme_data={"test_ed_gutter": raw_theme})
        ed_styles = styles["editor"]
        self.assertEqual(ed_styles["line_number"].color.name, "color(214)")
        self.assertEqual(ed_styles["line_number"].bgcolor.name, "color(235)")
        self.assertEqual(ed_styles["eof_tilde"].color.name, "color(214)")
        self.assertEqual(ed_styles["eof_tilde"].bgcolor.name, "color(235)")

    def test_menuedit_and_bashedit_header_footer_status_background_inheritance(self):
        """Verify MenuEditScreen and BashEditScreen inherit background when header/footer/status bgcolor is None (-1)."""
        raw_theme = {
            "background": 16,
            "header": [251, -1],
            "footer": [245, -1],
            "menu_editor": {
                "background": 233,
                "header": [251, -1],
                "footer": [245, -1],
            },
            "editor": {
                "background": 234,
                "header": [251, -1],
                "status": [250, -1],
                "footer": [245, -1],
            },
        }
        styles = bashmenu_ui.init_theme_colors("test_hdr_bg", raw_theme_data={"test_hdr_bg": raw_theme})

        # 1. Verify MenuEditScreen.apply_theme
        me_widgets = {
            "#workspace": mock.MagicMock(),
            "#tree_panel": mock.MagicMock(),
            "#inspector_panel": mock.MagicMock(),
            "#tree": mock.MagicMock(),
            "#inspector_content": mock.MagicMock(),
            "#header": mock.MagicMock(),
            "#header_title": mock.MagicMock(),
            "#inspector_title": mock.MagicMock(),
            "#footer": mock.MagicMock(),
            "#btn_close_x": mock.MagicMock(),
        }
        me_footer_item = mock.MagicMock()
        me_screen = mock.MagicMock()
        me_screen.app.batch_update.return_value.__enter__ = mock.MagicMock()
        me_screen.app.batch_update.return_value.__exit__ = mock.MagicMock()
        me_screen.query_one.side_effect = lambda sel, *a: me_widgets[sel]
        me_screen.query.side_effect = lambda sel: [me_footer_item] if sel == ".footer_item" else []

        with mock.patch("bashmenu_ui.resolve_theme_dict", return_value=styles), mock.patch(
            "bashmenu_ui.apply_theme_to_textual_borders"
        ):
            menuedit.MenuEditScreen.apply_theme(me_screen)

        expected_me_bg = bashmenu_ui.parse_css_color("color(233)")
        self.assertEqual(me_widgets["#header"].styles.background, expected_me_bg)
        self.assertEqual(me_widgets["#footer"].styles.background, expected_me_bg)
        self.assertEqual(me_widgets["#header_title"].styles.color, bashmenu_ui.parse_css_color("color(251)"))
        self.assertEqual(me_footer_item.styles.color, bashmenu_ui.parse_css_color("color(245)"))

        # 2. Verify BashEditScreen.apply_theme
        be_widgets = {
            "#editor_main": mock.MagicMock(),
            "#editor_widget": mock.MagicMock(),
            "#editor_header_bar": mock.MagicMock(),
            "#editor_header": mock.MagicMock(),
            "#editor_divider": mock.MagicMock(),
            "#editor_status": mock.MagicMock(),
            "#editor_legend": mock.MagicMock(),
            "#btn_close_x": mock.MagicMock(),
            "#editor_tab_bar": mock.MagicMock(),
        }
        be_footer_item = mock.MagicMock()
        be_screen = mock.MagicMock()
        be_screen.app.batch_update.return_value.__enter__ = mock.MagicMock()
        be_screen.app.batch_update.return_value.__exit__ = mock.MagicMock()
        be_screen.query_one.side_effect = lambda sel, *a: be_widgets[sel]
        be_screen.query.side_effect = lambda sel: [be_footer_item] if sel == ".footer_item" else []

        with mock.patch("bashmenu_ui.resolve_theme_dict", return_value=styles), mock.patch(
            "bashmenu_ui.apply_theme_to_textual_borders"
        ):
            bashedit.BashEditScreen.apply_theme(be_screen)

        expected_ed_bg = bashmenu_ui.parse_css_color("color(234)")
        self.assertEqual(be_widgets["#editor_header_bar"].styles.background, expected_ed_bg)
        self.assertEqual(be_widgets["#editor_status"].styles.background, expected_ed_bg)
        self.assertEqual(be_widgets["#editor_legend"].styles.background, expected_ed_bg)
        self.assertEqual(be_widgets["#editor_header"].styles.color, bashmenu_ui.parse_css_color("color(251)"))
        self.assertEqual(be_footer_item.styles.color, bashmenu_ui.parse_css_color("color(245)"))

    def test_preview_widget_menu_and_text_editor_background_inheritance(self):
        """Verify ThemePreviewWidget applies menu_editor.background and editor.background when token bgcolor is None."""
        raw_theme = {
            256: {
                "background": 16,
                "header": [251, -1],
                "menu_editor": {
                    "background": 233,
                    "header": [251, -1],
                    "text": [250, -1],
                },
                "editor": {
                    "background": 234,
                    "header": [251, -1],
                    "text": [250, -1],
                },
            }
        }
        preview = themeedit.ThemePreviewWidget(raw_theme, theme_name="custom_bg_test", preview_mode="menu_editor")

        # Render menu_editor preview
        me_text = preview.render()
        me_lines = me_text.split("\n")
        # Line 0 is the header line; verify its spans carry color(233) background
        self.assertTrue(
            any(span.style and getattr(span.style.bgcolor, "name", None) == "color(233)" for span in me_lines[0].spans)
        )

        # Render text_editor preview
        preview.set_preview_mode("text_editor")
        ed_text = preview.render()
        ed_lines = ed_text.split("\n")
        # Line 0 is the header line; verify its spans carry color(234) background
        self.assertTrue(
            any(span.style and getattr(span.style.bgcolor, "name", None) == "color(234)" for span in ed_lines[0].spans)
        )


if __name__ == "__main__":
    unittest.main()
