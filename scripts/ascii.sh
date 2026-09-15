#!/bin/bash

# Loop through the printable Standard ASCII range (32 to 126)
printf "Standard ASCII Range (32 - 126)\n"
c=0
for i in {32..126}; do
    # Convert decimal value to its corresponding ASCII character
    printf "$i:\\$(printf '%03o' "$i")"
    printf "\t"
    ((c++))
    if [[ $c -eq 10 ]]; then
        printf "\n"
        c=0
    fi
done

# Print a final newline and separator
printf "\n\n Extended ASCII (CP437) \n"

# Loop through the Extended ASCII range (128 to 255)
c=0
for i in {128..255}; do
    # Convert the decimal to an octal byte string
    octal_byte=$(printf '\\%03o' "$i")
    
    # Use iconv to safely convert the CP437 byte into modern UTF-8 text
    char=$(printf "$octal_byte" | iconv -f CP437 -t UTF-8 2>/dev/null)
    
    # Print the index and the converted symbol
    printf "%d:%s\t" "$i" "$char"
    
    ((c++))
    if [[ $c -eq 10 ]]; then
        printf "\n"
        c=0
    fi
done

echo ""

