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
fi

if [ "$LOCAL_IPS_FOUND" = false ]; then
    echo "Could not fetch local IP addresses."
fi

# Fetch Public IP Address
echo -e "\n[Public IP Address]"
public_ip=""
if command -v curl &>/dev/null; then
    fourip="$(curl -s -m 3 -4 https://ifconfig.me 2>/dev/null || true)"
    sixip="$(curl -s -m 3 -6 https://icanhazip.com 2>/dev/null || true)"
    [ -n "$fourip" ] && public_ip+="IPV4: $fourip\n"
    [ -n "$sixip" ] && public_ip+="IPV6: $sixip\n"
elif command -v wget &>/dev/null; then
    fourip=$(wget -qO- -t 1 -T 3 https://ifconfig.me 2>/dev/null || true)
    [ -n "$fourip" ] && public_ip+="IPV4: $fourip\n"
fi

if [ -z "$public_ip" ]; then
    echo "Could not fetch public IP (Check internet connection)"
else
    printf "%b" "$public_ip"
fi

echo "=========================================="
