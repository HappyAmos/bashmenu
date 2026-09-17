#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: bsdgames.sh
# DESCRIPTION: Cross-platform wrapper script to run bsdgames on macOS and Linux.
# ==============================================================================

# Set games directory
GAMES_DIR="/usr/games"

# Infinite interactive menu loop
while true; do
    clear
    echo "=================================================="
    echo "            UNICODE BLOCK EXPLORER                "
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
    read -r -p "Select an option [1-10, c, q]: " choice
    
    # Check if user wants to quit
    if [[ "$choice" == "q" || "$choice" == "Q" ]]; then
        echo "Goodbye!"
        break
    fi
    
    # Run the selected game
    case $choice in
        1)  "$GAMES_DIR"/adventure ;;
        2)  "$GAMES_DIR"/arithmetic ;;
        3)  "$GAMES_DIR"/atc ;;
        4)  "$GAMES_DIR"/backgammon ;;
        5)  "$GAMES_DIR"/battlestar ;;
        6)  "$GAMES_DIR"/boggle ;;
        7)  "$GAMES_DIR"/canfield ;;
        8)  "$GAMES_DIR"/cribbage ;;
        9)  "$GAMES_DIR"/gomoku ;;
        10) "$GAMES_DIR"/hangman ;;
        11) "$GAMES_DIR"/hunt ;;
        12) "$GAMES_DIR"/monopoly ;;
        13) "$GAMES_DIR"/robots ;;
        14) "$GAMES_DIR"/sail ;;
        15) "$GAMES_DIR"/snake ;;
        16) "$GAMES_DIR"/tetris-bsd ;;
        17) "$GAMES_DIR"/trek ;;
        18) "$GAMES_DIR"/wump ;;
        *)  echo -e "\nInvalid choice! Please choose a number from 1 to 18, 'q' to exit." ;;
    esac
    
    # Pause mechanism to let them review before clearing and returning to prompt
    echo "--------------------------------------------------"
    read -r -p "Finished printing. Press [Enter] to return to the menu..."
done
