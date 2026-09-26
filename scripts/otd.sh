#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: thisday.sh
# DESCRIPTION: Prints a random item from on this day from today.zenquotes.io
# ==============================================================================

echo "[b]On This Day:[/b]"
curl -s https://today.zenquotes.io/api | jq -r 'if type == "object" and .data?.Events then .data.Events | .[(now * 1000 | floor) % length] | "\(.text)\n\([.links[]? | select(.url | startswith("http"))][1].url // "")" elif type == "array" and .[1]?.q then .[1].q else empty end'
echo "On This Day courtesy of https://today.zenquotes.io/"

