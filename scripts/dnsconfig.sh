#!/usr/bin/env bash
# Version: 0.0.2
# Author:  HappyAmos

# ==============================================================================
# SCRIPT: dnsconfig.sh
# DESCRIPTION: Automatically detects the active network management tool on
#              Linux systems (Debian/Ubuntu, Fedora/RHEL, Arch, openSUSE) and macOS,
#              and configures IPv4 & IPv6 DNS.
# FALLBACK: Directly edits /etc/resolv.conf if no manager is available.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status during critical operations
set -e

# ------------------------------------------------------------------------------
# 1. ENVIRONMENT CHECK (Termux / WSL)
# ------------------------------------------------------------------------------
if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"/com.termux/"* ]] || grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Notice: Global DNS configuration requires systemd-resolved or NetworkManager, which are not used natively in Termux or WSL."
    echo "Skipping DNS configuration."
    exit 0
fi

# ------------------------------------------------------------------------------
# 2. PRIVILEGE CHECK
# ------------------------------------------------------------------------------
# Network configuration requires root (administrator) privileges.
if [ "$(id -u)" -ne 0 ] && [ "$(uname)" != "Darwin" ]; then
  echo "Error: This script must be run as root (use sudo)." >&2
  exit 1
fi

echo "Starting DNS configuration..."

# ------------------------------------------------------------------------------
# 3. Argument Check & Assignment
# ------------------------------------------------------------------------------
# Verify that we are working with correct ipv4 and ipv6 parameters

is_ipv4() {
    local ip="$1"
    local regex='^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    [[ "$ip" =~ $regex ]]
}

is_ipv6() {
    local ip="$1"
    local regex='^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$'
    [[ "$ip" =~ $regex ]]
}

if [ "$#" -ne 4 ]; then
    echo "Error: Exactly 4 parameters are required (2x IPv4, 2x IPv6)." >&2
    echo "Usage: $0 <IPv4_1> <IPv4_2> <IPv6_1> <IPv6_2>" >&2
    exit 1
fi

if ! is_ipv4 "$1" || ! is_ipv4 "$2"; then
    echo "Error: Invalid IPv4 address provided." >&2
    exit 1
fi

if ! is_ipv6 "$3" || ! is_ipv6 "$4"; then
    echo "Error: Invalid IPv6 address provided." >&2
    exit 1
fi

DNS_IPV4_PRIMARY="$1"
DNS_IPV4_SECONDARY="$2"
DNS_IPV6_PRIMARY="$3"
DNS_IPV6_SECONDARY="$4"

echo "Parameters passed:"
echo "    IPv4 Primary:   $DNS_IPV4_PRIMARY"
echo "    IPv4 Secondary: $DNS_IPV4_SECONDARY"
echo "    IPv6 Primary:   $DNS_IPV6_PRIMARY"
echo "    IPv6 Secondary: $DNS_IPV6_SECONDARY"

# ------------------------------------------------------------------------------
# METHOD 0: macOS networksetup
# ------------------------------------------------------------------------------
if [ "$(uname)" = "Darwin" ] && command -v networksetup >/dev/null 2>&1; then
    echo "[+] Detected: macOS networksetup utility."
    SERVICE=$(networksetup -listallnetworkservices | grep -v '\*' | head -n1 || true)
    if [ -n "$SERVICE" ]; then
        echo "    Configuring DNS on active service: '$SERVICE'..."
        networksetup -setdnsservers "$SERVICE" "$DNS_IPV4_PRIMARY" "$DNS_IPV4_SECONDARY" "$DNS_IPV6_PRIMARY" "$DNS_IPV6_SECONDARY"
        echo "[SUCCESS] DNS configured via macOS networksetup."
        exit 0
    fi
fi

