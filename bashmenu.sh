#!/bin/sh
# Version: 0.0.7
# Author:  HA Bash Menu

# --------------------------------------------------------------------------
# POSIX /bin/sh Trampoline: Auto-elevate to Bash or guide the user
# --------------------------------------------------------------------------
if [ -z "$BASH_VERSION" ]; then
    if command -v bash >/dev/null 2>&1; then
        exec bash "$0" "$@"
    else
        echo "Error: Bash is required to run BashMenu, but is not installed." >&2
        if command -v apk >/dev/null 2>&1; then
            echo "Alpine Linux detected. Install Bash using: apk add bash" >&2
        elif command -v pkg >/dev/null 2>&1; then
            echo "FreeBSD/Termux detected. Install Bash using: pkg install bash" >&2
        elif command -v pacman >/dev/null 2>&1; then
            echo "Arch Linux detected. Install Bash using: pacman -S bash" >&2
        elif command -v dnf >/dev/null 2>&1; then
            echo "Fedora/RHEL detected. Install Bash using: dnf install bash" >&2
        elif command -v apt-get >/dev/null 2>&1; then
            echo "Debian/Ubuntu detected. Install Bash using: apt-get install -y bash" >&2
        fi
        exit 1
    fi
fi

# Ensure UTF-8 locale handling across minimal containers and full distros
if command -v locale >/dev/null 2>&1; then
    if locale -a 2>/dev/null | grep -qiE "^en_US\.(utf-?8)$"; then
        export LANG=en_US.UTF-8
        export LC_ALL=en_US.UTF-8
    elif locale -a 2>/dev/null | grep -qiE "^c\.(utf-?8)$"; then
        export LANG=C.UTF-8
        export LC_ALL=C.UTF-8
    else
        export LANG="${LANG:-C.UTF-8}"
        export LC_ALL="${LC_ALL:-C.UTF-8}"
    fi
else
    export LANG="${LANG:-C.UTF-8}"
    export LC_ALL="${LC_ALL:-C.UTF-8}"
fi

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
ADDITIONAL_SCRIPTS_DIR="${SCRIPT_DIR}/scripts"
VENV_DIR="${SCRIPT_DIR}/.venv"

# --------------------------------------------------------------------------
# Multi-Platform Detection Engine
# --------------------------------------------------------------------------
PLATFORM="unknown"
IS_TERMUX=false
IS_WSL=false
IS_MAC=false
IS_WINDOWS=false
IS_BSD=false
IS_LINUX=false
IS_RPI=false

KERNEL="$(uname -s 2>/dev/null || echo "Unknown")"

case "$KERNEL" in
    Darwin)
        PLATFORM="macos"; IS_MAC=true ;;
    FreeBSD|OpenBSD|NetBSD)
        PLATFORM="bsd"; IS_BSD=true ;;
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM="windows"; IS_WINDOWS=true ;;
    Linux)
        if [ -n "$TERMUX_VERSION" ] || [[ "${PREFIX:-}" == *"/com.termux/"* ]]; then
            PLATFORM="termux"; IS_TERMUX=true
        elif grep -qi microsoft /proc/version 2>/dev/null; then
            PLATFORM="wsl"; IS_WSL=true; IS_LINUX=true
        else
            PLATFORM="linux"; IS_LINUX=true
        fi
        if [ -f /sys/firmware/devicetree/base/model ] && grep -qi "raspberry pi" /sys/firmware/devicetree/base/model 2>/dev/null; then
            IS_RPI=true
        fi
        ;;
    *)
        PLATFORM="unknown" ;;
esac

# Virtualenv activation path based on platform directory structure
if [ -d "${VENV_DIR}/Scripts" ] || [ "$IS_WINDOWS" = true ]; then
    VENV_ACTIVATE="${VENV_DIR}/Scripts/activate"
else
    VENV_ACTIVATE="${VENV_DIR}/bin/activate"
fi

# Define standard CLI tools required (glow eliminated via rich.sh | pager.sh)
REQUIRED_TOOLS=("python3" "curl")
MISSING_PACKAGES=()

