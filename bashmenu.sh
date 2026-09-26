#!/usr/bin/env bash
# Version: 0.0.7
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Canonical symlink resolution to determine true script directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

BASHMENU_SCRIPT="${SCRIPT_DIR}/bashmenu.py"
BASHMENU_SETTINGS="${SCRIPT_DIR}/bashmenu.yml"
GLOW_INSTALLER="${SCRIPT_DIR}/scripts/install_glow.sh"
VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_ACTIVATE="${VENV_DIR}/bin/activate"
# Define the standard CLI tools required
REQUIRED_TOOLS=("curl" "git" "glow" "jq" "tput" "python3")
MISSING_PACKAGES=()
GLOW_IS_MISSING=false

# Function to extract a value from a YAML file using yq or python3 fallback.
yaml_get() {
  local key="$1"
  local file="$2"
  if command -v yq &>/dev/null; then
      yq -r ".$key" "$file" 2>/dev/null || yq ".$key" "$file" 2>/dev/null || true
  elif command -v python3 &>/dev/null; then
      python3 -c "import yaml, sys; data=yaml.safe_load(open('$file')); keys='$key'.split('.'); [data := data.get(k, {}) for k in keys if isinstance(data, dict)]; print(data if not isinstance(data, dict) else '')" 2>/dev/null || true
  fi
}

# Resolve configurable cache directory
RAW_CACHE_DIR=$(yaml_get "settings.cache_dir" "${BASHMENU_SETTINGS}")
if [ -n "$RAW_CACHE_DIR" ] && [ "$RAW_CACHE_DIR" != "null" ]; then
    CACHE_DIR="${RAW_CACHE_DIR//\{home\}/$HOME}"
    CACHE_DIR="${CACHE_DIR//\{bashmenu_dir\}/$SCRIPT_DIR}"
else
    CACHE_DIR="$HOME/.cache/bashmenu"
fi
export CACHE_DIR

# Setup a cache directory
mkdir -p "$CACHE_DIR" &>/dev/null || exit 1

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
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
elif command -v zypper &> /dev/null; then
    PKG_MANAGER="zypper"
elif command -v apk &> /dev/null; then
    PKG_MANAGER="apk"
elif command -v brew &> /dev/null; then
    PKG_MANAGER="brew"
fi

# Flag to ensure package manager index update only runs once per execution
APT_UPDATED=false

# Function to execute a command with root privileges if necessary.
run_as_root() {
    if [ "$IS_TERMUX" = true ] || [ "$IS_MAC" = true ]; then
        "$@"
    else
        if [ "$(id -u)" = 0 ]; then
            "$@"
        elif command -v sudo &>/dev/null; then
            sudo "$@"
        else
            echo "Warning: Root privileges required but sudo is not available." >&2
            "$@"
        fi
    fi
}

# Function to check if a single tool is installed and available in system PATH.
is_installed() {
    local tool="$1"
    command -v "$tool" &> /dev/null
}

# Function to check if man page is installed
is_man_installed() {
    local manpage="${1:-bashmenu}"
    if command -v man &>/dev/null && man -w "$manpage" &>/dev/null; then
        return 0
    fi

    local candidate_dirs=(
        "/usr/local/share/man/man1"
        "/usr/share/man/man1"
        "$HOME/.local/share/man/man1"
    )
    [ -n "$PREFIX" ] && candidate_dirs+=("$PREFIX/share/man/man1" "$PREFIX/man/man1")

    for dir in "${candidate_dirs[@]}"; do
        if [ -f "$dir/${manpage}.1" ] || [ -L "$dir/${manpage}.1" ] || [ -f "$dir/${manpage}" ] || [ -L "$dir/${manpage}" ]; then
            return 0
        fi
    done

    return 1
}