# ------------------------------------------------------------------------------
# METHOD 1: NetworkManager (nmcli)
# ------------------------------------------------------------------------------
if command -v nmcli >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager; then
    echo "[+] Detected: NetworkManager is active."
    ACTIVE_CONN=$(nmcli -t -f NAME,TYPE connection show --active | grep -v '^lo:' | head -n1 | cut -d: -f1)

    if [ -n "$ACTIVE_CONN" ]; then
        echo "    Configuring active connection: '$ACTIVE_CONN'"
        nmcli connection modify "$ACTIVE_CONN" ipv4.dns "$DNS_IPV4_PRIMARY $DNS_IPV4_SECONDARY"
        nmcli connection modify "$ACTIVE_CONN" ipv4.ignore-auto-dns yes
        nmcli connection modify "$ACTIVE_CONN" ipv6.dns "$DNS_IPV6_PRIMARY $DNS_IPV6_SECONDARY"
        nmcli connection modify "$ACTIVE_CONN" ipv6.ignore-auto-dns yes
        echo "    Reapplying network connection..."
        nmcli connection up "$ACTIVE_CONN" >/dev/null

        echo "[SUCCESS] DNS configured via NetworkManager."
        exit 0
    fi
fi

# ------------------------------------------------------------------------------
# METHOD 2: systemd-resolved (resolvctl)
# ------------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet systemd-resolved; then
    echo "[+] Detected: systemd-resolved is active."
    RESOLVED_CONF="/etc/systemd/resolved.conf"
    echo "    Updating $RESOLVED_CONF..."
    [ ! -f "${RESOLVED_CONF}.bak" ] && cp "$RESOLVED_CONF" "${RESOLVED_CONF}.bak"

    sed -i '/^DNS=/d' "$RESOLVED_CONF"
    sed -i '/^FallbackDNS=/d' "$RESOLVED_CONF"
    echo "DNS=$DNS_IPV4_PRIMARY $DNS_IPV4_SECONDARY $DNS_IPV6_PRIMARY $DNS_IPV6_SECONDARY" >> "$RESOLVED_CONF"

    echo "    Restarting systemd-resolved..."
    systemctl restart systemd-resolved

    echo "[SUCCESS] DNS configured via systemd-resolved."
    exit 0
fi

# ------------------------------------------------------------------------------
# METHOD 3: resolvconf package
# ------------------------------------------------------------------------------
if command -v resolvconf >/dev/null 2>&1; then
    echo "[+] Detected: resolvconf utility."
    HEAD_FILE="/etc/resolvconf/resolv.conf.d/head"
    mkdir -p /etc/resolvconf/resolv.conf.d/
    echo "    Injecting DNS servers into $HEAD_FILE..."
    sed -i '/nameserver/d' "$HEAD_FILE"
    {
        echo "nameserver $DNS_IPV4_PRIMARY"
        echo "nameserver $DNS_IPV4_SECONDARY"
        echo "nameserver $DNS_IPV6_PRIMARY"
        echo "nameserver $DNS_IPV6_SECONDARY"
    } >> "$HEAD_FILE"
    resolvconf -u
    echo "[SUCCESS] DNS configured via resolvconf."
    exit 0
fi

# ------------------------------------------------------------------------------
# METHOD 4: Direct Fallback (/etc/resolv.conf)
# ------------------------------------------------------------------------------
echo "[!] WARNING: No active network manager detected. Falling back to direct modification of /etc/resolv.conf."
RESOLV_FILE="/etc/resolv.conf"

if [ -L "$RESOLV_FILE" ]; then
    echo "    Removing symlinked $RESOLV_FILE..."
    rm -f "$RESOLV_FILE"
fi

cat << EOF > "$RESOLV_FILE"
# Generated manually by dnsconfig.sh fallback mechanism
nameserver $DNS_IPV4_PRIMARY
nameserver $DNS_IPV4_SECONDARY
nameserver $DNS_IPV6_PRIMARY
nameserver $DNS_IPV6_SECONDARY
EOF

echo "[SUCCESS] Static DNS written directly to /etc/resolv.conf."
exit 0
