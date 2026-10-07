#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: serverup.sh
# DESCRIPTION: Cross-platform script to check the status of a server.
# ==============================================================================

param="$#"
usage="Usage: ./serverup.sh <ip> [server-name]"

# Require 1 or 2 arguments
if [ "$param" -lt 1 ]; then
    echo "Error: Expected at least 1 argument, but received $#."
    echo "$usage"
    exit 1
fi

if [ "$param" -eq 1 ]; then
    SERVER_IP="$1"
    SERVER_NAME="$1"
elif [ "$param" -eq 2 ]; then
    SERVER_IP="$1"
    SERVER_NAME="$2"
else
    echo "Unknown argument count: $param"
    echo "$usage"
    exit 1
fi

echo "$SERVER_NAME:"
ping -c 1 -W 2 "$SERVER_IP" > /dev/null 2>&1 \
  && echo "  $SERVER_IP | UP" \
  || echo "  $SERVER_IP | DOWN"

exit 0

