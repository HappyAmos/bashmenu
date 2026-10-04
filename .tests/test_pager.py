"""Unit tests for the scripts/pager.sh utility."""

import fcntl
import os
import pty
import subprocess
import sys
import tempfile
import termios
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

PAGER_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "pager.sh")


class TestPagerScript(unittest.TestCase):
    """Test suite verifying scripts/pager.sh performance, flags, and TUI."""

    def test_help_and_version(self):
        """Verify -h/--help and -V/--version flags exit cleanly."""
        res_help = subprocess.run(
            ["bash", PAGER_SCRIPT, "--help"],
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("Usage:", res_help.stdout)
        self.assertIn("Open in editor", res_help.stdout)

        res_ver = subprocess.run(
            ["bash", PAGER_SCRIPT, "--version"],
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("1.0.0", res_ver.stdout)

    def test_passthrough_stdin(self):
        """Verify non-interactive pipeline pass-through."""
        input_data = "line 1\nline 2\nline 3\n"
        res = subprocess.run(
            ["bash", PAGER_SCRIPT],
            input=input_data,
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout, input_data)

    def test_passthrough_max_lines(self):
        """Verify --max-lines truncates input in non-interactive pass-through."""
        input_data = "".join(f"line {i}\n" for i in range(1, 20))
        res = subprocess.run(
            ["bash", PAGER_SCRIPT, "--max-lines=5"],
            input=input_data,
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(res.returncode, 0)
        output_lines = res.stdout.strip().splitlines()
        self.assertEqual(len(output_lines), 5)
        self.assertIn("truncated", res.stderr)

    def test_interactive_pty_navigation(self):
        """Verify interactive execution, scrolling, and clean exit via PTY."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            for i in range(1, 100):
                tf.write(f"Sample line number {i}\n")
            temp_path = tf.name

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            # Let initial frame render
            time.sleep(0.15)
            # Navigate: down, space (pgdn), up, b (pgup), then quit
            os.write(master, b"j")
            time.sleep(0.05)
            os.write(master, b" ")
            time.sleep(0.05)
            os.write(master, b"k")
            time.sleep(0.05)
            os.write(master, b"b")
            time.sleep(0.05)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break
            self.assertIn(b"Sample line number", out)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_interactive_ansi_color_and_strip(self):
        """Verify ANSI escapes are rendered normally and stripped with -c."""
        # Test 1: Color preserved
        master1, slave1 = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("\033[31mRed Text\033[0m\n")
            temp_path = tf.name

        try:
            proc1 = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave1,
                stdout=slave1,
                stderr=slave1,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave1)
            time.sleep(0.15)
            os.write(master1, b"q")
            proc1.wait(timeout=3)
            self.assertEqual(proc1.returncode, 0)
            out1 = b""
            while True:
                try:
                    chunk = os.read(master1, 1024)
                    if not chunk:
                        break
                    out1 += chunk
                except OSError:
                    break
            self.assertIn(b"\x1b[31m", out1)
        finally:
            os.close(master1)

        # Test 2: Color stripped with --no-color
        master2, slave2 = pty.openpty()
        try:
            proc2 = subprocess.Popen(
                ["bash", PAGER_SCRIPT, "--no-color", temp_path],
                stdin=slave2,
                stdout=slave2,
                stderr=slave2,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave2)
            time.sleep(0.15)
            os.write(master2, b"q")
            proc2.wait(timeout=3)
            self.assertEqual(proc2.returncode, 0)
            out2 = b""
            while True:
                try:
                    chunk = os.read(master2, 1024)
                    if not chunk:
                        break
                    out2 += chunk
                except OSError:
                    break
            self.assertIn(b"Red Text", out2)
            self.assertNotIn(b"\x1b[31m", out2)
        finally:
            os.close(master2)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_bottom_scroll_and_tildes(self):
        """Verify bottom-most item scrolls to top and non-file rows show '~'."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("Alpha\nBeta\n\nDelta\nOmega\n")
            temp_path = tf.name

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            # Let initial frame render
            time.sleep(0.15)
            # Press 'G' to jump to bottom so final line (Omega) scrolls to top
            os.write(master, b"G")
            time.sleep(0.1)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            # In the final view, Omega should be at row 1 (1;1HOmega), followed by '~' on row 2
            self.assertIn("1;1HOmega", text)
            self.assertIn("2;1H~", text)
            self.assertIn("BOT", text)
            # Ensure Omega itself does not have a tilde attached
            self.assertNotIn("~Omega", text)
            self.assertNotIn("Omega~", text)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_editor_shortcut_file(self):
        """Verify pressing 'e' opens the file in $EDITOR and reloads modified content."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("Initial line 1\nInitial line 2\n")
            temp_path = tf.name

        with tempfile.NamedTemporaryFile("w+", delete=False) as ef:
            ef.write('#!/bin/sh\nfor arg in "$@"; do [ -f "$arg" ] && echo "Appended by editor" >> "$arg"; done\n')
            editor_path = ef.name
        os.chmod(editor_path, 0o755)

        env = os.environ.copy()
        env["EDITOR"] = editor_path

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.15)
            os.write(master, b"e")
            time.sleep(0.2)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("Appended by editor", text)

            with open(temp_path, "r") as f:
                content = f.read()
            self.assertIn("Appended by editor", content)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(editor_path):
                os.remove(editor_path)

    def test_editor_shortcut_piped_input(self):
        """Verify pressing 'e' on piped input shows 'cannot edit piped input' message."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        try:
            proc = subprocess.Popen(
                f"printf 'line 1\\nline 2\\n' | bash {PAGER_SCRIPT}",
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.2)
            os.write(master, b"e")
            time.sleep(0.1)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("cannot edit piped input", text)
        finally:
            os.close(master)

    def test_editor_shortcut_piped_with_file_flag(self):
        """Verify pressing 'e' on piped input with --file flag opens the file and runs reload command."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("# Markdown Title\nSome content\n")
            target_path = tf.name

        with tempfile.NamedTemporaryFile("w+", delete=False) as ef:
            ef.write('#!/bin/sh\nfor arg in "$@"; do [ -f "$arg" ] && echo "Appended to md" >> "$arg"; done\n')
            editor_path = ef.name
        os.chmod(editor_path, 0o755)

        env = os.environ.copy()
        env["EDITOR"] = editor_path

        try:
            reload_cmd = f"cat {target_path}"
            proc = subprocess.Popen(
                f"printf 'Formatted Initial Stream\\n' | bash {PAGER_SCRIPT} --file='{target_path}' --reload-cmd='{reload_cmd}'",
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.15)
            os.write(master, b"e")
            time.sleep(0.2)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("Appended to md", text)

            with open(target_path, "r") as f:
                self.assertIn("Appended to md", f.read())
        finally:
            os.close(master)
            if os.path.exists(target_path):
                os.remove(target_path)
            if os.path.exists(editor_path):
                os.remove(editor_path)

    def test_pager_search(self):
        """Verify interactive search with / and jumping forward."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            for i in range(1, 40):
                tf.write(f"Line {i}\n")
            tf.write("Line 40 UNIQUE_SEARCH_KEYWORD\n")
            for i in range(41, 100):
                tf.write(f"Line {i}\n")
            temp_path = tf.name

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.15)
            os.write(master, b"/UNIQUE_SEARCH_KEYWORD\n")
            time.sleep(0.2)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("UNIQUE_SEARCH_KEYWORD", text)
            self.assertIn("/UNIQUE_SEARCH_KEYWORD", text)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_pager_link_navigation(self):
        """Verify interactive link dialog and anchor jump with l key."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("# Table of Contents\n\n")
            tf.write("- [1. Target Section](#1-target-section)\n\n")
            for i in range(1, 40):
                tf.write(f"Filler line {i}\n")
            tf.write("## 1. Target Section\n")
            tf.write("Content of target section.\n")
            temp_path = tf.name

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.15)
            os.write(master, b"l")
            time.sleep(0.15)
            os.write(master, b"\n")
            time.sleep(0.2)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("jumped to #1-target-section", text)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_status_bar_filename_badge(self):
        """Verify file viewing renders the centered [ filename.ext ] badge."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        with tempfile.NamedTemporaryFile(
            "w+", suffix="_report.txt", delete=False
        ) as tf:
            tf.write("Hello world file content line 1\nLine 2\n")
            temp_path = tf.name

        base_name = os.path.basename(temp_path)
        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, temp_path],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)

            time.sleep(0.15)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            expected_badge = f"[ {base_name} ]"
            self.assertIn(expected_badge, text)
        finally:
            os.close(master)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_status_bar_stdin_badge(self):
        """Verify piped stdin renders the centered [ <stdin> ] badge."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(1, termios.TIOCSCTTY, 0)

        # Pipe stdin into pager.sh using pty for interactive tty output
        pipe_r, pipe_w = os.pipe()
        os.write(pipe_w, b"Piped line 1\nPiped line 2\n")
        os.close(pipe_w)

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT],
                stdin=pipe_r,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)
            os.close(pipe_r)

            time.sleep(0.15)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("[ <stdin> ]", text)
        finally:
            os.close(master)

    def test_status_bar_file_flag_badge(self):
        """Verify --file= flag renders the specified filename badge."""
        master, slave = pty.openpty()

        def preexec():
            os.setsid()
            fcntl.ioctl(1, termios.TIOCSCTTY, 0)

        pipe_r, pipe_w = os.pipe()
        os.write(pipe_w, b"Stream line 1\nStream line 2\n")
        os.close(pipe_w)

        try:
            proc = subprocess.Popen(
                ["bash", PAGER_SCRIPT, "--file=manual_stream.md"],
                stdin=pipe_r,
                stdout=slave,
                stderr=slave,
                preexec_fn=preexec,  # noqa: PLW1509
                close_fds=False,
                cwd=PROJECT_ROOT,
            )
            os.close(slave)
            os.close(pipe_r)

            time.sleep(0.15)
            os.write(master, b"q")

            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)

            out = b""
            while True:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break

            text = out.decode("utf-8", errors="replace")
            self.assertIn("[ manual_stream.md ]", text)
        finally:
            os.close(master)

    def test_status_bar_centering_and_columns(self):
        """Verify build_bar accurately centers badge and pads to exact COLS."""
        cmd = """
        source scripts/pager.sh >/dev/null 2>&1 || true
        for cols in 120 80 60 40; do
            COLS=$cols
            TOTAL=50
            TOP_LINE=1
            LAST_SHOWN=23
            SHOW_HELP=1
            MESSAGE=""
            HAVE_FILES=1
            FILES=("doc.md")
            ORIGINAL_FILE=""
            build_bar
            printf "%d:%d:%s\\n" "$cols" "${#BAR_LINE}" "$BAR_LINE"
        done
        """
        res = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(res.returncode, 0)
        lines = res.stdout.strip().splitlines()
        for line in lines:
            parts = line.split(":", 2)
            cols = int(parts[0])
            bar_len = int(parts[1])
            bar_text = parts[2]
            self.assertEqual(
                bar_len,
                cols,
                f"Bar length {bar_len} does not match COLS {cols}",
            )
            self.assertIn("[ doc.md ]", bar_text)

    def test_spool_directory_uses_cache_dir(self):
        """Verify pager.sh creates and cleans up spools in CACHE_DIR/spool."""
        with tempfile.TemporaryDirectory() as custom_cache:
            custom_env = os.environ.copy()
            custom_env["CACHE_DIR"] = custom_cache

            res = subprocess.run(
                ["bash", PAGER_SCRIPT],
                input="Test content for spool\n",
                capture_output=True,
                text=True,
                check=False,
                cwd=PROJECT_ROOT,
                env=custom_env,
            )
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, "Test content for spool\n")

            spool_dir = os.path.join(custom_cache, "spool")
            self.assertTrue(os.path.isdir(spool_dir))
            # Verify temporary spool files are cleaned up on exit
            self.assertEqual(os.listdir(spool_dir), [])


if __name__ == "__main__":
    unittest.main()

