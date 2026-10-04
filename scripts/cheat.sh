#!/usr/bin/env bash
# Version: 0.0.7
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Canonical symlink resolution to determine true script directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Save your current terminal location, then move to the script directory
pushd "$SCRIPT_DIR" > /dev/null || exit 1

if [ -f "${SCRIPT_DIR}/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/.venv/bin/activate"
    python "${SCRIPT_DIR}/cheat.py" "$@"
    deactivate
else
    python3 "${SCRIPT_DIR}/cheat.py" "$@"
fi

# Restore your original terminal location
popd > /dev/null || exit 1
