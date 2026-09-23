#!/usr/bin/env bash
# Version: 0.0.5
# Author:  HA Bash Menu (Debian + Apt Update Fix)

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"
BASHMENU_SCRIPT="${SCRIPT_DIR}/bashmenu.py"
BASHMENU_SETTINGS="${SCRIPT_DIR}/bashmenu.yml"
GLOW_INSTALLER="${SCRIPT_DIR}/scripts/install_glow.sh"
VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_ACTIVATE="${VENV_DIR}/bin/activate"
CACHE_DIR="$HOME/.cache/bashmenu"

# Define the standard CLI tools required
REQUIRED_TOOLS=("curl" "git" "glow" "jq" "tput" "yq" "python3")
MISSING_PACKAGES=()
GLOW_IS_MISSING=false

# Setup a cache directory
mkdir -p "$CACHE_DIR" &>/dev/null || exit 1

# Function to extract a value from a YAML file using yq.
yaml_get() {
  local key="$1"
  local file="$2"
  yq -r ".$key" "$file"
}

IS_TERMUX=false
IS_WSL=false
IS_MAC=false

if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
elif grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
elif [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
fi

# Detect the available package manager safely
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
fi

# Flag to ensure apt-get update only runs once per execution
APT_UPDATED=false

# Function to execute a command with root privileges if necessary.
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

# Function to check if a single tool is installed and available in system PATH.
is_installed() {
    local tool="$1"
    command -v "$tool" &> /dev/null
}

# Map binary names to their respective installation package names based on the package manager
get_package_name() {
    local binary="$1"
    
    case "$binary" in
        "pip3")
            if [ "$PKG_MANAGER" = "apt" ] || [ "$PKG_MANAGER" = "dnf" ]; then
                echo "python3-pip"
            else
                echo "python3"
            fi
            ;;
        "venv")
            if [ "$PKG_MANAGER" = "apt" ]; then
                echo "python3-venv"
            elif [ "$PKG_MANAGER" = "dnf" ]; then
                echo "python3-virtualenv"
            else
                echo "python3"
            fi
            ;;
        *)
            echo "$binary"
            ;;
    esac
}

