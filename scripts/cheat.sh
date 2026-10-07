#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: cheat.sh
# DESCRIPTION: Terminal cheatsheet CLI wrapper. Resolves paths, activates the
#              virtual environment, and executes cheat.py.
# ==============================================================================
# Version: 0.0.8
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Helper function to exit or return depending on how the script was run
safe_exit() {
    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        return "$1" # Sourced: return to parent shell safely
    else
        exit "$1"   # Executed: exit subshell
    fi
}

# Canonical symlink resolution to determine true script directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Save your current terminal location, then move to the script directory
pushd "$SCRIPT_DIR" > /dev/null || safe_exit 1

if [ -f "${SCRIPT_DIR}/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/.venv/bin/activate"
    python "${SCRIPT_DIR}/cheat.py" "$@"
    deactivate
else
    python3 "${SCRIPT_DIR}/cheat.py" "$@"
fi

# Restore your original terminal location
popd > /dev/null || safe_exit 1

