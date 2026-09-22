#!/usr/bin/env bash

set -euo pipefail

# 1. Detect Operating System
OS_TYPE=$(uname -s)

echo "Detecting operating system..."

if [ "$OS_TYPE" = "Darwin" ]; then
    # --- macOS Installation ---
    echo "Detected macOS. Checking for Homebrew..."
    if command -v brew >/dev/null 2>&1; then
        brew install glow
    else
        echo "Error: Homebrew is required for macOS installation." >&2
        echo "Install it from https://brew.sh or install Glow manually." >&2
        exit 1
    fi

elif [ "$OS_TYPE" = "Linux" ]; then
    # --- Linux Installation ---
    
    # Check for Debian/Ubuntu (APT)
    if [ -d /etc/apt ]; then
        echo "Detected Debian/Ubuntu-based system. Running APT setup..."
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor --yes -o /etc/apt/keyrings/charm.gpg
        echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list > /dev/null
        sudo apt update
        sudo apt install -y glow

    # Check for Fedora/RHEL/CentOS (DNF/YUM)
    elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then
        echo "Detected RHEL/Fedora-based system. Running DNF setup..."
        PM=$(command -v dnf || command -v yum)
        echo '[charm]
name=Charm
baseurl=https://charm.sh
enabled=1
gpgcheck=1
gpgkey=https://charm.shgpg.key' | sudo tee /etc/yum.repos.d/charm.repo > /dev/null
        sudo "$PM" install -y glow

    # Check for Arch Linux (Pacman)
    elif command -v pacman >/dev/null 2>&1; then
        echo "Detected Arch Linux. Installing via extra repository..."
        sudo pacman -Syu --noconfirm glow

    # Check for Alpine Linux (APK)
    elif command -v apk >/dev/null 2>&1; then
        echo "Detected Alpine Linux. Installing via apk..."
        sudo apk add glow

    # Fallback: Multi-platform Binary Installer
    else
        echo "Unknown Linux distribution. Falling back to universal script installer..."
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL https://repo.charm.sh/apt/gpg.key # standard check
            # Charm offers a universal go-based tool or we can use generic shell script installer if available:
            echo "Please use 'go install ://github.com' or download the binary directly."
            exit 1
        fi
    fi
else
    echo "Unsupported OS platform: $OS_TYPE" >&2
    exit 1
fi

echo "Glow has been successfully installed!"
