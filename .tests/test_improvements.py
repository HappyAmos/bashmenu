#!/usr/bin/env python3
import os
import sys
import unittest

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
                self.assertIsInstance(msg_widget.content, Markdown)

        asyncio.run(run_f1_check())

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


if __name__ == "__main__":
    unittest.main()