# Multi-layer in-house YAML value extractor (Python -> yq -> pure POSIX awk/grep)
yaml_get() {
  local key="$1"
  local file="$2"
  [ ! -f "$file" ] && return 0

  # Layer 1: Python PyYAML check
  local py_cmd=""
  if [ -f "${VENV_DIR}/bin/python3" ] && "${VENV_DIR}/bin/python3" -c "import yaml" &>/dev/null; then
      py_cmd="${VENV_DIR}/bin/python3"
  elif [ -f "${VENV_DIR}/Scripts/python.exe" ] && "${VENV_DIR}/Scripts/python.exe" -c "import yaml" &>/dev/null; then
      py_cmd="${VENV_DIR}/Scripts/python.exe"
  elif command -v python3 &>/dev/null && python3 -c "import yaml" &>/dev/null; then
      py_cmd="python3"
  elif command -v python &>/dev/null && python -c "import yaml" &>/dev/null; then
      py_cmd="python"
  fi

  if [ -n "$py_cmd" ]; then
      "$py_cmd" -c "import yaml, sys; data=yaml.safe_load(open('$file')) or {}; keys='$key'.split('.'); [data := data.get(k, {}) for k in keys if isinstance(data, dict)]; print(data if not isinstance(data, dict) else '')" 2>/dev/null && return 0
  fi

  # Layer 2: yq if installed
  if command -v yq &>/dev/null; then
      local val
      val=$(yq -r ".$key" "$file" 2>/dev/null || yq ".$key" "$file" 2>/dev/null || true)
      if [ -n "$val" ] && [ "$val" != "null" ]; then
          echo "$val"
          return 0
      fi
  fi

  # Layer 3: Pure POSIX awk/grep fallback for bootstrap scalar keys
  local leaf_key="${key##*.}"
  grep -E "^[[:space:]]*${leaf_key}:" "$file" 2>/dev/null | head -n 1 | awk -F': ' '{print $2}' | tr -d '"'\'' ' || true
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

# Setup cache directory
mkdir -p "$CACHE_DIR" &>/dev/null || exit 1

# Detect available package manager safely
PKG_MANAGER=""
if [ "$IS_TERMUX" = true ] && command -v pkg &> /dev/null; then
    PKG_MANAGER="pkg"
elif [ "$IS_MAC" = true ] && command -v brew &> /dev/null; then
    PKG_MANAGER="brew"
elif [ "$IS_WINDOWS" = true ] && command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
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
PACMAN_UPDATED=false

# Function to execute a command with root privileges if necessary
run_as_root() {
    if [ "$IS_TERMUX" = true ] || [ "$IS_MAC" = true ] || [ "$IS_WINDOWS" = true ]; then
        "$@"
    else
        if [ "$(id -u)" = 0 ]; then
            "$@"
        elif command -v sudo &>/dev/null; then
            sudo "$@"
        elif command -v doas &>/dev/null; then
            doas "$@"
        else
            echo "Warning: Root privileges required but sudo/doas is not available." >&2
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

# Install 'bm' and 'bashmenu' command symlinks pointing to bashmenu.sh
install_bm() {
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
    local real_script_path="${SCRIPT_DIR}/bashmenu.sh"
    local installed_any=false

    for shortcut_name in "bm" "bashmenu"; do
        local target_file="${target_dir}/${shortcut_name}"
        echo "Installing symlink '$shortcut_name' shortcut pointing to: $real_script_path"
        ln -sf "$real_script_path" "$target_file" 2>/dev/null || run_as_root ln -sf "$real_script_path" "$target_file"

        if [ -L "$target_file" ] || [ -f "$target_file" ]; then
            echo "  [✓] Successfully installed '$shortcut_name' shortcut at $target_file"
            installed_any=true
        else
            echo "  [✗] Failed to create shortcut at $target_file" >&2
        fi
    done

    if [ "$installed_any" = true ]; then
        if [[ ":$PATH:" != *":$target_dir:"* ]]; then
            echo "  [!] Notice: $target_dir is not currently in your PATH environment variable."
            for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
                if [ -f "$rc" ] && ! grep -q "$target_dir" "$rc"; then
                    echo "export PATH=\"$target_dir:\$PATH\"" >> "$rc"
                    echo "  [+] Added $target_dir to $rc"
                fi
            done
        fi
        return 0
    else
        return 1
    fi
}

# Install 'cheat' command symlink pointing to bashmenu.sh
install_cheat() {
    local shortcut_name="cheat"
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
    local real_script_path="${ADDITIONAL_SCRIPTS_DIR}/cheat.sh"

    echo "Installing symlink '$shortcut_name' shortcut pointing to: $real_script_path"

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
        echo "  [✗] Failed to create shortcut (symlink) at $target_file" >&2
        return 1
    fi
}


# Map binary names to their respective installation package names based on the package manager
get_package_name() {
    local binary="$1"
    
    case "$binary" in
        "pip3"|"pip")
            if [ "$PKG_MANAGER" = "apt" ] || [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "zypper" ]; then
                echo "python3-pip"
            elif [ "$PKG_MANAGER" = "pacman" ]; then
                [ "$IS_WINDOWS" = true ] && echo "mingw-w64-x86_64-python-pip" || echo "python-pip"
            elif [ "$PKG_MANAGER" = "pkg" ]; then
                echo "python"
            elif [ "$PKG_MANAGER" = "apk" ]; then
                echo "py3-pip"
            elif [ "$PKG_MANAGER" = "brew" ]; then
                echo ""
            else
                echo "python3-pip"
            fi
            ;;
        "venv")
            if [ "$PKG_MANAGER" = "apt" ]; then
                echo "python3-venv"
            elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "zypper" ]; then
                echo "python3-virtualenv"
            elif [ "$PKG_MANAGER" = "apk" ]; then
                echo "py3-virtualenv"
            elif [ "$PKG_MANAGER" = "pacman" ]; then
                [ "$IS_WINDOWS" = true ] && echo "mingw-w64-x86_64-python-virtualenv" || echo "python-virtualenv"
            elif [ "$PKG_MANAGER" = "pkg" ] || [ "$PKG_MANAGER" = "brew" ]; then
                echo ""
            else
                echo "python3-venv"
            fi
            ;;
        "python3"|"python")
            if [ "$PKG_MANAGER" = "pacman" ]; then
                [ "$IS_WINDOWS" = true ] && echo "mingw-w64-x86_64-python" || echo "python"
            elif [ "$PKG_MANAGER" = "pkg" ]; then
                echo "python"
            elif [ "$PKG_MANAGER" = "brew" ]; then
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
    elif [ "$PKG_MANAGER" = "pacman" ] && [ "$PACMAN_UPDATED" = false ] && [ ${#packages_to_install[@]} -gt 0 ]; then
        run_as_root mkdir -p /var/lib/pacman/local /var/lib/pacman/sync /var/cache/pacman/pkg 2>/dev/null || true
        if [ -f "/etc/pacman.conf" ]; then
            if grep -q "^#DisableSandbox" /etc/pacman.conf 2>/dev/null; then
                run_as_root sed -i 's/^#DisableSandbox/DisableSandbox/' /etc/pacman.conf 2>/dev/null || true
            elif ! grep -q "^DisableSandbox" /etc/pacman.conf 2>/dev/null; then
                if grep -q "^\[options\]" /etc/pacman.conf 2>/dev/null; then
                    run_as_root sed -i '/^\[options\]/a DisableSandbox' /etc/pacman.conf 2>/dev/null || true
                fi
            fi
        fi
        if [ -f "/etc/pacman.d/mirrorlist" ] && ! grep -q "^Server = " /etc/pacman.d/mirrorlist 2>/dev/null; then
            run_as_root sed -i '0,/^#Server = /s/^#//' /etc/pacman.d/mirrorlist 2>/dev/null || \
            run_as_root sh -c "echo 'Server = https://geo.mirror.pkgbuild.com/\$repo/os/\$arch' >> /etc/pacman.d/mirrorlist" 2>/dev/null || true
        fi
        if [ ! -d "/var/lib/pacman/sync" ] || [ -z "$(ls -A /var/lib/pacman/sync 2>/dev/null)" ]; then
            echo "Running pacman -Sy to synchronize package databases..."
            if command -v pacman-key >/dev/null 2>&1 && [ ! -d "/etc/pacman.d/gnupg" ]; then
                run_as_root pacman-key --init 2>/dev/null || true
                run_as_root pacman-key --populate archlinux 2>/dev/null || true
            fi
            run_as_root pacman -Sy --noconfirm 2>/dev/null || run_as_root pacman -Sy || true
        fi
        PACMAN_UPDATED=true
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
                run_as_root mkdir -p /var/lib/pacman/local /var/lib/pacman/sync /var/cache/pacman/pkg 2>/dev/null || true
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

# If being sourced by tests or subshells, don't execute the main menu loop
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    return 0 2>/dev/null || true
fi

show_help() {
    cat <<EOF
Usage: $(basename "$0") [options]

HA Bash Menu - Lightweight, cross-platform Textual TUI menu engine.

Options:
  -h, --help               Display this help message and exit
  -v, --version            Display version information and exit
  --check-env              Inspect platform detection, paths, and dependencies
  --install-bm             Install 'bm' command shortcut [/.local/bin/bm]
  --install-cheat          Install 'cheat' command shortcut [/.local/bin/cheat]
  --install-man            Install bashmenu.1 man page [/.local/share/man/man1/bashmenu.1]
  --setup                  Run non-interactive setup (venv, deps, shortcuts) and exit
  -y, --yes                Automatically answer yes to dependency installation prompts
EOF
}

SETUP_ONLY=false
AUTO_YES=false

# Handle standalone CLI flags
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--version)
            echo "bashmenu version 0.0.7"
            exit 0
            ;;
        --check-env)
            echo "Platform:     $PLATFORM (Kernel: $KERNEL)"
            echo "Pkg Manager:  ${PKG_MANAGER:-none}"
            echo "Cache Dir:    $CACHE_DIR"
            echo "Venv Dir:     $VENV_DIR"
            echo "Venv Active:  $VENV_ACTIVATE"
            exit 0
            ;;
        --install-bm)
            install_bm
            exit $?
            ;;
        --install-cheat)
            install_cheat
            exit $?
            ;;
        --install-man|--install-manpage)
            install_man_page
            exit $?
            ;;
        --setup)
            SETUP_ONLY=true
            AUTO_YES=true
            ;;
        -y|--yes)
            AUTO_YES=true
            ;;
    esac
