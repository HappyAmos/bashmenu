#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: install_basics.sh
# DESCRIPTION: Cross-platform basic tools installer for Termux, macOS, and
#              various Linux distributions (Debian/Ubuntu, Fedora/RHEL, Arch).
#              Installs each app independently so failures do not block others.
#              Invokes custom fallback installer scripts if available.
#              Generates a final report with status and solutions.
# ==============================================================================

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PACKAGES=(vim mc htop glow gum curl wget git shellcheck shfmt jq yq)

IS_TERMUX=false
IS_MAC=false
if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
elif [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
fi

# Detect available package manager safely
PKG_MANAGER=""
if [ "$IS_TERMUX" = true ] && command -v pkg &> /dev/null; then
    PKG_MANAGER="pkg"
elif command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
elif command -v brew &> /dev/null; then
    PKG_MANAGER="brew"
else
    echo "Error: Unsupported package manager."
    exit 1
fi

# Function to execute commands with root privileges if necessary
run_as_root() {
    if [ "$IS_TERMUX" = true ] || [ "$IS_MAC" = true ]; then
        "$@"
    else
        if [ "$(id -u)" = 0 ]; then
            "$@"
        else
            sudo "$@"
        fi
    fi
}

# Function to display tailored solutions for failed package installations
get_solution_for_pkg() {
    local pkg="$1"
    case "$pkg" in
        glow)
            echo "  - Issue: 'glow' is not in default repositories for many Linux distributions."
            echo "  - Solutions:"
            echo "      1. Run custom script: scripts/install_glow.sh"
            echo "      2. Add Charm APT repository: curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg"
            echo "      3. Install using Go: go install github.com/charmbracelet/glow@latest"
            echo "      4. Install using Homebrew: brew install glow"
            ;;
        gum)
            echo "  - Issue: 'gum' is missing from default package repositories."
            echo "  - Solutions:"
            echo "      1. Add Charm APT repository (https://repo.charm.sh)"
            echo "      2. Install using Go: go install github.com/charmbracelet/gum@latest"
            echo "      3. Install using Homebrew: brew install gum"
            ;;
        shfmt)
            echo "  - Issue: 'shfmt' may not be present in distribution repositories."
            echo "  - Solutions:"
            echo "      1. Install using Go: go install mvdan.cc/sh/v3/cmd/shfmt@latest"
            echo "      2. Download pre-built binary from https://github.com/mvdan/sh/releases"
            echo "      3. Install using Homebrew: brew install shfmt"
            ;;
        yq)
            echo "  - Issue: 'yq' failed to install via package manager."
            echo "  - Solutions:"
            echo "      1. Download binary: wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && chmod +x /usr/local/bin/yq"
            echo "      2. Install via Python pip: pip install yq"
            echo "      3. Install using Homebrew: brew install yq"
            ;;
        shellcheck)
            echo "  - Issue: 'shellcheck' failed to install via package manager."
            echo "  - Solutions:"
            echo "      1. Ensure 'universe' (Ubuntu) or 'epel' (RHEL/Fedora) repository is enabled."
            echo "      2. Install using Haskell cabal: cabal install shellcheck"
            echo "      3. Download binary from https://github.com/koalaman/shellcheck/releases"
            ;;
        *)
            echo "  - Issue: '$pkg' could not be installed using package manager '$PKG_MANAGER'."
            echo "  - Solutions:"
            echo "      1. Check if package name differs on your OS."
            echo "      2. Search official project repo/website for manual installation instructions."
            ;;
    esac
}

echo "Installing basic packages: ${PACKAGES[*]}"
echo "Detected package manager: $PKG_MANAGER"
echo "Updating package index..."

case "$PKG_MANAGER" in
    apt)
        run_as_root apt-get update -qq || true
        ;;
    pkg)
        pkg update -y || true
        ;;
    pacman)
        run_as_root pacman -Sy --noconfirm &>/dev/null || true
        ;;
esac

INSTALLED=()
FAILED=()

for pkg in "${PACKAGES[@]}"; do
    echo ""
    echo "Processing package: $pkg"

    if command -v "$pkg" &> /dev/null; then
        echo "  [✓] $pkg is already installed."
        INSTALLED+=("$pkg")
        continue
    fi

    echo "  [→] Attempting to install $pkg via $PKG_MANAGER..."
    INSTALL_SUCCESS=false

    case "$PKG_MANAGER" in
        pkg)
            if pkg install -y "$pkg"; then
                INSTALL_SUCCESS=true
            fi
            ;;
        apt)
            if run_as_root apt-get install -y "$pkg"; then
                INSTALL_SUCCESS=true
            fi
            ;;
        dnf)
            if run_as_root dnf install -y "$pkg"; then
                INSTALL_SUCCESS=true
            fi
            ;;
        pacman)
            if run_as_root pacman -S --noconfirm "$pkg"; then
                INSTALL_SUCCESS=true
            fi
            ;;
        brew)
            if brew install "$pkg"; then
                INSTALL_SUCCESS=true
            fi
            ;;
    esac

    if [ "$INSTALL_SUCCESS" = true ] && command -v "$pkg" &> /dev/null; then
        echo "  [✓] Successfully installed $pkg."
        INSTALLED+=("$pkg")
        continue
    fi

    # Fallback: check for package-specific script in scripts/ (e.g. install_glow.sh)
    FALLBACK_SCRIPT="$SCRIPT_DIR/install_${pkg}.sh"
    if [ -f "$FALLBACK_SCRIPT" ]; then
        echo "  [!] Package manager failed for $pkg. Trying fallback installer: install_${pkg}.sh..."
        chmod +x "$FALLBACK_SCRIPT" 2>/dev/null || true
        if bash "$FALLBACK_SCRIPT"; then
            if command -v "$pkg" &> /dev/null; then
                echo "  [✓] Successfully installed $pkg via fallback script."
                INSTALLED+=("$pkg")
                continue
            fi
        fi
    fi

    echo "  [✗] Failed to install $pkg."
    FAILED+=("$pkg")
done

echo ""
echo "============================================================"
echo "                   FINAL INSTALLATION REPORT                "
echo "============================================================"
echo "Total packages evaluated: ${#PACKAGES[@]}"
echo "Successfully installed / available: ${#INSTALLED[@]}"
echo "Failed: ${#FAILED[@]}"
echo "------------------------------------------------------------"

if [ ${#INSTALLED[@]} -gt 0 ]; then
    echo "Installed / Available Apps:"
    for pkg in "${INSTALLED[@]}"; do
        echo "  [✓] $pkg"
    done
fi

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "Failed Apps and Possible Solutions:"
    for pkg in "${FAILED[@]}"; do
        echo ""
        echo "[✗] App: $pkg"
        get_solution_for_pkg "$pkg"
    done
    echo ""
    echo "============================================================"
    echo "Installation finished with warnings (${#FAILED[@]} package(s) failed)."
    exit 1
else
    echo ""
    echo "============================================================"
    echo "All basic tools are installed and available!"
    exit 0
fi
