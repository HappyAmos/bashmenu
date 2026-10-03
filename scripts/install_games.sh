#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: install_games.sh
# DESCRIPTION: Cross-platform wrapper script to install games using the
#              system's native package manager (apt, dnf, pacman, pkg, or brew).
# ==============================================================================

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Function to check whether a game is already installed
is_game_installed() {
    local game="$1"
    case "$game" in
        bsdgames)
            # bsdgames installs individual command binaries into /usr/games or PATH
            for bin_path in /usr/games/robots /usr/games/adventure /usr/games/battlestar robots adventure; do
                if command -v "$bin_path" &>/dev/null || [ -x "$bin_path" ]; then
                    return 0
                fi
            done
            return 1
            ;;
        asteroids)
            if [ -x "/usr/local/bin/asteroids" ] || command -v asteroids &>/dev/null; then
                return 0
            fi
            return 1
            ;;
        nethack-console)
            if command -v nethack-console &>/dev/null || command -v nethack &>/dev/null || [ -x "/usr/games/nethack" ]; then
                return 0
            fi
            return 1
            ;;
        *)
            if command -v "$game" &>/dev/null || [ -x "/usr/games/$game" ] || [ -x "/usr/local/bin/$game" ]; then
                return 0
            fi
            return 1
            ;;
    esac
}

IS_TERMUX=false
if [ -n "$TERMUX_VERSION" ] || [[ "${PREFIX:-}" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
fi

run_root() {
    if [ "$IS_TERMUX" = true ] || [ "$(uname -s)" = "Darwin" ]; then
        "$@"
    elif [ "$(id -u)" = "0" ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        "$@"
    fi
}

# Install games using the system's native package manager
for game in "${games[@]}"; do
    if is_game_installed "$game"; then
        echo "Game '$game' is already installed."
    else
        echo "Installing game '$game'..."
        if [ "$game" = "asteroids" ]; then
            if [ -f "$SCRIPT_DIR/asteroids.sh" ]; then
                bash "$SCRIPT_DIR/asteroids.sh"
            else
                echo "Error: $SCRIPT_DIR/asteroids.sh not found." >&2
            fi
            continue
        fi

        if [ "$IS_TERMUX" = true ] && command -v pkg &>/dev/null; then
            pkg_name="$game"
            [ "$game" = "nethack-console" ] && pkg_name="nethack"
            [ "$game" = "bsdgames" ] && pkg_name="bsd-games"
            pkg install -y "$pkg_name" || echo "Note: Package '$pkg_name' not available in Termux repo."
            continue
        fi

        case "$(uname -s)" in
            Darwin)
                pkg_name="$game"
                [ "$game" = "nethack-console" ] && pkg_name="nethack"
                [ "$game" = "bsdgames" ] && pkg_name="bsd-games"
                brew install "$pkg_name"
                ;;            
            Linux)
                if command -v apt-get &> /dev/null; then
                    run_root apt-get install -y "$game"
                elif command -v dnf &> /dev/null; then
                    pkg_name="$game"
                    [ "$game" = "nethack-console" ] && pkg_name="nethack"
                    run_root dnf install -y "$pkg_name"
                elif command -v pacman &> /dev/null; then
                    pkg_name="$game"
                    [ "$game" = "nethack-console" ] && pkg_name="nethack"
                    run_root pacman -Syu --noconfirm "$pkg_name"
                elif command -v apk &> /dev/null; then
                    pkg_name="$game"
                    [ "$game" = "nethack-console" ] && pkg_name="nethack"
                    run_root apk add "$pkg_name"
                elif command -v zypper &> /dev/null; then
                    pkg_name="$game"
                    [ "$game" = "nethack-console" ] && pkg_name="nethack"
                    run_root zypper install -y "$pkg_name"
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
