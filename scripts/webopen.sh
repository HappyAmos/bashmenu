#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: webopen.sh
# DESCRIPTION: Cross-platform web browser launcher wrapper. Opens a specified
#              URL, file, or the default configured web browser (GUI or CLI)
#              with flags to force GUI (--gui) or console/terminal (--tty/tty).
# Usage: webopen.sh [--gui|--tty|tty] [url_or_file]
# ==============================================================================

set -uo pipefail

MODE="auto"
TARGET=""

# Parse flags and arguments
for arg in "$@"; do
    case "$arg" in
        --gui|-g)
            MODE="gui"
            ;;
        --tty|-t|--cli|--console|tty)
            MODE="tty"
            ;;
        --auto|-a)
            MODE="auto"
            ;;
        --help|-h)
            echo "Usage: $(basename "$0") [--gui|--tty|tty] [url_or_file]"
            echo ""
            echo "Options:"
            echo "  --gui, -g                 Force launching a graphical (GUI) browser"
            echo "  --tty, -t, tty, --cli     Force launching a console/terminal (CLI) browser"
            echo "  --auto, -a                Auto-detect browser based on environment (default)"
            echo "  --help, -h                Show this help message"
            exit 0
            ;;
        *)
            if [ -z "$TARGET" ]; then
                TARGET="$arg"
            fi
            ;;
    esac
done

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

# 1. Check configured browser in bashmenu.yml (if set)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASHMENU_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${BASHMENU_DIR}/bashmenu.yml"
CFG_BROWSER=""

if [ -f "$CONFIG_FILE" ]; then
    CFG_BROWSER="$(python3 -c "
import yaml
try:
    with open('$CONFIG_FILE') as f:
        d = yaml.safe_load(f) or {}
    val = d.get('settings', {}).get('browser', '') or ''
    print(val.strip())
except Exception:
    pass
" 2>/dev/null || true)"
fi

# Helper to attempt launching a browser binary
try_launch() {
    local bin="$1"
    bin="${bin/#\~/$HOME}"
    if ! command -v "$bin" >/dev/null 2>&1 && [ ! -x "$bin" ]; then
        return 1
    fi
    if [ -n "$TARGET" ]; then
        "$bin" "$TARGET" 2>/dev/null && exit 0 || return 1
    else
        "$bin" 2>/dev/null && exit 0 || return 1
    fi
}

# Known Terminal / Console browser candidates in priority order
KNOWN_TTY_BROWSERS=(
    "$HOME/github/brow6el/build/brow6el"
    "$HOME/.local/bin/brow6el"
    brow6el
    links
    links2
    lynx
    w3m
    elinks
    carbonyl
    edbrowse
)

# Known GUI browser candidates in priority order
KNOWN_GUI_BROWSERS=(
    google-chrome
    google-chrome-stable
    firefox
    firefox-esr
    chromium
    chromium-browser
    brave-browser
    microsoft-edge
    opera
    vivaldi
    midori
    epiphany
    falkon
)

# Function: Launch in TTY / Console mode
launch_tty_mode() {
    # Check user overrides if they point to a terminal browser
    if [ -n "$CFG_BROWSER" ] && [ "$CFG_BROWSER" != "auto" ]; then
        try_launch "$CFG_BROWSER" || true
    fi
    if [ -n "${BROWSER:-}" ] && [ "$BROWSER" != "auto" ]; then
        try_launch "$BROWSER" || true
    fi

    # Check system default CLI alternative (Debian/Ubuntu/etc.)
    if command -v www-browser >/dev/null 2>&1; then
        try_launch www-browser || true
    fi

    # Check known terminal browser candidates
    for tb in "${KNOWN_TTY_BROWSERS[@]}"; do
        try_launch "$tb" || true
    done

    echo "Error: No terminal/console web browser could be found or launched." >&2
    echo "Please install a terminal browser (e.g., brow6el, links, lynx, w3m, elinks)." >&2
    exit 1
}

