#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: install_games.sh
# DESCRIPTION: Cross-platform wrapper script to install games using the
#              system's native package manager (apt, dnf, pacman, pkg, or brew).
# ==============================================================================

games=(
    "ninvaders"
    "pacman4console"
    "nsnake"
    "greed"
    "moon-buggy"
    "nethack-console"
    "bsdgames"
    "asteroids"
)

# Install games using the system's native package manager
for game in "${games[@]}"; do
    if command -v "$game" &>/dev/null; then
        echo "Game '$game' is already installed."
    else
        echo "Installing game '$game'..."
        case "$(uname -s)" in
            Darwin)
                brew install "$game"
                ;;            
            Linux)
                if command -v apt-get &> /dev/null; then
                    sudo apt-get install -y "$game"
                elif command -v dnf &> /dev/null; then
                    sudo dnf install -y "$game"
                elif command -v pacman &> /dev/null; then
                    sudo pacman -Syu --noconfirm "$game"
                elif command -v apk &> /dev/null; then
                    sudo apk add "$game"
                elif command -v zypper &> /dev/null; then
                    sudo zypper install -y "$game"
                else
                    echo "Unsupported package manager."
                    exit 1
                fi
                ;;
            *)
                echo "Unsupported operating system."
                exit 1
                ;;
        esac
    fi
done

echo "Game installation complete."
