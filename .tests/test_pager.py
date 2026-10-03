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


if __name__ == "__main__":
    unittest.main()