# Install man page (bashmenu.1) into standard man directory
install_man_page() {
    local man_name="bashmenu.1"
    local source_man="${SCRIPT_DIR}/${man_name}"
    local target_dir=""

    if [ ! -f "$source_man" ]; then
        echo "  [✗] Man page source file not found at $source_man" >&2
        return 1
    fi

    if [ "$IS_TERMUX" = true ] && [ -n "$PREFIX" ]; then
        if [ -d "$PREFIX/share/man" ]; then
            target_dir="$PREFIX/share/man/man1"
        elif [ -d "$PREFIX/man" ]; then
            target_dir="$PREFIX/man/man1"
        else
            target_dir="$PREFIX/share/man/man1"
        fi
    elif [ "$(id -u)" = 0 ]; then
        target_dir="/usr/local/share/man/man1"
    elif [ -w "/usr/local/share/man/man1" ] || [ -w "/usr/local/share/man" ]; then
        target_dir="/usr/local/share/man/man1"
    else
        target_dir="$HOME/.local/share/man/man1"
    fi

    mkdir -p "$target_dir" 2>/dev/null || run_as_root mkdir -p "$target_dir"
    local target_file="${target_dir}/${man_name}"

    echo "Installing man page '$man_name' pointing to: $source_man"

    ln -sf "$source_man" "$target_file" 2>/dev/null || run_as_root ln -sf "$source_man" "$target_file" || \
    cp "$source_man" "$target_file" 2>/dev/null || run_as_root cp "$source_man" "$target_file"

    if [ -L "$target_file" ] || [ -f "$target_file" ]; then
        echo "  [✓] Successfully installed man page at $target_file"
        return 0
    else
        echo "  [✗] Failed to install man page at $target_file" >&2
        return 1
    fi
}

# Install global 'bm' command shortcut pointing to bashmenu.sh
install_shortcut() {
    local shortcut_name="bm"
    local target_dir=""

    if [ "$IS_TERMUX" = true ] && [ -n "$PREFIX" ] && [ -d "$PREFIX/bin" ]; then
        target_dir="$PREFIX/bin"
    elif [ "$(id -u)" = 0 ]; then
        target_dir="/usr/local/bin"
    elif [ -w "/usr/local/bin" ]; then
        target_dir="/usr/local/bin"
    else
        target_dir="$HOME/.local/bin"
    fi

    mkdir -p "$target_dir" 2>/dev/null || true
    local target_file="${target_dir}/${shortcut_name}"
    local real_script_path="${SCRIPT_DIR}/bashmenu.sh"

    echo "Installing global '$shortcut_name' shortcut pointing to: $real_script_path"

    ln -sf "$real_script_path" "$target_file" 2>/dev/null || run_as_root ln -sf "$real_script_path" "$target_file"

    if [ -L "$target_file" ] || [ -f "$target_file" ]; then
        echo "  [✓] Successfully installed '$shortcut_name' shortcut at $target_file"

        if [[ ":$PATH:" != *":$target_dir:"* ]]; then
            echo "  [!] Notice: $target_dir is not currently in your PATH environment variable."
            for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
                if [ -f "$rc" ] && ! grep -q "$target_dir" "$rc"; then
                    echo "export PATH=\"$target_dir:\$PATH\"" >> "$rc"
                    echo "  [+] Added $target_dir to $rc"
                fi
            done
        fi
        return 0
    else
        echo "  [✗] Failed to create shortcut at $target_file" >&2
        return 1
    fi
}

# Handle standalone CLI flags
for arg in "$@"; do
    case "$arg" in
        --install-shortcut|--install-bm)
            install_shortcut
            exit $?
            ;;
        --install-man|--install-manpage)
            install_man_page
            exit $?
            ;;
    esac
done

