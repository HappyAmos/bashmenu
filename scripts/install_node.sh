#!/usr/bin/env bash

# Detect OS
OS_TYPE=$(uname -s)

if [ "$OS_TYPE" = "Darwin" ]; then
    echo "=========================================="
    echo "🍏 macOS detected. Setting up via Homebrew..."
    echo "=========================================="

    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add Homebrew to PATH for the current session depending on architecture
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    else
        echo "Homebrew is already installed."
        brew update
    fi

    # Install Node and NPM directly via Homebrew
    echo "Installing Node.js and npm via Homebrew..."
    brew install node

    # Verify installation
    echo "=========================================="
    echo "✅ Installation Complete!"
    echo "Node version: $(node -v)"
    echo "npm version:  $(npm -v)"
    echo "=========================================="

elif [ "$OS_TYPE" = "Linux" ]; then
    echo "=========================================="
    echo "🐧 Linux detected. Running NVM setup..."
    echo "=========================================="
    
    # Determine Package Manager and install dependencies
    if command -v apt-get &> /dev/null; then
        echo "Detected Debian/Ubuntu-based system."
        sudo apt-get update
        sudo apt-get install -y curl git build-essential
    elif command -v dnf &> /dev/null; then
        echo "Detected Fedora/RHEL-based system."
        sudo dnf groupinstall -y "Development Tools"
        sudo dnf install -y curl git
    elif command -v pacman &> /dev/null; then
        echo "Detected Arch Linux-based system."
        sudo pacman -Syu --noconfirm base-devel curl git
    elif command -v apk &> /dev/null; then
        echo "Detected Alpine Linux-based system."
        sudo apk add build-base curl git
    elif command -v zypper &> /dev/null; then
        echo "Detected openSUSE-based system."
        sudo zypper install -y -t pattern devel_basis
        sudo zypper install -y curl git
    else
        echo "Warning: Unknown package manager. Proceeding with NVM install anyway..."
    fi

    # Install NVM
    echo "Installing NVM (Node Version Manager)..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

    # Load NVM into current session
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

    # Install Node LTS
    echo "Installing Node.js LTS version via NVM..."
    nvm install --lts

    # Verify installation
    echo "=========================================="
    echo "✅ Installation Complete!"
    echo "Node version: $(node -v)"
    echo "npm version:  $(npm -v)"
    echo "=========================================="
else
    echo "❌ Unsupported operating system: $OS_TYPE"
    exit 1
fi
