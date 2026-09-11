# Get the directory that the script is located in:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

# Make sure our target directory exists
mkdir -p ~/cheat

# cd into our target directory or exit with error because it still doesn't exist
cd ~/cheat || exit 1 

# Clone the private git repository into ~/cheat
git clone https://HappyAmos:$("$SCRIPT_DIR/get_api_key.sh" "gitpat.txt")@github.com/HappyAmos/cheat.git
exit
