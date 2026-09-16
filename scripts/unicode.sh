#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: unicode.sh
# DESCRIPTION: Interactive Unicode Block Explorer. Allows viewing predefined
#              or custom ranges of Unicode characters printed directly to the terminal.
# ==============================================================================

# Simple bash script to print unicode characters to the screen.
# Since there are literally millions of them, only a few chosen
# blocks have been included, but you could easily configure more
# blocks using a tool like https://unicode-explorer.com/search/
# to find the unicode blocks you are interested in.
#
# All you'd have to do is include a menu item in the interactive
# menu loop below, and add the retrieval line in the case 
# statement below.

# Function to cleanly print a specific range with a header
print_unicode_range() {
    local label="$1"
    local start="$2"
    local end="$3"
    local cols="$4"
    local c=0

    printf "\n======================================================================\n"
    printf "  Printing: %s (U+%04X - U+%04X)\n" "$label" "$start" "$end"
    printf "======================================================================\n\n"
    
    for ((i=start; i<=end; i++)); do
        # Format code point to 8 hex digits for the Bash \U escape sequence
        local hex
        hex=$(printf "%08X" "$i")
        
        # Display short code point notation and the rendered symbol
        printf "U+%04X:\U$hex\t" "$i"
        
        ((c++))
        if [[ $c -eq cols ]]; then
            printf "\n"
            c=0
        fi
    done
    printf "\n"
}

# Trap Ctrl+C to cleanly exit without showing an ugly error break
trap 'echo -e "\n\nGoodbye!"; exit 0' INT

# Infinite interactive menu loop
while true; do
    clear
    echo "=================================================="
    echo "            UNICODE BLOCK EXPLORER                "
    echo "=================================================="
    echo " 1) Mahjong Tiles"
    echo " 2) Domino Tiles"
    echo " 3) Playing Cards"
    echo " 4) Counting Rod Numerals"
    echo " 5) Mathematical Alphanumeric Symbols"
    echo " 6) Ornamental Dingbats"
    echo " 7) Transport and Map Symbols (Emojis)"
    echo " 8) Supplemental Symbols & Pictographs"
    echo " 9) Symbols for Legacy Computing"
    echo "10) Chess Symbols"
    echo "--------------------------------------------------"
    echo " c) Enter a CUSTOM Hex Range"
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
    
    # Match the choice to its corresponding Unicode range parameters
    case $choice in
        1)  print_unicode_range "Mahjong Tiles" 0x1F000 0x1F02F 4 ;;
        2)  print_unicode_range "Domino Tiles" 0x1F030 0x1F09F 4 ;;
        3)  print_unicode_range "Playing Cards" 0x1F0A0 0x1F0FF 4 ;;
        4)  print_unicode_range "Counting Rod Numerals" 0x1D360 0x1D37F 4 ;;
        5)  print_unicode_range "Mathematical Alphanumeric Symbols" 0x1D400 0x1D7FF 4 ;;
        6)  print_unicode_range "Ornamental Dingbats" 0x1F650 0x1F67F 4 ;;
        7)  print_unicode_range "Transport and Map Symbols" 0x1F680 0x1F6FF 4 ;;
        8)  print_unicode_range "Supplemental Symbols and Pictographs" 0x1F900 0x1F9FF 4 ;;
        9)  print_unicode_range "Symbols for Legacy Computing" 0x1FB00 0x1FBFF 4 ;;
        10) print_unicode_range "Chess Symbols" 0x1FA00 0x1FA6F 4 ;;
        
        [cC])
            echo ""
            echo "--- Custom Range Configuration ---"
            read -r -p "Enter START hexadecimal value (e.g., 2500 or 1F600): " start_input
            read -r -p "Enter END hexadecimal value (e.g., 257F or 1F64F): " end_input
            
            # Clean inputs by stripping common user additions like 'U+' or '0x'
            start_hex=$(echo "$start_input" | sed -E 's/^[Uu]\+//; s/^0[xX]//')
            end_hex=$(echo "$end_input" | sed -E 's/^[Uu]\+//; s/^0[xX]//')
            
            # Validate that the strings are actual hex numbers
            if [[ ! "$start_hex" =~ ^[0-9a-fA-F]+$ || ! "$end_hex" =~ ^[0-9a-fA-F]+$ ]]; then
                echo -e "\n❌ Error: Invalid hexadecimal input. Use characters 0-9 and A-F."
                read -r -p "Press Enter to return to the menu..."
                continue
            fi
            
            # Convert hex to decimal numbers for comparison and looping
            start_dec=$((16#$start_hex))
            end_dec=$((16#$end_hex))
            
            # Make sure start code point is less than or equal to end code point
            if [ $start_dec -gt $end_dec ]; then
                echo -e "\n❌ Error: Start value cannot be greater than the End value."
                read -r -p "Press Enter to return to the menu..."
                continue
            fi
            
            # Warn if range is absurdly large to protect terminal performance
            range_size=$((end_dec - start_dec))
            if [ $range_size -gt 2000 ]; then
                echo "⚠️  Warning: You are attempting to print $range_size characters."
                read -r -p "This could flood your terminal. Proceed anyway? (y/n): " confirm
                if [[ ! "$confirm" =~ ^[yY]$ ]]; then
                    continue
                fi
            fi
            
            # Run the print function on the verified custom range
            print_unicode_range "Custom User Range" "$start_dec" "$end_dec" 4
            ;;
            
        *)  
            echo -e "\nInvalid choice! Please choose a number from 1 to 10, 'c', or 'q'."
            read -r -p "Press Enter to return to the menu..."
            continue 
            ;;
    esac
    
    # Pause mechanism to let them review before clearing and returning to prompt
    echo "--------------------------------------------------"
    read -r -p "Finished printing. Press [Enter] to return to the menu..."
done

