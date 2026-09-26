#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: bsdgames.sh
# DESCRIPTION: Cross-platform wrapper script to run bsdgames on macOS and Linux.
# ==============================================================================

# Get the script directory path for this script
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to run a game searching across common system paths
run_game() {
    local name="$1"
    local paths=(
        "$name"
        "/usr/games/$name"
        "/usr/bin/$name"
        "/usr/local/bin/$name"
        "/opt/homebrew/bin/$name"
        "${PREFIX:-}/bin/$name"
    )

    for cmd in "${paths[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            "$cmd"
            return 0
        fi
    done

    echo "Error: Game '$name' not found in standard system paths or PATH." >&2
    echo "Try installing it with the install script, install_games.sh" >&2
    return 1
}

# Infinite interactive menu loop
while true; do
    clear
    echo "=================================================="
    echo "                  GAMES RUNNER                    "
    echo "=================================================="
    echo " 1) Ninvaders"
    echo " 2) Pacman4console"
    echo " 3) Nsnake"
    echo " 4) Greed"
    echo " 5) Moon-buggy"
    echo " 6) Nethack-console"
    echo " 7) Asteroids"
    echo "--------------------------------------------------"
    echo " q) Quit"
    echo "=================================================="
    echo ""
    
    # Prompt the user for choice
    read -r -p "Select an option [1-18, q]: " choice
    
    # Check if user wants to quit
    if [[ "$choice" == "q" || "$choice" == "Q" ]]; then
        echo "Goodbye!"
        break
    fi
    
    # Run the selected game
    case $choice in
        1)  run_game ninvaders ;;
        2)  run_game pacman4console ;;
        3)  run_game nsnake ;;
        4)  run_game greed ;;
        5)  run_game moon-buggy ;;
        6)  run_game nethack-console ;;
        7)  . "$SCRIPT_DIR"/asteroids.sh ;;
        *)  echo -e "\nInvalid choice! Please choose a number from 1 to 7, 'q' to exit." ;;
    esac
    
    # Pause mechanism to let them review before clearing and returning to prompt
    echo "--------------------------------------------------"
    read -r -p "Finished. Press [Enter] to return to the menu..."
done
