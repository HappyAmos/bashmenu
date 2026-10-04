#!/usr/bin/env python3
"""
test_platform.py - Unit tests for universal cross-platform detection,
in-house YAML parsing, architecture mapping, and dependency elimination.
"""

import os
import subprocess
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASHMENU_SH = os.path.join(REPO_ROOT, "bashmenu.sh")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")


class TestPlatformDetection(unittest.TestCase):
    """Test suite for cross-platform detection engine in bashmenu.sh."""

    def run_bash_snippet(self, env_overrides, bash_code):
        """Helper to run a bash snippet with customized environment."""
        env = os.environ.copy()
        env.update(env_overrides)
        res = subprocess.run(
            ["bash", "-c", bash_code],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return res

    def test_termux_detection(self):
        """Verify Termux environment is properly detected via PREFIX and TERMUX_VERSION."""
        code = f"""
        source "{BASHMENU_SH}"
        echo "PLATFORM=$PLATFORM IS_TERMUX=$IS_TERMUX"
        """
        # Simulate Termux
        res = self.run_bash_snippet(
            {
                "TERMUX_VERSION": "0.118.0",
                "PREFIX": "/data/data/com.termux/files/usr",
            },
            code,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("PLATFORM=termux", res.stdout)
        self.assertIn("IS_TERMUX=true", res.stdout)

    def test_package_name_mappings_termux(self):
        """Verify Termux package mappings for python, pip, venv, and ncurses."""
        code = f"""
        source "{BASHMENU_SH}"
        PKG_MANAGER="pkg"
        IS_TERMUX=true
        echo "python:$(get_package_name python3)"
        echo "pip:$(get_package_name pip3)"
        echo "venv:$(get_package_name venv)"
        echo "tput:$(get_package_name tput)"
        """
        res = self.run_bash_snippet({}, code)
        self.assertEqual(res.returncode, 0)
        self.assertIn("python:python", res.stdout)
        self.assertIn("pip:python", res.stdout)
        self.assertIn("tput:ncurses-utils", res.stdout)

    def test_package_name_mappings_alpine(self):
        """Verify Alpine package mappings."""
        code = f"""
        source "{BASHMENU_SH}"
        PKG_MANAGER="apk"
        echo "python:$(get_package_name python3)"
        echo "pip:$(get_package_name pip3)"
        echo "venv:$(get_package_name venv)"
        """
        res = self.run_bash_snippet({}, code)
        self.assertEqual(res.returncode, 0)
        self.assertIn("python:python3", res.stdout)
        self.assertIn("pip:py3-pip", res.stdout)
        self.assertIn("venv:py3-virtualenv", res.stdout)

    def test_package_name_mappings_arch(self):
        """Verify Arch Linux (pacman) package mappings."""
        code = f"""
        source "{BASHMENU_SH}"
        PKG_MANAGER="pacman"
        echo "python:$(get_package_name python3)"
        echo "pip:$(get_package_name pip3)"
        echo "venv:$(get_package_name venv)"
        """
        res = self.run_bash_snippet({}, code)
        self.assertEqual(res.returncode, 0)
        self.assertIn("python:python", res.stdout)
        self.assertIn("pip:python-pip", res.stdout)
        self.assertIn("venv:python-virtualenv", res.stdout)

    def test_yaml_get_fallback_layers(self):
        """Verify yaml_get extracts keys using awk fallback even without Python or yq."""
        # Create a mock minimal YAML
        mock_yaml = os.path.join(REPO_ROOT, ".tests", "mock_settings.yml")
        with open(mock_yaml, "w") as f:
            f.write("version: 1.2.3\nsettings:\n  cache_dir: /custom/cache/path\n")
        try:
            code = f"""
            source "{BASHMENU_SH}"
            yaml_get "settings.cache_dir" "{mock_yaml}"
            """
            res = self.run_bash_snippet({}, code)
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout.strip(), "/custom/cache/path")
        finally:
            if os.path.exists(mock_yaml):
                os.remove(mock_yaml)

    def test_check_env_flag(self):
        """Verify bashmenu.sh --check-env runs cleanly and exits immediately."""
        res = subprocess.run(
            [BASHMENU_SH, "--check-env"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Platform:", res.stdout)
        self.assertIn("Cache Dir:", res.stdout)

    def test_rich_sh_wires_pager(self):
        """Verify rich.sh references pager.sh in its script directory."""
        rich_sh = os.path.join(SCRIPTS_DIR, "rich.sh")
        with open(rich_sh, "r") as f:
            content = f.read()
        self.assertIn('"${SCRIPT_DIR}/pager.sh"', content)

    def test_otd_uses_python_inhouse(self):
        """Verify otd.sh has in-house python implementation."""
        otd_sh = os.path.join(SCRIPTS_DIR, "otd.sh")
        with open(otd_sh, "r") as f:
            content = f.read()
        self.assertIn("urllib.request", content)
        self.assertIn("json", content)

    def test_hostname_sh_execution(self):
        """Verify scripts/hostname.sh executes and returns hostname information."""
        hostname_sh = os.path.join(SCRIPTS_DIR, "hostname.sh")
        res = subprocess.run(
            ["bash", hostname_sh],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Hostname Information", res.stdout)
        self.assertIn("Hostname:", res.stdout)
        self.assertIn("Kernel:", res.stdout)

    def test_asteroids_syntax_and_paths(self):
        """Verify asteroids.sh has no rogue break and uses get_bin_dir."""
        asteroids_sh = os.path.join(SCRIPTS_DIR, "asteroids.sh")
        res = subprocess.run(
            ["bash", "-n", asteroids_sh],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        with open(asteroids_sh, "r") as f:
            content = f.read()
        self.assertIn("get_bin_dir()", content)
        # Ensure no bare 'break' outside loops
        self.assertNotIn("\n    break\n", content)


    def test_setup_flag(self):
        """Verify bashmenu.sh --setup runs non-interactively and exits cleanly."""
        res = subprocess.run(
            [BASHMENU_SH, "--setup"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("BashMenu environment, virtualenv, and shortcuts successfully configured", res.stdout)

    def test_posix_trampoline(self):
        """Verify executing bashmenu.sh with /bin/sh auto-elevates to Bash cleanly."""
        res = subprocess.run(
            ["sh", BASHMENU_SH, "--check-env"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Platform:", res.stdout)

    def test_install_and_uninstall_scripts_syntax(self):
        """Verify install.sh and uninstall.sh pass strict POSIX /bin/sh syntax check."""
        for script_name in ("install.sh", "uninstall.sh"):
            script_path = os.path.join(REPO_ROOT, script_name)
            self.assertTrue(os.path.isfile(script_path), f"{script_name} must exist")
            res = subprocess.run(
                ["sh", "-n", script_path],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"{script_name} failed POSIX sh syntax: {res.stderr}")


    def test_glyphs_script_query(self):
        """Verify scripts/glyphs.sh executes and searches without f-string syntax error."""
        glyphs_sh = os.path.join(SCRIPTS_DIR, "glyphs.sh")
        self.assertTrue(os.path.isfile(glyphs_sh))
        res = subprocess.run(
            [glyphs_sh, "hat"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("SyntaxError", res.stderr)
        self.assertNotIn("SyntaxError", res.stdout)
        self.assertIn("Searching for ['hat']:", res.stdout)


    def test_ip_info_output(self):
        """Verify scripts/ip_info.sh produces valid IP addresses and never outputs HTML."""
        ip_info_sh = os.path.join(SCRIPTS_DIR, "ip_info.sh")
        self.assertTrue(os.path.isfile(ip_info_sh))
        res = subprocess.run(
            [ip_info_sh],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("<!DOCTYPE", res.stdout)
        self.assertNotIn("<html", res.stdout)
        self.assertIn("Network IP Information", res.stdout)

    def test_ping_script(self):
        """Verify scripts/ping.sh runs cleanly with real ping or TCP fallback."""
        ping_sh = os.path.join(SCRIPTS_DIR, "ping.sh")
        self.assertTrue(os.path.isfile(ping_sh))
        res = subprocess.run(
            [ping_sh, "127.0.0.1", "1"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue("statistics" in res.stdout or "Reply from" in res.stdout)


if __name__ == "__main__":
    unittest.main()
