#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: rich.sh
# DESCRIPTION: Renders a Markdown file using the Python Rich library.
# Usage: rich.sh <filename>
# ==============================================================================

set -eo pipefail

ALLOW_FILE=1
TARGET_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --no-file|--no-edit|--view-only)
            ALLOW_FILE=0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--no-file] <filename>" >&2
            exit 1
            ;;
        *)
            if [ -z "$TARGET_FILE" ]; then
                TARGET_FILE="$1"
            else
                echo "Error: Unexpected argument '$1'" >&2
                exit 1
            fi
            ;;
    esac
    shift
done

# Check if filename argument is provided
if [ -z "$TARGET_FILE" ]; then
    echo "Usage: $0 [--no-file] <filename>" >&2
    exit 1
fi

# Verify the file exists
if [ ! -f "$TARGET_FILE" ]; then
    echo "Error: File '$TARGET_FILE' does not exist." >&2
    exit 1
fi

# Resolve file path portably without hardcoded paths
if command -v realpath >/dev/null 2>&1; then
    TARGET_FILE="$(realpath "$TARGET_FILE")"
elif command -v readlink >/dev/null 2>&1; then
    TARGET_FILE="$(readlink -f "$TARGET_FILE" 2>/dev/null || echo "$(cd "$(dirname "$TARGET_FILE")" && pwd)/$(basename "$TARGET_FILE")")"
else
    TARGET_FILE="$(cd "$(dirname "$TARGET_FILE")" && pwd)/$(basename "$TARGET_FILE")"
fi

# Canonical symlink resolution to determine true script directory
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect Python interpreter
PYTHON_BIN=""
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Error: Python 3 executable was not found." >&2
    exit 1
fi

# Verify Rich module is available
if ! "$PYTHON_BIN" -c "import rich" >/dev/null 2>&1; then
    echo "Error: Python Rich library is not available in '$PYTHON_BIN'." >&2
    exit 1
fi

# Force Rich to preserve ANSI color codes through pipes and generate hyperlinks
export FORCE_COLOR=1
if [ -z "$TERM" ] || [ "$TERM" = "dumb" ] || [ "$TERM" = "unknown" ]; then
    export TERM="xterm-256color"
fi
export COLORTERM="${COLORTERM:-truecolor}"

# Tell less to interpret raw ANSI color escape sequences
export LESS="-R"

# Detect terminal width when running interactively
WIDTH_ARGS=()
if [ -t 1 ]; then
    WIDTH="$(tput cols 2>/dev/null || true)"
    if [ -z "$WIDTH" ] || [ "$WIDTH" -le 0 ] 2>/dev/null; then
        WIDTH="${COLUMNS:-}"
    fi
    if [ -z "$WIDTH" ] || [ "$WIDTH" -le 0 ] 2>/dev/null; then
        WIDTH="$(stty size 2>/dev/null | awk '{print $2}')"
    fi
    if [ -n "$WIDTH" ] && [ "$WIDTH" -gt 0 ] 2>/dev/null; then
        WIDTH_ARGS=("-w" "$WIDTH")
    fi
fi

render_markdown() {
    "$PYTHON_BIN" -c '
import sys
from rich.console import Console
from rich.markdown import Heading, Markdown
from rich.containers import Lines
from rich.cells import cell_len

if hasattr(Heading, "LEVEL_ALIGN"):
    Heading.LEVEL_ALIGN["h1"] = "left"
else:
    def _custom_h1_console(self, console, options):
        text = self.text
        text.justify = "left"
        if self.tag == "h1":
            from rich import box
            from rich.panel import Panel
            yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
        else:
            if self.tag == "h2":
                from rich.text import Text
                yield Text("")
            yield text
    Heading.__rich_console__ = _custom_h1_console

_orig_lines_justify = Lines.justify
def _custom_lines_justify(self, console, width, justify="left", overflow="fold"):
    if justify == "center":
        for line in self._lines:
            has_protected_end = any(span.end >= len(line.plain) for span in line.spans) or (bool(line.plain) and line.plain[-1] in ("\xa0", "\u202f"))
            if not has_protected_end:
                line.rstrip()
            line.truncate(width, overflow=overflow)
            line.pad_left((width - cell_len(line.plain)) // 2)
            line.pad_right(width - cell_len(line.plain))
    elif justify == "right":
        for line in self._lines:
            has_protected_end = any(span.end >= len(line.plain) for span in line.spans) or (bool(line.plain) and line.plain[-1] in ("\xa0", "\u202f"))
            if not has_protected_end:
                line.rstrip()
            line.truncate(width, overflow=overflow)
            line.pad_left(width - cell_len(line.plain))
    else:
        _orig_lines_justify(self, console, width, justify=justify, overflow=overflow)
Lines.justify = _custom_lines_justify

width = None
if "-w" in sys.argv:
    w_idx = sys.argv.index("-w") + 1
    if w_idx < len(sys.argv):
        try:
            width = int(sys.argv[w_idx])
        except ValueError:
            pass

Console(force_terminal=True, width=width).print(Markdown(sys.stdin.read(), hyperlinks=True))

' "${WIDTH_ARGS[@]}"
}

# Pipe through pager.sh for interactive terminals, or fallback to less -R, $PAGER, or raw stream
if [ -t 1 ]; then
    if [ -x "${SCRIPT_DIR}/pager.sh" ]; then
        PAGER_ARGS=()
        if [ "$ALLOW_FILE" = "1" ]; then
            RELOAD_CMD="\"${SCRIPT_DIR}/rich.sh\" \"$TARGET_FILE\""
            PAGER_ARGS+=(--file="$TARGET_FILE" --reload-cmd="$RELOAD_CMD")
        else
            PAGER_ARGS+=(--no-file)
        fi
        sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
            render_markdown | \
            "${SCRIPT_DIR}/pager.sh" "${PAGER_ARGS[@]}"
    elif command -v bmpager >/dev/null 2>&1; then
        PAGER_ARGS=()
        if [ "$ALLOW_FILE" = "1" ]; then
            RELOAD_CMD="\"${SCRIPT_DIR}/rich.sh\" \"$TARGET_FILE\""
            PAGER_ARGS+=(--file="$TARGET_FILE" --reload-cmd="$RELOAD_CMD")
        else
            PAGER_ARGS+=(--no-file)
        fi
        sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
            render_markdown | \
            bmpager "${PAGER_ARGS[@]}"
    elif command -v less >/dev/null 2>&1; then
        sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
            render_markdown | less -R
    elif [ -n "$PAGER" ]; then
        sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
            render_markdown | $PAGER
    else
        sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
            render_markdown
    fi
else
    sed 's/^```[[:space:]]\+/```/' "$TARGET_FILE" | \
        render_markdown
fi

