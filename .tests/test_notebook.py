#!/usr/bin/env python3
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from textual.geometry import Size

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bashmenu
import bashmenu_ui
import ymlcheck


class TestNotebookFeature(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.notebook_path = os.path.join(self.test_dir, "test_notes.yml")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_notebook_creates_file_if_missing(self):
        """Verify that loading a non-existent notebook file auto-creates it with valid structure."""
        self.assertFalse(os.path.exists(self.notebook_path))
        data = bashmenu_ui.load_notebook(self.notebook_path)
        self.assertTrue(os.path.exists(self.notebook_path))
        self.assertIn("notebook", data)
        self.assertEqual(data["notebook"]["title"], "Test Notes")
        self.assertEqual(data["notebook"]["notes"], [])

    def test_save_and_load_notebook_roundtrip(self):
        """Verify adding notes, literal block scalar dumping (content: |), and roundtrip loading."""
        data = bashmenu_ui.load_notebook(self.notebook_path)
        bashmenu_ui.add_or_update_note(
            data,
            title="Daily Checklist",
            content="# Daily Checklist\n- [x] Task 1\n- [ ] Task 2\n",
            note_type="note",
            note_format="markdown",
        )
        bashmenu_ui.save_notebook(self.notebook_path, data)

        with open(self.notebook_path, "r", encoding="utf-8") as f:
            raw_yaml = f.read()

        # Check for literal block scalar
        self.assertIn("content: |", raw_yaml)
        self.assertIn("Daily Checklist:", raw_yaml)

        # Reload from disk
        reloaded = bashmenu_ui.load_notebook(self.notebook_path)
        notes = bashmenu_ui.get_notebook_notes(reloaded)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0][0], "Daily Checklist")
        self.assertEqual(notes[0][1]["content"], "# Daily Checklist\n- [x] Task 1\n- [ ] Task 2\n")

    def test_notebook_notes_crud_operations(self):
        """Test adding, finding, updating, renaming, and deleting notes."""
        data = bashmenu_ui.load_notebook(self.notebook_path)

        # 1. Add Note A
        bashmenu_ui.add_or_update_note(data, "Note A", "Content A")
        self.assertEqual(len(bashmenu_ui.get_notebook_notes(data)), 1)
        note_a = bashmenu_ui.get_note_by_title(data, "Note A")
        self.assertIsNotNone(note_a)
        self.assertEqual(note_a["content"], "Content A")

        # 2. Update Note A
        bashmenu_ui.add_or_update_note(data, "Note A", "Content A Updated")
        self.assertEqual(len(bashmenu_ui.get_notebook_notes(data)), 1)
        self.assertEqual(bashmenu_ui.get_note_by_title(data, "Note A")["content"], "Content A Updated")

        # 3. Rename Note A -> Note A Prime
        bashmenu_ui.add_or_update_note(data, "Note A Prime", "Content A Prime", orig_title="Note A")
        self.assertEqual(len(bashmenu_ui.get_notebook_notes(data)), 1)
        self.assertIsNone(bashmenu_ui.get_note_by_title(data, "Note A"))
        self.assertIsNotNone(bashmenu_ui.get_note_by_title(data, "Note A Prime"))

        # 4. Add Note B
        bashmenu_ui.add_or_update_note(data, "Note B", "Content B")
        self.assertEqual(len(bashmenu_ui.get_notebook_notes(data)), 2)

        # 5. Delete Note A Prime
        deleted = bashmenu_ui.delete_note(data, "Note A Prime")
        self.assertTrue(deleted)
        self.assertEqual(len(bashmenu_ui.get_notebook_notes(data)), 1)
        self.assertEqual(bashmenu_ui.get_notebook_notes(data)[0][0], "Note B")

        # 6. Delete non-existent note
        self.assertFalse(bashmenu_ui.delete_note(data, "Nonexistent"))

    def test_build_dynamic_notebook_submenu(self):
        """Verify dynamic submenu structure for empty and populated notebooks."""
        # Empty
        sub_empty = bashmenu.build_dynamic_notebook_submenu(self.notebook_path)
        self.assertTrue(sub_empty["_is_notebook"])
        items = sub_empty["items"]
        empty_items = [i for i in items if i.get("type") == "notebook_empty"]
        self.assertEqual(len(empty_items), 1)
        self.assertIn("No notes yet", empty_items[0]["label"])

        # Populated
        data = bashmenu_ui.load_notebook(self.notebook_path)
        bashmenu_ui.add_or_update_note(data, "My First Note", "Hello World")
        bashmenu_ui.save_notebook(self.notebook_path, data)

        sub_populated = bashmenu.build_dynamic_notebook_submenu(self.notebook_path)
        pop_items = [i for i in sub_populated["items"] if i.get("type") == "notebook_note"]
        self.assertEqual(len(pop_items), 1)
        self.assertEqual(pop_items[0]["title"], "My First Note")
        self.assertEqual(pop_items[0]["_note_title"], "My First Note")
        self.assertEqual(pop_items[0]["_notebook_file"], self.notebook_path)
        self.assertIn("#f039e", pop_items[0]["icon"])
        # Verify resolution with nerd fonts returns Nerd Font glyph, not emoji
        resolved_icon = bashmenu.resolve_glyph(pop_items[0]["icon"], {"settings": {"use_nerd_fonts": True}})
        self.assertEqual(resolved_icon, "\U000f039e")

    def test_process_item_action_notebook_dispatch(self):
        """Verify process_item_action pushes dynamic notebook submenu."""
        mock_screen = MagicMock()
        mock_screen.menu_view.menu_stack = []
        mock_screen.menu_view.selected_rows = []
        mock_screen.menu_view.scroll_offsets = []

        item = {"type": "notebook", "file": self.notebook_path}
        config = bashmenu.load_config()[0]

        bashmenu.process_item_action(mock_screen, item, config)
        self.assertEqual(len(mock_screen.menu_view.menu_stack), 1)
        pushed_sub = mock_screen.menu_view.menu_stack[0]
        self.assertTrue(pushed_sub.get("_is_notebook"))
        self.assertEqual(pushed_sub.get("_notebook_file"), self.notebook_path)

    def test_process_item_action_notebook_reloads_on_reentry(self):
        """Verify re-entering a notebook from menu reloads newly added notes from disk."""
        mock_screen = MagicMock()
        mock_screen.menu_view.menu_stack = []
        mock_screen.menu_view.selected_rows = []
        mock_screen.menu_view.scroll_offsets = []

        item = {"type": "notebook", "file": self.notebook_path}
        config = bashmenu.load_config()[0]

        # 1. First open: notebook has 0 notes
        bashmenu.process_item_action(mock_screen, item, config)
        first_sub = mock_screen.menu_view.menu_stack[-1]
        self.assertEqual(len([i for i in first_sub["items"] if i.get("type") == "notebook_note"]), 0)

        # 2. Add notes to file on disk
        data = bashmenu_ui.load_notebook(self.notebook_path)
        bashmenu_ui.add_or_update_note(data, "Note A", "Content A")
        bashmenu_ui.add_or_update_note(data, "Note B", "Content B")
        bashmenu_ui.save_notebook(self.notebook_path, data)

        # 3. Simulate user pressing Back (pop menu stack)
        mock_screen.menu_view.menu_stack.pop()

        # 4. Re-enter notebook from menu item (even though item["submenu"] was previously set)
        bashmenu.process_item_action(mock_screen, item, config)
        second_sub = mock_screen.menu_view.menu_stack[-1]
        notes = [i["title"] for i in second_sub["items"] if i.get("type") == "notebook_note"]
        self.assertEqual(notes, ["Note A", "Note B"])

    def test_process_item_action_notebook_note_dispatch(self):
        """Verify selecting a note dispatches open_note_viewer."""
        mock_screen = MagicMock()
        item = {
            "type": "notebook_note",
            "_notebook_file": self.notebook_path,
            "_note_title": "Note 1",
        }
        config = bashmenu.load_config()[0]
        bashmenu.process_item_action(mock_screen, item, config)
        mock_screen.open_note_viewer.assert_called_once_with(self.notebook_path, "Note 1")

    def test_help_gutter_in_notebook_mode(self):
        """Verify help gutter renders notebook keys when _is_notebook is True."""
        config = bashmenu.load_config()[0]
        sub = bashmenu.build_dynamic_notebook_submenu(self.notebook_path)
        mv = bashmenu.MainMenuView(config=config, menu_data=sub)
        mv.menu_stack = [sub]
        with patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)):
            out = mv.render()
        out_text = out.plain if hasattr(out, "plain") else str(out)
        self.assertIn("New Note", out_text)
        self.assertIn("Read", out_text)
        self.assertIn("Delete", out_text)

        # Non-notebook mode must not contain Delete shortcut in gutter
        non_nb = {"title": "Standard Menu", "items": [{"title": "Item 1"}]}
        mv_std = bashmenu.MainMenuView(config=config, menu_data=non_nb)
        mv_std.menu_stack = [non_nb]
        with patch.object(bashmenu.MainMenuView, "size", new_callable=PropertyMock, return_value=Size(80, 24)):
            out_std = mv_std.render()
        out_std_text = (
            out_std.plain if hasattr(out_std, "plain") else str(out_std)
        )
        self.assertNotIn("Delete", out_std_text)

    def test_on_key_notebook_creates_new_note(self):
        """Verify pressing 'n' when active menu is notebook calls action_new_note."""
        screen = bashmenu.BashMenuScreen(config=bashmenu.load_config()[0])
        screen.action_new_note = MagicMock()
        sub = bashmenu.build_dynamic_notebook_submenu(self.notebook_path)

        mock_mv = MagicMock()
        mock_mv.current_menu.return_value = sub
        mock_mv.show_shortcuts = False

        with unittest.mock.patch.object(bashmenu.BashMenuScreen, "menu_view", new_callable=lambda: mock_mv):
            event = MagicMock()
            event.key = "n"
            event.character = "n"
            screen.on_key(event)
            screen.action_new_note.assert_called_once()

    def test_on_key_notebook_deletes_selected_note(self):
        """Verify pressing 'd' when active menu is notebook calls action_delete_note."""
        screen = bashmenu.BashMenuScreen(config=bashmenu.load_config()[0])
        screen.action_delete_note = MagicMock()
        sub = bashmenu.build_dynamic_notebook_submenu(self.notebook_path)

        mock_mv = MagicMock()
        mock_mv.current_menu.return_value = sub
        mock_mv.show_shortcuts = False

        with unittest.mock.patch.object(bashmenu.BashMenuScreen, "menu_view", new_callable=lambda: mock_mv):
            event = MagicMock()
            event.key = "d"
            event.character = "d"
            screen.on_key(event)
            screen.action_delete_note.assert_called_once()

    def test_on_key_outside_notebook_does_not_delete_note(self):
        """Verify pressing 'd' outside notebook does not call action_delete_note."""
        screen = bashmenu.BashMenuScreen(config=bashmenu.load_config()[0])
        screen.action_delete_note = MagicMock()
        std_menu = {"title": "Standard Menu", "items": [{"title": "Option 1"}]}

        mock_mv = MagicMock()
        mock_mv.current_menu.return_value = std_menu
        mock_mv.show_shortcuts = False

        with unittest.mock.patch.object(bashmenu.BashMenuScreen, "menu_view", new_callable=lambda: mock_mv):
            event = MagicMock()
            event.key = "d"
            event.character = "d"
            screen.on_key(event)
            screen.action_delete_note.assert_not_called()

            # Calling action_delete_note directly outside notebook returns immediately
            real_action = bashmenu.BashMenuScreen.action_delete_note
            screen.confirm_delete_note = MagicMock()
            real_action(screen)
            screen.confirm_delete_note.assert_not_called()

    def test_ymlcheck_valid_option_types(self):
        """Verify ymlcheck recognizes 'notebook' as a valid option type."""
        self.assertIn("notebook", ymlcheck.VALID_OPTION_TYPES)

    def test_note_viewer_and_editor_modal_init(self):
        """Verify NoteViewerModalScreen and NoteEditorModalScreen can be instantiated."""
        viewer = bashmenu_ui.NoteViewerModalScreen("Test Title", "# Hello\nWorld", note_format="markdown")
        self.assertEqual(viewer.modal_title, "Test Title")
        self.assertEqual(viewer.content, "# Hello\nWorld")

        editor = bashmenu_ui.NoteEditorModalScreen("Test Title", "# Hello\nWorld", note_format="markdown")
        self.assertEqual(editor.modal_title, "Test Title")
        self.assertEqual(editor.initial_content, "# Hello\nWorld")

    async def test_note_viewer_modal_actions(self):
        """Verify NoteViewerModalScreen action dismissal for edit, delete, and close."""
        from textual.app import App

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            # 1. Edit
            results = []
            screen = bashmenu_ui.NoteViewerModalScreen("Title", "Content")
            app.push_screen(screen, lambda res: results.append(res))
            await pilot.pause()
            screen.action_edit_note()
            await pilot.pause()
            self.assertEqual(results, ["edit"])

            # 2. Delete
            results.clear()
            screen = bashmenu_ui.NoteViewerModalScreen("Title", "Content")
            app.push_screen(screen, lambda res: results.append(res))
            await pilot.pause()
            screen.action_delete_note()
            await pilot.pause()
            self.assertEqual(results, ["delete"])

            # 3. Close
            results.clear()
            screen = bashmenu_ui.NoteViewerModalScreen("Title", "Content")
            app.push_screen(screen, lambda res: results.append(res))
            await pilot.pause()
            screen.action_close_modal()
            await pilot.pause()
            self.assertEqual(results, ["close"])

    async def test_note_editor_modal_save_and_cancel(self):
        """Verify NoteEditorModalScreen saves text and cancels cleanly."""
        from textual.app import App

        class EditorApp(App):
            pass

        app = EditorApp()
        async with app.run_test() as pilot:
            # 1. Save
            results = []
            screen = bashmenu_ui.NoteEditorModalScreen("Title", "Initial Content")
            app.push_screen(screen, lambda res: results.append(res))
            await pilot.pause()
            screen.action_save_note()
            await pilot.pause()
            self.assertEqual(results, ["Initial Content"])

            # 2. Cancel
            results.clear()
            screen = bashmenu_ui.NoteEditorModalScreen("Title", "Initial Content")
            app.push_screen(screen, lambda res: results.append(res))
            await pilot.pause()
            screen.action_cancel_note()
            await pilot.pause()
            self.assertEqual(results, [None])

    async def test_note_viewer_interactive_checkboxes_space_and_click(self):
        """Verify markdown checkboxes toggle via space bar and mouse click."""
        from textual.app import App
        from textual.widgets import Checkbox

        content = "# Todo\n- [ ] Task 1\n- [x] Task 2\n* [ ] Task 3"

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen("Test", content)
            app.push_screen(screen)
            await pilot.pause()

            cbs = list(screen.query(Checkbox))
            self.assertEqual(len(cbs), 3)
            self.assertFalse(cbs[0].value)
            self.assertTrue(cbs[1].value)
            self.assertFalse(cbs[2].value)

            # Test space toggle on highlighted checkbox
            cbs[0].focus()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            self.assertTrue(cbs[0].value)
            self.assertIn("- [x] Task 1", screen.content)

            # Test mouse click toggle
            await pilot.click(cbs[1])
            await pilot.pause()
            self.assertFalse(cbs[1].value)
            self.assertIn("- [ ] Task 2", screen.content)

    async def test_note_viewer_interactive_checkboxes_file_persistence(self):
        """Verify interactive checkbox toggles automatically persist to notebook YAML file."""
        from textual.app import App
        from textual.widgets import Checkbox

        nb = bashmenu_ui.load_notebook(self.notebook_path)
        bashmenu_ui.add_or_update_note(nb, "Checklist", "- [ ] Item A\n- [ ] Item B")
        bashmenu_ui.save_notebook(self.notebook_path, nb)

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen(
                title="Checklist",
                content="- [ ] Item A\n- [ ] Item B",
                filepath=self.notebook_path,
                note_title="Checklist",
            )
            app.push_screen(screen)
            await pilot.pause()

            cb0 = screen.query_one("#cb_0", Checkbox)
            cb0.focus()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()

            # Verify persisted directly to notebook YAML file
            reloaded_nb = bashmenu_ui.load_notebook(self.notebook_path)
            note = bashmenu_ui.get_note_by_title(reloaded_nb, "Checklist")
            self.assertIsNotNone(note)
            self.assertIn("- [x] Item A", note["content"])
            self.assertIn("- [ ] Item B", note["content"])

    async def test_note_viewer_fenced_code_blocks_not_checkboxes(self):
        """Verify task-list syntax inside fenced code blocks remains code and not checkboxes."""
        from textual.app import App
        from textual.widgets import Checkbox

        content = "```markdown\n- [ ] Inside code fence\n```\n- [ ] Real task"

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen("Test", content)
            app.push_screen(screen)
            await pilot.pause()

            cbs = list(screen.query(Checkbox))
            self.assertEqual(len(cbs), 1)
            self.assertEqual(str(cbs[0].label), "Real task")

    async def test_note_viewer_arrow_key_navigation(self):
        """Verify up and down arrow keys navigate focus between checkboxes."""
        from textual.app import App
        from textual.widgets import Checkbox

        content = "- [ ] First\n- [ ] Second\n- [ ] Third"

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen("Test", content)
            app.push_screen(screen)
            await pilot.pause()

            cbs = list(screen.query(Checkbox))
            self.assertEqual(len(cbs), 3)

            # Initially first checkbox is focused on mount
            self.assertEqual(app.focused, cbs[0])

            # Down arrow moves focus to second checkbox
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(app.focused, cbs[1])

            # Down arrow moves focus to third checkbox
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(app.focused, cbs[2])

            # Up arrow moves focus back to second checkbox
            await pilot.press("up")
            await pilot.pause()
            self.assertEqual(app.focused, cbs[1])

    def test_resolve_notebook_path_prefers_notebooks_dir(self):
        """Verify resolve_notebook_path looks in notebooks/ first for relative paths and defaults."""
        custom_nb = os.path.join(bashmenu.NOTEBOOKS_DIR, "notes.yml")
        resolved_default = bashmenu.resolve_notebook_path(None)
        if os.path.exists(custom_nb):
            self.assertEqual(resolved_default, custom_nb)

        # Relative path resolution
        resolved_rel = bashmenu.resolve_notebook_path("test_custom.yml")
        expected_rel = os.path.join(bashmenu.NOTEBOOKS_DIR, "test_custom.yml")
        self.assertEqual(resolved_rel, expected_rel)

        # Macro interpolation
        resolved_macro = bashmenu.resolve_notebook_path("{notebooks_dir}/special.yml")
        self.assertEqual(resolved_macro, os.path.join(bashmenu.NOTEBOOKS_DIR, "special.yml"))

        resolved_alias = bashmenu.resolve_notebook_path("{notebooks}/special.yml")
        self.assertEqual(resolved_alias, os.path.join(bashmenu.NOTEBOOKS_DIR, "special.yml"))

    def test_notebooks_placeholders_interpolation(self):
        """Verify {notebooks} and {notebooks_dir} placeholders interpolate cleanly."""
        text = "Path: {notebooks_dir}/notes.yml Alias: {notebooks}"
        interpolated = bashmenu.interpolate_placeholders(text, {})
        self.assertIn(bashmenu.NOTEBOOKS_DIR, interpolated)
        self.assertNotIn("{notebooks_dir}", interpolated)
        self.assertNotIn("{notebooks}", interpolated)

    async def test_message_modal_screen_anchors_accuracy_and_fast_jump(self):
        """Verify MessageModalScreen matches anchors accurately and scrolls immediately without delay."""
        from textual.app import App

        md_text = """# HA Bash Menu Manual
- [Section 1](#1-first-section)
- [Section 2](#2-second-section--extra)

## 1. First Section
Content here.

## 2. Second Section & Extra
Detailed section content here.
""" + "\n" + "\n".join(f"Trailing content paragraph line {i}" for i in range(50))
        class ModalApp(App):
            pass

        app = ModalApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.MessageModalScreen("Test", md_text, is_help=True, is_markdown=True)
            app.push_screen(screen)
            await pilot.pause()

            # Ensure anchors are populated and accurate
            anchors = screen._compute_anchor_lines()
            self.assertIn("1-first-section", anchors)
            self.assertIn("2-second-section-extra", anchors)
            self.assertIn("2-second-section--extra", anchors)

            # Handle link jump
            screen.handle_link("#2-second-section--extra")
            await pilot.pause()

            scroller = screen.query_one("#scroll_container")
            expected_y = anchors["2-second-section--extra"]
            self.assertEqual(scroller.scroll_y, expected_y)

    async def test_note_viewer_modal_theme_contrast_and_colors(self):
        """Verify NoteViewerModalScreen applies high-contrast theme text and button colors under light themes."""
        from textual.app import App
        from textual.widgets import Button, Checkbox

        theme = bashmenu_ui.init_theme_colors("dayscape")
        note_content = "# Test Note\nThis is a paragraph.\n- [ ] Task Item 1\n- [x] Task Item 2"

        class TestModalApp(App):
            pass

        app = TestModalApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen("Test", note_content, theme=theme)
            app.push_screen(screen)
            await pilot.pause()

            # Dialog container text and background
            dialog = screen.query_one("#dialog")
            self.assertEqual(str(dialog.styles.color), "Color(0, 0, 0)")
            self.assertEqual(str(dialog.styles.background), "Color(215, 215, 255)")

            # Markdown blocks and checkboxes
            for mb in screen.query(".markdown_block"):
                self.assertEqual(str(mb.styles.color), "Color(0, 0, 0)")

            for cb in screen.query(Checkbox):
                self.assertEqual(str(cb.styles.color), "Color(0, 0, 0)")

            # Buttons fallback mapping
            btn_edit = screen.query_one("#btn_edit", Button)
            btn_delete = screen.query_one("#btn_delete", Button)
            btn_close = screen.query_one("#btn_close", Button)

            # btn_edit uses button_primary (charcoal bg #262626)
            self.assertEqual(str(btn_edit.styles.background), "Color(38, 38, 38)")
            # btn_delete falls back from button_danger to button_error (red bg #ff0000)
            self.assertEqual(str(btn_delete.styles.background), "Color(255, 0, 0)")
            # btn_close falls back from button_default to button_cancel (olive-grey bg #87875f)
            self.assertEqual(str(btn_close.styles.background), "Color(135, 135, 95)")

    def test_apply_button_theme_semantic_fallbacks(self):
        """Verify apply_button_theme properly resolves danger->error and default->cancel fallbacks."""
        from textual.widgets import Button

        theme = bashmenu_ui.init_theme_colors("dayscape")
        btn = Button("Test")

        # button_danger maps to button_error
        bashmenu_ui.apply_button_theme(btn, theme=theme, button_type="button_danger")
        self.assertEqual(str(btn.styles.background), "Color(255, 0, 0)")

        # button_default maps to button_cancel
        bashmenu_ui.apply_button_theme(btn, theme=theme, button_type="button_default")
        self.assertEqual(str(btn.styles.background), "Color(135, 135, 95)")

    def test_notebook_delete_shortcut_gutter_display(self):
        """Verify [D]: Delete keyboard shortcut is preserved and displayed in notebook help gutter."""
        from rich.style import Style

        # 1. is_formatting_tag must reject single-character shortcut codes
        self.assertFalse(bashmenu_ui.is_formatting_tag("d"))
        self.assertFalse(bashmenu_ui.is_formatting_tag("D"))
        self.assertFalse(bashmenu_ui.is_formatting_tag("n"))
        self.assertFalse(bashmenu_ui.is_formatting_tag("s"))

        # Valid formatting tags must still be accepted
        self.assertTrue(bashmenu_ui.is_formatting_tag("b"))
        self.assertTrue(bashmenu_ui.is_formatting_tag("u"))
        self.assertTrue(bashmenu_ui.is_formatting_tag("dim"))
        self.assertTrue(bashmenu_ui.is_formatting_tag("reverse"))

        # 2. formatting_to_rich_text must preserve [D]: Delete intact
        gutter_str = (
            "[UP/DN]: Nav | [ENTER]: Read | [N]: New Note | [D]: Delete | "
            "[F1]: Help | [F2]: Themes | [F7]: Gutter | [F8]: ThemeEdit | [ESC]: Back"
        )
        rt = bashmenu_ui.formatting_to_rich_text(gutter_str)
        self.assertIn("[D]: Delete", rt.plain)
        self.assertNotIn(": Delete", rt.plain.replace("[D]: Delete", ""))

        # 3. MainMenuView gutter rendering in notebook mode retains [D]: Delete
        bm = bashmenu.MainMenuView()
        styles = {
            "help_text": Style(color="cyan"),
            "gutter": Style(color="blue"),
            "border": Style(color="white"),
        }
        rendered = bm._render_raw_gutter_lines([gutter_str], ["dracula | 12:00"], 1, 140, styles, w=151)
        self.assertTrue(len(rendered) > 0)
        self.assertIn("[D]: Delete", rendered[0].plain)

    async def test_notebook_text_area_auto_format_checkboxes(self):
        """Verify Enter automatically continues checkboxes and de-escalates empty checkboxes."""
        from textual.app import App, ComposeResult

        class AreaApp(App):
            def compose(self) -> ComposeResult:
                yield bashmenu_ui.NotebookTextArea("", id="editor")

        app = AreaApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", bashmenu_ui.NotebookTextArea)
            ed.load_text("- [ ] Task 1")
            ed.move_cursor((0, len("- [ ] Task 1")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "- [ ] Task 1\n- [ ] ")

            # Hitting Enter on empty checkbox de-escalates to empty line
            await pilot.press("enter")
            self.assertEqual(ed.text, "- [ ] Task 1\n")

            # Checkbox with checked mark [x] continues as unchecked [ ]
            ed.load_text("- [x] Done Task")
            ed.move_cursor((0, len("- [x] Done Task")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "- [x] Done Task\n- [ ] ")

            # Indented checkbox
            ed.load_text("  - [ ] Subtask")
            ed.move_cursor((0, len("  - [ ] Subtask")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "  - [ ] Subtask\n  - [ ] ")
            # De-escalate indented checkbox preserves leading indentation
            await pilot.press("enter")
            self.assertEqual(ed.text, "  - [ ] Subtask\n  ")

    async def test_notebook_text_area_ordered_and_unordered_lists(self):
        """Verify Enter continues ordered/unordered lists and de-escalates empty items."""
        from textual.app import App, ComposeResult

        class AreaApp(App):
            def compose(self) -> ComposeResult:
                yield bashmenu_ui.NotebookTextArea("", id="editor")

        app = AreaApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", bashmenu_ui.NotebookTextArea)
            # Ordered numbered list
            ed.load_text("1. First item")
            ed.move_cursor((0, len("1. First item")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "1. First item\n2. ")
            await pilot.press("enter")
            self.assertEqual(ed.text, "1. First item\n")

            # Parenthesis ordered list
            ed.load_text("1) Alpha")
            ed.move_cursor((0, len("1) Alpha")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "1) Alpha\n2) ")

            # Unordered bullet lists: -, *, +
            for bullet in ("-", "*", "+"):
                ed.load_text(f"{bullet} Bullet item")
                ed.move_cursor((0, len(f"{bullet} Bullet item")))
                await pilot.press("enter")
                self.assertEqual(ed.text, f"{bullet} Bullet item\n{bullet} ")
                await pilot.press("enter")
                self.assertEqual(ed.text, f"{bullet} Bullet item\n")

            # Blockquotes
            ed.load_text("> Quote")
            ed.move_cursor((0, len("> Quote")))
            await pilot.press("enter")
            self.assertEqual(ed.text, "> Quote\n> ")
            await pilot.press("enter")
            self.assertEqual(ed.text, "> Quote\n")

    async def test_notebook_text_area_ghost_text_and_tab_completion(self):
        """Verify ghost text suggestions appear for partial checkboxes and Tab completes them."""
        from textual.app import App, ComposeResult

        class AreaApp(App):
            def compose(self) -> ComposeResult:
                yield bashmenu_ui.NotebookTextArea("", id="editor")

        app = AreaApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", bashmenu_ui.NotebookTextArea)
            # Type "- [" -> ghost suggestion should be " ] "
            await pilot.press("-", " ", "[")
            self.assertEqual(ed.text, "- [")
            self.assertEqual(ed.suggestion, " ] ")
            await pilot.press("tab")
            self.assertEqual(ed.text, "- [ ] ")
            self.assertEqual(ed.suggestion, "")

    async def test_notebook_cross_interface_clipboard(self):
        """Verify clipboard and cutbuffer interoperability between notes and bashedit."""
        import bashedit

        test_msg = "Hello Notebook Clipboard Sync 123"
        # Test unified setting
        bashmenu_ui.set_system_clipboard(test_msg)
        # Should be retrievable from bashmenu_ui and bashedit
        self.assertEqual(bashmenu_ui.get_system_clipboard(), test_msg)
        self.assertEqual(bashedit.get_system_clipboard(), test_msg)

        # Shared cutbuffer file fallback
        cb_path = bashmenu_ui.get_shared_cutbuffer_path()
        self.assertTrue(os.path.isfile(cb_path))
        with open(cb_path, "r", encoding="utf-8") as f:  # noqa: ASYNC230
            self.assertEqual(f.read(), test_msg)

        # NoteViewerModalScreen copy action
        viewer = bashmenu_ui.NoteViewerModalScreen("Test Note", "Markdown body content to copy")
        viewer.action_copy_note()
        self.assertEqual(bashmenu_ui.get_system_clipboard(), "Markdown body content to copy")
        self.assertEqual(bashedit.get_system_clipboard(), "Markdown body content to copy")

        # Copy from bashedit into NotebookTextArea
        bashedit.set_system_clipboard("Copied from bashedit editor")
        from textual.app import App, ComposeResult

        class AreaApp(App):
            def compose(self) -> ComposeResult:
                yield bashmenu_ui.NotebookTextArea("", id="editor")

        app = AreaApp()
        async with app.run_test():
            ed = app.query_one("#editor", bashmenu_ui.NotebookTextArea)
            ed.action_paste()
            self.assertEqual(ed.text, "Copied from bashedit editor")

            # Cut line in NotebookTextArea and verify bashedit can paste it
            ed.move_cursor((0, 0))
            ed.action_cut()
            self.assertEqual(ed.text, "")
            self.assertEqual(bashedit.get_system_clipboard(), "Copied from bashedit editor")

    async def test_note_viewer_text_wrapping_for_checkboxes(self):
        """Verify NoteViewerModalScreen uses MarkdownCheckbox to wrap multi-line task text without truncation."""
        from textual.app import App
        from textual.widgets import Checkbox

        long_task = (
            "RESPONSIVENESS: notebook UI, particularily in edit mode has become very sluggish. "
            "This needs an immediate fix as it's so sluggish it's almost unusable. When any window "
            "is currently over the main menu UI (i.e., help modal, reference modals, selection popups, "
            "etc, notebook notes) background ticks should ALL pause until the window is closed."
        )
        content = f"- [ ] Short item\n- [x] {long_task}"

        class ViewerApp(App):
            pass

        app = ViewerApp()
        async with app.run_test() as pilot:
            screen = bashmenu_ui.NoteViewerModalScreen("Test", content)
            app.push_screen(screen)
            await pilot.pause()

            cbs = list(screen.query(Checkbox))
            self.assertEqual(len(cbs), 2)

            # Check that MarkdownCheckbox is used and subclasses Checkbox
            self.assertIsInstance(cbs[0], bashmenu_ui.MarkdownCheckbox)
            self.assertIsInstance(cbs[1], bashmenu_ui.MarkdownCheckbox)

            # Short task height is 1, long wrapped task height is > 1 (e.g. 3-8 lines)
            self.assertEqual(cbs[0].size.height, 1)
            self.assertGreater(cbs[1].size.height, 1)

            # Label preserves full text without truncation or ellipsis
            self.assertEqual(str(cbs[1].label), long_task)

            # Interactive toggle via space and click
            cbs[0].focus()
            await pilot.press("space")
            await pilot.pause()
            self.assertTrue(cbs[0].value)

            await pilot.click(cbs[1])
            await pilot.pause()
            self.assertFalse(cbs[1].value)

    async def test_modal_pauses_background_ticks(self):
        """Verify opening any modal window pauses background timers on BashMenuScreen."""
        from textual.app import App

        import bashmenu

        cfg = {
            "version": "0.0.1",
            "theme": "default",
            "menu": {"title": "Test Menu", "items": [{"name": "Item 1", "action": "echo 1"}]},
        }

        class MenuApp(App):
            pass

        app = MenuApp()
        async with app.run_test() as pilot:
            screen = bashmenu.BashMenuScreen(config=cfg)
            await app.push_screen(screen)
            await pilot.pause()

            # Background timers initially active
            self.assertFalse(screen._is_covered())
            self.assertTrue(screen._refresh_timer._active.is_set())
            self.assertTrue(screen.menu_view._marquee_timer._active.is_set())

            # Pushing a modal screen pauses timers and marks screen covered
            modal = bashmenu_ui.NoteViewerModalScreen("Notes", "- [ ] Task")
            await app.push_screen(modal)
            await pilot.pause()

            self.assertTrue(screen._is_covered())
            self.assertFalse(screen._refresh_timer._active.is_set())
            self.assertFalse(screen.menu_view._marquee_timer._active.is_set())

            # Popping modal resumes timers and marks screen uncovered
            app.pop_screen()
            await pilot.pause()

            self.assertFalse(screen._is_covered())
            self.assertTrue(screen._refresh_timer._active.is_set())
            self.assertTrue(screen.menu_view._marquee_timer._active.is_set())


if __name__ == "__main__":
    unittest.main()


