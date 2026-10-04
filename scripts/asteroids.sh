#!/usr/bin/env bash

# Helper to determine writable binary installation directory
get_bin_dir() {
    if [ -n "$TERMUX_VERSION" ] || [[ "${PREFIX:-}" == *"/com.termux/"* ]]; then
        echo "${PREFIX:-/data/data/com.termux/files/usr}/bin"
    elif [ "$(id -u)" = "0" ] || [ -w "/usr/local/bin" ]; then
        echo "/usr/local/bin"
    else
        mkdir -p "$HOME/.local/bin"
        echo "$HOME/.local/bin"
    fi
}

BIN_DIR="$(get_bin_dir)"
ASTEROIDS_BIN="${BIN_DIR}/asteroids"

# Check if asteroids is already in PATH or installed in BIN_DIR
if command -v asteroids >/dev/null 2>&1; then
    asteroids
    exit 0
elif [ -x "$ASTEROIDS_BIN" ]; then
    "$ASTEROIDS_BIN"
    exit 0
fi

# Resolve cache directory using environment variable CACHE_DIR, cachedir, or config file
if [ -z "$CACHE_DIR" ]; then
    CACHE_DIR="${cachedir:-}"
fi

if [ -z "$CACHE_DIR" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CONF_FILE="$SCRIPT_DIR/../bashmenu.yml"
    if [ -f "$CONF_FILE" ]; then
        if command -v python3 &>/dev/null; then
            RAW_CACHE=$(python3 -c "import yaml; data=yaml.safe_load(open('$CONF_FILE')); print(data.get('settings', {}).get('cache_dir', ''))" 2>/dev/null)
        elif command -v yq &>/dev/null; then
            RAW_CACHE=$(yq '.settings.cache_dir' "$CONF_FILE" 2>/dev/null | tr -d '"')
        else
            RAW_CACHE=$(grep -E '^[[:space:]]*cache_dir:' "$CONF_FILE" 2>/dev/null | awk -F': ' '{print $2}' | tr -d '"'\'' ')
        fi
        if [ -n "$RAW_CACHE" ] && [ "$RAW_CACHE" != "null" ]; then
            CACHE_DIR="${RAW_CACHE//\{home\}/$HOME}"
            CACHE_DIR="${CACHE_DIR//\{bashmenu_dir\}/$(dirname "$SCRIPT_DIR")}"
        fi
    fi
fi

CACHE_DIR="${CACHE_DIR:-"$HOME/.cache/bashmenu"}"
mkdir -p "$CACHE_DIR" &>/dev/null

# Detect C compiler (gcc, clang, or cc)
CC=""
if command -v gcc &>/dev/null; then
    CC="gcc"
elif command -v clang &>/dev/null; then
    CC="clang"
elif command -v cc &>/dev/null; then
    CC="cc"
else
    echo "Error: No C compiler (gcc, clang, or cc) found."
    exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "git is not installed"
    exit 1
fi

# Install if not present
if [ ! -x "$ASTEROIDS_BIN" ] && ! command -v asteroids >/dev/null 2>&1; then
    echo "Installing asteroids to $BIN_DIR..."
    rm -rf "$CACHE_DIR/asteroids"

    # Get the latest version of asteroids from github
    git clone https://github.com/tsotchke/asteroids "$CACHE_DIR/asteroids"

    # Build asteroids
    pushd "$CACHE_DIR/asteroids" >/dev/null || exit 1
    "$CC" -o asteroids asteroids.c -lm
    chmod +x asteroids
    if [ -w "$BIN_DIR" ]; then
        mv asteroids "$ASTEROIDS_BIN"
    elif command -v sudo >/dev/null 2>&1; then
        sudo mv asteroids "$ASTEROIDS_BIN"
    else
        mkdir -p "$HOME/.local/bin"
        mv asteroids "$HOME/.local/bin/asteroids"
        ASTEROIDS_BIN="$HOME/.local/bin/asteroids"
    fi
    popd >/dev/null || exit 1

    # Cleanup
    rm -rf "$CACHE_DIR/asteroids"
fi

# Check if asteroids is installed and run
if [ -x "$ASTEROIDS_BIN" ]; then
    echo "(q) to quit, (r) to restart"
    sleep 1
    "$ASTEROIDS_BIN"
    exit 0
elif command -v asteroids >/dev/null 2>&1; then
    echo "(q) to quit, (r) to restart"
    sleep 1
    asteroids
    exit 0
else
    echo "Asteroids is not installed, installation failed."
    exit 1
fi

