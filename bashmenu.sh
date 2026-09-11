#!/bin/bash
# Version: 0.0.1
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASHMENU_SCRIPT="${SCRIPT_DIR}/bashmenu.py"
VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_ACTIVATE="${VENV_DIR}/bin/activate"

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
