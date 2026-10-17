#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: pager.sh
# DESCRIPTION: Interactive full-screen text pager for Unix-like systems.
#              Accepts piped stdin or file arguments, spools the text to a
#              temporary file, and renders one windowful at a time on the
#              alternate screen buffer with a command bar on the bottom row.
#              ANSI color sequences in the input are preserved.
# USAGE:       command | pager.sh [options]
#              pager.sh [options] <file> [file...]
# OPTIONS:     -h | --help        Show usage and exit.
#              -V | --version     Print version and exit.
#              +N                 Open with line N at the top of the window.
#              +/PATTERN          Open at the first line matching PATTERN.
#              -c | --no-color    Strip all ANSI escape sequences on display.
#              --no-help          Hide the shortcut hints in the command bar.
#              --max-lines=N      Cap stored input at N lines (default 1000000).
# REQUIREMENTS: bash 3.2+, stty, tput, sed, awk, wc, cat. No Python needed.
# ==============================================================================

set -u

PAGER_VERSION="1.0.0"

# Literal control bytes used throughout the renderer and key parser.
ESC=$'\033'
READ_TIMEOUT="0.05"

# Tunables and state. Every global is declared here so the render loop stays
# free of hidden allocations.
MAX_LINES=1000000
STRIP_COLORS=0
SHOW_HELP=1
ALLOW_FILE=1
HAVE_FILES=0
START_LINE=""
START_PATTERN=""
SPOOL=""
STTY_ORIG=""
TERM_SETUP=0
NEED_RESIZE=0
TRUNCATED=0
TOTAL=0
TOP_LINE=1
PAGE_ROWS=23
ROWS=24
COLS=80
LAST_SHOWN=0
DONE=0
KEY=""
MESSAGE=""
BAR_LINE=""
HINTS=""
FILES=()
ORIGINAL_FILE=""
RELOAD_CMD=""
LAST_SEARCH=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect Python interpreter (virtualenv, project .venv, or system)
PYTHON_BIN=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python3" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python3"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
fi

# ------------------------------------------------------------------ utilities

die() {
    # Print a fatal message on stderr and terminate with a non-zero status.
    printf '%s: %s\n' "${0##*/}" "$*" >&2
    exit 2
}

usage() {
    # Emit the help screen. Wrapped for an 80 column terminal.
    cat <<EOF
Usage: command | ${0##*/} [options]
       ${0##*/} [options] <file> [file...]

Interactive pager. Text is read from stdin or from the named files, then
displayed one screenful at a time. Press SPACE for the next page, b for
the previous page, arrow keys (or j/k) for single lines, and q to quit.

Options:
  -h, --help        Show this help and exit.
  -V, --version     Print the version and exit.
  +N                Start with line N at the top of the window.
  +/PATTERN         Start at the first line containing PATTERN.
  -c, --no-color    Discard ANSI escape sequences instead of rendering them.
  --no-help         Omit the shortcut hints from the command bar.
  --no-file         Do not show filename badge or allow editing current file.
  --max-lines=N     Store at most N input lines (default ${MAX_LINES}).
  --file=PATH       Associated file path to open when editing piped streams.
  --reload-cmd=CMD  Command to refresh spool after editing piped streams.

Keys:
  DOWN j            Next line            UP k            Previous line
  SPACE f PgDn      Next page            b PgUp          Previous page
  Ctrl-D            Half page down       Ctrl-U          Half page up
  g Home            Jump to TOP          G End           Jump to BOT
  /                 Search forward       n / N           Next / prev match
  l o               Follow / open link   e               Open in editor
  h ? F1            Help manual modal    q Q Ctrl-C Esc  Quit
EOF
}

tty_usable() {
    # Verify that a controlling terminal exists and reports its geometry,
    # which is required for raw mode and cursor addressing.
    [ -c /dev/tty ] || return 1
    stty -g < /dev/tty >/dev/null 2>&1
}

cleanup() {
    # Restore the terminal and remove the spool. Safe to call twice; wired
    # to EXIT so Ctrl-C and SIGTERM leave a sane screen behind.
    local status=$?
    trap 0 2>/dev/null
    if [ "${TERM_SETUP}" = "1" ]; then
        TERM_SETUP=0
        printf '%s' "${ESC}[0m"
        printf '%s' "${ESC}[?7h"
        tput rmcup 2>/dev/null || printf '%s' "${ESC}[?1049l"
        tput cnorm 2>/dev/null || printf '%s' "${ESC}[?25h"
        stty "${STTY_ORIG}" < /dev/tty 2>/dev/null
        printf '\n'
    fi
    [ -n "${SPOOL}" ] && rm -f "${SPOOL}" 2>/dev/null
    exit "${status}"
}

# ---------------------------------------------------------------------- input

load_input() {
    # Copy the incoming text into the temporary spool. awk normalises the
    # final newline and enforces MAX_LINES so an endless producer such as
    # `yes | pager.sh` cannot exhaust the filesystem.
    local status=0
    if [ "${HAVE_FILES}" -ge 1 ]; then
        awk -v lim="${MAX_LINES}" '
            NR <= lim { print }
            END { if (NR > lim) exit 99 }
        ' "${FILES[@]}" > "${SPOOL}" || status=$?
    else
        awk -v lim="${MAX_LINES}" '
            NR <= lim { print }
            END { if (NR > lim) exit 99 }
        ' > "${SPOOL}" || status=$?
    fi
    [ "${status}" = "99" ] && TRUNCATED=1
    return 0
}

resolve_start() {
    # Translate the +N and +/PATTERN startup requests into TOP_LINE.
    local hit=""
    if [ -n "${START_LINE}" ]; then
        case "${START_LINE}" in
            *[!0-9]*) die "invalid line number: +${START_LINE}" ;;
        esac
        TOP_LINE="${START_LINE}"
    elif [ -n "${START_PATTERN}" ]; then
        hit="$(grep -m1 -Fn -- "${START_PATTERN}" "${SPOOL}" 2>/dev/null)"
        if [ -z "${hit}" ]; then
            MESSAGE="pattern not found: ${START_PATTERN}"
        else
            TOP_LINE="${hit%%:*}"
        fi
    fi
}

# -------------------------------------------------------------------- terminal

term_setup() {
    # Enter the alternate screen, hide the cursor, disable autowrap, and switch
    # the tty into raw mode with a 100ms read timeout so idle polling stays responsive.
    [ -z "${STTY_ORIG}" ] && { STTY_ORIG="$(stty -g < /dev/tty 2>/dev/null)" || die "cannot control /dev/tty"; }
    trap 'cleanup' EXIT INT TERM HUP
    trap 'NEED_RESIZE=1' WINCH
    TERM_SETUP=1
    tput smcup 2>/dev/null || printf '%s' "${ESC}[?1049h"
    tput civis 2>/dev/null || printf '%s' "${ESC}[?25l"
    printf '%s' "${ESC}[?7l"
    stty -icanon -isig min 0 time 1 < /dev/tty
}

query_size() {
    # Refresh ROWS, COLS and PAGE_ROWS from the terminal so resizes take
    # effect on the next frame. Falls back to tput, then to the environment.
    local size=""
    size="$(stty size < /dev/tty 2>/dev/null)"
    if [ -n "${size}" ] && [ "${size}" != "0 0" ]; then
        ROWS="${size% *}"
        COLS="${size#* }"
    else
        ROWS="$(tput lines 2>/dev/null || printf '%s' "${LINES:-24}")"
        COLS="$(tput cols 2>/dev/null || printf '%s' "${COLUMNS:-80}")"
    fi
    case "${ROWS}${COLS}" in
        *[!0-9]*) ROWS="${LINES:-24}"; COLS="${COLUMNS:-80}" ;;
    esac
    [ "${ROWS}" -lt 3 ] && ROWS=3
    [ "${COLS}" -lt 20 ] && COLS=20
    PAGE_ROWS=$(( ROWS - 1 ))
}

