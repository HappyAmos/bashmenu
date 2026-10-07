#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: otd.sh
# DESCRIPTION: Prints a random item from on this day from today.zenquotes.io
# ==============================================================================

# Determine terminal width (with fallback) and export for subprocesses
if [[ -z "${COLUMNS:-}" || "${COLUMNS}" -le 0 ]] 2>/dev/null; then
    COLUMNS="$(tput cols 2>/dev/null || echo 80)"
fi
export COLUMNS

echo "[b]On This Day:[/b]"
if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import urllib.request, json, random, sys, os, textwrap

width = 80
try:
    cols_env = os.environ.get("COLUMNS")
    if cols_env:
        width = max(20, int(cols_env))
except Exception:
    pass

try:
    req = urllib.request.Request("https://today.zenquotes.io/api", headers={"User-Agent": "BashMenu/1.0"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and "data" in data and "Events" in data["data"]:
            events = data["data"]["Events"]
            if events:
                ev = random.choice(events)
                event_text = ev.get("text", "")
                if event_text:
                    print(textwrap.fill(event_text, width=width))
                links = [l.get("url", "") for l in ev.get("links", []) if l.get("url", "").startswith("http")]
                if len(links) > 1:
                    print(links[1])
                elif links:
                    print(links[0])
        elif isinstance(data, list) and len(data) > 1 and "q" in data[1]:
            quote_text = data[1]["q"]
            if quote_text:
                print(textwrap.fill(quote_text, width=width))
except Exception:
    sys.exit(0)
'
elif command -v curl >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    raw=$(curl -s -m 3 https://today.zenquotes.io/api 2>/dev/null)
    if [ -n "$raw" ]; then
        if command -v fold >/dev/null 2>&1; then
            echo "$raw" | jq -r 'if type == "object" and .data?.Events then .data.Events | .[(now * 1000 | floor) % length] | "\(.text)\n\([.links[]? | select(.url | startswith("http"))][1].url // "")" elif type == "array" and .[1]?.q then .[1].q else empty end' 2>/dev/null | fold -s -w "$COLUMNS" || true
        else
            echo "$raw" | jq -r 'if type == "object" and .data?.Events then .data.Events | .[(now * 1000 | floor) % length] | "\(.text)\n\([.links[]? | select(.url | startswith("http"))][1].url // "")" elif type == "array" and .[1]?.q then .[1].q else empty end' 2>/dev/null || true
        fi
    fi
fi
echo "On This Day courtesy of https://today.zenquotes.io/"


