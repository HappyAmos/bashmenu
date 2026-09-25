#!/usr/bin/env bash

set -euo pipefail

OS_TYPE=$(uname -s)

echo "Detecting operating system..."

run_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        "$@"
    fi
}

if [ "$OS_TYPE" = "Darwin" ]; then
    # --- macOS Installation ---
    echo "Detected macOS. Checking for Homebrew..."
    if command -v brew >/dev/null 2>&1; then
        brew install glow
    else
        echo "Homebrew not found. Attempting universal binary installer..."
        curl -fsSL https://charm.sh/install.sh | bash -s -- --to=/usr/local/bin
    fi

elif [ "$OS_TYPE" = "Linux" ]; then
    # --- Linux Installation ---
    
    # Check for Debian/Ubuntu (APT)
    if [ -d /etc/apt ]; then
        echo "Detected Debian/Ubuntu-based system. Running APT setup..."
        run_root mkdir -p /etc/apt/keyrings
        curl -fsSL https://repo.charm.sh/apt/gpg.key | run_root gpg --dearmor --yes -o /etc/apt/keyrings/charm.gpg
        echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | run_root tee /etc/apt/sources.list.d/charm.list > /dev/null
        run_root apt-get update -qq
        run_root apt-get install -y glow

    # Check for Fedora/RHEL/CentOS (DNF/YUM)
    elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then
        echo "Detected RHEL/Fedora-based system. Running DNF/YUM setup..."
        PM=$(command -v dnf || command -v yum)
        echo '[charm]
name=Charm
baseurl=https://repo.charm.sh/yum/
enabled=1
gpgcheck=1
gpgkey=https://repo.charm.sh/yum/gpg.key' | run_root tee /etc/yum.repos.d/charm.repo > /dev/null
        run_root "$PM" install -y glow

    # Check for Arch Linux (Pacman)
    elif command -v pacman >/dev/null 2>&1; then
        echo "Detected Arch Linux. Installing via extra repository..."
        run_root pacman -Sy --noconfirm glow

    # Check for Alpine Linux (APK)
    elif command -v apk >/dev/null 2>&1; then
        echo "Detected Alpine Linux. Installing via apk..."
        run_root apk add glow

    # Check for openSUSE (Zypper)
    elif command -v zypper >/dev/null 2>&1; then
        echo "Detected openSUSE. Installing via charm repo..."
        run_root rpm --import https://repo.charm.sh/yum/gpg.key
        run_root zypper ar -f https://repo.charm.sh/yum/ charm
        run_root zypper install -y glow

    # Fallback: Multi-platform Binary Installer
    else
        echo "Falling back to Charm universal script installer..."
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL https://charm.sh/install.sh | bash
        else
            echo "Error: curl is required to run the universal installer." >&2
            exit 1
        fi
    fi
else
    echo "Unsupported OS platform: $OS_TYPE" >&2
    exit 1
fi

echo "Glow has been successfully installed!"
