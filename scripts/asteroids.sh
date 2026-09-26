#!/bin/bash

# Check if asteroids is already installed
if [ -f /usr/local/bin/asteroids ]; then
    /usr/local/bin/asteroids
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
        if command -v yq &>/dev/null; then
            RAW_CACHE=$(yq '.settings.cache_dir' "$CONF_FILE" 2>/dev/null | tr -d '"')
        elif command -v python3 &>/dev/null; then
            RAW_CACHE=$(python3 -c "import yaml; data=yaml.safe_load(open('$CONF_FILE')); print(data.get('settings', {}).get('cache_dir', ''))" 2>/dev/null)
        fi
        if [ -n "$RAW_CACHE" ] && [ "$RAW_CACHE" != "null" ]; then
            CACHE_DIR="${RAW_CACHE//\{home\}/$HOME}"
            CACHE_DIR="${CACHE_DIR//\{bashmenu_dir\}/$(dirname "$SCRIPT_DIR")}"
        fi
    fi
fi

CACHE_DIR="${CACHE_DIR:-"$HOME/.cache/bashmenu"}"
mkdir -p "$CACHE_DIR" &>/dev/null

# Check if gcc is installed
if ! command -v gcc &> /dev/null; then
    echo "gcc is not installed"
    exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "git is not installed"
    exit 1
fi

# Check if asteroids is installed and install if not
if [ ! -f /usr/local/bin/asteroids ]; then
    echo "Installing asteroids..."

    # Get the latest version of asteroids from github
    git clone https://github.com/tsotchke/asteroids "$CACHE_DIR/asteroids"

    # Build asteroids
    cd "$CACHE_DIR/asteroids" || exit 1
    gcc -o asteroids asteroids.c -lm

    # Make it executable
    chmod +x "$CACHE_DIR/asteroids/asteroids"

    # Move it to /usr/local/bin
    sudo mv "$CACHE_DIR/asteroids/asteroids" /usr/local/bin

    # Cleanup
    rm -rf "$CACHE_DIR/asteroids"
fi

# Check if asteroids is installed
if [ -f /usr/local/bin/asteroids ]; then
    echo "(q) to quit, (r) to restart"
    sleep 1
    /usr/local/bin/asteroids
    break
else
    echo "Asteroids is not installed, installation failed."
    exit 1
fi
