#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: install_basics.sh
# DESCRIPTION: Cross-platform basic tools installer for Termux, macOS, and
#              various Linux distributions (Debian/Ubuntu, Fedora/RHEL, Arch).
# ==============================================================================

# Cross-platform basic tools installer

PACKAGES="vim mc htop glow gum curl wget git shellcheck shfmt jq yq"

IS_TERMUX=false
IS_MAC=false
if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
elif [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
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

echo "Installing basics: $PACKAGES"

if [ "$IS_TERMUX" = true ] && command -v pkg &> /dev/null; then
    pkg update -y && pkg install -y "$PACKAGES"
elif command -v apt-get &> /dev/null; then
    run_as_root apt-get update -qq && run_as_root apt-get install -y "$PACKAGES"
elif command -v dnf &> /dev/null; then
    run_as_root dnf install -y "$PACKAGES"
elif command -v pacman &> /dev/null; then
    run_as_root pacman -S --noconfirm "$PACKAGES"
elif command -v brew &> /dev/null; then
    brew install "$PACKAGES"
else
    echo "Unsupported package manager."
    exit 1
fi
