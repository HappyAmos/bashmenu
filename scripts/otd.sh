#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: thisday.sh
# DESCRIPTION: Prints a random item from on this day from today.zenquotes.io
# ==============================================================================

echo "[b]On This Day:[/b]"
if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import urllib.request, json, random, sys
try:
    req = urllib.request.Request("https://today.zenquotes.io/api", headers={"User-Agent": "BashMenu/1.0"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and "data" in data and "Events" in data["data"]:
            events = data["data"]["Events"]
            if events:
                ev = random.choice(events)
                print(ev.get("text", ""))
                links = [l.get("url", "") for l in ev.get("links", []) if l.get("url", "").startswith("http")]
                if len(links) > 1:
                    print(links[1])
                elif links:
                    print(links[0])
        elif isinstance(data, list) and len(data) > 1 and "q" in data[1]:
            print(data[1]["q"])
except Exception:
    sys.exit(0)
'
elif command -v curl >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    curl -s -m 3 https://today.zenquotes.io/api | jq -r 'if type == "object" and .data?.Events then .data.Events | .[(now * 1000 | floor) % length] | "\(.text)\n\([.links[]? | select(.url | startswith("http"))][1].url // "")" elif type == "array" and .[1]?.q then .[1].q else empty end' 2>/dev/null || true
fi
echo "On This Day courtesy of https://today.zenquotes.io/"