clamp_top() {
    # Keep the first visible line inside the file bounds.
    # The bottom-most item can scroll to the very top row (TOP_LINE = TOTAL).
    local max="${TOTAL}"
    [ "${max}" -lt 1 ] && max=1
    [ "${TOP_LINE}" -lt 1 ] && TOP_LINE=1
    [ "${TOP_LINE}" -gt "${max}" ] && TOP_LINE="${max}"
    return 0
}

# -------------------------------------------------------------------- renderer

build_bar() {
    # Compose the bottom command bar: position label and line range on the
    # left, centered badge (filename or <stdin>), message or shortcut hints
    # flush right, padded to exactly COLS.
    local label="" pct=0 left="" badge="" fname="" extra="" right=""
    local pad_left=0 pad_right=0 pad_left_str="" pad_right_str=""
    local center_start=0 center_end=0 avail_right=0 prefix="" pad=0 pad_str=""

    if [ "${TOTAL}" -eq 0 ]; then
        label="EMPTY"
    elif [ "${TOP_LINE}" -le 1 ]; then
        label="TOP"
    elif [ "${TOP_LINE}" -ge "${TOTAL}" ]; then
        label="BOT"
    else
        pct=$(( (TOP_LINE * 100 + TOTAL / 2) / TOTAL ))
        [ "${pct}" -gt 100 ] && pct=100
        printf -v label '%3d%%' "${pct}"
    fi

    left="${label}"
    if [ "${TOTAL}" -gt 0 ]; then
        left="${label}  ${TOP_LINE}-${LAST_SHOWN}/${TOTAL}"
    fi

    # Determine badge label: [ filename.ext ] or [ <stdin> ]
    if [ "${ALLOW_FILE}" = "1" ]; then
        if [ "${HAVE_FILES}" -ge 1 ]; then
            fname="${FILES[0]##*/}"
            if [ "${HAVE_FILES}" -gt 1 ]; then
                extra=" (+$((HAVE_FILES - 1)))"
            fi
        elif [ -n "${ORIGINAL_FILE}" ]; then
            fname="${ORIGINAL_FILE##*/}"
        fi

        if [ -n "${fname}" ]; then
            local max_fname=28
            [ "${COLS}" -lt 80 ] && max_fname=20
            [ "${COLS}" -lt 60 ] && max_fname=14
            [ "${COLS}" -lt 40 ] && max_fname=8
            if [ "${#fname}" -gt "${max_fname}" ]; then
                fname="${fname:0:$((max_fname - 3))}..."
            fi
            badge="[ ${fname}${extra} ]"
        else
            badge="[ <stdin> ]"
        fi
        center_start=$(( (COLS - ${#badge}) / 2 ))
        center_end=$(( center_start + ${#badge} ))
        avail_right=$(( COLS - center_end - 1 ))
    else
        badge=""
        center_start=0
        center_end=0
        avail_right=$(( COLS - ${#left} - 2 ))
        [ "${avail_right}" -lt 0 ] && avail_right=0
    fi

    if [ -n "${MESSAGE}" ]; then
        right="${MESSAGE}"
        if [ "${#right}" -gt "${avail_right}" ] && [ "${avail_right}" -gt 4 ]; then
            right="${right:0:$((avail_right - 3))}..."
        fi
    elif [ "${SHOW_HELP}" = "1" ]; then
        if [ "${avail_right}" -ge 62 ]; then
            right="${HINTS}"
        elif [ "${avail_right}" -ge 42 ]; then
            right="SPACE pgDn  b pgUp  / find  q quit"
        elif [ "${avail_right}" -ge 24 ]; then
            right="SPACE pgDn  / find  q"
        elif [ "${avail_right}" -ge 14 ]; then
            right="h help  q quit"
        elif [ "${avail_right}" -ge 6 ]; then
            right="q quit"
        fi
    fi

    if [ -n "${badge}" ]; then
        if [ "${center_start}" -gt "${#left}" ]; then
            pad_left=$(( center_start - ${#left} ))
            printf -v pad_left_str '%*s' "${pad_left}" ''
            pad_right=$(( COLS - center_end - ${#right} ))
            [ "${pad_right}" -lt 0 ] && pad_right=0
            printf -v pad_right_str '%*s' "${pad_right}" ''
            BAR_LINE="${left}${pad_left_str}${badge}${pad_right_str}${right}"
        else
            prefix="${left} ${badge}"
            if [ "${#prefix}" -lt "${COLS}" ]; then
                if [ -n "${right}" ] && [ $(( ${#prefix} + 1 + ${#right} )) -le "${COLS}" ]; then
                    pad=$(( COLS - ${#prefix} - ${#right} ))
                    printf -v pad_str '%*s' "${pad}" ''
                    BAR_LINE="${prefix}${pad_str}${right}"
                else
                    pad=$(( COLS - ${#prefix} ))
                    printf -v pad_str '%*s' "${pad}" ''
                    BAR_LINE="${prefix}${pad_str}"
                fi
            else
                BAR_LINE="${prefix:0:${COLS}}"
            fi
        fi
    else
        if [ -n "${right}" ] && [ $(( ${#left} + 1 + ${#right} )) -le "${COLS}" ]; then
            pad=$(( COLS - ${#left} - ${#right} ))
            printf -v pad_str '%*s' "${pad}" ''
            BAR_LINE="${left}${pad_str}${right}"
        else
            BAR_LINE="${left:0:${COLS}}"
        fi
    fi

    if [ "${#BAR_LINE}" -lt "${COLS}" ]; then
        printf -v pad_str '%*s' "$(( COLS - ${#BAR_LINE} ))" ''
        BAR_LINE="${BAR_LINE}${pad_str}"
    elif [ "${#BAR_LINE}" -gt "${COLS}" ]; then
        BAR_LINE="${BAR_LINE:0:${COLS}}"
    fi
}

render() {
    # Draw one frame: visible window of the spool plus the command bar.
    # Uses a single-pass awk pipeline to seek, clip ANSI codes, format lines,
    # render non-file trailing rows with '~', and paint the command bar.
    LAST_SHOWN=$(( TOP_LINE + PAGE_ROWS - 1 ))
    [ "${LAST_SHOWN}" -gt "${TOTAL}" ] && LAST_SHOWN="${TOTAL}"

    build_bar

    LC_ALL=C BAR_LINE="${BAR_LINE}" awk \
        -v top="${TOP_LINE}" \
        -v last="${LAST_SHOWN}" \
        -v page_rows="${PAGE_ROWS}" \
        -v rows="${ROWS}" \
        -v cols="${COLS}" \
        -v strip="${STRIP_COLORS}" '
    BEGIN {
        esc = "\033"
        bar = ENVIRON["BAR_LINE"]
        row = 1
    }
    NR < top { next }
    NR <= last {
        line = $0
        if (strip == 1) {
            gsub(/\033\[[0-9;?]*[a-zA-Z]/, "", line)
            gsub(/\033\][^\a\033]*(\a|\033\\)/, "", line)
        }
        # In byte-oriented awks (like mawk), length() is byte count.
        # If length(line) <= cols and there is no escape sequence to strip, the line always fits.
        if (index(line, esc) == 0 && length(line) <= cols) {
            # Line fits within cols without truncation
        } else {
            out = ""
            used = 0
            rest = line
            while (length(rest) > 0 && used < cols) {
                p = index(rest, esc)
                if (p == 0) {
                    chunk = rest
                    rest = ""
                } else if (p > 1) {
                    chunk = substr(rest, 1, p - 1)
                    rest = substr(rest, p)
                } else {
                    if (match(rest, /^\033\[[0-9;?]*[a-zA-Z]/) || match(rest, /^\033\][^\a\033]*(\a|\033\\)/)) {
                        out = out substr(rest, RSTART, RLENGTH)
                        rest = substr(rest, RLENGTH + 1)
                        continue
                    } else {
                        out = out substr(rest, 1, 1)
                        rest = substr(rest, 2)
                        used++
                        continue
                    }
                }

                while (length(chunk) > 0 && used < cols) {
                    if (match(chunk, /^[\300-\377][\200-\277]+/)) {
                        out = out substr(chunk, 1, RLENGTH)
                        chunk = substr(chunk, RLENGTH + 1)
                        used++
                    } else {
                        m = match(chunk, /[\300-\377]/)
                        if (m == 0) {
                            take = cols - used
                            if (take > length(chunk)) take = length(chunk)
                            out = out substr(chunk, 1, take)
                            used += take
                            chunk = substr(chunk, take + 1)
                        } else if (m > 1) {
                            take = cols - used
                            if (take > m - 1) take = m - 1
                            out = out substr(chunk, 1, take)
                            used += take
                            chunk = substr(chunk, take + 1)
                        }
                    }
                }
            }
            line = out "\033[0m"
        }
        printf "%s[%d;1H%s%s[0m%s[K", esc, row, line, esc, esc
        row++
        if (NR == last) exit
    }
    END {
        # Screen rows after the last line of the file (beyond EOF):
        while (row <= page_rows) {
            printf "%s[%d;1H~%s[0m%s[K", esc, row, esc, esc
            row++
        }
        printf "%s[%d;1H%s[7m%s%s[0m%s[K", esc, rows, esc, bar, esc, esc
    }
    ' "${SPOOL}"
}

# ---------------------------------------------------------------- key handling

grab_char() {
    # Read a single character from the controlling terminal into GRAB.
    # Accepts an optional timeout in seconds ($1).
    # Returns 1 when the read timed out or the terminal went away.
    GRAB=""
    local st=0 timeout="${1:-}"
    if [ -n "${timeout}" ]; then
        IFS= read -rsn1 -t "${timeout}" GRAB < /dev/tty 2>/dev/null || st=$?
    else
        IFS= read -rsn1 GRAB < /dev/tty || st=$?
    fi
    if [ "${st}" -eq 0 ] && [ -z "${GRAB}" ]; then
        GRAB=$'\n'
    fi
    [ "${st}" -eq 0 ] && [ -n "${GRAB}" ]
}

read_key() {
    # Decode one keypress into the KEY global. Escape payloads are consumed
    # so arrow, page and home/end keys arrive as stable names; a bare ESC is
    # reported as ESCAPE. Periodic liveness checks ensure a severed tty
    # terminates cleanly while allowing indefinite idle reading.
    local c="" c2="" c3="" body="" idle=0

    while :; do
        if [ "${NEED_RESIZE}" = "1" ]; then
            KEY="RESIZE"
            return 0
        fi
        if grab_char; then
            c="${GRAB}"
            break
        fi
        idle=$(( idle + 1 ))
        if [ "${idle}" -ge 50 ]; then
            idle=0
            if ! tty_usable; then
                KEY="EOF"
                return 1
            fi
        fi
    done

    case "${c}" in
        $'\003') KEY="CTRL_C"; return 0 ;;
        $'\004') KEY="CTRL_D"; return 0 ;;
        $'\025') KEY="CTRL_U"; return 0 ;;
        $'\n'|$'\r') KEY="ENTER"; return 0 ;;
        "$ESC") : ;;
        *) KEY="${c}"; return 0 ;;
    esac

    if ! grab_char "${READ_TIMEOUT}"; then
        KEY="ESCAPE"
        return 0
    fi
    c2="${GRAB}"

    case "${c2}" in
        '['|'O')
            if ! grab_char "${READ_TIMEOUT}"; then
                KEY="ESCAPE"
                return 0
            fi
            c3="${GRAB}"
            case "${c3}" in
                'A') KEY="UP" ;;
                'B') KEY="DOWN" ;;
                'C') KEY="RIGHT" ;;
                'D') KEY="LEFT" ;;
                'H') KEY="HOME" ;;
                'F') KEY="END" ;;
                'P') KEY="F1" ;;
                '') KEY="ESCAPE" ;;
                [0-9])
                    body="${c3}"
                    while grab_char "${READ_TIMEOUT}"; do
                        c3="${GRAB}"
                        body="${body}${c3}"
                        case "${c3}" in
                            [0-9]) : ;;
                            *) break ;;
                        esac
                    done
                    case "${body}" in
                        1~|7~) KEY="HOME" ;;
                        4~|8~) KEY="END" ;;
                        5~) KEY="PGUP" ;;
                        6~) KEY="PGDN" ;;
                        11~) KEY="F1" ;;
                        *) KEY="CSI${body}" ;;
                    esac
                    ;;
                *) KEY="CSI${c3}" ;;
            esac
            ;;
        *) KEY="ALT${c2}" ;;
    esac
    return 0
}

get_editor() {
    # Resolve the preferred text editor: $VISUAL, $EDITOR, or system fallbacks.
    if [ -n "${VISUAL:-}" ]; then
        printf '%s' "${VISUAL}"
    elif [ -n "${EDITOR:-}" ]; then
        printf '%s' "${EDITOR}"
    elif command -v nano >/dev/null 2>&1; then
        printf 'nano'
    elif command -v vim >/dev/null 2>&1; then
        printf 'vim'
    elif command -v vi >/dev/null 2>&1; then
        printf 'vi'
    fi
}

open_in_editor() {
    # Launch the user's default text editor on the current file, positioned at TOP_LINE.
    if [ "${ALLOW_FILE}" != "1" ]; then
        MESSAGE="editing disabled"
        return 0
    fi

    local target_file=""
    if [ "${HAVE_FILES}" -ge 1 ]; then
        target_file="${FILES[0]}"
    elif [ -n "${ORIGINAL_FILE}" ]; then
        target_file="${ORIGINAL_FILE}"
    else
        MESSAGE="cannot edit piped input"
        return 0
    fi

    local editor=""
    editor="$(get_editor)"
    if [ -z "${editor}" ]; then
        MESSAGE="no editor found (set \$EDITOR or \$VISUAL)"
        return 0
    fi

    # Temporarily restore the terminal for interactive editor execution.
    printf '%s' "${ESC}[0m"
    printf '%s' "${ESC}[?7h"
    tput cnorm 2>/dev/null || printf '%s' "${ESC}[?25h"
    tput rmcup 2>/dev/null || printf '%s' "${ESC}[?1049l"
    stty "${STTY_ORIG}" < /dev/tty 2>/dev/null

    if [ "${HAVE_FILES}" -gt 1 ]; then
        ${editor} "${FILES[@]}" < /dev/tty > /dev/tty 2>&1 || :
    else
        ${editor} "+${TOP_LINE}" "${target_file}" < /dev/tty > /dev/tty 2>&1 || :
    fi

    # Re-initialize the alternate screen and raw input mode for the pager.
    term_setup

    # Reload input from reload command or file in case modifications were saved.
    if [ -n "${RELOAD_CMD}" ]; then
        eval "${RELOAD_CMD}" > "${SPOOL}" 2>/dev/null || :
    elif [ "${HAVE_FILES}" -ge 1 ]; then
        load_input
    elif [ -n "${ORIGINAL_FILE}" ] && [ -r "${ORIGINAL_FILE}" ]; then
        awk -v lim="${MAX_LINES}" '
            NR <= lim { print }
            END { if (NR > lim) exit 99 }
        ' "${ORIGINAL_FILE}" > "${SPOOL}" 2>/dev/null || :
    fi

    TOTAL=$(( $(wc -l < "${SPOOL}") ))
    clamp_top
    query_size
    printf '%s[2J' "${ESC}"
}

prompt_search() {
    local query=""
    printf '%s[%d;1H%s[7m/%s[K%s[0m' "${ESC}" "${ROWS}" "${ESC}" "${ESC}" "${ESC}"
    while :; do
        if grab_char; then
            case "${GRAB}" in
                $'\n'|$'\r') break ;;
                $'\033') return 0 ;;
                $'\177'|$'\010')
                    if [ "${#query}" -gt 0 ]; then
                        query="${query:0:$(( ${#query} - 1 ))}"
                    fi
                    ;;
                [[:print:]]) query="${query}${GRAB}" ;;
            esac
            printf '%s[%d;1H%s[7m/%s%s[K%s[0m' "${ESC}" "${ROWS}" "${ESC}" "${query}" "${ESC}" "${ESC}"
        fi
    done

    if [ -n "${query}" ]; then
        LAST_SEARCH="${query}"
        search_forward "${LAST_SEARCH}" "$(( TOP_LINE + 1 ))"
    fi
}

search_forward() {
    local pat="$1" start="$2"
    local hit=""
    hit="$(awk -v top="${start}" -v pat="${pat}" '
        BEGIN { IGNORECASE=1 }
        NR >= top && tolower($0) ~ tolower(pat) { print NR; exit }
    ' "${SPOOL}" 2>/dev/null)"
    if [ -z "${hit}" ] && [ "${start}" -gt 1 ]; then
        hit="$(awk -v pat="${pat}" '
            BEGIN { IGNORECASE=1 }
            tolower($0) ~ tolower(pat) { print NR; exit }
        ' "${SPOOL}" 2>/dev/null)"
    fi
    if [ -n "${hit}" ]; then
        TOP_LINE="${hit}"
        MESSAGE="/${pat}"
    else
        MESSAGE="pattern not found: ${pat}"
    fi
}

search_next() {
    local dir="$1"
    if [ -z "${LAST_SEARCH:-}" ]; then
        MESSAGE="no previous search pattern"
        return 0
    fi
    if [ "${dir}" = "1" ]; then
        search_forward "${LAST_SEARCH}" "$(( TOP_LINE + 1 ))"
    else
        local hit=""
        hit="$(awk -v top="$(( TOP_LINE - 1 ))" -v pat="${LAST_SEARCH}" '
            BEGIN { IGNORECASE=1 }
            NR <= top && tolower($0) ~ tolower(pat) { last = NR }
            END { if (last) print last }
        ' "${SPOOL}" 2>/dev/null)"
        if [ -z "${hit}" ]; then
            hit="$(awk -v pat="${LAST_SEARCH}" '
                BEGIN { IGNORECASE=1 }
                tolower($0) ~ tolower(pat) { last = NR }
                END { if (last) print last }
            ' "${SPOOL}" 2>/dev/null)"
        fi
        if [ -n "${hit}" ]; then
            TOP_LINE="${hit}"
            MESSAGE="?${LAST_SEARCH}"
        else
            MESSAGE="pattern not found: ${LAST_SEARCH}"
        fi
    fi
}

choose_link() {
    local links_raw=""
    if [ -n "${PYTHON_BIN}" ]; then
        links_raw="$("${PYTHON_BIN}" -c '
import sys, re
with open(sys.argv[1], "rb") as f:
    raw_lines = f.readlines()

osc8_re = re.compile(rb"\x1b\]8;[^\x1b\x07]*;([^\x1b\x07]+)\x1b\\(.*?)\x1b\]8;;\x1b\\", re.DOTALL)
links = []
for idx, line in enumerate(raw_lines, 1):
    for m in osc8_re.finditer(line):
        url = m.group(1).decode("utf-8", "ignore").strip()
        raw_text = m.group(2)
        clean = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", raw_text).decode("utf-8", "ignore").strip()
        if not clean:
            clean = url
        links.append((url, clean, idx))

if not links:
    md_re = re.compile(rb"\[([^\]]+)\]\(([^)]+)\)")
    bare_re = re.compile(rb"https?://[^\s)\]]+")
    for idx, line in enumerate(raw_lines, 1):
        for m in md_re.finditer(line):
            clean = m.group(1).decode("utf-8", "ignore").strip()
            url = m.group(2).decode("utf-8", "ignore").strip()
            links.append((url, clean, idx))
        for m in bare_re.finditer(line):
            url = m.group(0).decode("utf-8", "ignore").strip()
            links.append((url, url, idx))

consolidated = []
for url, text, line in links:
    if consolidated and consolidated[-1][0] == url and consolidated[-1][2] == line:
        prev_url, prev_text, prev_line = consolidated[-1]
        consolidated[-1] = (prev_url, (prev_text + " " + text).strip(), prev_line)
    else:
        consolidated.append((url, text, line))

for url, text, line in consolidated:
    print(f"{url}\t{text}\t{line}")
' "${SPOOL}" 2>/dev/null)"
    fi

    if [ -z "${links_raw}" ]; then
        MESSAGE="no links found in document"
        return 0
    fi

    local link_urls=() link_texts=() link_lines=()
    local url="" text="" line_no=""
    while IFS=$'\t' read -r url text line_no; do
        [ -z "${url}" ] && continue
        link_urls+=("${url}")
        link_texts+=("${text}")
        link_lines+=("${line_no}")
    done <<< "${links_raw}"

    local count="${#link_urls[@]}"
    if [ "${count}" -eq 0 ]; then
        MESSAGE="no links found in document"
        return 0
    fi

    local sel=0 offset=0 max_display=$(( ROWS - 4 ))
    [ "${max_display}" -lt 3 ] && max_display=3

    local i=0
    for (( i=0; i<count; i++ )); do
        if [ "${link_lines[i]}" -ge "${TOP_LINE}" ]; then
            sel=$i
            break
        fi
    done

    while :; do
        if [ "${sel}" -lt "${offset}" ]; then
            offset="${sel}"
        elif [ "${sel}" -ge $(( offset + max_display )) ]; then
            offset=$(( sel - max_display + 1 ))
        fi

        printf '%s[2J%s[1;1H%s[7m── Follow Link (%d found, j/k/arrows, 1-9/Enter to select, ESC to cancel) ──%s[0m%s[K\n' \
            "${ESC}" "${ESC}" "${ESC}" "${count}" "${ESC}" "${ESC}"

        local row=2 d_idx=0
        for (( d_idx=offset; d_idx<count && d_idx<offset+max_display; d_idx++ )); do
            local num=$(( d_idx + 1 ))
            local item_txt="${link_texts[d_idx]}"
            local item_url="${link_urls[d_idx]}"
            local display_str=" [${num}] ${item_txt} (${item_url})"
            if [ "${#display_str}" -gt "$(( COLS - 2 ))" ]; then
                display_str="${display_str:0:$(( COLS - 5 ))}..."
            fi
            if [ "${d_idx}" -eq "${sel}" ]; then
                printf '%s[%d;1H%s[1;37;44m>%s%s[0m%s[K\n' "${ESC}" "${row}" "${ESC}" "${display_str}" "${ESC}" "${ESC}"
            else
                printf '%s[%d;1H  %s%s[0m%s[K\n' "${ESC}" "${row}" "${display_str}" "${ESC}" "${ESC}"
            fi
            row=$(( row + 1 ))
        done

        while [ "${row}" -lt "${ROWS}" ]; do
            printf '%s[%d;1H%s[K\n' "${ESC}" "${row}" "${ESC}"
            row=$(( row + 1 ))
        done

        printf '%s[%d;1H%s[7mSelect link [1-%d] or ENTER on selection (ESC to cancel): %s[K%s[0m' \
            "${ESC}" "${ROWS}" "${ESC}" "${count}" "${ESC}" "${ESC}"

        read_key
        case "${KEY}" in
            UP|k)
                [ "${sel}" -gt 0 ] && sel=$(( sel - 1 ))
                ;;
            DOWN|j)
                [ "${sel}" -lt $(( count - 1 )) ] && sel=$(( sel + 1 ))
                ;;
            ENTER)
                break
                ;;
            [1-9])
                local typed_num="${KEY}"
                if [ "${count}" -ge 10 ] && grab_char; then
                    case "${GRAB}" in
                        [0-9]) typed_num="${typed_num}${GRAB}" ;;
                        $'\n'|$'\r') : ;;
                    esac
                fi
                local target_idx=$(( typed_num - 1 ))
                if [ "${target_idx}" -ge 0 ] && [ "${target_idx}" -lt "${count}" ]; then
                    sel="${target_idx}"
                    break
                fi
                ;;
            q|Q|ESCAPE|CTRL_C)
                printf '%s[2J' "${ESC}"
                return 0
                ;;
        esac
    done

    printf '%s[2J' "${ESC}"

    local chosen_url="${link_urls[sel]}"
    local chosen_text="${link_texts[sel]}"
    local source_line="${link_lines[sel]}"

    if [[ "${chosen_url}" == \#* ]]; then
        local target_anchor="${chosen_url#\#}"
        local dest_line=""
        if [ -n "${PYTHON_BIN}" ]; then
            dest_line="$("${PYTHON_BIN}" -c '
import sys, re
spool = sys.argv[1]
anchor = sys.argv[2]
text = sys.argv[3]
source_line = int(sys.argv[4])

def normalize(s):
    if isinstance(s, bytes):
        s = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", s).decode("utf-8", "ignore")
    else:
        s = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", s)
    return re.sub(r"[^a-zA-Z0-9]+", " ", s).lower().strip()

with open(spool, "rb") as f:
    lines = f.readlines()

norm_text = normalize(text)
norm_anchor = normalize(anchor)

best_line = None
best_score = -1

for idx, raw in enumerate(lines[source_line:], source_line + 1):
    clean = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", raw).decode("utf-8", "ignore").strip()
    if clean.startswith("•") or clean.startswith("-") or not clean:
        continue
    norm_line = normalize(raw)
    if not norm_line:
        continue

    score = 0
    if norm_line.startswith(norm_text) or (norm_text and norm_text.startswith(norm_line)):
        score += 100
    elif norm_line.startswith(norm_anchor) or (norm_anchor and norm_anchor.startswith(norm_line)):
        score += 90
    else:
        tw = norm_text.split()
        lw = norm_line.split()
        if len(tw) >= 2 and lw[:2] == tw[:2]:
            score += 80
        elif len(tw) >= 1 and lw and lw[0] == tw[0]:
            score += 40
        common = set(tw) & set(lw)
        score += len(common) * 5

    if score > best_score and score >= 40:
        best_score = score
        best_line = idx
        if score >= 90:
            break

if not best_line:
    for idx, raw in enumerate(lines, 1):
        clean = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", raw).decode("utf-8", "ignore").strip()
        if clean.startswith("•") or clean.startswith("-") or not clean:
            continue
        norm_line = normalize(raw)
        if not norm_line:
            continue
        score = 0
        if norm_line.startswith(norm_text) or (norm_text and norm_text.startswith(norm_line)):
            score += 100
        elif norm_line.startswith(norm_anchor) or (norm_anchor and norm_anchor.startswith(norm_line)):
            score += 90
        else:
            tw = norm_text.split()
            lw = norm_line.split()
            if len(tw) >= 2 and lw[:2] == tw[:2]:
                score += 80
            common = set(tw) & set(lw)
            score += len(common) * 5
        if score > best_score and score >= 40:
            best_score = score
            best_line = idx
            if score >= 90:
                break

if best_line:
    print(best_line)
' "${SPOOL}" "${target_anchor}" "${chosen_text}" "${source_line}" 2>/dev/null)"
        fi

        if [ -n "${dest_line}" ] && [ "${dest_line}" -gt 0 ] 2>/dev/null; then
            TOP_LINE="${dest_line}"
            MESSAGE="jumped to ${chosen_url}"
        else
            MESSAGE="anchor not found: ${chosen_url}"
        fi
    elif [[ "${chosen_url}" == http://* ]] || [[ "${chosen_url}" == https://* ]]; then
        local webopen="${PROJECT_ROOT}/scripts/webopen.sh"
        if [ -x "${webopen}" ]; then
            "${webopen}" "${chosen_url}" >/dev/null 2>&1 &
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "${chosen_url}" >/dev/null 2>&1 &
        elif [ -n "${PYTHON_BIN}" ]; then
            "${PYTHON_BIN}" -m webbrowser "${chosen_url}" >/dev/null 2>&1 &
        fi
        MESSAGE="opened ${chosen_url}"
    else
        local clean_file="${chosen_url#file://}"
        local full_file=""
        if [ -e "${clean_file}" ]; then
            full_file="${clean_file}"
        elif [ -e "${PROJECT_ROOT}/${clean_file}" ]; then
            full_file="${PROJECT_ROOT}/${clean_file}"
        fi

        if [ -n "${full_file}" ]; then
            if [ -x "${PROJECT_ROOT}/scripts/rich.sh" ] && [[ "${full_file}" == *.md ]]; then
                "${PROJECT_ROOT}/scripts/rich.sh" "${full_file}"
            elif [ -x "${0}" ]; then
                "${0}" "${full_file}"
            fi
            MESSAGE="viewed ${chosen_url}"
        else
            MESSAGE="file not found: ${chosen_url}"
        fi
    fi
}

show_help_modal() {
    # Render an interactive scrolling popup modal displaying pager usage and shortcuts.
    local help_lines=(
        "BASHMENU PAGER - HELP & MANUAL"
        ""
        "USAGE:"
        "  command | pager.sh [options]"
        "  pager.sh [options] <file> [file...]"
        ""
        "DESCRIPTION:"
        "  Interactive full-screen text pager for terminal output and files."
        "  Supports ANSI color preservation, line truncation, piped streams,"
        "  interactive hyperlinks, and seamless external editor integration."
        ""
        "KEYBOARD SHORTCUTS:"
        ""
        "  Navigation & Scrolling"
        "    j, DOWN, ENTER   Scroll down one line"
        "    k, UP            Scroll up one line"
        "    SPACE, f, PGDN   Scroll down one full page (window)"
        "    b, PGUP          Scroll up one full page (window)"
        "    Ctrl-D           Scroll down half a page"
        "    Ctrl-U           Scroll up half a page"
        "    g, HOME          Jump to top of document (line 1)"
        "    G, END           Jump to bottom of document"
        ""
        "  Searching"
        "    /                Search forward (pattern or regular expression)"
        "    n                Repeat search forward for next match"
        "    N                Repeat search backward for previous match"
        ""
        "  Hyperlinks & Anchors"
        "    l, o             Open interactive link selector menu:"
        "                     - OSC 8 terminal hyperlinks"
        "                     - Markdown [label](url) links"
        "                     - Plain web URLs (http:// or https://)"
        "                     - Internal section anchors (#anchor)"
        ""
        "  Editor Integration"
        "    e, E             Open file in \$EDITOR or \$VISUAL (nano, vim, vi)"
        "                     positioned at current line; reloads automatically"
        ""
        "  Help & Exit"
        "    h, ?, F1         Open / close this scrolling help modal"
        "    q, Q, ESC        Close help modal / exit pager"
        ""
        "COMMAND LINE OPTIONS:"
        "  -h, --help         Print CLI help screen and exit"
        "  -V, --version      Display pager version"
        "  +N                 Start viewing at line number N"
        "  +/PATTERN          Start viewing at first line matching PATTERN"
        "  -c, --no-color     Strip all ANSI escape codes from display"
        "  --no-help          Omit shortcut hints from the command bar"
        "  --no-file          Disable editor launch and filename badge"
        "  --max-lines=N      Maximum lines to buffer (default: 1,000,000)"
        "  --file=PATH        Target file to associate with piped input"
        "  --reload-cmd=CMD   Command to refresh spool after editing"
    )

    local total_lines="${#help_lines[@]}"
    local scroll_top=0
    local box_w=0 box_h=0 start_r=0 start_c=0 inner_w=0 inner_h=0 max_scroll=0
    local b_style="" t_style="" s_style="" r_style=""
    local title="" t_len=0 r_len=0 top_bar="" i=0
    local r_idx=0 line_idx=0 line_content="" l_style="" padded="" cur_r=0
    local pct_str="" pct=0 hint="" h_len=0 b_len=0 bot_bar="" bot_r=0

    while :; do
        query_size

        box_w=$(( COLS - 6 ))
        [ "${box_w}" -gt 74 ] && box_w=74
        [ "${box_w}" -lt 40 ] && box_w=$(( COLS > 40 ? 40 : COLS ))
        box_h=$(( ROWS - 4 ))
        [ "${box_h}" -gt 22 ] && box_h=22
        [ "${box_h}" -lt 8 ] && box_h=$(( ROWS > 8 ? 8 : ROWS ))

        start_r=$(( (ROWS - box_h) / 2 + 1 ))
        start_c=$(( (COLS - box_w) / 2 + 1 ))
        inner_w=$(( box_w - 6 ))
        inner_h=$(( box_h - 2 ))
        [ "${inner_w}" -lt 10 ] && inner_w=10
        [ "${inner_h}" -lt 2 ] && inner_h=2

        max_scroll=$(( total_lines - inner_h ))
        [ "${max_scroll}" -lt 0 ] && max_scroll=0

        if [ "${scroll_top}" -gt "${max_scroll}" ]; then
            scroll_top="${max_scroll}"
        fi
        if [ "${scroll_top}" -lt 0 ]; then
            scroll_top=0
        fi

        b_style="${ESC}[1;36m"
        t_style="${ESC}[1;37;44m"
        s_style="${ESC}[1;33m"
        r_style="${ESC}[0m"
        if [ "${STRIP_COLORS}" = "1" ]; then
            b_style=""
            t_style=""
            s_style=""
            r_style=""
        fi

        # Top border
        title=" Pager Help & Manual "
        t_len=${#title}
        r_len=$(( box_w - t_len - 3 ))
        [ "${r_len}" -lt 0 ] && r_len=0
        top_bar=""
        for (( i=0; i<r_len; i++ )); do top_bar="${top_bar}─"; done
        printf '%s[%d;%dH%s┌─%s%s%s%s%s┐%s' \
            "${ESC}" "${start_r}" "${start_c}" \
            "${b_style}" "${t_style}" "${title}" "${r_style}${b_style}" "${top_bar}" "${b_style}" "${r_style}"

        # Content rows
        for (( r_idx=0; r_idx<inner_h; r_idx++ )); do
            line_idx=$(( scroll_top + r_idx ))
            line_content=""
            if [ "${line_idx}" -lt "${total_lines}" ]; then
                line_content="${help_lines[line_idx]}"
            fi

            l_style="${r_style}"
            if [[ "${line_content}" =~ ^[A-Z\ ]+:$ ]] || [ "${line_idx}" -eq 0 ]; then
                l_style="${s_style}"
            fi

            padded=""
            printf -v padded '%-*.*s' "${inner_w}" "${inner_w}" "${line_content}"
            cur_r=$(( start_r + 1 + r_idx ))
            printf '%s[%d;%dH%s│  %s%s%s  │%s' \
                "${ESC}" "${cur_r}" "${start_c}" \
                "${b_style}" "${l_style}" "${padded}" "${b_style}" "${r_style}"
        done

        # Bottom border with scroll percentage indicator
        if [ "${max_scroll}" -eq 0 ]; then
            pct_str="All"
        elif [ "${scroll_top}" -eq 0 ]; then
            pct_str="Top"
        elif [ "${scroll_top}" -ge "${max_scroll}" ]; then
            pct_str="Bot"
        else
            pct=$(( ((scroll_top + inner_h) * 100) / total_lines ))
            pct_str="${pct}%"
        fi

        hint=" [▲▼/PgUp/PgDn: scroll • q/ESC: close] (${pct_str}) "
        h_len=${#hint}
        b_len=$(( box_w - h_len - 3 ))
        [ "${b_len}" -lt 0 ] && b_len=0
        bot_bar=""
        for (( i=0; i<b_len; i++ )); do bot_bar="${bot_bar}─"; done
        bot_r=$(( start_r + box_h - 1 ))
        printf '%s[%d;%dH%s└─%s%s%s%s%s┘%s' \
            "${ESC}" "${bot_r}" "${start_c}" \
            "${b_style}" "${r_style}${b_style}" "${hint}" "${b_style}" "${bot_bar}" "${b_style}" "${r_style}"

        read_key
        case "${KEY}" in
            j|DOWN|ENTER)
                [ "${scroll_top}" -lt "${max_scroll}" ] && scroll_top=$(( scroll_top + 1 ))
                ;;
            k|UP)
                [ "${scroll_top}" -gt 0 ] && scroll_top=$(( scroll_top - 1 ))
                ;;
            ' '|f|PGDN)
                scroll_top=$(( scroll_top + inner_h ))
                [ "${scroll_top}" -gt "${max_scroll}" ] && scroll_top="${max_scroll}"
                ;;
            b|PGUP)
                scroll_top=$(( scroll_top - inner_h ))
                [ "${scroll_top}" -lt 0 ] && scroll_top=0
                ;;
            CTRL_D)
                scroll_top=$(( scroll_top + inner_h / 2 ))
                [ "${scroll_top}" -gt "${max_scroll}" ] && scroll_top="${max_scroll}"
                ;;
            CTRL_U)
                scroll_top=$(( scroll_top - inner_h / 2 ))
                [ "${scroll_top}" -lt 0 ] && scroll_top=0
                ;;
            g|HOME)
                scroll_top=0
                ;;
            G|END)
                scroll_top="${max_scroll}"
                ;;
            RESIZE)
                query_size
                render
                ;;
            q|Q|ESCAPE|CTRL_C|h|'?'|F1)
                break
                ;;
        esac
    done

    render
}

