#!/usr/bin/env bash
# Version: 0.0.1
# Author:  HappyAmos

# ==============================================================================
# SCRIPT: set-dns.sh
# DESCRIPTION: Automatically detects the active network management tool on
#              Debian/Ubuntu/Mint systems and configures IPv4 & IPv6 DNS.
# FALLBACK: Directly edits /etc/resolv.conf if no manager is available.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status during critical operations
set -e

# ------------------------------------------------------------------------------
# 1. PRIVILEGE CHECK
# ------------------------------------------------------------------------------
# Network configuration requires root (administrator) privileges.
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (use sudo)." >&2
  exit 1
fi

echo "Starting DNS configuration..."


# ------------------------------------------------------------------------------
# 2. Argument Check & Assignment
# ------------------------------------------------------------------------------
# Verify that we are working with correct ipv4 and ipv6 parameters

# Function to validate IPv4 format
is_ipv4() {
    local ip="$1"
    local regex='^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    [[ "$ip" =~ $regex ]]
}

# Function to validate IPv6 format (supports standard and compressed :: notation)
is_ipv6() {
    local ip="$1"
    local regex='^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$'
    [[ "$ip" =~ $regex ]]
}

# 1. Verify exactly 4 parameters were passed
if [ "$#" -ne 4 ]; then
    echo "Error: Exactly 4 parameters are required (2x IPv4, 2x IPv6)." >&2
    echo "Usage: $0 <IPv4_1> <IPv4_2> <IPv6_1> <IPv6_2>" >&2
    exit 1
fi

# 2. Verify Parameter 1 (IPv4)
if ! is_ipv4 "$1"; then
    echo "Error: Parameter 1 ('$1') is not a valid IPv4 address." >&2
    exit 1
fi

# 3. Verify Parameter 2 (IPv4)
if ! is_ipv4 "$2"; then
    echo "Error: Parameter 2 ('$2') is not a valid IPv4 address." >&2
    exit 1
fi

# 4. Verify Parameter 3 (IPv6)
if ! is_ipv6 "$3"; then
    echo "Error: Parameter 3 ('$3') is not a valid IPv6 address." >&2
    exit 1
fi

# 5. Verify Parameter 4 (IPv6)
if ! is_ipv6 "$4"; then
    echo "Error: Parameter 4 ('$4') is not a valid IPv6 address." >&2
    exit 1
fi

# ==============================================================================
# ASSIGN ARGUMENTS TO VARIABLES (This was missing!)
# ==============================================================================
DNS_IPV4_PRIMARY="$1"
DNS_IPV4_SECONDARY="$2"
DNS_IPV6_PRIMARY="$3"
DNS_IPV6_SECONDARY="$4"

echo -e "Parameters passed:\n \
    \tipv4 (primary): $DNS_IPV4_PRIMARY\n \
    \tipv4 (secondary): $DNS_IPV4_SECONDARY\n \
    \tipv6 (primary): $DNS_IPV6_PRIMARY\n \
    \tipv6 (secondary): $DNS_IPV6_SECONDARY"


# ------------------------------------------------------------------------------
# METHOD 1: NetworkManager (nmcli)
# Common on Desktop systems (Ubuntu Desktop, Linux Mint) and some servers.
# ------------------------------------------------------------------------------
# We check if 'nmcli' binary exists AND if the NetworkManager daemon is active.
if command -v nmcli >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager; then
    echo "[+] Detected: NetworkManager is active."

    # Retrieve the name of the currently active primary network connection.
    # 'nmcli -t' gives script-friendly output, '-f NAME,DEVICE' fields.
    ACTIVE_CONN=$(nmcli -t -f NAME,TYPE connection show --active | grep -v '^lo:' | head -n1 | cut -d: -f1)

    if [ -n "$ACTIVE_CONN" ]; then
        echo "    Configuring active connection: '$ACTIVE_CONN'"

        # Set IPv4 DNS servers and ignore DNS provided by DHCP routers
        nmcli connection modify "$ACTIVE_CONN" ipv4.dns "$DNS_IPV4_PRIMARY $DNS_IPV4_SECONDARY"
        nmcli connection modify "$ACTIVE_CONN" ipv4.ignore-auto-dns yes

        # Set IPv6 DNS servers and ignore DNS provided by DHCP routers
        nmcli connection modify "$ACTIVE_CONN" ipv6.dns "$DNS_IPV6_PRIMARY $DNS_IPV6_SECONDARY"
        nmcli connection modify "$ACTIVE_CONN" ipv6.ignore-auto-dns yes

        # Reactivate the connection to apply changes immediately
        echo "    Reapplying network connection..."
        nmcli connection up "$ACTIVE_CONN" >/dev/null

        echo "[SUCCESS] DNS configured via NetworkManager."
        exit 0
    else
        echo "    NetworkManager is running, but no active connection was found. Trying next method..."
    fi