done

# ==========================================================================
# Dependency Checking Phase
# ==========================================================================

# Check standard system binaries
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! is_installed "$tool"; then
        echo "  [✗] $tool is missing."
        pkg_name=$(get_package_name "$tool")
        if [ -n "$pkg_name" ]; then
            MISSING_PACKAGES+=("$pkg_name")
        fi
    fi
done

# Check Python internal pip binary status (soft check on Termux/Mac)
if [ "$IS_TERMUX" = false ] && [ "$IS_MAC" = false ]; then
    if ! is_installed "pip3" && ! is_installed "pip" && ! python3 -m pip --version >/dev/null 2>&1; then
        echo "  [✗] pip is missing."
        pkg_name=$(get_package_name "pip3")
        [ -n "$pkg_name" ] && MISSING_PACKAGES+=("$pkg_name")
    fi
fi

# Check Python internal venv engine status (omit ensurepip requirement on Termux)
if [ "$IS_TERMUX" = true ]; then
    if ! python3 -c "import venv" >/dev/null 2>&1; then
        echo "  [✗] python venv module is missing."
        pkg_name=$(get_package_name "venv")
        [ -n "$pkg_name" ] && MISSING_PACKAGES+=("$pkg_name")
    fi
else
    if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
        echo "  [✗] python3 venv module is missing."
        pkg_name=$(get_package_name "venv")
        if [ -n "$pkg_name" ] && [[ ! " ${MISSING_PACKAGES[*]} " =~ " ${pkg_name} " ]]; then
            MISSING_PACKAGES+=("$pkg_name")
        fi
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
if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "Found missing dependencies: ${MISSING_PACKAGES[*]}"
    if [ "$AUTO_YES" = true ]; then
        REPLY="y"
    else
        read -p "Would you like to install the missing tools? [y/N]: " -n 1 -r
        echo ""
    fi
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        # 1. Handle package manager updates
        if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
            if ! install_apps "${MISSING_PACKAGES[@]}"; then
                echo "Package installation failed. Exiting script." >&2
                exit 1
            fi
        fi

        # 2. Perform global validation confirmation
        ALL_VALID=true
        for tool in "${REQUIRED_TOOLS[@]}"; do
            if ! is_installed "$tool"; then ALL_VALID=false; fi
        done
        if [ "$IS_TERMUX" = false ] && ! python3 -c "import venv" >/dev/null 2>&1; then
            ALL_VALID=false
        fi
        
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

