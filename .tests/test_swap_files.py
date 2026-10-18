import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from textual.app import App, ComposeResult
from textual.events import Key

import bashedit


class TestSwapFileCore(unittest.TestCase):
    """Test swap file utilities: hashing, path resolution, PID liveness, serialization, and cleanup."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = os.path.join(self.temp_dir.name, "sample.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_compute_file_sha256(self):
        self.assertEqual(bashedit.compute_file_sha256(""), "")
        self.assertEqual(bashedit.compute_file_sha256("/nonexistent/file.txt"), "")
        h = bashedit.compute_file_sha256(self.test_file)
        self.assertTrue(len(h) == 64)

    def test_get_swap_path_colocated(self):
        swp = bashedit.get_swap_path(self.test_file)
        expected = os.path.join(self.temp_dir.name, ".sample.txt.swp")
        self.assertEqual(swp, expected)

    def test_is_pid_running(self):
        self.assertFalse(bashedit.is_pid_running(0))
        self.assertFalse(bashedit.is_pid_running(-1))
        self.assertTrue(bashedit.is_pid_running(os.getpid()))
        self.assertFalse(bashedit.is_pid_running(99999999))

    def test_write_and_read_swap_file(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        lines = ["Recovered Line A", "Recovered Line B"]
        ok = bashedit.write_swap_file(
            swp_path,
            self.test_file,
            lines,
            base_mtime=os.path.getmtime(self.test_file),
            base_sha256=bashedit.compute_file_sha256(self.test_file),
        )
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(swp_path))

        hdr, read_lines = bashedit.read_swap_file(swp_path)
        self.assertIsNotNone(hdr)
        self.assertEqual(hdr["magic"], bashedit.SWAP_MAGIC)
        self.assertEqual(hdr["file_path"], os.path.abspath(self.test_file))
        self.assertEqual(read_lines, lines)

    def test_remove_swap_file(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        bashedit.write_swap_file(swp_path, self.test_file, ["test"])
        self.assertTrue(os.path.exists(swp_path))
        self.assertTrue(bashedit.remove_swap_file(swp_path))
        self.assertFalse(os.path.exists(swp_path))
        self.assertFalse(bashedit.remove_swap_file(swp_path))


class TestSwapPromptModal(unittest.TestCase):
    """Test SwapPromptModalScreen compose and dismiss actions."""

    def test_modal_collision_mode_dismiss_actions(self):
        hdr = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": 12345,
            "user": "tester",
            "host": "testhost",
            "updated_at": time.time(),
        }
        modal = bashedit.SwapPromptModalScreen(
            mode="collision",
            file_path="/path/test.txt",
            header=hdr,
            swap_lines_count=10,
            disk_lines_count=5,
        )

        modal.dismiss = MagicMock()
        modal.action_dismiss_readonly()
        modal.dismiss.assert_called_with("readonly")

        modal.dismiss.reset_mock()
        modal.action_dismiss_edit_anyway()
        modal.dismiss.assert_called_with("edit_anyway")

        modal.dismiss.reset_mock()
        modal.action_dismiss_abort()
        modal.dismiss.assert_called_with("abort")

    def test_modal_recovery_mode_dismiss_actions(self):
        hdr = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": 999999,
            "user": "crashed_user",
            "host": "testhost",
            "updated_at": time.time(),
        }
        modal = bashedit.SwapPromptModalScreen(
            mode="recovery",
            file_path="/path/test.txt",
            header=hdr,
            swap_lines_count=12,
            disk_lines_count=8,
        )

        modal.dismiss = MagicMock()
        modal.action_dismiss_recover()
        modal.dismiss.assert_called_with("recover")

        modal.dismiss.reset_mock()
        modal.action_dismiss_delete()
        modal.dismiss.assert_called_with("delete")


def _create_raw_swap(swp_path: str, header: dict, payload: str) -> None:
    import json

    with open(swp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + bashedit.SWAP_DELIMITER + payload)


class TestBashEditSwapIntegration(unittest.IsolatedAsyncioTestCase):
    """Test BashEditScreen swap file lifecycle, crash recovery, collision, and read-only mode."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = os.path.join(self.temp_dir.name, "doc.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("Disk Line 1\nDisk Line 2\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_swap_file_created_on_open_and_removed_on_clean_exit(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        self.assertFalse(os.path.exists(swp_path))

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        async with app.run_test() as pilot:
            screen = app.query_one(bashedit.BashEditScreen)
            await pilot.pause()
            # Swap file should now exist for the open document
            self.assertTrue(os.path.exists(swp_path))
            hdr, lines = bashedit.read_swap_file(swp_path)
            self.assertEqual(hdr["pid"], os.getpid())
            self.assertEqual(lines, ["Disk Line 1", "Disk Line 2"])

            # Clean exit should remove swap file
            screen.action_exit_editor_force()
            await pilot.pause()
            self.assertFalse(os.path.exists(swp_path))

    async def test_recovery_flow_when_dead_pid_swap_exists(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        recovered_lines = ["Unsaved Edit 1", "Unsaved Edit 2", "Unsaved Edit 3"]

        # Simulate earlier crashed session
        header = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": 99999999,  # Inactive PID
            "user": "crash_user",
            "host": "localhost",
            "file_path": os.path.abspath(self.test_file),
            "updated_at": time.time(),
            "base_mtime": 0.0,
            "base_sha256": "",
            "line_count": len(recovered_lines),
        }
        _create_raw_swap(swp_path, header, "\n".join(recovered_lines))

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        # Mock push_screen to simulate user selecting "recover"
        app = TestApp(self.test_file)
        with patch.object(App, "push_screen") as mock_push:

            def push_side_effect(screen_obj, callback=None):
                if isinstance(screen_obj, bashedit.SwapPromptModalScreen) and callback:
                    callback("recover")

            mock_push.side_effect = push_side_effect
            async with app.run_test() as pilot:
                screen = app.query_one(bashedit.BashEditScreen)
                ed = screen.query_one("#editor_widget", bashedit.EditorWidget)
                await pilot.pause()

                # Verify recovered lines are loaded into editor widget
                self.assertEqual(ed.lines, recovered_lines)
                self.assertTrue(ed.modified)
                self.assertTrue(screen.tabs[0].modified)

                # Clean exit removes swap
                screen.action_exit_editor_force()
                await pilot.pause()
                self.assertFalse(os.path.exists(swp_path))

    async def test_collision_flow_opens_read_only(self):
        swp_path = bashedit.get_swap_path(self.test_file)

        # Simulate another active process PID
        active_pid = os.getppid()  # Parent process is guaranteed running
        header = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": active_pid,
            "user": "other_user",
            "host": "localhost",
            "file_path": os.path.abspath(self.test_file),
            "updated_at": time.time(),
            "base_mtime": 0.0,
            "base_sha256": "",
            "line_count": 2,
        }
        _create_raw_swap(swp_path, header, "Disk Line 1\nDisk Line 2")

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        with patch.object(App, "push_screen") as mock_push:

            def push_side_effect(screen_obj, callback=None):
                if isinstance(screen_obj, bashedit.SwapPromptModalScreen) and callback:
                    callback("readonly")

            mock_push.side_effect = push_side_effect
            async with app.run_test() as pilot:
                screen = app.query_one(bashedit.BashEditScreen)
                ed = screen.query_one("#editor_widget", bashedit.EditorWidget)
                await pilot.pause()

                tab = screen.tabs[0]
                self.assertTrue(tab.read_only)
                self.assertFalse(tab.swap_enabled)

                # Keystroke should not modify lines in Read-Only mode
                orig_lines = list(ed.lines)
                screen.on_key(Key("a", "a"))
                await pilot.pause()
                self.assertEqual(ed.lines, orig_lines)

                # Action cut line should be blocked
                screen.action_cut_line()
                self.assertEqual(ed.lines, orig_lines)

                # Save file should be blocked in Read-Only mode
                screen.action_save_file()
                status_text = str(screen.query_one("#editor_status").render())
                self.assertIn("Read-Only Mode", status_text)

                # Safe exit should NOT remove the other user's swap file
                screen.action_exit_editor_force()
                await pilot.pause()
                self.assertTrue(os.path.exists(swp_path))

    async def test_keystroke_and_timer_swap_flush(self):
        swp_path = bashedit.get_swap_path(self.test_file)

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        async with app.run_test() as pilot:
            screen = app.query_one(bashedit.BashEditScreen)
            ed = screen.query_one("#editor_widget", bashedit.EditorWidget)
            await pilot.pause()

            # Insert newline and characters
            ed.insert_newline()
            ed.insert_char("Flushed Content")
            ed.modified = True
            screen.tabs[0].modified = True

            # Trigger flush_dirty_swaps
            screen.flush_dirty_swaps()
            await pilot.pause()

            # Swap file on disk should reflect updated lines
            _, swp_lines = bashedit.read_swap_file(swp_path)
            self.assertEqual(swp_lines, ed.lines)

            # Saving file resets modified and updates swap
            screen.action_save_file()
            self.assertFalse(screen.tabs[0].modified)
            self.assertTrue(os.path.exists(swp_path))

            # Close clean tab removes swap file
            screen.action_close_tab(0)
            await pilot.pause()
            self.assertFalse(os.path.exists(swp_path))

    async def test_recovery_flow_delete_swap_file(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        header = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": 99999999,
            "user": "crash_user",
            "host": "localhost",
            "file_path": os.path.abspath(self.test_file),
            "updated_at": time.time(),
            "base_mtime": 0.0,
            "base_sha256": "",
            "line_count": 1,
        }
        _create_raw_swap(swp_path, header, "Stale Unsaved Edits")

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        with patch.object(App, "push_screen") as mock_push:

            def push_side_effect(screen_obj, callback=None):
                if isinstance(screen_obj, bashedit.SwapPromptModalScreen) and callback:
                    callback("delete")

            mock_push.side_effect = push_side_effect
            async with app.run_test() as pilot:
                screen = app.query_one(bashedit.BashEditScreen)
                ed = screen.query_one("#editor_widget", bashedit.EditorWidget)
                await pilot.pause()

                # Disk lines preserved, not stale swap lines
                self.assertEqual(ed.lines, ["Disk Line 1", "Disk Line 2"])
                self.assertFalse(ed.modified)
                screen.action_exit_editor_force()

    async def test_collision_flow_edit_anyway(self):
        swp_path = bashedit.get_swap_path(self.test_file)
        header = {
            "magic": bashedit.SWAP_MAGIC,
            "pid": os.getppid(),
            "user": "other_user",
            "host": "localhost",
            "file_path": os.path.abspath(self.test_file),
            "updated_at": time.time(),
            "base_mtime": 0.0,
            "base_sha256": "",
            "line_count": 2,
        }
        _create_raw_swap(swp_path, header, "Disk Line 1\nDisk Line 2")

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        with patch.object(App, "push_screen") as mock_push:

            def push_side_effect(screen_obj, callback=None):
                if isinstance(screen_obj, bashedit.SwapPromptModalScreen) and callback:
                    callback("edit_anyway")

            mock_push.side_effect = push_side_effect
            async with app.run_test() as pilot:
                screen = app.query_one(bashedit.BashEditScreen)
                ed = screen.query_one("#editor_widget", bashedit.EditorWidget)
                await pilot.pause()

                tab = screen.tabs[0]
                self.assertFalse(tab.read_only)
                self.assertTrue(tab.swap_enabled)

                # Editing is allowed
                screen.on_key(Key("a", "a"))
                await pilot.pause()
                self.assertIn("a", ed.lines[0])

                screen.action_exit_editor_force()

    async def test_keystroke_counter_triggers_flush(self):
        swp_path = bashedit.get_swap_path(self.test_file)

        class TestApp(App):
            def __init__(self, file_path):
                super().__init__()
                self.file_path = file_path

            def compose(self) -> ComposeResult:
                yield bashedit.BashEditScreen(file_path=self.file_path)

        app = TestApp(self.test_file)
        async with app.run_test() as pilot:
            screen = app.query_one(bashedit.BashEditScreen)
            await pilot.pause()

            # Record 50 edit operations
            for _ in range(51):
                screen.on_key(Key("x", "x"))
            await pilot.pause()

            # Verify swap was flushed
            _, lines = bashedit.read_swap_file(swp_path)
            self.assertTrue(lines[0].startswith("x" * 20))
            screen.action_exit_editor_force()


if __name__ == "__main__":
    unittest.main()
