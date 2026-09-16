#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: get_api_key.sh
# DESCRIPTION: Retrieves text from a file on a remote server via SSH.
#              Useful for fetching API keys or tokens securely.
# ==============================================================================
# Version: 0.0.1
# Author:  HappyAmos
# Echo's out string contained on a directory in a remote server
# Passes string, or exits with an error code on failure.

# Define connection details
SERVER="pi3b.lan"
REMOTE_FILE_DIR="/mnt/wd320/private/andrew/Linux/"

# Sample files:
# gapikey.txt
# gitpat.txt

# Function to display help information
function print_help_text {
    echo "Download the text from a file via SSH from [$SERVER@$REMOTE_FILE_DIR]"
    echo "Usage: [options] <filename>"
    echo "Options:"
    echo -e "  -h\t--help\t\t This information."
}

# Handle flags and arguments
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    print_help_text
    exit 0
elif [[ -z "$1" ]]; then
    print_help_text >&2
    exit 1
fi

# Assign to a variable so we can safely perform parameter expansion
FILE_ARG="$1"

# Trim leading whitespace
TRIMMED="${FILE_ARG#"${FILE_ARG%%[![:space:]]*}"}"

# Trim trailing whitespace
TRIMMED="${TRIMMED%"${TRIMMED##*[![:space:]]*}"}"
TRIMMED="${TRIMMED#/}"
REMOTE_FILE_PATH="$REMOTE_FILE_DIR/$TRIMMED"

# Check if the SSH command succeeded and returned data
if ! SECRET=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "cat '$REMOTE_FILE_PATH'" 2>/dev/null) || [ -z "$SECRET" ]; then
    #echo "Error: Could not connect to $SERVER, the file was empty, or the file doesn't exist." >&2
    exit 1
fi

echo "$SECRET"
trap 'unset SECRET' EXIT