# Map binary names to their respective installation package names based on the package manager
get_package_name() {
    local binary="$1"
    
    case "$binary" in
        "pip3")
            if [ "$PKG_MANAGER" = "apt" ] || [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "zypper" ]; then
                echo "python3-pip"
            elif [ "$PKG_MANAGER" = "pacman" ] || [ "$PKG_MANAGER" = "pkg" ]; then
                echo "python-pip"
            elif [ "$PKG_MANAGER" = "apk" ]; then
                echo "py3-pip"
            else
                echo "python3"
            fi
            ;;
        "venv")
            if [ "$PKG_MANAGER" = "apt" ]; then
                echo "python3-venv"
            elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
                echo "python3-virtualenv"
            elif [ "$PKG_MANAGER" = "zypper" ]; then
                echo "python3-virtualenv"
            elif [ "$PKG_MANAGER" = "apk" ]; then
                echo "python3"
            else
                echo "python3"
            fi
            ;;
        "python3")
            if [ "$PKG_MANAGER" = "pacman" ]; then
                echo "python"
            else
                echo "python3"
            fi
            ;;
        "tput")
            if [ "$PKG_MANAGER" = "apt" ]; then
                echo "ncurses-bin"
            elif [ "$PKG_MANAGER" = "pkg" ]; then
                echo "ncurses-utils"
            elif [ "$PKG_MANAGER" = "brew" ]; then
                echo ""
            else
                echo "ncurses"
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
        echo "Error: Supported package manager (pkg, apt, dnf, yum, pacman, zypper, apk, brew) not found." >&2
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
        [ -z "$pkg" ] && continue
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
            "yum")
                run_as_root yum install -y "$pkg"
                ;;
            "pacman")
                run_as_root pacman -S --noconfirm "$pkg"
                ;;
            "zypper")
                run_as_root zypper install -y "$pkg"
                ;;
            "apk")
                run_as_root apk add "$pkg"
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
            if [ -n "$pkg_name" ]; then
                MISSING_PACKAGES+=("$pkg_name")
            fi
        fi
    fi
done

# Check Python internal pip3 binary status
if ! is_installed "pip3"; then
    echo "  [✗] pip3 is missing."
    pkg_name=$(get_package_name "pip3")
    [ -n "$pkg_name" ] && MISSING_PACKAGES+=("$pkg_name")
fi

# Check Python internal venv engine status
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "  [✗] python3 venv module is missing."
    pkg_name=$(get_package_name "venv")
    if [ -n "$pkg_name" ] && [[ ! " ${MISSING_PACKAGES[*]} " =~ " ${pkg_name} " ]]; then
        MISSING_PACKAGES+=("$pkg_name")
    fi
fi

# Deduplicate items in the package manager missing list safely
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    DEDUP_PACKAGES=()
    for pkg in "${MISSING_PACKAGES[@]}"; do
        if [ -n "$pkg" ] && [[ ! " ${DEDUP_PACKAGES[*]} " =~ " ${pkg} " ]]; then
            DEDUP_PACKAGES+=("$pkg")
        fi
    done
    MISSING_PACKAGES=("${DEDUP_PACKAGES[@]}")
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

# Check if 'bm' shortcut is missing and prompt user if interactive session
if ! is_installed "bm"; then
    if [ -t 0 ]; then
        read -p "Global 'bm' command shortcut is not installed. Install it now? [y/N]: " -n 1 -r
        echo ""
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            install_shortcut
        fi
    fi
fi

# Check if man page is missing and prompt user if interactive session
if ! is_man_installed "bashmenu"; then
    if [ -t 0 ]; then
        read -p "Man page 'bashmenu.1' is not installed. Install it now? [y/N]: " -n 1 -r
        echo ""
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            install_man_page
        fi
    fi
fi

# ==========================================================================
# Update checking mechanism
# ==========================================================================
if [ -f "$BASHMENU_SETTINGS" ]; then
    UPDATES=$(yaml_get "settings.check_for_updates" "${BASHMENU_SETTINGS}")
    UPDATES_LOWER=$(echo "$UPDATES" | tr '[:upper:]' '[:lower:]')
    if [[ "$UPDATES_LOWER" == "true" ]]; then
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
    VENV_PYTHON="${VENV_DIR}/bin/python3"
    [ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="${VENV_DIR}/bin/python"
    if "$VENV_PYTHON" -c "import yaml, ruff" >/dev/null 2>&1; then
        USE_VENV=true
    else
        echo "Virtual environment is broken or missing PyYAML and/or Ruff. Recreating..." >&2
        rm -rf "$VENV_DIR"
    fi
fi

if [ "$USE_VENV" = false ]; then
    echo "Setting up virtual environment at $VENV_DIR..." >&2
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
        VENV_PIP="${VENV_DIR}/bin/pip"
        [ ! -f "$VENV_PIP" ] && VENV_PIP="${VENV_DIR}/bin/pip3"
        if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
            if "$VENV_PIP" install --upgrade pip >/dev/null 2>&1 && "$VENV_PIP" install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null 2>&1; then
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
