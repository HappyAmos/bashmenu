#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: bsdgames.sh
# DESCRIPTION: Cross-platform wrapper script to run bsdgames on macOS and Linux.
# ==============================================================================

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
    return 1
}

# Infinite interactive menu loop
while true; do
    clear
    echo "=================================================="
    echo "                 BSD GAMES RUNNER                 "
    echo "=================================================="
    echo " 1) Adventure"
    echo " 2) Arithmetic"
    echo " 3) ATC"
    echo " 4) Backgammon"
    echo " 5) Battlestar"
    echo " 6) Boggle"
    echo " 7) Canfield"
    echo " 8) Cribbage"
    echo " 9) Gomoku"
    echo "10) Hangman"
    echo "11) Hunt"
    echo "12) Monopoly"
    echo "13) Robots"
    echo "14) Sail"
    echo "15) Snake"
    echo "16) Tetris"
    echo "17) Trek"
    echo "18) Wump"
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
        1)  run_game adventure ;;
        2)  run_game arithmetic ;;
        3)  run_game atc ;;
        4)  run_game backgammon ;;
        5)  run_game battlestar ;;
        6)  run_game boggle ;;
        7)  run_game canfield ;;
        8)  run_game cribbage ;;
        9)  run_game gomoku ;;
        10) run_game hangman ;;
        11) run_game hunt ;;
        12) run_game monopoly ;;
        13) run_game robots ;;
        14) run_game sail ;;
        15) run_game snake ;;
        16) run_game tetris-bsd || run_game tetris ;;
        17) run_game trek ;;
        18) run_game wump ;;
        *)  echo -e "\nInvalid choice! Please choose a number from 1 to 18, 'q' to exit." ;;
    esac
    
    # Pause mechanism to let them review before clearing and returning to prompt
    echo "--------------------------------------------------"
    read -r -p "Finished. Press [Enter] to return to the menu..."
done