# Function to install missing applications using the local package manager.
install_apps() {
    local packages_to_install=("$@")
    
    if [ -z "$PKG_MANAGER" ] && [ ${#packages_to_install[@]} -gt 0 ]; then
        echo "Error: Supported package manager (pkg, apt, dnf, pacman, brew) not found." >&2
        return 1
    fi

    if [ ${#packages_to_install[@]} -gt 0 ]; then
        echo "Using package manager: $PKG_MANAGER"
    fi

    # Trigger apt update once if running on a Debian-based environment
    if [ "$PKG_MANAGER" = "apt" ] && [ "$APT_UPDATED" = false ] && [ ${#packages_to_install[@]} -gt 0 ]; then
        echo "Running apt-get update to synchronize package index..."
        run_as_root apt-get update -qq
        APT_UPDATED=true
    fi

    for pkg in "${packages_to_install[@]}"; do
        echo "Installing $pkg via package manager..."
        
        case "$PKG_MANAGER" in
            "pkg")
                pkg update -y && pkg install -y "$pkg"
                ;;
            "apt")
                run_as_root apt-get install -y "$pkg"
                ;;
            "dnf")
                run_as_root dnf install -y "$pkg"
                ;;
            "pacman")
                run_as_root pacman -S --noconfirm "$pkg"
                ;;
            "brew")
                brew install "$pkg"
                ;;
        esac
    done
}

# ==========================================================================
# Dependency Checking Phase
# ==========================================================================

# Check standard system binaries
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! is_installed "$tool"; then
        echo "  [✗] $tool is missing."
        if [ "$tool" = "glow" ]; then
            GLOW_IS_MISSING=true
        else
            pkg_name=$(get_package_name "$tool")
            MISSING_PACKAGES+=("$pkg_name")
        fi
    fi
done

# Check Python internal pip3 binary status
if ! is_installed "pip3"; then
    echo "  [✗] pip3 is missing."
    pkg_name=$(get_package_name "pip3")
    MISSING_PACKAGES+=("$pkg_name")
fi

# Check Python internal venv engine status
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "  [✗] python3 venv module is missing."
    pkg_name=$(get_package_name "venv")
    if [[ ! " ${MISSING_PACKAGES[*]} " =~ " ${pkg_name} " ]]; then
        MISSING_PACKAGES+=("$pkg_name")
    fi
fi

# Deduplicate items in the package manager missing list safely
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    IFS=" " read -r -a MISSING_PACKAGES <<< "$(tr ' ' '
' <<< "${MISSING_PACKAGES[@]}" | sort -u | tr '
' ' ')"
fi

# Trigger installation if elements are missing
if [ ${#MISSING_PACKAGES[@]} -gt 0 ] || [ "$GLOW_IS_MISSING" = true ]; then
    echo "Found missing dependencies."
    read -p "Would you like to install the missing tools? [y/N]: " -n 1 -r
    echo ""
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        # 1. Handle package manager updates first
        if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
            if ! install_apps "${MISSING_PACKAGES[@]}"; then
                echo "Package installation failed. Exiting script." >&2
                exit 1
            fi
        fi

        # 2. Run custom installer specifically for Glow
        if [ "$GLOW_IS_MISSING" = true ]; then
            if [ -f "$GLOW_INSTALLER" ]; then
                echo "Installing glow via custom script: $GLOW_INSTALLER"
                chmod +x "$GLOW_INSTALLER"
                if ! bash "$GLOW_INSTALLER"; then
                    echo "Custom Glow installer exited with errors." >&2
                fi
            else
                echo "Error: Glow custom script expected at $GLOW_INSTALLER but it is missing." >&2
                exit 1
            fi
        fi

        # 3. Perform global validation confirmation
        ALL_VALID=true
        for tool in "${REQUIRED_TOOLS[@]}"; do
            if ! is_installed "$tool"; then ALL_VALID=false; fi
        done
        if ! is_installed "pip3"; then ALL_VALID=false; fi
        if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then ALL_VALID=false; fi
        
        if [ "$ALL_VALID" = true ]; then
            echo "All dependencies resolved successfully!"
        else
            echo "Dependency configuration mismatch post-install. System states invalid." >&2
            exit 1
        fi
    else
        echo "Skipping installation of missing tools, some functions may not work properly."
    fi
fi

# ==========================================================================
# Update checking mechanism
# ==========================================================================
if [ -f "$BASHMENU_SETTINGS" ] && command -v yq &> /dev/null; then
    UPDATES=$(yaml_get "settings.check_for_updates" "${BASHMENU_SETTINGS}")
    if [[ "${UPDATES,,}" == "true" ]]; then
        if git rev-parse --is-inside-work-tree &>/dev/null; then
            git fetch -q
            CHANGES_AHEAD=$(git rev-list --count "HEAD..@{u}" 2>/dev/null || echo 0)

            if [ "$CHANGES_AHEAD" -gt 0 ]; then
                echo "There has been an update! ($CHANGES_AHEAD new commit(s))"
                read -p "Would you like to update? [y/N]: " -n 1 -r
                echo ""
                if [[ "$REPLY" =~ ^[Yy]$ ]]; then
                    git pull
                else
                    echo "Skipping update."
                fi
            else
                echo "Your local version is up to date."
            fi
        fi
    fi
fi

# ==========================================================================
# Python Runtime & Virtual Environment Bootloader
# ==========================================================================
if [ ! -f "$BASHMENU_SCRIPT" ]; then
    echo "Error: $BASHMENU_SCRIPT not found." >&2
    exit 1
fi

# ENHANCED DEBIAN ENVIRONMENT RECOVERY PASS:
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1 && [ "$PKG_MANAGER" = "apt" ]; then
    echo "python3-venv is missing from the environment. Attempting immediate resolution..." >&2
    if install_apps "python3-venv"; then
        echo "python3-venv resolved." >&2
    fi
fi

USE_VENV=false
if [ -f "$VENV_ACTIVATE" ]; then
    if "${VENV_DIR}/bin/python3" -c "import yaml, ruff" >/dev/null 2>&1; then
        USE_VENV=true
    else
        echo "Virtual environment is broken or missing PyYAML and/or Ruff. Recreating..." >&2
        rm -rf "$VENV_DIR"
    fi
fi

if [ "$USE_VENV" = false ]; then
    echo "Setting up virtual environment at $VENV_DIR..." >&2
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
        if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
            if "${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null 2>&1 &&                "${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null 2>&1; then
                USE_VENV=true
            else
                echo "Warning: Failed to install requirements inside virtual environment." >&2
            fi
        else
            echo "Warning: requirements.txt file not located. Environment left plain." >&2
            USE_VENV=true
        fi
    else
        echo "Warning: Could not create virtual environment. Falling back to system Python." >&2
    fi
fi

if [ "$USE_VENV" = true ]; then
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    PYTHON_BIN="python3"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

exec "$PYTHON_BIN" "$BASHMENU_SCRIPT" "$@"
