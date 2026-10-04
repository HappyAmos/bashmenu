#!/usr/bin/env python3
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bashmenu
import bashmenu_ui
import ymlcheck


class TestImprovements(unittest.TestCase):
    def test_date_time_12_short_interpolation(self):
        config = bashmenu.load_config()[0]
        text = "Current: {date_time_12_short}"
        result = bashmenu.interpolate_placeholders(text, config)
        self.assertNotIn("{date_time_12_short}", result)
        self.assertTrue("AM" in result or "PM" in result)

    def test_file_picker_allow_new(self):
        fp = bashmenu_ui.FilePickerModalScreen("Test Picker", mode="file", allow_new=True)
        self.assertTrue(fp.allow_new)
        # Bindings should include 'n'
        binding_keys = [b.key for b in fp.BINDINGS]
        self.assertIn("n", binding_keys)

    def test_theme_picker_modal(self):
        tp = bashmenu_ui.ThemePickerModalScreen(current_theme="dracula")
        self.assertEqual(tp.current_theme, "dracula")
        binding_keys = [b.key for b in tp.BINDINGS]
        self.assertIn("escape", binding_keys)

    def test_ymlcheck_modes(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        theme_path = os.path.join(base_dir, "bashmenu.themes")
        config_path = os.path.join(base_dir, "bashmenu.yml")
        menu_path = os.path.join(base_dir, "bashmenu.mnu")

        self.assertTrue(ymlcheck.validate_yaml_syntax(config_path))
        self.assertTrue(ymlcheck.validate_yaml_syntax(menu_path))
        self.assertTrue(ymlcheck.validate_theme_file(theme_path))
        self.assertTrue(ymlcheck.validate_config_file(config_path))
        self.assertTrue(ymlcheck.validate_menu_file(menu_path))

    def test_bashedit_character_input(self):
        import asyncio

        import textual.keys as k
        from textual.app import App

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_input_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")

                # Specifically test period and letter f (which were previously blocked by event.key.startswith('f'))
                for test_char in [".", "f", "F", " ", "/", "-", "a", "Z", "0", "@"]:
                    ed.lines = [""]
                    ed.cursor_x = 0
                    ed.cursor_y = 0
                    key_name = k._character_to_key(test_char)
                    await pilot.press(key_name)
                    self.assertEqual(ed.lines[0], test_char, f"Character '{test_char}' (key '{key_name}') was blocked!")

        asyncio.run(run_input_checks())

    def test_bashedit_mouse_scroll_and_page_nav(self):
        import asyncio

        from textual.app import App
        from textual.events import MouseScrollDown, MouseScrollUp

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_scroll_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")
                ed.lines = [f"Line {i}" for i in range(100)]
                ed.top_line = 0
                ed.cursor_y = 0

                # Test mouse wheel scroll down
                ed.post_message(
                    MouseScrollDown(ed, x=10, y=5, delta_x=0, delta_y=1, button=4, shift=False, meta=False, ctrl=False)
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 3)

                # Test mouse wheel scroll up
                ed.post_message(
                    MouseScrollUp(ed, x=10, y=5, delta_x=0, delta_y=-1, button=5, shift=False, meta=False, ctrl=False)
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 0)

                # Test pagedown and pageup keys
                await pilot.press("pagedown")
                self.assertTrue(ed.top_line > 0)
                await pilot.press("pageup")
                self.assertEqual(ed.top_line, 0)

                # Test scrolling last line all the way to top of viewport
                ed.scroll_lines_down(200)
                self.assertEqual(ed.top_line, 99)
                self.assertEqual(ed.cursor_y, 99)
                lines_rendered = ed.render().plain.splitlines()
                self.assertIn("Line 99", lines_rendered[0])
                self.assertEqual(lines_rendered[1], "~")
                self.assertNotIn("~Line 99", lines_rendered[0])

        asyncio.run(run_scroll_checks())

    def test_theme_submenu_divider(self):
        sub = bashmenu.build_dynamic_theme_submenu()
        self.assertIn("options", sub)
        options = sub["options"]
        self.assertTrue(len(options) > 2)
        # First item must be a divider
        first_item = options[0]
        self.assertEqual(first_item.get("type"), "divider")
        self.assertEqual(first_item.get("length"), "{window_width}")
        # Second item must be a theme item
        second_item = options[1]
        self.assertIn("set_theme", second_item)

    def test_f1_help_markdown(self):
        import asyncio

        from rich.markdown import Markdown
        from textual.app import App

        class TestApp(App):
            def on_mount(self):
                self.push_screen(bashmenu.BashMenuScreen())

        async def run_f1_check():
            app = TestApp()
            async with app.run_test() as pilot:
                await pilot.press("f1")
                modal = app.screen
                self.assertIsInstance(modal, bashmenu_ui.MessageModalScreen)
                msg_widget = modal.query_one("#message")
                from textual.widgets import Markdown as TextualMarkdown
                self.assertTrue(
                    isinstance(msg_widget, TextualMarkdown)
                    or isinstance(getattr(msg_widget, "content", None), Markdown)
                )

        asyncio.run(run_f1_check())

    def test_help_modal_link_clicked(self):
        import asyncio
        from unittest.mock import patch

        from textual.app import App

        sample_md = (
            "# Help Menu\n\n"
            "- [Jump to Section 2](#section-2)\n"
            "- [Web](https://example.com)\n\n"
            "## Section 2\n\n"
            "Section 2 body."
        )

        class ModalApp(App):
            def on_mount(self):
                self.push_screen(
                    bashmenu_ui.MessageModalScreen("Help", sample_md, is_markdown=True, is_help=True)
                )

        async def run_modal_links():
            app = ModalApp()
            async with app.run_test() as _:
                modal = app.screen
                self.assertIsInstance(modal, bashmenu_ui.MessageModalScreen)
                msg_widget = modal.query_one("#message")
                self.assertIsNotNone(msg_widget)

                # Test anchor link jump
                with patch.object(modal, "goto_anchor") as mock_goto:
                    modal.handle_link("#section-2")
                    mock_goto.assert_called_once_with("section-2")

                # Test external link click
                with patch("subprocess.Popen") as mock_popen, patch("webbrowser.open") as mock_wb:
                    modal.handle_link("https://example.com")
                    self.assertTrue(mock_popen.called or mock_wb.called)

        asyncio.run(run_modal_links())

    def test_bashedit_f12_markdown_toggle(self):
        import asyncio

        from textual.app import App
        from textual.events import MouseScrollDown, MouseScrollUp
        from textual.widgets import Label

        from bashedit import BashEditScreen

        class TestApp(App):
            def on_mount(self):
                self.push_screen(BashEditScreen())

        async def run_markdown_toggle_checks():
            app = TestApp()
            async with app.run_test() as pilot:
                screen = app.screen
                ed = screen.query_one("#editor_widget")
                lbl_md = screen.query_one("#lbl_markdown", Label)

                # 1. Legend label verification
                self.assertIsNotNone(lbl_md)
                self.assertEqual(str(lbl_md.render()), "F12 MD")

                # Set up sample markdown lines
                ed.lines = ["# Title", "", "A paragraph of markdown text.", ""] + [
                    f"- Item {i}" for i in range(50)
                ]
                self.assertFalse(ed.show_markdown)
                self.assertFalse(screen.tabs[screen.active_tab_idx].show_markdown)

                # 2. Press F12 to enable Markdown rendering
                await pilot.press("f12")
                await pilot.pause()
                self.assertTrue(ed.show_markdown)
                self.assertTrue(screen.tabs[screen.active_tab_idx].show_markdown)
                status_lbl = screen.query_one("#editor_status", Label)
                self.assertIn("Markdown rendering enabled", str(status_lbl.render()))

                # 3. Test scrolling in Markdown mode
                ed.top_line = 0
                ed.post_message(
                    MouseScrollDown(
                        ed, x=10, y=5, delta_x=0, delta_y=1, button=4, shift=False, meta=False, ctrl=False
                    )
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 3)

                ed.post_message(
                    MouseScrollUp(
                        ed, x=10, y=5, delta_x=0, delta_y=-1, button=5, shift=False, meta=False, ctrl=False
                    )
                )
                await pilot.pause()
                self.assertEqual(ed.top_line, 0)

                # 4. In Markdown preview mode, typing keys does not mutate lines
                initial_lines = list(ed.lines)
                await pilot.press("a")
                await pilot.pause()
                self.assertEqual(ed.lines, initial_lines)
                self.assertIn("Markdown preview active", str(status_lbl.render()))

                # 5. Press F12 again to disable Markdown rendering
                await pilot.press("f12")
                await pilot.pause()
                self.assertFalse(ed.show_markdown)
                self.assertFalse(screen.tabs[screen.active_tab_idx].show_markdown)
                self.assertIn("Markdown rendering disabled", str(status_lbl.render()))

                # 6. Regular editing resumes
                ed.lines = [""]
                ed.cursor_x = 0
                ed.cursor_y = 0
                await pilot.press("x")
                await pilot.pause()
                self.assertEqual(ed.lines[0], "x")

                # 7. Clicking lbl_markdown toggles markdown
                screen.action_toggle_markdown()
                self.assertTrue(ed.show_markdown)

        asyncio.run(run_markdown_toggle_checks())

    def test_menuedit_inspector_properties(self):
        import menuedit

        screen = menuedit.MenuEditScreen()
        updated_content = []

        class DummyInspector:
            def update(self, content):
                updated_content.append(content)

        screen.query_one = lambda *a, **kw: DummyInspector()

        test_item = {
            "type": "command",
            "title": "Full Property Test",
            "command": "echo test",
            "alt_buffer": True,
            "no_formatting": True,
            "start_dir": "/tmp/testdir",
            "picker": "file_picker",
            "on_yes": "echo yes",
            "on_no": "echo no",
            "show_whitespace": True,
            "external": True,
            "custom_prop": "custom_val",
        }

        screen.update_inspector(test_item)
        self.assertEqual(len(updated_content), 1)
        inspector_text = updated_content[0]

        self.assertIn("Alt Buffer:[/bold cyan] True", inspector_text)
        self.assertIn("No Formatting:[/bold cyan] True", inspector_text)
        self.assertIn("Start Directory:[/bold cyan] /tmp/testdir", inspector_text)
        self.assertIn("Picker Type:[/bold cyan] file_picker", inspector_text)
        self.assertIn("On Yes Action:[/bold green] echo yes", inspector_text)
        self.assertIn("On No Action:[/bold red] echo no", inspector_text)
        self.assertIn("show_whitespace=True", inspector_text)
        self.assertIn("external=True", inspector_text)
        self.assertIn("Extra Properties:[/bold yellow] [dim]custom_prop=custom_val[/dim]", inspector_text)

    def test_menuedit_modal_properties(self):
        import menuedit

        item = {
            "type": "command",
            "title": "Edit Test",
            "command": "echo 1",
            "alt_buffer": True,
            "no_formatting": True,
            "show_whitespace": True,
            "external": True,
        }
        modal = menuedit.ItemEditModal(item)

        class DummyCheckbox:
            def __init__(self, val=True):
                self.value = val

        class DummyInput:
            value = "val"

        class DummyContainer:
            selected_mode_idx = 1

        def dummy_query(selector, *a, **kw):
            if "exec_mode_container" in selector or selector == menuedit.ExecModeContainer:
                return DummyContainer()
            if "chk" in selector:
                return DummyCheckbox(True)
            return DummyInput()

        modal.query_one = dummy_query
        modal.dismiss = lambda item: None
        modal.perform_save()

        self.assertTrue(modal.item.get("alt_buffer"))
        self.assertTrue(modal.item.get("no_formatting"))
        self.assertTrue(modal.item.get("show_whitespace"))
        self.assertTrue(modal.item.get("external"))

    def test_menuedit_two_line_footer(self):
        """Verify MenuEditScreen yields a 2-line footer with two footer_row containers."""
        import asyncio

        from textual.app import App
        from textual.containers import Horizontal, Vertical

        import menuedit

        class TestApp(App):
            def on_mount(self):
                self.push_screen(menuedit.MenuEditScreen())

        async def run_checks():
            app = TestApp()
            async with app.run_test():
                screen = app.screen
                footer = screen.query_one("#footer", Vertical)
                self.assertIsNotNone(footer)
                rows = list(footer.query(".footer_row"))
                self.assertEqual(len(rows), 2)
                for r in rows:
                    self.assertIsInstance(r, Horizontal)
                self.assertIsNotNone(screen.query_one("#lbl_add"))
                self.assertIsNotNone(screen.query_one("#lbl_exit"))

        asyncio.run(run_checks())
        self.assertIn("height: 2;", menuedit.MenuEditScreen.DEFAULT_CSS)
        self.assertIn(".footer_row", menuedit.MenuEditScreen.DEFAULT_CSS)

    def test_menuedit_input_modal_help_and_footer_clicks(self):
        """Verify ItemEditModal F1 shortcut, help modal, and clickable footer items."""
        import menuedit

        modal = menuedit.ItemEditModal({"type": "command", "title": "Test", "command": "ls"})

        actions_called = []
        modal.action_show_help = lambda: actions_called.append("help")
        modal.action_save_changes = lambda: actions_called.append("save")
        modal.action_lookup_ascii = lambda: actions_called.append("ascii")
        modal.action_show_placeholders = lambda: actions_called.append("placeholders")
        modal.action_cancel = lambda: actions_called.append("cancel")

        class DummyWidget:
            def __init__(self, wid):
                self.id = wid
                self.classes = []

        class DummyClickEvent:
            def __init__(self, widget):
                self.widget = widget
                self.target = widget

        modal.on_click(DummyClickEvent(DummyWidget("lbl_modal_help")))
        self.assertIn("help", actions_called)

        modal.on_click(DummyClickEvent(DummyWidget("lbl_modal_save")))
        self.assertIn("save", actions_called)

        modal.on_click(DummyClickEvent(DummyWidget("lbl_modal_ascii")))
        self.assertIn("ascii", actions_called)

        modal.on_click(DummyClickEvent(DummyWidget("lbl_modal_placeholders")))
        self.assertIn("placeholders", actions_called)

        modal.on_click(DummyClickEvent(DummyWidget("lbl_modal_cancel")))
        self.assertIn("cancel", actions_called)

        binding_keys = [b.key for b in modal.BINDINGS]
        self.assertIn("f1", binding_keys)

        self.assertIn("BashMenu Item Properties", menuedit.ITEM_EDIT_HELP_TEXT)
        self.assertIn("Title / Label", menuedit.ITEM_EDIT_HELP_TEXT)
        self.assertIn("alt_buffer", menuedit.ITEM_EDIT_HELP_TEXT)


    def test_editor_theme_background_color_inversion_and_contrast(self):
        """Test editor color pair inversion and neutral contrast against theme background."""
        import bashedit

        # 1. qbasic theme: background is color 19 (#0000af)
        qbasic_theme = bashmenu_ui.init_theme_colors("qbasic")
        ed_qbasic = bashedit.EditorWidget(display_theme_colors=True, theme=qbasic_theme)

        # In title: [226, 19], 19 matches qbasic theme background.
        # It must invert foreground and background colors (blue on yellow).
        spans_title = ed_qbasic.get_line_color_spans("title: [226, 19]")
        self.assertEqual(len(spans_title), 2)
        _s0, _e0, st0 = spans_title[0]
        _s1, _e1, st1 = spans_title[1]
        self.assertEqual(st0.color.name, "#ffff00")
        self.assertIsNone(st0.bgcolor)
        self.assertEqual(st1.color.name, "#0000af")
        self.assertEqual(st1.bgcolor.name, "#ffff00")

        # In border: [51, 19], 19 matches background, inverting with cyan 51.
        spans_border = ed_qbasic.get_line_color_spans("border: [51, 19]")
        self.assertEqual(len(spans_border), 2)
        self.assertEqual(spans_border[0][2].color.name, "#00ffff")
        self.assertEqual(spans_border[1][2].color.name, "#0000af")
        self.assertEqual(spans_border[1][2].bgcolor.name, "#00ffff")

        # 2. dracula theme: background is COLOR_BLACK (#000000)
        dracula_theme = bashmenu_ui.init_theme_colors("dracula")
        ed_dracula = bashedit.EditorWidget(display_theme_colors=True, theme=dracula_theme)

        # In shadow: [16, 16], both fg and bg are the same and match background.
        # Must choose a neutral primary 8 color that contrasts the background (white).
        spans_shadow = ed_dracula.get_line_color_spans("shadow: [16, 16]")
        self.assertEqual(len(spans_shadow), 2)
        for _s, _e, st in spans_shadow:
            self.assertEqual(st.color.name, "#000000")
            self.assertEqual(st.bgcolor.name, "white")

        # In shadow: [19, 19] under qbasic, both match blue background.
        spans_qbasic_shadow = ed_qbasic.get_line_color_spans("shadow: [19, 19]")
        self.assertEqual(len(spans_qbasic_shadow), 2)
        for _s, _e, st in spans_qbasic_shadow:
            self.assertEqual(st.color.name, "#0000af")
            self.assertEqual(st.bgcolor.name, "white")

        # 3. Helper function unit tests
        self.assertTrue(bashedit.is_same_color("19", "#0000af"))
        self.assertTrue(bashedit.is_same_color("COLOR_BLUE", "#5f87ff"))
        self.assertFalse(bashedit.is_same_color("COLOR_BLUE", "COLOR_RED"))
        self.assertEqual(bashedit.get_contrast_neutral_color("#000000"), "white")
        self.assertEqual(bashedit.get_contrast_neutral_color("#0000af"), "white")
        self.assertEqual(bashedit.get_contrast_neutral_color("#ffffff"), "black")
        self.assertTrue(bashedit.has_sufficient_contrast("#0000af", "#ffff00"))
        self.assertFalse(bashedit.has_sufficient_contrast("#0000af", "#000087"))

    def test_item_edit_modal_perform_save_prevents_shadowing(self):
        """Test ItemEditModal.perform_save() updates dual action keys.

        Verifies that editing action payload updates both action and command
        when present, preventing stale keys from shadowing new values.
        """
        import menuedit

        # Simulate item with dual action keys (like item #9)
        item = {
            "label": "Help [glow -p bashmenu.md]",
            "type": "command",
            "action": "glow -p {bashmenu_dir}/bashmenu.md",
            "command": "{scripts_dir}/rich.sh glow -p {bashmenu_dir}/bashmenu.md",
        }
        modal = menuedit.ItemEditModal(item)

        dismissed = []
        modal.dismiss = lambda res: dismissed.append(res)

        widget_map = {
            "#inp_title": type("Input", (), {"value": "Help Updated"})(),
            "#inp_icon": type("Input", (), {"value": "{nf::#1234:}"})(),
            "#inp_action": type(
                "Input", (), {"value": "nano {bashmenu_dir}/bashmenu.md"}
            )(),
            "#inp_prompt": type("Input", (), {"value": ""})(),
            "#inp_template": type("Input", (), {"value": ""})(),
            "#inp_target": type("Input", (), {"value": ""})(),
            "#inp_block_id": type("Input", (), {"value": ""})(),
            "#inp_start_dir": type("Input", (), {"value": ""})(),
            "#inp_tabstop": type("Input", (), {"value": "4"})(),
            "#exec_mode_container": type("Container", (), {"selected_mode_idx": 1})(),
            "#chk_alt_buffer": type("Checkbox", (), {"value": True})(),
            "#chk_no_formatting": type("Checkbox", (), {"value": False})(),
            "#chk_masked": type("Checkbox", (), {"value": False})(),
            "#chk_refresh": type("Checkbox", (), {"value": False})(),
            "#chk_show_whitespace": type("Checkbox", (), {"value": False})(),
            "#chk_external": type("Checkbox", (), {"value": False})(),
        }
        modal.query_one = lambda selector, *args, **kwargs: widget_map[selector]

        modal.perform_save()
        self.assertEqual(len(dismissed), 1)
        res = dismissed[0]
        # Both action and command must be updated to the new action
        self.assertEqual(res["action"], "nano {bashmenu_dir}/bashmenu.md")
        self.assertEqual(res["command"], "nano {bashmenu_dir}/bashmenu.md")
        self.assertEqual(res["label"], "Help Updated")

        # Test single action key item (command type with only action)
        item2 = {
            "label": "Copilot",
            "type": "command",
            "action": "copilot",
        }
        modal2 = menuedit.ItemEditModal(item2)
        dismissed2 = []
        modal2.dismiss = lambda res: dismissed2.append(res)
        widget_map["#inp_action"].value = "copilot --model gpt-4"
        modal2.query_one = lambda selector, *args, **kwargs: widget_map[selector]
        modal2.perform_save()
        self.assertEqual(len(dismissed2), 1)
        res2 = dismissed2[0]
        self.assertEqual(res2["action"], "copilot --model gpt-4")
        self.assertNotIn("command", res2)

        # Test clearing action
        widget_map["#inp_action"].value = ""
        item3 = {
            "label": "Test",
            "type": "command",
            "action": "old_action",
            "command": "old_command",
        }
        modal3 = menuedit.ItemEditModal(item3)
        dismissed3 = []
        modal3.dismiss = lambda res: dismissed3.append(res)
        modal3.query_one = lambda selector, *args, **kwargs: widget_map[selector]
        modal3.perform_save()
        res3 = dismissed3[0]
        self.assertNotIn("action", res3)
        self.assertNotIn("command", res3)

    def test_menuedit_item_type_change_in_modal(self):
        """Verify ItemEditModal allows changing item type, migrating action keys and updating display."""
        import menuedit

        # 1. Changing command to script
        item_cmd = {
            "title": "Run Script",
            "type": "command",
            "command": "run.sh",
            "action": "run.sh",
        }
        modal = menuedit.ItemEditModal(item_cmd)
        self.assertEqual(modal.current_type, "command")
        self.assertIn("[CMD]", modal.get_type_display_str())

        # Apply type change to script
        modal.apply_type_change("script")
        self.assertEqual(modal.current_type, "script")
        self.assertIn("[SCR]", modal.get_type_display_str())
        self.assertEqual(modal.get_title_bar_text(), "Edit Properties [SCRIPT]")
        self.assertIn("script", modal.get_action_label_text().lower())

        widget_map = {
            "#inp_title": type("Input", (), {"value": "Run Script"})(),
            "#inp_icon": type("Input", (), {"value": ""})(),
            "#inp_action": type("Input", (), {"value": "{scripts_dir}/run.sh"})(),
            "#inp_prompt": type("Input", (), {"value": ""})(),
            "#inp_template": type("Input", (), {"value": ""})(),
            "#inp_target": type("Input", (), {"value": ""})(),
            "#inp_block_id": type("Input", (), {"value": ""})(),
            "#inp_start_dir": type("Input", (), {"value": ""})(),
            "#inp_tabstop": type("Input", (), {"value": "4"})(),
            "#exec_mode_container": type("Container", (), {"selected_mode_idx": 2})(),
            "#chk_alt_buffer": type("Checkbox", (), {"value": True})(),
            "#chk_no_formatting": type("Checkbox", (), {"value": False})(),
            "#chk_masked": type("Checkbox", (), {"value": False})(),
            "#chk_refresh": type("Checkbox", (), {"value": False})(),
            "#chk_show_whitespace": type("Checkbox", (), {"value": False})(),
            "#chk_external": type("Checkbox", (), {"value": False})(),
        }
        modal.query_one = lambda selector, *args, **kwargs: widget_map[selector]

        dismissed = []
        modal.dismiss = lambda res: dismissed.append(res)
        modal.perform_save()

        self.assertEqual(len(dismissed), 1)
        res = dismissed[0]
        self.assertEqual(res["type"], "script")
        self.assertEqual(res["script"], "{scripts_dir}/run.sh")
        self.assertEqual(res["action"], "{scripts_dir}/run.sh")
        self.assertNotIn("command", res)

        # 2. Changing command to submenu
        item_cmd2 = {"title": "Tools", "type": "command", "command": "tools.sh"}
        modal2 = menuedit.ItemEditModal(item_cmd2)
        modal2.apply_type_change("submenu")
        modal2.query_one = lambda selector, *args, **kwargs: widget_map[selector]
        dismissed2 = []
        modal2.dismiss = lambda res: dismissed2.append(res)
        modal2.perform_save()

        res2 = dismissed2[0]
        self.assertEqual(res2["type"], "submenu")
        self.assertIn("submenu", res2)
        self.assertIn("options", res2["submenu"])
        self.assertEqual(res2["submenu"]["options"], [])

    def test_menuedit_item_type_divider_transitions(self):
        """Verify transitioning between divider and standard item types."""
        import menuedit

        # 1. Standard item to divider
        item_cmd = {"title": "Separator Item", "type": "command", "command": "echo 1"}
        modal = menuedit.ItemEditModal(item_cmd)
        modal.apply_type_change("divider")
        self.assertEqual(modal.current_type, "divider")

        div_widgets = {
            "#inp_char": type("Input", (), {"value": "═"})(),
            "#inp_length": type("Input", (), {"value": "60"})(),
        }
        modal.query_one = lambda selector, *args, **kwargs: div_widgets[selector]

        dismissed = []
        modal.dismiss = lambda res: dismissed.append(res)
        modal.perform_save()

        self.assertEqual(len(dismissed), 1)
        res = dismissed[0]
        self.assertEqual(res["type"], "divider")
        self.assertEqual(res["char"], "═")
        self.assertEqual(res["length"], "60")
        self.assertNotIn("command", res)
        self.assertNotIn("title", res)

        # 2. Divider to standard item
        item_div = {"type": "divider", "char": "─", "length": "{window_width}"}
        modal2 = menuedit.ItemEditModal(item_div)
        self.assertEqual(modal2.current_type, "divider")
        modal2.apply_type_change("command")
        self.assertEqual(modal2.current_type, "command")

        std_widgets = {
            "#inp_title": type("Input", (), {"value": "New Command"})(),
            "#inp_icon": type("Input", (), {"value": "star"})(),
            "#inp_action": type("Input", (), {"value": "htop"})(),
            "#inp_prompt": type("Input", (), {"value": ""})(),
            "#inp_template": type("Input", (), {"value": ""})(),
            "#inp_target": type("Input", (), {"value": ""})(),
            "#inp_block_id": type("Input", (), {"value": ""})(),
            "#inp_start_dir": type("Input", (), {"value": ""})(),
            "#inp_tabstop": type("Input", (), {"value": "4"})(),
            "#exec_mode_container": type("Container", (), {"selected_mode_idx": 2})(),
            "#chk_alt_buffer": type("Checkbox", (), {"value": True})(),
            "#chk_no_formatting": type("Checkbox", (), {"value": False})(),
            "#chk_masked": type("Checkbox", (), {"value": False})(),
            "#chk_refresh": type("Checkbox", (), {"value": False})(),
            "#chk_show_whitespace": type("Checkbox", (), {"value": False})(),
            "#chk_external": type("Checkbox", (), {"value": False})(),
        }
        modal2.query_one = lambda selector, *args, **kwargs: std_widgets[selector]

        dismissed2 = []
        modal2.dismiss = lambda res: dismissed2.append(res)
        modal2.perform_save()

        res2 = dismissed2[0]
        self.assertEqual(res2["type"], "command")
        self.assertEqual(res2["title"], "New Command")
        self.assertEqual(res2["command"], "htop")
        self.assertNotIn("char", res2)
        self.assertNotIn("length", res2)

    def test_menuedit_item_type_change_direct_action(self):
        """Verify MenuEditScreen.action_change_item_type directly converts node data."""
        import menuedit

        screen = menuedit.MenuEditScreen(menu_file_path="/tmp/fake.mnu")
        screen.menu_data = {
            "title": "Main Menu",
            "options": [
                {"title": "Check Health", "type": "command", "command": "health.sh"},
            ],
        }

        class MockNode:
            def __init__(self, data):
                self.data = data
                self.label = ""

        mock_node = MockNode(screen.menu_data["options"][0])
        tree_mock = type("TreeMock", (), {"cursor_node": mock_node, "root": object()})()
        screen.query_one = lambda selector, *args, **kwargs: tree_mock
        screen.populate_tree = lambda **kw: None
        screen.update_inspector = lambda item: None
        screen.action_save_menu = lambda: None

        pushed_screens = []
        screen._app = type("DummyApp", (), {"push_screen": lambda self, s, cb: pushed_screens.append((s, cb))})()

        screen.action_change_item_type()
        self.assertEqual(len(pushed_screens), 1)
        picker, callback = pushed_screens[0]
        self.assertIsInstance(picker, menuedit.ItemTypePickerModal)

        # Trigger callback with "script"
        callback("script")
        self.assertEqual(mock_node.data["type"], "script")
        self.assertEqual(mock_node.data["script"], "health.sh")
        self.assertNotIn("command", mock_node.data)
        self.assertIn("[SCR]", mock_node.label)

    def test_scrolling_modal_scrollbar_margins(self):
        """Verify scrolling modals provide at least a one-character right margin before scrollbars."""
        import asyncio

        from textual.app import App

        import bashmenu_ui
        import menuedit

        async def run_checks():
            app = App()
            # 1. MessageModalScreen (Help modal)
            long_content = "Line of help text content\n" * 50
            help_modal = bashmenu_ui.MessageModalScreen("Help", long_content, is_help=True)
            async with app.run_test(size=(80, 24)) as pilot:
                await app.push_screen(help_modal)
                await pilot.pause()
                sc = help_modal.query_one("#scroll_container")
                msg = help_modal.query_one("#message")
                sb_x = sc.vertical_scrollbar.region.x
                msg_right = msg.region.x + msg.region.width
                self.assertGreaterEqual(sb_x - msg_right, 1)

            # 2. ItemEditModal
            app2 = App()
            item = {"type": "command", "title": "Test Item", "command": "echo test"}
            edit_modal = menuedit.ItemEditModal(item)
            async with app2.run_test(size=(90, 30)) as pilot:
                await app2.push_screen(edit_modal)
                await pilot.pause()
                fs = edit_modal.query_one("#form_scroll")
                inp = edit_modal.query_one("#inp_title")
                c_std = edit_modal.query_one("#container_standard")
                row_type = edit_modal.query_one("#row_item_type")
                sb_x = fs.vertical_scrollbar.region.x
                self.assertGreaterEqual(sb_x - (c_std.region.x + c_std.region.width), 1)
                self.assertGreaterEqual(sb_x - (inp.region.x + inp.region.width), 1)
                self.assertGreaterEqual(sb_x - (row_type.region.x + row_type.region.width), 1)

        asyncio.run(run_checks())

    def test_menuedit_tree_selection_indicator_theme(self):
        """Verify the menu editor hierarchy tree selection indicator follows theme highlight definition."""
        import asyncio

        from textual.app import App

        import bashmenu_ui
        import menuedit

        async def run_checks():
            for tname in ["dracula", "matrix", "everforest"]:
                theme_dict = bashmenu_ui.init_theme_colors(tname)
                high_style = theme_dict.get("highlight")
                app = App()
                screen = menuedit.MenuEditScreen(theme=theme_dict)
                async with app.run_test() as pilot:
                    await app.push_screen(screen)
                    await pilot.pause()
                    tree = screen.query_one("#tree", menuedit.MenuEditTree)

                    # 1. Custom cursor style is set and matches theme highlight definition
                    self.assertIsNotNone(tree.custom_cursor_style)
                    self.assertEqual(tree.custom_cursor_style.bgcolor, high_style.bgcolor)
                    self.assertEqual(tree.custom_cursor_style.color, high_style.color)

                    # 2. Rich style returned for tree--cursor matches highlight, not default blue (#0178d4)
                    cur_rich = tree.get_component_rich_style("tree--cursor")
                    self.assertEqual(cur_rich.bgcolor, high_style.bgcolor)
                    self.assertNotEqual(str(cur_rich.bgcolor), "#0178d4")

                    # 3. Selected guide matches highlight bgcolor
                    guides_rich = tree.get_component_rich_style("tree--guides-selected")
                    self.assertEqual(guides_rich.color, high_style.bgcolor)

                    # 4. Moving selection renders child item with theme highlight background
                    await pilot.press("down")
                    await pilot.pause()
                    line1 = tree.render_line(1)
                    has_theme_bg = any(
                        seg.style is not None and seg.style.bgcolor == high_style.bgcolor
                        for seg in line1._segments
                    )
                    self.assertTrue(has_theme_bg)

        asyncio.run(run_checks())

    def test_scrollbar_theming(self):
        """Verify scrollbar foreground (thumb) and background (track) colors are themed."""
        import asyncio

        from textual.app import App

        import bashmenu_ui
        import menuedit

        async def run_checks():
            for tname in ["dracula", "matrix", "everforest"]:
                theme_dict = bashmenu_ui.init_theme_colors(tname)
                sb_style = theme_dict.get("scrollbar")
                exp_fg = bashmenu_ui.parse_css_color(sb_style.color.name)
                exp_bg = bashmenu_ui.parse_css_color(sb_style.bgcolor.name)

                # 1. Modal scrollbar theming
                app_modal = App()
                modal = bashmenu_ui.MessageModalScreen("Help", "Line\n" * 50, theme=theme_dict, is_help=True)
                async with app_modal.run_test() as pilot:
                    await app_modal.push_screen(modal)
                    await pilot.pause()
                    sc = modal.query_one("#scroll_container")
                    self.assertEqual(sc.styles.scrollbar_color.hex.lower(), exp_fg.lower())
                    self.assertEqual(sc.styles.scrollbar_background.hex.lower(), exp_bg.lower())

                # 2. Menu editor inspector panel scrollbar theming
                app_editor = App()
                editor = menuedit.MenuEditScreen(theme=theme_dict)
                async with app_editor.run_test() as pilot:
                    await app_editor.push_screen(editor)
                    await pilot.pause()
                    insp = editor.query_one("#inspector_panel")
                    self.assertEqual(insp.styles.scrollbar_color.hex.lower(), exp_fg.lower())
                    self.assertEqual(insp.styles.scrollbar_background.hex.lower(), exp_bg.lower())

        asyncio.run(run_checks())

    def test_placeholder_documentation_parity(self):
        """Verify that all key placeholders and directives have documentation parity."""
        import menuedit

        # 1. UI placeholder sections verification
        all_ui_placeholders = [
            ph for _, items in bashmenu_ui.PLACEHOLDER_SECTIONS for ph, _ in items
        ]
        essential_placeholders = [
            "{param}",
            "{file_picker}",
            "{file_picker_new}",
            "{dir_picker}",
            "{dir_picker_new}",
            "{user}",
            "{home}",
            "{bashmenu_dir}",
            "{scripts_dir}",
            "{scripts}",
            "{templates_dir}",
            "{templates}",
            "{cache_dir}",
            "{cache}",
            "{battery}",
            "{localip}",
            "{date_time_12}",
            "{date_time_12_short}",
            "{date_time_24}",
            "{date_time_24_short}",
            "{window_width}",
            "{window_height}",
            "{divider}",
            "{ascii:<code_num>}",
            "{command:<cmd>}",
            "{nf:<char>:<hex>:<emoji>}",
            "{<key.path>}",
        ]
        for ep in essential_placeholders:
            self.assertIn(ep, all_ui_placeholders, f"Missing {ep} in PLACEHOLDER_SECTIONS")
            self.assertIn(ep, bashmenu_ui.PLACEHOLDER_HELP_TEXT, f"Missing {ep} in PLACEHOLDER_HELP_TEXT")

        # 2. Menu editor help text verification
        for directive in ["{param}", "{file_picker}", "{dir_picker}"]:
            self.assertIn(directive, menuedit.ITEM_EDIT_HELP_TEXT, f"Missing {directive} in menuedit ITEM_EDIT_HELP_TEXT")

        # 3. Markdown manual verification
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base_dir, "bashmenu.md"), "r", encoding="utf-8") as f:
            md_content = f.read()
        for ep in ["{param}", "{file_picker}", "{dir_picker}", "{localip}", "{cache_dir}", "{battery}"]:
            self.assertIn(ep, md_content, f"Missing {ep} in bashmenu.md")

        # 4. Man page verification
        with open(os.path.join(base_dir, "bashmenu.1"), "r", encoding="utf-8") as f:
            man_content = f.read()
        for ep in ["{param}", "{file_picker}", "{dir_picker}", "{localip}", "{cache_dir}", "{battery}"]:
            self.assertIn(ep, man_content, f"Missing {ep} in bashmenu.1")

    def test_theme_window_borders(self):
        """Test window border extraction, defaults, and CP437 ASCII macro resolution."""
        # 1. Default fallback (dracula theme has no window section)
        dracula_borders = bashmenu_ui.get_theme_window_borders("dracula")
        self.assertEqual(dracula_borders["border_horizontal"], "─")
        self.assertEqual(dracula_borders["border_vertical"], "│")
        self.assertEqual(dracula_borders["border_top_left"], "┌")
        self.assertEqual(dracula_borders["border_top_right"], "┐")
        self.assertEqual(dracula_borders["border_bottom_left"], "└")
        self.assertEqual(dracula_borders["border_bottom_right"], "┘")

        # 2. QBasic theme double-line border overrides
        qbasic_borders = bashmenu_ui.get_theme_window_borders("qbasic")
        self.assertEqual(qbasic_borders["border_horizontal"], "═")
        self.assertEqual(qbasic_borders["border_vertical"], "║")
        self.assertEqual(qbasic_borders["border_top_left"], "╔")
        self.assertEqual(qbasic_borders["border_top_right"], "╗")
        self.assertEqual(qbasic_borders["border_bottom_left"], "╚")
        self.assertEqual(qbasic_borders["border_bottom_right"], "╝")

        # 3. Partial override and specific edge tests (half blocks)
        mock_theme_data = {
            "custom_theme": {
                "window": {
                    "border_horizontal": "=",
                }
            },
            "variant_theme": {
                "window": {
                    "border_horizontal_top": "▀",
                    "border_horizontal_bottom": "▄",
                    "border_vertical_left": "▌",
                    "border_vertical_right": "▐",
                    "border_top_left": "┌",
                    "border_top_right": "┐",
                    "border_bottom_left": "└",
                    "border_bottom_right": "┘",
                }
            },
        }
        custom_borders = bashmenu_ui.get_theme_window_borders("custom_theme", raw_theme_data=mock_theme_data)
        self.assertEqual(custom_borders["border_horizontal"], "=")
        self.assertEqual(custom_borders["border_horizontal_top"], "=")
        self.assertEqual(custom_borders["border_horizontal_bottom"], "=")
        self.assertEqual(custom_borders["border_vertical"], "│")  # Unspecified falls back to default

        variant_borders = bashmenu_ui.get_theme_window_borders("variant_theme", raw_theme_data=mock_theme_data)
        self.assertEqual(variant_borders["border_horizontal_top"], "▀")
        self.assertEqual(variant_borders["border_horizontal_bottom"], "▄")
        self.assertEqual(variant_borders["border_vertical_left"], "▌")
        self.assertEqual(variant_borders["border_vertical_right"], "▐")

    def test_ymlcheck_theme_window_validation(self):
        """Test ymlcheck validation for theme window: and divider: sections."""
        # Valid window section with top/bottom/left/right, title caps, and tees
        valid_section = {
            "border_horizontal_top": "{ascii:223}",
            "border_horizontal_bottom": "{ascii:220}",
            "border_vertical_left": "{ascii:221}",
            "border_vertical_right": "{ascii:222}",
            "border_tee_left": "{ascii:195}",
            "border_tee_right": "{ascii:180}",
            "title_left_cap": "╡",
            "title_right_cap": "╞",
            "shadow_char": "░",
        }
        self.assertEqual(ymlcheck.validate_window_section(valid_section, "test.window"), [])

        # Valid divider section
        valid_divider = {
            "char": "{ascii:205}",
            "length": "{window_width}",
        }
        self.assertEqual(ymlcheck.validate_divider_section(valid_divider, "test.divider"), [])

        # Invalid window key
        invalid_section = {
            "invalid_border_key": "-",
        }
        errors = ymlcheck.validate_window_section(invalid_section, "test.window")
        self.assertTrue(len(errors) > 0)
        self.assertIn("Unknown window border property", errors[0])

        # Non-dict section
        errors_non_dict = ymlcheck.validate_window_section("not_a_dict", "test.window")
        self.assertTrue(len(errors_non_dict) > 0)

    def test_draw_shadow_compatibility(self):
        """Test draw_shadow curses compatibility helper with shade characters."""
        mock_scr = MagicMock()
        mock_scr.getmaxyx.return_value = (30, 80)
        bashmenu_ui.draw_shadow(mock_scr, start_y=5, start_x=10, box_h=8, box_w=30)
        self.assertTrue(mock_scr.addstr.called)
        calls = [c[0] for c in mock_scr.addstr.call_args_list]
        # Verify shadow_char '░' was drawn
        chars_drawn = {c[2] for c in calls}
        self.assertIn("░", chars_drawn)

    def test_theme_window_borders_propagation(self):
        """Verify theme window borders propagate to Textual borders, bashedit, and menuedit."""
        import textual._border as tb

        import bashmenu_ui
        import menuedit

        # 1. Test Textual border synchronization on init_theme_colors
        styles_qbasic = bashmenu_ui.init_theme_colors("qbasic")
        self.assertIn("window_borders", styles_qbasic)
        self.assertEqual(styles_qbasic["window_borders"]["border_horizontal"], "═")

        # BORDER_CHARS['thick'] and ['solid'] should match qbasic box characters
        self.assertEqual(tb.BORDER_CHARS["thick"][0], ("╔", "═", "╗"))
        self.assertEqual(tb.BORDER_CHARS["thick"][1], ("║", " ", "║"))
        self.assertEqual(tb.BORDER_CHARS["thick"][2], ("╚", "═", "╝"))
        self.assertEqual(tb.BORDER_CHARS["solid"][0], ("╔", "═", "╗"))

        # Re-initialize with dracula
        styles_dracula = bashmenu_ui.init_theme_colors("dracula")
        self.assertEqual(styles_dracula["window_borders"]["border_horizontal"], "─")
        self.assertEqual(tb.BORDER_CHARS["thick"][0], ("┌", "─", "┐"))
        self.assertEqual(tb.BORDER_CHARS["thick"][1], ("│", " ", "│"))
        self.assertEqual(tb.BORDER_CHARS["thick"][2], ("└", "─", "┘"))

        # 2. Test pacman theme: divider uses explicit divider char (═), window borders use blocks (█)
        div_item = {"type": "divider"}
        preview_pacman = menuedit.render_menu_item_preview(div_item, config={"theme": "pacman"}, width=10)
        self.assertEqual(preview_pacman, "═" * 10)

        # Confirm window border_horizontal does NOT bleed into divider
        div_str_pacman = bashmenu.resolve_divider_string({"theme": "pacman"}, target_w=10)
        self.assertIn("═" * 10, div_str_pacman)
        self.assertNotIn("█", div_str_pacman)

        # 3. Test divider priority: Theme > Plugin > Default
        # Case A: Theme divider overrides plugin divider
        cfg_theme_and_plugin = {
            "theme": "pacman",  # pacman defines divider char: {ascii:205} (═)
            "settings": {
                "plugins": {
                    "sample": {"divider": {"char": "#"}}
                }
            },
        }
        res_a = bashmenu.resolve_divider_string(cfg_theme_and_plugin, target_w=10)
        self.assertIn("═" * 10, res_a)

        # Case B: Plugin divider used when theme does not define divider
        cfg_plugin_only = {
            "theme": "dracula",  # dracula defines no divider
            "settings": {
                "plugins": {
                    "sample": {"divider": {"char": "#"}}
                }
            },
        }
        res_b = bashmenu.resolve_divider_string(cfg_plugin_only, target_w=10)
        self.assertIn("#" * 10, res_b)

        # Case C: Default used when neither defines divider
        cfg_default = {"theme": "dracula"}
        res_c = bashmenu.resolve_divider_string(cfg_default, target_w=10)
        self.assertIn("─" * 10, res_c)

    def test_bashedit_help_modal_and_ascii_stream(self):
        """Verify bashedit help modal uses markdown table and ASCII table streaming works."""
        import bashedit

        screen = bashedit.BashEditScreen()
        pushed_screens = []
        mock_app = MagicMock()
        mock_app.push_screen = lambda scr, *args, **kwargs: pushed_screens.append(scr)

        with patch.object(bashedit.BashEditScreen, "app", property(lambda s: mock_app)):
            # 1. Test action_help_manual uses markdown table
            screen.action_help_manual()
            self.assertEqual(len(pushed_screens), 1)
            help_modal = pushed_screens[0]
            self.assertTrue(help_modal.is_markdown)
            self.assertTrue(help_modal.is_help)
            self.assertIn("| Keybinding / Shortcut | Description / Action |", help_modal.message)
            self.assertIn("| `^A` / `F11` | View ASCII Character Table (`ascii.sh`) |", help_modal.message)

            # 2. Test action_show_ascii_table pushes StreamOutputModalScreen
            screen.action_show_ascii_table()
            self.assertEqual(len(pushed_screens), 2)
            stream_modal = pushed_screens[1]
            self.assertEqual(stream_modal.modal_title, "ASCII Character Table")
            self.assertIn("ascii.sh", stream_modal.command)

        # 3. Test bindings in BashEditScreen
        binding_keys = {b.key for b in bashedit.BashEditScreen.BINDINGS}
        self.assertIn("ctrl+a", binding_keys)
        self.assertIn("f11", binding_keys)

    def test_bashedit_terminal_key_input_handling(self):
        """Verify Enter, Tab, Backspace, and characters are never swallowed by control character checks."""
        import textual.events as te

        import bashedit

        screen = bashedit.BashEditScreen()
        ed = bashedit.EditorWidget(lines=["FirstLine"])
        status_mock = MagicMock()
        screen.query_one = lambda selector, *args, **kwargs: ed if selector == "#editor_widget" else status_mock

        # 1. Terminal Enter key (key='enter', character='\r')
        ed.cursor_x = len(ed.lines[0])
        screen.on_key(te.Key("enter", "\r"))
        self.assertEqual(ed.lines, ["FirstLine", ""])

        # 2. Typing characters
        for ch in "Text":
            screen.on_key(te.Key(ch, ch))
        self.assertEqual(ed.lines, ["FirstLine", "Text"])

        # 3. Terminal Tab key (key='tab', character='\t')
        screen.on_key(te.Key("tab", "\t"))
        self.assertTrue(ed.lines[1].startswith("Text"))
        self.assertTrue(len(ed.lines[1]) > 4)

        # 4. Terminal Backspace with \x08 and \x7f
        prev_len = len(ed.lines[1])
        screen.on_key(te.Key("backspace", "\x08"))
        self.assertEqual(len(ed.lines[1]), prev_len - 1)
        screen.on_key(te.Key("backspace", "\x7f"))
        self.assertEqual(len(ed.lines[1]), prev_len - 2)

        # 5. Terminal ctrl+h backspace
        screen.on_key(te.Key("ctrl+h", "\x08"))
        self.assertEqual(len(ed.lines[1]), prev_len - 3)

        # 6. Terminal Enter with ctrl+j (\n)
        screen.on_key(te.Key("ctrl+j", "\n"))
        self.assertEqual(len(ed.lines), 3)

        # 7. Action shortcuts (e.g. ctrl+s) must not type into lines
        lines_before = list(ed.lines)
        screen.on_key(te.Key("ctrl+s", "\x13"))
        self.assertEqual(ed.lines, lines_before)

    def test_title_caps_rendering_and_styling(self):
        """Test title caps default to brackets, use title/cap style, and decorate titles."""
        # 1. Default window borders default to '[' and ']'
        default_borders = bashmenu_ui.get_theme_window_borders("nonexistent_theme", raw_theme_data={})
        self.assertEqual(default_borders["title_left_cap"], "[")
        self.assertEqual(default_borders["title_right_cap"], "]")

        # 2. Config window overrides
        custom_cfg = {"window": {"title_left_cap": "«", "title_right_cap": "»"}}
        cfg_borders = bashmenu_ui.get_theme_window_borders("dracula", config=custom_cfg, raw_theme_data={})
        self.assertEqual(cfg_borders["title_left_cap"], "«")
        self.assertEqual(cfg_borders["title_right_cap"], "»")

        # 3. MainMenuView.render uses cap_style matching title
        cfg = {"theme": "pacman"}
        mnu = {"title": "My Title", "options": [{"name": "Opt1"}]}
        mv = bashmenu.MainMenuView(config=cfg, menu_data=mnu)
        mv._size = type("Size", (), {"width": 80, "height": 24})()
        rendered_top = mv.render().split("\n")[0]
        self.assertIn("My Title", rendered_top.plain)
        theme_styles = bashmenu_ui.init_theme_colors("pacman")
        expected_title_style = theme_styles.get("title")
        cap_spans = [s for s in rendered_top.spans if s.style.color == expected_title_style.color]
        self.assertTrue(len(cap_spans) > 0)

    def test_screen_width_vs_window_width_divider_rendering(self):
        """Test divider rendering with {window_width} (margins, no tees) vs {screen_width} (no margins, with tees)."""
        custom_cfg = {
            "window": {
                "border_vertical_left": "│",
                "border_vertical_right": "│",
                "left_tee": "├",
                "right_tee": "┤",
            }
        }
        # 1. Window width divider: bounded by margins, framed by b_v_left/b_v_right + 2 spaces, NO tees
        mnu_win = {
            "title": "Test Window Div",
            "options": [{"type": "divider", "length": "{window_width}"}],
        }
        mv_win = bashmenu.MainMenuView(config=custom_cfg, menu_data=mnu_win)
        mv_win._size = type("Size", (), {"width": 80, "height": 24})()
        lines_win = [line.plain for line in mv_win.render().split("\n")]
        # Content starts at line 3 (index 3: after top border and 2 margin lines)
        div_line_win = lines_win[3]
        self.assertEqual(len(div_line_win), 80)
        self.assertTrue(div_line_win.startswith("│  "))
        self.assertTrue(div_line_win.endswith("  │"))
        self.assertNotIn("├", div_line_win)
        self.assertNotIn("┤", div_line_win)

        # 2. Screen width divider: runs border to border, starts at left_tee, ends at right_tee, overrides margins
        mnu_scr = {
            "title": "Test Screen Div",
            "options": [{"type": "divider", "length": "{screen_width}"}],
        }
        mv_scr = bashmenu.MainMenuView(config=custom_cfg, menu_data=mnu_scr)
        mv_scr._size = type("Size", (), {"width": 80, "height": 24})()
        lines_scr = [line.plain for line in mv_scr.render().split("\n")]
        div_line_scr = lines_scr[3]
        self.assertEqual(len(div_line_scr), 80)
        self.assertTrue(div_line_scr.startswith("├"))
        self.assertTrue(div_line_scr.endswith("┤"))
        self.assertFalse(div_line_scr.startswith("├ "))
        self.assertFalse(div_line_scr.endswith(" ┤"))

    def test_tee_border_theme_keys(self):
        """Test left_tee, right_tee, top_tee, and bottom_tee border keys and aliases."""
        cfg = {
            "window": {
                "left_tee": "L",
                "right_tee": "R",
                "top_tee": "T",
                "bottom_tee": "B",
            }
        }
        borders = bashmenu_ui.get_theme_window_borders("dracula", config=cfg)
        self.assertEqual(borders["left_tee"], "L")
        self.assertEqual(borders["right_tee"], "R")
        self.assertEqual(borders["top_tee"], "T")
        self.assertEqual(borders["bottom_tee"], "B")
        self.assertEqual(borders["border_tee_left"], "L")
        self.assertEqual(borders["border_tee_right"], "R")
        self.assertEqual(borders["border_tee_top"], "T")
        self.assertEqual(borders["border_tee_bottom"], "B")

    def test_four_tier_divider_precedence_and_presence(self):
        """Test full 4-tier divider precedence (Theme > YML plugins > MNU declarations > Default)
        and presence rules (no dividers in menu unless declared in bashmenu.mnu).
        """
        # Tier 1: Theme overrides declared divider item in bashmenu.mnu
        # pacman defines char: {ascii:205} (═) and length: {window_width}
        cfg_pacman = {"theme": "pacman"}
        item_declared = {"type": "divider", "char": "*", "length": "{screen_width}"}
        res_t1 = bashmenu.get_effective_divider_config(cfg_pacman, item_conf=item_declared)
        # Theme's char {ascii:205} and length {window_width} override item_declared's '*' and {screen_width}
        self.assertEqual(res_t1["char"], "{ascii:205}")
        self.assertEqual(res_t1["length"], "{window_width}")

        # Tier 2: Plugin in bashmenu.yml overrides declared divider item when theme has no divider
        cfg_plugin = {
            "theme": "dracula",  # dracula has no divider block
            "settings": {"plugins": {"myplug": {"divider": {"char": "#", "length": "{screen_width}"}}}},
        }
        res_t2 = bashmenu.get_effective_divider_config(cfg_plugin, item_conf=item_declared)
        self.assertEqual(res_t2["char"], "#")
        self.assertEqual(res_t2["length"], "{screen_width}")

        # Tier 3: Declared divider item in bashmenu.mnu is used when neither theme nor plugin defines divider
        cfg_empty = {"theme": "dracula"}
        res_t3 = bashmenu.get_effective_divider_config(cfg_empty, item_conf=item_declared)
        self.assertEqual(res_t3["char"], "*")
        self.assertEqual(res_t3["length"], "{screen_width}")

        # Tier 4: Default fallback when nothing is declared
        res_t4 = bashmenu.get_effective_divider_config(cfg_empty, item_conf={"type": "divider"})
        self.assertEqual(res_t4["char"], "{ascii:196}")
        self.assertEqual(res_t4["length"], "{window_width}")

        # Presence Test: If no dividers are declared in bashmenu.mnu, render NO dividers
        mnu_no_div = {
            "title": "Menu Without Dividers",
            "options": [
                {"label": "Item 1", "action": "echo 1"},
                {"label": "Item 2", "action": "echo 2"},
            ],
        }
        mv_no_div = bashmenu.MainMenuView(config=cfg_pacman, menu_data=mnu_no_div)
        mv_no_div._size = type("Size", (), {"width": 80, "height": 24})()
        rendered_no_div = mv_no_div.render().plain
        # pacman divider char is ═ (ascii 205). It must NOT appear anywhere in the rendered menu!
        self.assertNotIn("═", rendered_no_div)
        self.assertNotIn("─", rendered_no_div)

        # Presence Test: If dividers ARE declared in bashmenu.mnu, they DO render (styled by theme)
        mnu_with_div = {
            "title": "Menu With Divider",
            "options": [
                {"label": "Item 1", "action": "echo 1"},
                {"type": "divider"},
                {"label": "Item 2", "action": "echo 2"},
            ],
        }
        mv_with_div = bashmenu.MainMenuView(config=cfg_pacman, menu_data=mnu_with_div)
        mv_with_div._size = type("Size", (), {"width": 80, "height": 24})()
        rendered_with_div = mv_with_div.render().plain
        self.assertIn("═", rendered_with_div)


if __name__ == "__main__":
    unittest.main()



