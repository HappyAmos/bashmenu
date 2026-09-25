#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: get_api_key.sh
# DESCRIPTION: Retrieves text from a file on a remote server via SSH.
#              Useful for fetching API keys or tokens securely.
# ==============================================================================

SERVER="pi3b.lan"
REMOTE_FILE_DIR="/mnt/wd320/private/andrew/Linux/"

print_help_text() {
    echo "Download the text from a file via SSH from [$SERVER@$REMOTE_FILE_DIR]"
    echo "Usage: [options] <filename>"
    echo "Options:"
    echo -e "  -h\t--help\t\t This information."
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    print_help_text
    exit 0
elif [[ -z "$1" ]]; then
    print_help_text >&2
    exit 1
fi

trap 'unset SECRET' EXIT

FILE_ARG="$1"
TRIMMED="${FILE_ARG#"${FILE_ARG%%[![:space:]]*}"}"
TRIMMED="${TRIMMED%"${TRIMMED##*[![:space:]]*}"}"
TRIMMED="${TRIMMED#/}"
REMOTE_FILE_PATH="$REMOTE_FILE_DIR/$TRIMMED"

if ! SECRET=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "cat '$REMOTE_FILE_PATH'" 2>/dev/null) || [ -z "$SECRET" ]; then
    exit 1
fi

echo "$SECRET"
