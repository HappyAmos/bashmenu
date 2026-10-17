#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: ascii.sh
# DESCRIPTION: Prints the standard ASCII character set and the extended CP437
#              character set safely to the terminal using iconv for conversion.
# ==============================================================================

# List non-printable characters
printf "Non-printable characters (0 - 31)\n"
cat << 'EOF' | column -t -s $'\t'
Dec	Hex	Description	Dec	Hex	Description
0	00	NUL (Null character)	16	10	DLE (Data Link Escape)
1	01	SOH (Start of Header)	17	11	DC1 (Device Control 1 / XON)
2	02	STX (Start of Text)	18	12	DC2 (Device Control 2)
3	03	ETX (End of Text)	19	13	DC3 (Device Control 3 / XOFF)
4	04	EOT (End of Transmission)	20	14	DC4 (Device Control 4)
5	05	ENQ (Enquiry)	21	15	NAK (Negative Acknowledgment)
6	06	ACK (Acknowledgment)	22	16	SYN (Synchronous Idle)
7	07	BEL (Bell / Beep)	23	17	ETB (End of Trans. Block)
8	08	BS (Backspace)	24	18	CAN (Cancel)
9	09	HT (Horizontal Tab)	25	19	EM (End of Medium)
10	0A	LF (Line Feed / New Line)	26	1A	SUB (Substitute)
11	0B	VT (Vertical Tab)	27	1B	ESC (Escape)
12	0C	FF (Form Feed / New Page)	28	1C	FS (File Separator)
13	0D	CR (Carriage Return)	29	1D	GS (Group Separator)
14	0E	SO (Shift Out)	30	1E	RS (Record Separator)
15	0F	SI (Shift In)	31	1F	US (Unit Separator)
EOF

echo ""

# Loop through the printable Standard ASCII range (32 to 126)
printf "Standard ASCII Range (32 - 126)\n"
c=0
for i in {32..126}; do
    # Convert decimal value to its corresponding ASCII character
    printf "%b" "$i:\\$(printf '%03o' "$i")"
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
    
    # Use iconv or python to safely convert the CP437 byte into modern UTF-8 text
    char=""
    if command -v iconv >/dev/null 2>&1; then
        char=$(printf "%b" "$octal_byte" | iconv -f CP437 -t UTF-8 2>/dev/null || true)
    elif command -v python3 >/dev/null 2>&1; then
        char=$(python3 -c "import sys; sys.stdout.write(bytes([$i]).decode('cp437', errors='replace'))" 2>/dev/null || true)
    fi
    
    # Print the index and the converted symbol
    printf "%d:%s\t" "$i" "$char"
    
    ((c++))
    if [[ $c -eq 10 ]]; then
        printf "\n"
        c=0
    fi
done

echo ""

