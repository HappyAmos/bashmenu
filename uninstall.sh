#!/bin/sh
# ==============================================================================
# BashMenu Uninstallation Script
# https://github.com/HappyAmos/bashmenu
#
# Usage:
#   uninstall.sh [-y|--yes]
#   or:
#   sh -c "$(wget -qO- https://raw.githubusercontent.com/HappyAmos/bashmenu/main/uninstall.sh 2>/dev/null || curl -fsSL https://raw.githubusercontent.com/HappyAmos/bashmenu/main/uninstall.sh)"
# ==============================================================================

set -e

AUTO_CONFIRM=false
STEP2=false
TARGET_DIR=""

# Parse flags
for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            AUTO_CONFIRM=true
            ;;
        --step2)
            STEP2=true
            ;;
        *)
            if [ "$STEP2" = "true" ] && [ -z "$TARGET_DIR" ]; then
                TARGET_DIR="$arg"
            fi
            ;;
    esac
done

# Resolve current script location
CURRENT_SCRIPT_DIR="$(cd -P "$(dirname "$0")" 2>/dev/null && pwd)"

# Resolve installation directory
if [ -n "$TARGET_DIR" ]; then
    INSTALL_DIR="$TARGET_DIR"
elif [ -n "${BASHMENU_DIR:-}" ]; then
    INSTALL_DIR="$BASHMENU_DIR"
elif [ -f "$CURRENT_SCRIPT_DIR/bashmenu.sh" ]; then
    INSTALL_DIR="$CURRENT_SCRIPT_DIR"
elif [ -d "$HOME/.local/share/bashmenu" ]; then
    INSTALL_DIR="$HOME/.local/share/bashmenu"
elif [ -d "$HOME/.bashmenu" ]; then
    INSTALL_DIR="$HOME/.bashmenu"
else
    INSTALL_DIR=""
fi

# ------------------------------------------------------------------------------
# Self-relocation: If running from inside the directory to be deleted, copy to /tmp
# ------------------------------------------------------------------------------
if [ "$STEP2" != "true" ] && [ -n "$INSTALL_DIR" ] && [ "$CURRENT_SCRIPT_DIR" = "$INSTALL_DIR" ]; then
    TMP_UNINSTALL="/tmp/bashmenu_uninstall_$$.sh"
    cp "$0" "$TMP_UNINSTALL"
    chmod +x "$TMP_UNINSTALL"
    if [ "$AUTO_CONFIRM" = "true" ]; then
        exec "$TMP_UNINSTALL" --step2 "$INSTALL_DIR" -y
    else
        exec "$TMP_UNINSTALL" --step2 "$INSTALL_DIR"
    fi
fi

# Cleanup temp script if running in step 2
if [ "$STEP2" = "true" ]; then
    # shellcheck disable=SC2064
    trap "rm -f '$0' 2>/dev/null || true" EXIT INT TERM
fi

echo "==================================================================="
echo "                BashMenu Uninstallation Script                     "
echo "==================================================================="

if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
    echo "Found BashMenu installation directory at: $INSTALL_DIR"
else
    echo "Notice: No installation directory found to delete (or already removed)."
fi

# Confirmation prompt unless -y / --yes is specified
if [ "$AUTO_CONFIRM" != "true" ]; then
    printf "Are you sure you want to completely remove BashMenu, shortcuts, and cache? [y/N]: "
    read -r REPLY
    case "$REPLY" in
        [Yy]*) ;;
        *)
            echo "Uninstallation cancelled."
            exit 0
            ;;
    esac
fi

echo "==> Removing installed symlinks and shortcuts..."
CANDIDATE_BIN_DIRS="$HOME/.local/bin /usr/local/bin ${PREFIX:-}/bin"
for dir in $CANDIDATE_BIN_DIRS; do
    [ -d "$dir" ] || continue
    for link_name in "bm" "bashmenu" "cheat"; do
        target_path="$dir/$link_name"
        if [ -L "$target_path" ] || [ -f "$target_path" ]; then
            # Verify if it points to bashmenu or remove it
            rm -f "$target_path" 2>/dev/null || sudo rm -f "$target_path" 2>/dev/null || true
            echo "  [-] Removed shortcut: $target_path"
        fi
    done
done

echo "==> Removing installed man pages..."
CANDIDATE_MAN_DIRS="/usr/local/share/man/man1 /usr/share/man/man1 $HOME/.local/share/man/man1 ${PREFIX:-}/share/man/man1"
for mdir in $CANDIDATE_MAN_DIRS; do
    [ -d "$mdir" ] || continue
    if [ -f "$mdir/bashmenu.1" ] || [ -L "$mdir/bashmenu.1" ]; then
        rm -f "$mdir/bashmenu.1" 2>/dev/null || sudo rm -f "$mdir/bashmenu.1" 2>/dev/null || true
        echo "  [-] Removed man page: $mdir/bashmenu.1"
    fi
done

echo "==> Removing cache directory..."
DEFAULT_CACHE="$HOME/.cache/bashmenu"
if [ -d "$DEFAULT_CACHE" ]; then
    rm -rf "$DEFAULT_CACHE"
    echo "  [-] Removed cache directory: $DEFAULT_CACHE"
fi

if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
    echo "==> Removing installation directory: $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    echo "  [-] Removed installation files: $INSTALL_DIR"
fi

echo ""
echo "==================================================================="
echo "  [✓] BashMenu has been completely uninstalled from this system.  "
echo "==================================================================="
