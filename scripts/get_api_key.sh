#!/bin/bash
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

SECRET=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "cat '$REMOTE_FILE_PATH'" 2>/dev/null)

# Check if the SSH command succeeded
if [ $? -ne 0 ] || [ -z "$SECRET" ]; then
    #echo "Error: Could not connect to $SERVER, the file was empty, or the file doesn't exist." >&2
    exit 1
fi

echo "$SECRET"
trap 'unset SECRET' EXIT

