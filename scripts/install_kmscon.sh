#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: install_kmscon.sh
# DESCRIPTION: Installs kmscon on a Linux system (Debian/Ubuntu/Mint) and configures
#              it as a systemd service. Useful for headless base systems.
# ==============================================================================
# Version: 0.0.1
# Author:  HA Bash Menu Development Team
# This script installs kmscon on a Linux system. Great for a headless base system without a GUI that doesn't
# install a system with a frame buffer
# It is intended for use on systems that use systemd and have access to the necessary package repositories.

# Check for incompatible environments (Termux / WSL)
if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]] || grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Notice: kmscon requires systemd and hardware TTYs, which are not supported in Termux or WSL."
    echo "Skipping installation."
    exit 0
fi

# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root."
    exit 1
fi

# Use quotes around the subshell assignment to handle empty results safely
KMSCON_INSTALLED="$(command -v kmscon)"

# Use the -n flag and the $ symbol to test if the variable's value is not empty
if [ -n "$KMSCON_INSTALLED" ]; then
    echo "kmscon is already installed."
    exit 0
fi



if [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    source /etc/os-release
else
    echo "Error: /etc/os-release not found. kmscon installation is only supported on Linux systemd distributions." >&2
    exit 1
fi

echo "Found OS: ${NAME:-Unknown}, Version: ${VERSION:-Unknown}, ID: ${ID:-Unknown}, Codename: ${VERSION_CODENAME:-Unknown}"

if [[ "${ID:-}" == "ubuntu" || "${ID:-}" == "linuxmint" ]]; then
    echo "Detected Debian-based system: $ID"
    apt update
    apt install -y kmscon
elif [[ "${ID:-}" == "debian" && "${VERSION_CODENAME:-}" == "trixie" ]]; then
    echo "Detected Debian Trixie"
    APT_PATH="/etc/apt/sources.list.d/"
    APT_FILE="debian-backports.sources"
    if [ ! -f "${APT_PATH}${APT_FILE}" ]; then
        cat << 'EOF' > "${APT_PATH}${APT_FILE}"
Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites: trixie-backports
Components: main
Enabled: yes
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF

    fi
    sudo apt update
    sudo apt install -y kmscon
else
    echo "Unsupported Linux distribution: $ID"
    exit 1
fi

if sudo systemctl disable getty@tty1.service; then
    echo "Successfully disabled getty."
    if sudo systemctl enable kmsconvt@tty1.service; then
        echo "Successfully enabled kmscon."
        exit 0
    else
        echo "Failed to enable kmscon. Please check your system configuration."
        exit 1
    fi
else
    echo "Failed to disable getty. Please check your system configuration."
    exit 1
fi
