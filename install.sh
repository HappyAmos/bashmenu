#!/bin/sh
# ==============================================================================
# BashMenu Universal Installation Script
# https://github.com/HappyAmos/bashmenu
#
# One-liner usage:
#   sh -c "$(wget -qO- https://raw.githubusercontent.com/HappyAmos/bashmenu/main/install.sh 2>/dev/null || curl -fsSL https://raw.githubusercontent.com/HappyAmos/bashmenu/main/install.sh)"
# ==============================================================================

set -e

# Default installation directory and repository settings
REPO_URL="${BASHMENU_REPO:-https://github.com/HappyAmos/bashmenu.git}"
REPO_BRANCH="${BASHMENU_BRANCH:-main}"
INSTALL_DIR="${BASHMENU_DIR:-$HOME/.local/share/bashmenu}"

# ------------------------------------------------------------------------------
# Self-cleanup trap: If this script was saved to a local file, remove it on exit
# ------------------------------------------------------------------------------
CURRENT_SCRIPT=""
if [ -n "$0" ] && [ -f "$0" ]; then
    CURRENT_SCRIPT="$(cd -P "$(dirname "$0")" 2>/dev/null && pwd)/$(basename "$0")"
fi

cleanup() {
    exit_code=$?
    if [ -n "$CURRENT_SCRIPT" ] && [ -f "$CURRENT_SCRIPT" ]; then
        # Do not delete install.sh inside the cloned target repo
        case "$CURRENT_SCRIPT" in
            "$INSTALL_DIR"/*) ;;
            *) rm -f "$CURRENT_SCRIPT" 2>/dev/null || true ;;
        esac
    fi
    exit $exit_code
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------------------
# Privilege escalation helper (sudo, doas, or direct root)
# ------------------------------------------------------------------------------
run_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    elif command -v doas >/dev/null 2>&1; then
        doas "$@"
    else
        echo "Error: Root privileges required to install system packages, but sudo/doas was not found." >&2
        return 1
    fi
}

echo "==================================================================="
echo "                  Installing BashMenu System                       "
echo "==================================================================="

# ------------------------------------------------------------------------------
# Detect and install required system prerequisites
# ------------------------------------------------------------------------------
echo "==> Inspecting host environment and package manager..."

if command -v apk >/dev/null 2>&1; then
    echo "  [+] Alpine Linux detected (apk)"
    missing_apk=""
    command -v bash >/dev/null 2>&1 || missing_apk="$missing_apk bash"
    command -v git >/dev/null 2>&1 || missing_apk="$missing_apk git"
    command -v python3 >/dev/null 2>&1 || missing_apk="$missing_apk python3"
    if ! python3 -m venv --help >/dev/null 2>&1; then
        missing_apk="$missing_apk py3-virtualenv py3-pip"
    fi
    if [ -n "$missing_apk" ]; then
        echo "  [+] Installing missing prerequisites:$missing_apk"
        # shellcheck disable=SC2086
        run_root apk add $missing_apk
    fi

elif command -v apt-get >/dev/null 2>&1; then
    echo "  [+] Debian/Ubuntu detected (apt)"
    missing_apt=""
    command -v bash >/dev/null 2>&1 || missing_apt="$missing_apt bash"
    command -v git >/dev/null 2>&1 || missing_apt="$missing_apt git"
    command -v python3 >/dev/null 2>&1 || missing_apt="$missing_apt python3"
    if ! python3 -c "import venv" >/dev/null 2>&1; then
        missing_apt="$missing_apt python3-venv"
    fi
    if ! python3 -m pip --version >/dev/null 2>&1; then
        missing_apt="$missing_apt python3-pip"
    fi
    if [ -n "$missing_apt" ]; then
        echo "  [+] Installing missing prerequisites:$missing_apt"
        run_root apt-get update -qq
        # shellcheck disable=SC2086
        run_root apt-get install -y $missing_apt
    fi

elif command -v dnf >/dev/null 2>&1; then
    echo "  [+] Fedora/RHEL detected (dnf)"
    missing_dnf=""
    command -v bash >/dev/null 2>&1 || missing_dnf="$missing_dnf bash"
    command -v git >/dev/null 2>&1 || missing_dnf="$missing_dnf git"
    command -v python3 >/dev/null 2>&1 || missing_dnf="$missing_dnf python3"
    if [ -n "$missing_dnf" ]; then
        echo "  [+] Installing missing prerequisites:$missing_dnf"
        # shellcheck disable=SC2086
        run_root dnf install -y $missing_dnf python3-pip
    fi

elif command -v pacman >/dev/null 2>&1; then
    echo "  [+] Arch Linux detected (pacman)"
    missing_pacman=""
    command -v bash >/dev/null 2>&1 || missing_pacman="$missing_pacman bash"
    command -v git >/dev/null 2>&1 || missing_pacman="$missing_pacman git"
    command -v python3 >/dev/null 2>&1 || missing_pacman="$missing_pacman python"
    if [ -n "$missing_pacman" ]; then
        echo "  [+] Installing missing prerequisites:$missing_pacman"
        # shellcheck disable=SC2086
        run_root pacman -S --noconfirm $missing_pacman python-pip
    fi

elif command -v pkg >/dev/null 2>&1; then
    echo "  [+] Termux/FreeBSD detected (pkg)"
    missing_pkg=""
    command -v bash >/dev/null 2>&1 || missing_pkg="$missing_pkg bash"
    command -v git >/dev/null 2>&1 || missing_pkg="$missing_pkg git"
    command -v python3 >/dev/null 2>&1 || missing_pkg="$missing_pkg python"
    if [ -n "$missing_pkg" ]; then
        echo "  [+] Installing missing prerequisites:$missing_pkg"
        # shellcheck disable=SC2086
        pkg install -y $missing_pkg
    fi

elif command -v brew >/dev/null 2>&1; then
    echo "  [+] macOS Homebrew detected"
    command -v git >/dev/null 2>&1 || brew install git
    command -v python3 >/dev/null 2>&1 || brew install python
fi

# Ensure git is available
if ! command -v git >/dev/null 2>&1; then
    echo "Error: 'git' is required but could not be installed automatically." >&2
    exit 1
fi

# Ensure bash is available
if ! command -v bash >/dev/null 2>&1; then
    echo "Error: 'bash' is required but could not be installed automatically." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# Clone or update the repository
# ------------------------------------------------------------------------------
echo "==> Deploying repository to $INSTALL_DIR..."

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  [+] Existing installation found. Updating repository..."
    git -C "$INSTALL_DIR" fetch --quiet
    git -C "$INSTALL_DIR" checkout "$REPO_BRANCH" --quiet
    git -C "$INSTALL_DIR" pull --ff-only --quiet
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# ------------------------------------------------------------------------------
# Run first-time setup and virtual environment bootstrap
# ------------------------------------------------------------------------------
echo "==> Configuring BashMenu virtual environment and shortcuts..."
bash "$INSTALL_DIR/bashmenu.sh" --setup

# ------------------------------------------------------------------------------
# PATH verification
# ------------------------------------------------------------------------------
BIN_DIR="$HOME/.local/bin"
if [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
    BIN_DIR="$PREFIX/bin"
elif [ "$(id -u)" = "0" ]; then
    BIN_DIR="/usr/local/bin"
fi

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo ""
        echo "  [!] Notice: $BIN_DIR is not currently in your PATH."
        for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            if [ -f "$rc" ] && ! grep -q "$BIN_DIR" "$rc"; then
                echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$rc"
                echo "  [+] Added $BIN_DIR to $rc"
            fi
        done
        echo "      Run 'export PATH=\"$BIN_DIR:\$PATH\"' or open a new terminal session."
        ;;
esac

echo ""
echo "==================================================================="
echo "            BashMenu Successfully Installed!                       "
echo "==================================================================="
echo "  Launch anytime by running:"
echo "      bashmenu"
echo "  or simply:"
echo "      bm"
echo ""
echo "  To uninstall in the future, run:"
echo "      $INSTALL_DIR/uninstall.sh"
echo "==================================================================="