handle_key() {
    # Apply the decoded key to the window position, or request termination.
    # This case statement is the single extension point for new bindings.
    MESSAGE=""

    case "${KEY}" in
        RESIZE) ;;
        DOWN|ENTER|j) TOP_LINE=$(( TOP_LINE + 1 )) ;;
        UP|k) TOP_LINE=$(( TOP_LINE - 1 )) ;;
        ' '|f|PGDN|PAGE) TOP_LINE=$(( TOP_LINE + PAGE_ROWS )) ;;
        b|PGUP) TOP_LINE=$(( TOP_LINE - PAGE_ROWS )) ;;
        CTRL_D) TOP_LINE=$(( TOP_LINE + PAGE_ROWS / 2 )) ;;
        CTRL_U) TOP_LINE=$(( TOP_LINE - PAGE_ROWS / 2 )) ;;
        HOME|g) TOP_LINE=1 ;;
        END|G) TOP_LINE=$(( TOTAL + 1 )) ;;
        /) prompt_search ;;
        n) search_next 1 ;;
        N) search_next -1 ;;
        l|o) choose_link ;;
        e|E) open_in_editor ;;
        h|'?'|F1) show_help_modal ;;
        q|Q|CTRL_C|ESCAPE|EOF) DONE=1 ;;
        LEFT|RIGHT|ALT*) : ;;
        *) MESSAGE="unbound key: ${KEY}" ;;
    esac

    clamp_top
}

