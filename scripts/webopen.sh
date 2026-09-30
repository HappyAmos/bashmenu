#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: webopen.sh
# DESCRIPTION: Cross-platform web browser launcher wrapper. Opens a specified
#              URL, file, or the default system web browser.
# Usage: webopen.sh [url_or_file]
# ==============================================================================

set -euo pipefail

TARGET="${1:-}"

# Format target path or URL if provided
if [ -n "$TARGET" ]; then
    if [ -f "$TARGET" ] || [ -d "$TARGET" ]; then
        # Local file or directory path resolution
        if command -v realpath >/dev/null 2>&1; then
            ABS_PATH="$(realpath "$TARGET")"
        elif command -v readlink >/dev/null 2>&1; then
            ABS_PATH="$(readlink -f "$TARGET" 2>/dev/null || echo "$TARGET")"
        else
            ABS_PATH="$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")"
        fi
        TARGET="file://${ABS_PATH}"
    elif [[ ! "$TARGET" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*:// ]] && [[ "$TARGET" != "about:"* ]]; then
        # Standard web domain without scheme prefix (e.g., example.com)
        TARGET="https://${TARGET}"
    fi
fi

# Operating system / environment detection
IS_TERMUX=false
IS_WSL=false
IS_MAC=false

if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"/com.termux/"* ]]; then
    IS_TERMUX=true
elif grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
elif [ "$(uname -s)" = "Darwin" ]; then
    IS_MAC=true
fi

# Cross-platform browser dispatch logic
if [ "$IS_TERMUX" = true ]; then
    if command -v termux-open-url >/dev/null 2>&1; then
        exec termux-open-url "${TARGET:-about:blank}"
    elif command -v termux-open >/dev/null 2>&1; then
        exec termux-open "${TARGET:-about:blank}"
    else
        echo "Error: termux-open-url or termux-open not found." >&2
        exit 1
    fi
elif [ "$IS_MAC" = true ]; then
    if [ -n "$TARGET" ]; then
        exec open "$TARGET"
    else
        exec open -a "Safari" 2>/dev/null || exec open "about:blank"
    fi
elif [ "$IS_WSL" = true ]; then
    if command -v wslview >/dev/null 2>&1; then
        exec wslview "${TARGET:-about:blank}"
    elif command -v powershell.exe >/dev/null 2>&1; then
        exec powershell.exe -c "Start-Process '${TARGET:-about:blank}'"
    elif command -v cmd.exe >/dev/null 2>&1; then
        exec cmd.exe /c start "" "${TARGET:-about:blank}"
    else
        echo "Error: WSL browser launcher (wslview/powershell.exe/cmd.exe) not found." >&2
        exit 1
    fi
else
    # Linux / Unix desktop environment dispatch
    if [ -n "${BROWSER:-}" ]; then
        exec "$BROWSER" "${TARGET:-about:blank}"
    elif command -v xdg-open >/dev/null 2>&1; then
        exec xdg-open "${TARGET:-about:blank}"
    elif command -v sensible-browser >/dev/null 2>&1; then
        exec sensible-browser "${TARGET:-about:blank}"
    elif command -v x-www-browser >/dev/null 2>&1; then
        exec x-www-browser "${TARGET:-about:blank}"
    elif command -v firefox >/dev/null 2>&1; then
        exec firefox "${TARGET:-about:blank}"
    elif command -v chromium >/dev/null 2>&1; then
        exec chromium "${TARGET:-about:blank}"
    elif command -v chromium-browser >/dev/null 2>&1; then
        exec chromium-browser "${TARGET:-about:blank}"
    elif command -v google-chrome >/dev/null 2>&1; then
        exec google-chrome "${TARGET:-about:blank}"
    else
        echo "Error: Compatible web browser or xdg-open launcher not found." >&2
        exit 1
    fi
fi
