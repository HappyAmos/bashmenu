#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: rich.sh
# DESCRIPTION: Renders a Markdown file using the Python Rich library.
# Usage: rich.sh <filename>
# ==============================================================================

set -eo pipefail

# Check if filename argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <filename>" >&2
    exit 1
fi

# Verify the file exists
if [ ! -f "$1" ]; then
    echo "Error: File '$1' does not exist." >&2
    exit 1
fi

# Resolve file path portably without hardcoded paths
if command -v realpath >/dev/null 2>&1; then
    TARGET_FILE="$(realpath "$1")"
elif command -v readlink >/dev/null 2>&1; then
    TARGET_FILE="$(readlink -f "$1" 2>/dev/null || echo "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")")"
else
    TARGET_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fi

# Resolve script directory and project root dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect Python interpreter
PYTHON_BIN=""
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Error: Python 3 executable was not found." >&2
    exit 1
fi

# Verify Rich module is available
if ! "$PYTHON_BIN" -c "import rich" >/dev/null 2>&1; then
    echo "Error: Python Rich library is not available in '$PYTHON_BIN'." >&2
    exit 1
fi

# Force Rich to preserve ANSI color codes through pipes
export FORCE_COLOR=1

# Tell less to interpret raw ANSI color escape sequences
export LESS="-R"

# Detect terminal width when running interactively
WIDTH_ARGS=()
if [ -t 1 ]; then
    WIDTH="$(tput cols 2>/dev/null || true)"
    if [ -n "$WIDTH" ] && [ "$WIDTH" -gt 0 ] 2>/dev/null; then
        WIDTH_ARGS=("-w" "$WIDTH")
    fi
fi

# Pipe through less -R for interactive terminals, or stream directly if redirected
if [ -t 1 ] && command -v less >/dev/null 2>&1; then
    "$PYTHON_BIN" -m rich.markdown -c "${WIDTH_ARGS[@]}" "$TARGET_FILE" | less -R
elif [ -t 1 ] && [ -n "$PAGER" ]; then
    "$PYTHON_BIN" -m rich.markdown -c "${WIDTH_ARGS[@]}" "$TARGET_FILE" | $PAGER
else
    "$PYTHON_BIN" -m rich.markdown -c "${WIDTH_ARGS[@]}" "$TARGET_FILE"
fi
