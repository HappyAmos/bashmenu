#!/bin/bash
# Version: 0.0.1
# Author:  HA Bash Menu

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASHMENU_SCRIPT="${SCRIPT_DIR}/bashmenu.py"
BASHMENU_SETTINGS="${SCRIPT_DIR}/bashmenu.yml"
VENV_DIR="${SCRIPT_DIR}/.venv"
VENV_ACTIVATE="${VENV_DIR}/bin/activate"
CACHE_DIR="$HOME/.cache/bashmenu"

# Define the list of tools your script requires
REQUIRED_TOOLS=("curl" "git" "glow" "jq" "tput" "yq")
MISSING_TOOLS=()

# Setup a cache directory
mkdir -p "$CACHE_DIR" &>/dev/null || exit 1

yaml_get() {
  local key="$1"
  local file="$2"
  yq -r ".$key" "$file"
}

# Function to check if a single tool is installed
is_installed() {
    local tool="$1"
    command -v "$tool" &> /dev/null
}

# Function to install missing applications using the local package manager
install_apps() {
    local apps_to_install=("$@")
    
    # Detect the available package manager
    local pkg_manager=""
    if command -v apt-get &> /dev/null; then
        pkg_manager="apt"
    elif command -v dnf &> /dev/null; then
        pkg_manager="dnf"
    elif command -v brew &> /dev/null; then
        pkg_manager="brew"
    else
        echo "Error: Supported package manager (apt, dnf, brew) not found." >&2
        return 1
    fi

    echo "Using package manager: $pkg_manager"

    # Loop through and install each missing tool
    for app in "${apps_to_install[@]}"; do
        echo "Installing $app..."
        
        case "$pkg_manager" in
            "apt")
                sudo apt-get update -qq && sudo apt-get install -y "$app"
                ;;
            "dnf")
                sudo dnf install -y "$app"
                ;;
            "brew")
                brew install "$app"
                ;;
         Redsas*)
                ;;
        esac

        # Verify if the installation actually succeeded
        if is_installed "$app"; then
            echo "Successfully installed $app."
        else
            echo "Failed to install $app." >&2
            return 1
        fi
    done
}

# Use the variables and functions above to install missing
# dependencies or exit with an error code.
#echo "Checking system dependencies..."

# Populate the array with items that are missing
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! is_installed "$tool"; then
    #    echo "  [✓] $tool is already installed."
    #else
        echo "  [✗] $tool is missing."
        MISSING_TOOLS+=("$tool")
    fi
done

# If there are missing tools, pass the entire array to the install function
if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    echo "Found missing dependencies."
    read -p "Would you like to install the missing tools? [y/N]: " -n 1 -r
    echo ""
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        # Passing the array expanded as separate arguments
        install_apps "${MISSING_TOOLS[@]}"
        
        if [ $? -eq 0 ]; then
            echo "All dependencies resolved successfully!"
        else
            echo "Dependency installation failed. Exiting script." >&2
            exit 1
        fi
    else
        echo "Skipping installation of missing tools, some included scripts or functions may not work properly."
    fi
fi

# ==========================================================================
# Check Github version against installed version
# ==========================================================================

UPDATES=$(yaml_get "settings.check_for_updates" "${BASHMENU_SETTINGS}")
if [[ "${UPDATES,,}" == "true" ]]; then

    # Download latest changes from the remote server silently
    git fetch -q

    # Count how many commits the remote is ahead of your local branch
    CHANGES_AHEAD=$(git rev-list --count HEAD..@{u})

    if [ "$CHANGES_AHEAD" -gt 0 ]; then
        echo "There has been an update! ($CHANGES_AHEAD new commit(s))"
        read -p "Would you like to update? [y/N]: " -n 1 -r
        echo ""
        if [[ "$REPLY" =~ ^[Yy]$ ]]; then
            git pull
        else
            echo "Skipping update."
        fi
    else
        echo "Your local version is up to date."
    fi
fi
# ==========================================================================

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
