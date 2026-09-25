#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: system_update.sh
# DESCRIPTION: Cross-platform wrapper script to update packages using the
#              system's native package manager (apt, dnf, yum, pacman, zypper, apk, brew, pkg).
# ==============================================================================

IS_TERMUX=false
IS_MAC=false
if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
elif [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
fi

run_as_root() {
    if [ "$IS_TERMUX" = true ] || [ "$IS_MAC" = true ]; then
        "$@"
    else
        if [ "$(id -u)" = 0 ]; then
            "$@"
        elif command -v sudo &>/dev/null; then
            sudo "$@"
        else
            "$@"
        fi
    fi
}

echo "Updating system..."

if [ "$IS_TERMUX" = true ] && command -v pkg &> /dev/null; then
    pkg update -y && pkg upgrade -y
elif command -v apt-get &> /dev/null; then
    run_as_root apt-get update && run_as_root apt-get upgrade -y
elif command -v dnf &> /dev/null; then
    run_as_root dnf upgrade -y
elif command -v yum &> /dev/null; then
    run_as_root yum update -y
elif command -v pacman &> /dev/null; then
    run_as_root pacman -Syu --noconfirm
elif command -v zypper &> /dev/null; then
    run_as_root zypper refresh && run_as_root zypper update -y
elif command -v apk &> /dev/null; then
    run_as_root apk update && run_as_root apk upgrade
elif command -v brew &> /dev/null; then
    brew update && brew upgrade
else
    echo "Unsupported package manager."
    exit 1
fi
