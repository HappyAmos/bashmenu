#!/bin/bash
# Version: 0.0.1
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASHMENU_SCRIPT="${SCRIPT_DIR}/bashmenu.py"
VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_ACTIVATE="${VENV_DIR}/bin/activate"
CACHE_DIR="$HOME/.cache/bashmenu"

# Setup a cache directory
mkdir -p "$CACHE_DIR" &>/dev/null || exit 1

# Check Github version against installed version

# Download latest changes from the remote server silently
git fetch -q

# Count how many commits the remote is ahead of your local branch
CHANGES_AHEAD=$(git rev-list --count HEAD..@{u})

if [ "$CHANGES_AHEAD" -gt 0 ]; then
    echo "There has been an update! ($CHANGES_AHEAD new commit(s))"
    echo "git pull to update" 
    # Put your update logic here (e.g., git pull)
else
    echo "Your local version is up to date."
fi


exit

if [ ! -f "$BASHMENU_SCRIPT" ]; then
    echo "Error: $BASHMENU_SCRIPT not found." >&2
    exit 1
fi

# Ensure virtual environment exists and is working
USE_VENV=false
if [ -f "$VENV_ACTIVATE" ]; then
    # Test if virtual environment Python works and can import yaml
    if "${VENV_DIR}/bin/python3" -c "import yaml" >/dev/null 2>&1; then
        USE_VENV=true
    else
        echo "Virtual environment is broken or missing PyYAML. Recreating..." >&2
        rm -rf "$VENV_DIR"
    fi
fi

if [ "$USE_VENV" = false ]; then
    echo "Setting up virtual environment at $VENV_DIR..." >&2
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
        if "${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null 2>&1; then
            USE_VENV=true
        else
            echo "Warning: Failed to install requirements inside virtual environment." >&2
        fi
    else
        echo "Warning: Could not create virtual environment. Falling back to system Python." >&2
    fi
fi

if [ "$USE_VENV" = true ]; then
    source "$VENV_ACTIVATE"
    PYTHON_BIN="python3"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

"$PYTHON_BIN"  "$BASHMENU_SCRIPT" "$@"
