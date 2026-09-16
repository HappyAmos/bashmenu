#!/usr/bin/env bash

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Check if search term was provided
if [ -z "$1" ]; then
    echo "Usage: $0 [option] <search-term>"
    echo "Options:"
    echo "-h | --help"
    exit 1
fi

# Show help if they ask for it
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 [option] <search-term>"
    echo "Options:"
    echo "-h | --help"
    exit
fi

# URL to a reliable, clean JSON list of emojis
NERD_URL="http://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/glyphnames.json"
EMOJI_URL="https://raw.githubusercontent.com/muan/unicode-emoji-json/refs/heads/main/data-by-emoji.json"
CACHE_DIR="$HOME/.cache/bashmenu"
NERD_CACHE="$HOME/.cache/bashmenu/glyphs.json"
EMOJI_CACHE="$HOME/.cache/bashmenu/emoji_list.json"

# Create cache directory if it doesn't exist
mkdir -p "$(dirname "$CACHE_DIR")" &>/dev/null

# Download and cache the nerd list if not already present
if [ ! -f "$NERD_CACHE" ]; then
    echo "Fetching nerd list..."
    curl -sSL "$NERD_URL" -o "$NERD_CACHE"
    # Make sure that the file is greater than zero bytes
    if [ ! -s "$NERD_CACHE" ]; then
        echo "Failed to download $NERD_CACHE from $NERD_URL"
        rm "$NERD_CACHE"
        exit 1
    fi
fi

# Download and cache the emoji list if not already present
if [ ! -f "$EMOJI_CACHE" ]; then
    echo "Fetching emoji database..."
    curl -sSL "$EMOJI_URL" -o "$EMOJI_CACHE"
    # Make sure that the file is greater than zero bytes
    if [ ! -s "$EMOJI_CACHE" ]; then
        echo "Failed to download $EMOJI_CACHE from $EMOJI_URL"
        rm "$EMOJI_CACHE"
        exit 1
    fi
fi

SEARCH_TERM=$(echo "$1" | tr '[:upper:]' '[:lower:]')

echo "Searching for ['$1']:"
echo "-------------------------"

# Nerd Fonts:
# SCHEMA: "cod-account":{"char":"","code":"eb99"},
RESULTS_NERD=$(
    jq -r --arg query "$SEARCH_TERM" '
        to_entries[] |
        select(.key | ascii_downcase | contains($query)) |
        "\(.value.char) - [\(.value.code)] - (\(.key))"
    ' "$NERD_CACHE"
)
if [ -n "$RESULTS_NERD" ]; then
    echo "$RESULTS_NERD"
    COUNT_NERD=$(echo "$RESULTS_NERD" | wc -l)
else
    COUNT_NERD=0
fi
echo "Found $COUNT_NERD nerd-fonts."

echo ""

echo "-------------------------"
# Emoji:
# SCHEMA
#   "🏴󠁧󠁢󠁷󠁬󠁳󠁿": {
#     "name": "flag Wales",
#     "slug": "flag_wales",
#     "group": "Flags",
#     "emoji_version": "5.0",
#     "unicode_version": "5.0",
#     "skin_tone_support": false
# Parse JSON using to_entries to access the emoji character (key) and its data (value)
RESULTS_EMOJI=$(
    jq -r --arg query "$SEARCH_TERM" '
      to_entries[] | 
      select(
        (.value.name | ascii_downcase | contains($query)) or 
        (.value.slug | ascii_downcase | contains($query))
      ) | 
      "\(.key) - [\(.value.name)] - (:\(.value.slug):)"
    ' "$EMOJI_CACHE"
)
if [ -n "$RESULTS_EMOJI" ]; then
    echo "$RESULTS_EMOJI"
    COUNT_EMOJI=$(echo "$RESULTS_EMOJI" | wc -l)
else
    COUNT_EMOJI=0
fi
echo "Found $COUNT_EMOJI emoji-glyphs."
