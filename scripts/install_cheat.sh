#!/bin/bash

# Personal script to clone private Github repo of cheatsheets (markdown) to a subdirectory 
# in my home folder. get_api_key.sh is a farily universal script to grab text 
# via ssh from another device on the network. Values are hard coded in script
# but very easy to customize.

# Get the directory that the script is located in:
SCRIPT_DIR="$(cd -P "$(dirname "$BASH_SOURCE")" && pwd)"
INSTALL_DIR="$HOME/cheatsheets"

# Make sure our target directory exists
mkdir -p "$INSTALL_DIR" &>/dev/null

# cd into our target directory or exit with error because it still doesn't exist
cd "$INSTALL_DIR" &>/dev/null || exit 1

# Check if the directory is empty or not. If it's not, it might already have scripts installed:
if [ -z "$(find "$INSTALL_DIR" -maxdepth 0 -empty)" ]; then
    echo "Directory is NOT empty, aborting git clone."
    exit 1
else
    # Clone the private git repository into ~/$INSTALL_DIR
    echo "Directory is empty, cloning git repository."
    # The '.' at the end tells git to install in the current directory, instead of creating a new folder in the 
    # current directory
    git clone https://HappyAmos:$("$SCRIPT_DIR/get_api_key.sh" "gitpat.txt")@github.com/HappyAmos/cheat.git .
fi
