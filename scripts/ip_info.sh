#!/usr/bin/env bash

echo "=========================================="
echo "          Network IP Information          "
echo "=========================================="

# Fetch Local IP Addresses                                        
echo -e "\n[Local IP Addresses]"
LOCAL_IPS_FOUND=false

if command -v hostname &>/dev/null && hostname -I &>/dev/null; then
    # GNU Linux hostname -I
    hostname -I | tr ' ' '\n' | awk '/:/ {print "IPV6:" $0} /\./ {print "IPV4:" $0}'
    LOCAL_IPS_FOUND=true
elif command -v ip &>/dev/null; then
    # Fallback using iproute2 (ip)
    ip -o addr show | awk '{split($4, a, "/"); if ($3 == "inet" && a[1] != "127.0.0.1") print "IPV4:" a[1]; else if ($3 == "inet6" && a[1] != "::1") print "IPV6:" a[1]}'
    LOCAL_IPS_FOUND=true
elif command -v ifconfig &>/dev/null; then
    # Fallback for macOS / BSD / systems without ip command
    ifconfig | awk '/inet / {if ($2 != "127.0.0.1") print "IPV4:" $2} /inet6 / {if ($2 != "::1" && $2 != "fe80::1%lo0") print "IPV6:" $2}'
    LOCAL_IPS_FOUND=true
elif command -v python3 &>/dev/null; then
    # In-house Python socket fallback
    py_ips=$(python3 -c "
import socket
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.2)
        s.connect(('1.1.1.1', 80))
        print('IPV4:' + s.getsockname()[0])
except Exception:
    pass
" 2>/dev/null || true)
    if [ -n "$py_ips" ]; then
        echo "$py_ips"
        LOCAL_IPS_FOUND=true
    fi
fi

if [ "$LOCAL_IPS_FOUND" = false ]; then
    echo "Could not fetch local IP addresses."
fi

# Fetch Public IP Address
echo -e "\n[Public IP Address]"
public_ip=""
fourip=""
sixip=""

fetch_ip() {
    local url="$1"
    if command -v curl &>/dev/null; then
        curl -s -m 3 "$url" 2>/dev/null || true
    elif command -v wget &>/dev/null; then
        wget -qO- -t 1 -T 3 "$url" 2>/dev/null || true
    elif command -v python3 &>/dev/null; then
        python3 -c "import urllib.request; req=urllib.request.Request('$url', headers={'User-Agent': 'curl/7.88.1'}); print(urllib.request.urlopen(req, timeout=3).read().decode('utf-8').strip())" 2>/dev/null || true
    fi
}

# Fetch IPv4 from dedicated plain-text endpoints (never returns HTML)
raw_v4=$(fetch_ip "https://api.ipify.org")
[ -z "$raw_v4" ] && raw_v4=$(fetch_ip "https://ifconfig.me/ip")

# Strictly validate that response is an IPv4 address and not HTML
if echo "$raw_v4" | grep -Eq '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
    fourip="$raw_v4"
fi

# Fetch IPv6 from dedicated endpoint
raw_v6=$(fetch_ip "https://api6.ipify.org")
[ -z "$raw_v6" ] && raw_v6=$(fetch_ip "https://icanhazip.com")

# Strictly validate that response is an IPv6 address and not HTML
if echo "$raw_v6" | grep -Eq '^[0-9a-fA-F:]+$' && [[ "$raw_v6" == *:* ]]; then
    sixip="$raw_v6"
fi

[ -n "$fourip" ] && public_ip+="IPV4: $fourip\n"
[ -n "$sixip" ] && public_ip+="IPV6: $sixip\n"

if [ -z "$public_ip" ]; then
    echo "Could not fetch public IP (Check internet connection)"
else
    printf "%b" "$public_ip"
fi

echo "=========================================="
