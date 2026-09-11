#!/bin/bash
# Version: 0.0.1
# Author:  HA Bash Menu Development Team
# This script installs kmscon on a Linux system. Great for a headless base system without a GUI that doesn't
# install a system with a frame buffer
# It is intended for use on systems that use systemd and have access to the necessary package repositories.

# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
	echo "Please run as root."
	exit 1
fi

# Use quotes around the subshell assignment to handle empty results safely
KMSCON_INSTALLED="$(command -v kmscon)"

# Use the -n flag and the $ symbol to test if the variable's value is not empty
if [ -n "$KMSCON_INSTALLED" ]; then
    echo "kmscon is already installed."
    exit 0
fi



# Source the file directly into your current shell session
source /etc/os-release

echo "Found OS: $NAME, Version: $VERSION, ID: $ID, Codename: $VERSION_CODENAME"
#ID=$("sudo -u $SUDO_USER source /etc/os-release && echo $ID")
#ID=$(source /etc/os-release && echo "$ID")
#CODENAME=$("sudo -u $SUDO_USER source /etc/os-release && echo $VERSION_CODENAME")

if [[ "$ID" == "ubuntu" || "$ID" == "linuxmint" ]]; then
	echo "Detected Debian-based system: $ID"
	apt update
	apt install -y kmscon
elif [[ "$ID" == "debian" && "$CODENAME" == "trixie" ]]; then
	echo "Detected Debian Trixie"
	APT_PATH="/etc/apt/sources.list.d/"
	APT_FILE="debian-backports.sources"
	if [ ! -f "${APT_PATH}${APT_FILE}" ]; then
		cat << 'EOF' > "${APT_PATH}${APT_FILE}"
Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites: trixie-backports
Components: main
Enabled: yes
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF

	fi
	sudo apt update
	sudo apt install -y kmscon
else
	echo "Unsupported Linux distribution: $ID"
	exit 1
fi

if sudo systemctl disable getty@tty1.service; then
	echo "Successfully disabled getty."
	if sudo systemctl enable kmsconvt@tty1.service; then
		echo "Successfully enabled kmscon."
		exit 0
	else
		echo "Failed to enable kmscon. Please check your system configuration."
		exit 1
	fi
else
	echo "Failed to disable getty. Please check your system configuration."
	exit 1
fi

exit 1 # Uncaught error, should not reach here if everything went well