# Function: Launch in GUI mode
launch_gui_mode() {
    # Check user overrides
    if [ -n "$CFG_BROWSER" ] && [ "$CFG_BROWSER" != "auto" ]; then
        try_launch "$CFG_BROWSER" || true
    fi
    if [ -n "${BROWSER:-}" ] && [ "$BROWSER" != "auto" ]; then
        try_launch "$BROWSER" || true
    fi

    # Check macOS
    if [ "$(uname -s)" = "Darwin" ]; then
        if [ -n "$TARGET" ]; then
            open "$TARGET" 2>/dev/null && exit 0 || true
        else
            open -a "Safari" 2>/dev/null && exit 0 || true
            open "https://duckduckgo.com" 2>/dev/null && exit 0 || true
        fi
    fi

    # Check WSL
    if grep -qi microsoft /proc/version 2>/dev/null; then
        local fallback="${TARGET:-https://duckduckgo.com}"
        if command -v wslview >/dev/null 2>&1; then
            wslview "$fallback" 2>/dev/null && exit 0 || true
        fi
        if command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "Start-Process '$fallback'" 2>/dev/null && exit 0 || true
        fi
        if command -v cmd.exe >/dev/null 2>&1; then
            cmd.exe /c start "" "$fallback" 2>/dev/null && exit 0 || true
        fi
    fi

    # Check Windows (Git Bash / MSYS2)
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            local fallback="${TARGET:-https://duckduckgo.com}"
            if command -v start >/dev/null 2>&1; then
                start "" "$fallback" 2>/dev/null && exit 0 || true
            elif command -v cmd.exe >/dev/null 2>&1; then
                cmd.exe /c start "" "$fallback" 2>/dev/null && exit 0 || true
            fi
            ;;
    esac

    # Check Android / Termux
    if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"/com.termux/"* ]]; then
        local fallback="${TARGET:-https://duckduckgo.com}"
        if command -v termux-open-url >/dev/null 2>&1; then
            termux-open-url "$fallback" 2>/dev/null && exit 0 || true
        fi
        if command -v termux-open >/dev/null 2>&1; then
            termux-open "$fallback" 2>/dev/null && exit 0 || true
        fi
    fi

    # Linux / BSD with Graphical Session
    local has_display=false
    if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
        has_display=true
    fi

    if [ "$has_display" = true ]; then
        # XFCE desktop launcher
        if command -v exo-open >/dev/null 2>&1; then
            if [ -n "$TARGET" ]; then
                exo-open "$TARGET" 2>/dev/null && exit 0 || true
            else
                exo-open --launch WebBrowser 2>/dev/null && exit 0 || true
            fi
        fi

        # System default GUI browser alternative (Debian/Ubuntu/Fedora/openSUSE)
        if command -v x-www-browser >/dev/null 2>&1; then
            try_launch x-www-browser || true
        fi

        # Sensible-browser dispatcher
        if command -v sensible-browser >/dev/null 2>&1; then
            try_launch sensible-browser || true
        fi

        # Desktop URL openers
        if [ -n "$TARGET" ]; then
            if command -v gio >/dev/null 2>&1; then
                gio open "$TARGET" 2>/dev/null && exit 0 || true
            fi
            if command -v xdg-open >/dev/null 2>&1; then
                xdg-open "$TARGET" 2>/dev/null && exit 0 || true
            fi
        else
            if command -v gio >/dev/null 2>&1; then
                gio open "https://duckduckgo.com" 2>/dev/null && exit 0 || true
            fi
            if command -v xdg-open >/dev/null 2>&1; then
                xdg-open "https://duckduckgo.com" 2>/dev/null && exit 0 || true
            fi
        fi

        # Known GUI browser binaries
        for b in "${KNOWN_GUI_BROWSERS[@]}"; do
            try_launch "$b" || true
        done
    fi

    echo "Error: No graphical (GUI) web browser could be found or launched." >&2
    echo "Make sure DISPLAY/WAYLAND_DISPLAY is active, or install a GUI browser (e.g. google-chrome, firefox)." >&2
    exit 1
}

# Dispatch based on selected mode
case "$MODE" in
    gui)
        launch_gui_mode
        ;;
    tty)
        launch_tty_mode
        ;;
    auto)
        # 1. Check user overrides first
        if [ -n "$CFG_BROWSER" ] && [ "$CFG_BROWSER" != "auto" ]; then
            try_launch "$CFG_BROWSER" || true
        fi
        if [ -n "${BROWSER:-}" ] && [ "$BROWSER" != "auto" ]; then
            try_launch "$BROWSER" || true
        fi

        # 2. Check if a graphical display is available
        if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ] || [ "$(uname -s)" = "Darwin" ] || grep -qi microsoft /proc/version 2>/dev/null; then
            # Attempt GUI launch without exiting on failure (to permit TTY fallback)
            ( launch_gui_mode ) 2>/dev/null && exit 0 || true
        fi

        # 3. Fallback to terminal/console mode
        launch_tty_mode
        ;;
esac
