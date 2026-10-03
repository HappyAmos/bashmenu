#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: glyphs.sh
# DESCRIPTION: Searches for Nerd Fonts and Emoji glyphs using online JSON
#              databases and caches them locally for faster subsequent lookups.
# ==============================================================================

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
CACHE_DIR="${CACHE_DIR:-"$HOME/.cache/bashmenu"}"
NERD_CACHE="$CACHE_DIR/glyphs.json"
EMOJI_CACHE="$CACHE_DIR/emoji_list.json"

# Create cache directory if it doesn't exist
mkdir -p "$CACHE_DIR" &>/dev/null

# Helper function to download files using curl, wget, or python3
download_file() {
    local url="$1"
    local dest="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -sSL "$url" -o "$dest"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$dest" "$url"
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "import urllib.request, sys; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$url" "$dest" 2>/dev/null || true
    fi
}

# Helper function to query glyphs using jq or python3
query_glyphs() {
    local mode="$1"
    local term="$2"
    local cache="$3"
    if command -v jq >/dev/null 2>&1; then
        if [ "$mode" = "nerd" ]; then
            jq -r --arg query "$term" '
                to_entries[] |
                select(.key | ascii_downcase | contains($query)) |
                "\(.value.char) - [\(.value.code)] - (\(.key))"
            ' "$cache"
        else
            jq -r --arg query "$term" '
              to_entries[] | 
              select(
                (.value.name | ascii_downcase | contains($query)) or 
                (.value.slug | ascii_downcase | contains($query))
              ) | 
              "\(.key) - [\(.value.name)] - (:\(.value.slug):)"
            ' "$cache"
        fi
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c '
import json, sys
mode = sys.argv[1]
term = sys.argv[2].lower()
cache = sys.argv[3]
try:
    with open(cache, "r", encoding="utf-8") as f:
        data = json.load(f)
    if mode == "nerd":
        for k, v in data.items():
            if term in k.lower():
                print(f"{v.get(\"char\", \"\")} - [{v.get(\"code\", \"\")}] - ({k})")
    elif mode == "emoji":
        for k, v in data.items():
            name = (v.get("name") or "").lower()
            slug = (v.get("slug") or "").lower()
            if term in name or term in slug:
                print(f"{k} - [{v.get(\"name\", \"\")}] - (:{v.get(\"slug\", \"\"):})")
except Exception:
    pass
' "$mode" "$term" "$cache"
    fi
}

# Download and cache the nerd list if not already present
if [ ! -f "$NERD_CACHE" ]; then
    echo "Fetching nerd list..."
    download_file "$NERD_URL" "$NERD_CACHE"
    # Make sure that the file is greater than zero bytes
    if [ ! -s "$NERD_CACHE" ]; then
        echo "Failed to download $NERD_CACHE from $NERD_URL"
        rm -f "$NERD_CACHE"
        exit 1
    fi
fi

# Download and cache the emoji list if not already present
if [ ! -f "$EMOJI_CACHE" ]; then
    echo "Fetching emoji database..."
    download_file "$EMOJI_URL" "$EMOJI_CACHE"
    # Make sure that the file is greater than zero bytes
    if [ ! -s "$EMOJI_CACHE" ]; then
        echo "Failed to download $EMOJI_CACHE from $EMOJI_URL"
        rm -f "$EMOJI_CACHE"
        exit 1
    fi
fi

SEARCH_TERM=$(echo "$1" | tr '[:upper:]' '[:lower:]')

echo "Searching for ['$1']:"
echo "-------------------------"

# Nerd Fonts:
RESULTS_NERD="$(query_glyphs "nerd" "$SEARCH_TERM" "$NERD_CACHE")"
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
RESULTS_EMOJI="$(query_glyphs "emoji" "$SEARCH_TERM" "$EMOJI_CACHE")"
if [ -n "$RESULTS_EMOJI" ]; then
    echo "$RESULTS_EMOJI"
    COUNT_EMOJI=$(echo "$RESULTS_EMOJI" | wc -l)
else
    COUNT_EMOJI=0
fi
echo "Found $COUNT_EMOJI emoji-glyphs."