fi

# ------------------------------------------------------------------------------
# METHOD 2: systemd-resolved (resolvctl)
# Default DNS manager on modern Ubuntu Server and Ubuntu Desktop installs.
# ------------------------------------------------------------------------------
# We check if systemd-resolved service is actively running on the system.
if systemctl is-active --quiet systemd-resolved; then
    echo "[+] Detected: systemd-resolved is active."

    # Option A: Modify global settings in /etc/systemd/resolved.conf (Persistent)
    RESOLVED_CONF="/etc/systemd/resolved.conf"

    echo "    Updating $RESOLVED_CONF..."

    # Backup existing config if no backup exists yet
    [ ! -f "${RESOLVED_CONF}.bak" ] && cp "$RESOLVED_CONF" "${RESOLVED_CONF}.bak"

    # Configure DNS lines in resolved.conf
    # We use sed to replace existing 'DNS=' or 'FallbackDNS=' lines, or append them.
    sed -i '/^DNS=/d' "$RESOLVED_CONF"
    sed -i '/^FallbackDNS=/d' "$RESOLVED_CONF"

    # Append new DNS values under the [Resolve] section
    echo "DNS=$DNS_IPV4_PRIMARY $DNS_IPV4_SECONDARY $DNS_IPV6_PRIMARY $DNS_IPV6_SECONDARY" >> "$RESOLVED_CONF"

    # Restart systemd-resolved to force changes to take effect immediately
    echo "    Restarting systemd-resolved..."
    systemctl restart systemd-resolved

    echo "[SUCCESS] DNS configured via systemd-resolved."
    exit 0
fi

# ------------------------------------------------------------------------------
# METHOD 3: resolvconf package
# An older framework still present on standard Debian installations.
# ------------------------------------------------------------------------------
if command -v resolvconf >/dev/null 2>&1; then
    echo "[+] Detected: resolvconf utility."

    HEAD_FILE="/etc/resolvconf/resolv.conf.d/head"

    # Ensure the configuration directory exists
    mkdir -p /etc/resolvconf/resolv.conf.d/

    echo "    Injecting DNS servers into $HEAD_FILE..."

    # Remove any existing manual entries we might have added previously to avoid duplicates
    sed -i '/nameserver/d' "$HEAD_FILE"

    # Append our custom DNS servers to the top of the head file
    {
        echo "nameserver $DNS_IPV4_PRIMARY"
        echo "nameserver $DNS_IPV4_SECONDARY"
        echo "nameserver $DNS_IPV6_PRIMARY"
        echo "nameserver $DNS_IPV6_SECONDARY"
    } >> "$HEAD_FILE"

    # Update resolvconf
    echo "    Updating resolvconf dynamic records..."
    resolvconf -u

    echo "[SUCCESS] DNS configured via resolvconf."
    exit 0
fi

# ------------------------------------------------------------------------------
# METHOD 4: Direct Fallback (/etc/resolv.conf)
# Executed ONLY if no other network management framework was detected above.
# ------------------------------------------------------------------------------
echo "[!] WARNING: No network management suite detected (NetworkManager, systemd-resolved, or resolvconf)."
echo "[!] Falling back to direct modification of /etc/resolv.conf."

RESOLV_FILE="/etc/resolv.conf"

# If /etc/resolv.conf is a symlink (e.g., pointing to systemd or resolvconf),
# remove the symlink so we can write a clean, plain text file instead.
if [ -L "$RESOLV_FILE" ]; then
    echo "    Removing symlinked $RESOLV_FILE..."
    rm -f "$RESOLV_FILE"
fi

# Overwrite /etc/resolv.conf with the specified DNS entries
echo "    Writing static configuration to $RESOLV_FILE..."
cat << EOF > "$RESOLV_FILE"
# Generated manually by dnsconfig.sh fallback mechanism
nameserver $DNS_IPV4_PRIMARY
nameserver $DNS_IPV4_SECONDARY
nameserver $DNS_IPV6_PRIMARY
nameserver $DNS_IPV6_SECONDARY
EOF

echo "[SUCCESS] Static DNS written directly to /etc/resolv.conf."
exit 0