# ------------------------------------------------------------------------ main

parse_args() {
    # Validate command line flags and collect file operands.
    local arg=""

    while [ "$#" -gt 0 ]; do
        arg="$1"
        case "${arg}" in
            -h|--help) usage; exit 0 ;;
            -V|--version) printf '%s %s\n' "${0##*/}" "${PAGER_VERSION}"
                          exit 0 ;;
            -c|--no-color|--no-colour) STRIP_COLORS=1 ;;
            --no-file|--no-edit|--view-only) ALLOW_FILE=0 ;;
            --no-help) SHOW_HELP=0 ;;
            --max-lines=*) MAX_LINES="${arg#*=}" ;;
            --max-lines) [ "$#" -ge 2 ] || die "--max-lines needs a value"
                         MAX_LINES="$2"; shift ;;
            --file=*) ORIGINAL_FILE="${arg#*=}" ;;
            --file) [ "$#" -ge 2 ] || die "--file needs a value"
                    ORIGINAL_FILE="$2"; shift ;;
            --edit-target=*) ORIGINAL_FILE="${arg#*=}" ;;
            --edit-target) [ "$#" -ge 2 ] || die "--edit-target needs a value"
                    ORIGINAL_FILE="$2"; shift ;;
            --reload-cmd=*) RELOAD_CMD="${arg#*=}" ;;
            --reload-cmd) [ "$#" -ge 2 ] || die "--reload-cmd needs a value"
                    RELOAD_CMD="$2"; shift ;;
            +[0-9]*) START_LINE="${arg#+}" ;;
            +/*) START_PATTERN="${arg#+/}" ;;
            +) die "invalid argument: +" ;;
            --) shift
                while [ "$#" -gt 0 ]; do FILES+=("$1"); shift; done
                break ;;
            -*) die "unknown option: ${arg}" ;;
            *) FILES+=("${arg}") ;;
        esac
        shift
    done

    HAVE_FILES="${#FILES[@]}"
    case "${MAX_LINES}" in
        *[!0-9]*|'') die "invalid line limit: ${MAX_LINES}" ;;
    esac
}

main() {
    parse_args "$@"

    local spool_dir="${CACHE_DIR:-${HOME}/.cache/bashmenu}/spool"
    mkdir -p "${spool_dir}" 2>/dev/null || die "cannot create spool directory: ${spool_dir}"
    SPOOL="$(mktemp "${spool_dir}/pager.XXXXXX")" \
        || die "cannot create a temporary spool file"
    trap 'cleanup' EXIT INT TERM HUP

    if [ "${HAVE_FILES}" -ge 1 ]; then
        local f=""
        for f in "${FILES[@]}"; do
            [ -e "${f}" ] || die "no such file: ${f}"
            [ -r "${f}" ] || die "cannot read: ${f}"
        done
    elif [ -t 0 ]; then
        usage >&2
        exit 2
    fi

    load_input
    TOTAL=$(( $(wc -l < "${SPOOL}") ))

    if [ ! -t 1 ] || ! tty_usable; then
        # No usable display: behave as a pass-through so the pager stays safe
        # inside larger pipelines and non-interactive shells.
        cat "${SPOOL}"
        [ "${TRUNCATED}" = "1" ] \
            && printf '%s: input truncated at %s lines\n' \
                  "${0##*/}" "${MAX_LINES}" >&2
        exit 0
    fi

    if [ "${ALLOW_FILE}" = "1" ]; then
        HINTS="j/k line  SPACE pgDn  b pgUp  / search  l link  e edit  h/? help  q quit"
    else
        HINTS="j/k line  SPACE pgDn  b pgUp  / search  l link  h/? help  q quit"
    fi

    NEED_RESIZE=0
    query_size
    resolve_start
    [ "${TRUNCATED}" = "1" ] && MESSAGE="stored only the first ${MAX_LINES} lines"
    clamp_top

    term_setup

    while [ "${DONE}" = "0" ]; do
        if [ "${NEED_RESIZE}" = "1" ]; then
            NEED_RESIZE=0
            query_size
        fi
        clamp_top
        render
        read_key
        handle_key
    done

    # The EXIT trap restores the terminal; exit explicitly so the status is
    # not inherited from the last test inside the loop.
    exit 0
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
