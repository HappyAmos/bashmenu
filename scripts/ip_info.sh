#!/usr/bin/env bash

echo "=========================================="
echo "          Network IP Information          "
echo "=========================================="

# Fetch Local IP Addresses                                        
echo -e "\n[Local IP Addresses]"                                     
if command -v hostname &>/dev/null; then                             
    # Quickest method on most modern Linux systems                   
    hostname -I | tr ' ' '\n' | awk '/:/ {print "IPV6:" $0} /\./ {print "IPV4:" $0}'
else                                                                 
    # Fallback using the ip command for both IPv4 and IPv6
    ip -o addr show | awk '{split($4, a, "/"); if ($3 == "inet") print "IPV4:" a[1]; else if ($3 == "inet6") print "IPV6:" a[1]}'
fi                                                                   

# Fetch Public IP Address
echo -e "\n[Public IP Address]"
# Uses an external service to check your internet-facing IP
if command -v curl &>/dev/null; then
    fourip="$(curl -s -4 https://ifconfig.me)"
    sixip="$(curl -s -6 https://icanhazip.com)"
    public_ip="IPV4: $fourip \nIPV6: $sixip"
elif command -v wget &>/dev/null; then
    public_ip=$(wget -qO- https://ifconfig.me)
fi

if [ -z "$public_ip" ]; then
    echo "Could not fetch public IP (Check internet connection)"
else
    printf "$public_ip\n"
fi

echo "=========================================="