# Check if shortcuts or man page need installation
if [ "$SETUP_ONLY" = true ]; then
    install_bm
    install_cheat
    install_man_page
else
    # Check if 'bm' shortcut is missing and prompt user if interactive session
    if ! is_installed "bm"; then
        if [ -t 0 ]; then
            read -p "Global 'bm' command shortcut is not installed. Install it now? [y/N]: " -n 1 -r
            echo ""
            if [[ "$REPLY" =~ ^[Yy]$ ]]; then
                install_bm
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

# ENHANCED DEBIAN & ALPINE ENVIRONMENT RECOVERY PASS:
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1 && [ "$PKG_MANAGER" = "apt" ]; then
    echo "python3-venv is missing from the environment. Attempting immediate resolution..." >&2
    if install_apps "python3-venv"; then
        echo "python3-venv resolved." >&2
    fi
elif [ "$PKG_MANAGER" = "apk" ]; then
    if ! command -v virtualenv >/dev/null 2>&1 || ! command -v pip3 >/dev/null 2>&1; then
        echo "Alpine virtualenv/pip packages missing. Resolving..." >&2
        install_apps "py3-virtualenv" "py3-pip"
    fi
fi

# Resolve venv python and pip paths across OS layouts
resolve_venv_paths() {
    if [ -d "${VENV_DIR}/Scripts" ] || [ "$IS_WINDOWS" = true ]; then
        VENV_ACTIVATE="${VENV_DIR}/Scripts/activate"
        VENV_PYTHON="${VENV_DIR}/Scripts/python.exe"
        [ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="${VENV_DIR}/Scripts/python"
        VENV_PIP="${VENV_DIR}/Scripts/pip.exe"
        [ ! -f "$VENV_PIP" ] && VENV_PIP="${VENV_DIR}/Scripts/pip"
    else
        VENV_ACTIVATE="${VENV_DIR}/bin/activate"
        VENV_PYTHON="${VENV_DIR}/bin/python3"
        [ ! -f "$VENV_PYTHON" ] && VENV_PYTHON="${VENV_DIR}/bin/python"
        VENV_PIP="${VENV_DIR}/bin/pip"
        [ ! -f "$VENV_PIP" ] && VENV_PIP="${VENV_DIR}/bin/pip3"
    fi
}
resolve_venv_paths

USE_VENV=false
if [ -f "$VENV_ACTIVATE" ]; then
    if "$VENV_PYTHON" -c "import yaml, textual, rich" >/dev/null 2>&1; then
        USE_VENV=true
    else
        # If pyvenv.cfg doesn't include system packages, check if enabling it satisfies dependencies
        if [ -f "${VENV_DIR}/pyvenv.cfg" ] && grep -q "include-system-site-packages = false" "${VENV_DIR}/pyvenv.cfg" 2>/dev/null; then
            sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' "${VENV_DIR}/pyvenv.cfg" 2>/dev/null || true
            if "$VENV_PYTHON" -c "import yaml, textual, rich" >/dev/null 2>&1; then
                USE_VENV=true
            fi
        fi
        if [ "$USE_VENV" = false ]; then
            echo "Virtual environment is missing required packages (PyYAML, Textual, Rich). Recreating..." >&2
            rm -rf "$VENV_DIR"
        fi
    fi
fi

if [ "$USE_VENV" = false ]; then
    echo "Setting up virtual environment at $VENV_DIR..." >&2
    VENV_CREATED=false
    if command -v virtualenv >/dev/null 2>&1 && virtualenv --system-site-packages "$VENV_DIR" >/dev/null 2>&1; then
        VENV_CREATED=true
    elif python3 -m virtualenv --system-site-packages "$VENV_DIR" >/dev/null 2>&1; then
        VENV_CREATED=true
    elif python3 -m venv --system-site-packages "$VENV_DIR" >/dev/null 2>&1; then
        VENV_CREATED=true
    elif [ "$IS_TERMUX" = true ] && python3 -m venv --system-site-packages --without-pip "$VENV_DIR" >/dev/null 2>&1; then
        VENV_CREATED=true
    fi

    if [ "$VENV_CREATED" = true ]; then
        resolve_venv_paths
        if [ ! -x "$VENV_PIP" ]; then
            # Attempt to bootstrap pip via ensurepip
            "$VENV_PYTHON" -m ensurepip --default-pip >/dev/null 2>&1 || true
            resolve_venv_paths
        fi

        if [ -x "$VENV_PIP" ]; then
            if ! "$VENV_PYTHON" -c "import yaml, textual, rich" >/dev/null 2>&1; then
                if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
                    if "$VENV_PIP" install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null 2>&1 || "$VENV_PIP" install PyYAML textual rich >/dev/null 2>&1; then
                        USE_VENV=true
                    else
                        echo "Warning: Failed to install requirements inside virtual environment." >&2
                    fi
                else
                    "$VENV_PIP" install PyYAML textual rich >/dev/null 2>&1 && USE_VENV=true
                fi
            else
                USE_VENV=true
            fi
        else
            # Venv created without pip: check if venv or system python has packages
            if "$VENV_PYTHON" -c "import yaml, textual, rich" >/dev/null 2>&1; then
                USE_VENV=true
            elif python3 -c "import yaml, textual, rich" >/dev/null 2>&1; then
                USE_VENV=false
            elif command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
                pip_cmd=$(command -v pip3 || command -v pip)
                "$pip_cmd" install --break-system-packages PyYAML textual rich >/dev/null 2>&1 || \
                "$pip_cmd" install PyYAML textual rich >/dev/null 2>&1 || true
                python3 -c "import yaml, textual, rich" >/dev/null 2>&1 && USE_VENV=false
            fi
            if [ "$PKG_MANAGER" = "apk" ] && ! python3 -c "import yaml" >/dev/null 2>&1; then
                install_apps "py3-yaml" "py3-rich" "py3-pip"
                python3 -c "import yaml" >/dev/null 2>&1 && USE_VENV=false
            fi
        fi
    else
        echo "Warning: Could not create virtual environment. Checking system Python packages..." >&2
        if ! python3 -c "import yaml, textual, rich" >/dev/null 2>&1; then
            if command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
                pip_cmd=$(command -v pip3 || command -v pip)
                "$pip_cmd" install --break-system-packages PyYAML textual rich >/dev/null 2>&1 || \
                "$pip_cmd" install PyYAML textual rich >/dev/null 2>&1 || true
            fi
            if [ "$PKG_MANAGER" = "apk" ] && ! python3 -c "import yaml" >/dev/null 2>&1; then
                install_apps "py3-yaml" "py3-rich" "py3-pip"
            fi
        fi
    fi
fi

if [ "$USE_VENV" = true ] && [ -f "$VENV_ACTIVATE" ]; then
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    PYTHON_BIN="$VENV_PYTHON"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

# Fallback check for yaml on Alpine
if ! "$PYTHON_BIN" -c "import yaml" >/dev/null 2>&1 && [ "$PKG_MANAGER" = "apk" ]; then
    install_apps "py3-yaml"
fi

if [ "$SETUP_ONLY" = true ]; then
    if ! "$PYTHON_BIN" -c "import yaml" >/dev/null 2>&1; then
        echo "Error: Python environment is missing required dependencies (PyYAML)." >&2
        exit 1
    fi
    echo "  [✓] BashMenu environment, virtualenv, and shortcuts successfully configured."
    exit 0
fi

exec "$PYTHON_BIN" "$BASHMENU_SCRIPT" "$@"
