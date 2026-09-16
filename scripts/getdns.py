#!/usr/bin/env python3
"""
getdns.py - Universal Upstream DNS Server Discovery Tool

Retrieves and displays real upstream IPv4 and IPv6 DNS servers on Linux systems
by querying resolvectl, NetworkManager (nmcli), systemd runtime resolv.conf
stubs, and /etc/resolv.conf.
"""

import argparse
import json

__version__ = "0.0.1"
__author__ = "HappyAmos"
import os
import re
import shutil
import subprocess


def is_loopback(ip_str):
    """Return True if IP address is a local loopback resolver address."""
    ip = ip_str.strip().lower()
    return ip.startswith("127.") or ip == "::1" or ip == "localhost"


def get_resolvectl_dns():
    """Query systemd-resolved via resolvectl or systemd-resolve."""
    bin_path = shutil.which("resolvectl") or shutil.which("systemd-resolve")
    if not bin_path:
        return None

    try:
        cmd = [bin_path, "status"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode != 0 or not res.stdout:
            return None

        dns_map = {}
        current_iface = "Global"

        for line in res.stdout.splitlines():
            line_str = line.strip()

            # Match interface header (e.g. "Link 2 (eth0):")
            if_match = re.search(r"Link\s+\d+\s*\(([^)]+)\)", line_str)
            if if_match:
                current_iface = if_match.group(1)

            if "DNS Servers:" in line_str or "Current DNS Server:" in line_str:
                parts = line_str.split(":", 1)
                if len(parts) == 2:
                    servers = parts[1].split()
                    for s in servers:
                        s_clean = s.strip()
                        if s_clean and not is_loopback(s_clean):
                            dns_map.setdefault(current_iface, []).append(
                                s_clean
                            )
            elif line_str.startswith("DNS:") or line_str.startswith(
                "Protocols:"
            ):
                pass
            elif re.match(r"^[\da-fA-F:\.]+$", line_str) and not is_loopback(
                line_str
            ):
                # Handles multi-line DNS server continuation entries
                dns_map.setdefault(current_iface, []).append(line_str)

        return dns_map if dns_map else None
    except Exception:
        return None


def get_nmcli_dns():
    """Query NetworkManager via nmcli dev show."""
    bin_path = shutil.which("nmcli")
    if not bin_path:
        return None

    try:
        cmd = [bin_path, "dev", "show"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
        )
        if res.returncode != 0 or not res.stdout:
            return None

        dns_map = {}
        current_iface = "Unknown"

        for line in res.stdout.splitlines():
            parts = [p.strip() for p in line.split(":", 1)]
            if len(parts) < 2:
                continue

            key, val = parts[0], parts[1]
            if key == "GENERAL.DEVICE":
                current_iface = val
            elif "IP4.DNS" in key or "IP6.DNS" in key:
                if val and not is_loopback(val):
                    dns_map.setdefault(current_iface, []).append(val)

        return dns_map if dns_map else None
    except Exception:
        return None


def parse_resolv_file(filepath):
    """Parse nameserver entries from a resolv.conf format file."""
    if not os.path.exists(filepath):
        return []

    servers = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str.startswith("nameserver"):
                    parts = line_str.split()
                    if len(parts) >= 2:
                        ip = parts[1].strip()
                        if ip and not is_loopback(ip) and ip not in servers:
                            servers.append(ip)
    except Exception:
        pass
    return servers


def get_upstream_resolv_files():
    """Check runtime resolv.conf files managed by network services."""
    runtime_files = [
        ("/run/systemd/resolve/resolv.conf", "systemd-resolved Upstream"),
        ("/run/NetworkManager/resolv.conf", "NetworkManager Upstream"),
        ("/run/connman/resolv.conf", "ConnMan Upstream"),
    ]

    results = {}
    for path, label in runtime_files:
        servers = parse_resolv_file(path)
        if servers:
            results[label] = servers
    return results


def collect_dns_data():
    """Collect DNS servers across discovery sources into structured data."""
    results = []

    # Method 1: Query systemd-resolved
    resolvectl_data = get_resolvectl_dns()
    if resolvectl_data:
        for iface, servers in resolvectl_data.items():
            unique_servers = list(dict.fromkeys(servers))
            if unique_servers:
                results.append({
                    "source": "systemd-resolved",
                    "interface": iface,
                    "servers": unique_servers,
                })

    # Method 2: Query NetworkManager
    nmcli_data = get_nmcli_dns()
    if nmcli_data:
        for iface, servers in nmcli_data.items():
            unique_servers = list(dict.fromkeys(servers))
            if unique_servers:
                results.append({
                    "source": "NetworkManager",
                    "interface": iface,
                    "servers": unique_servers,
                })

    # Method 3: Check runtime resolv.conf files
    runtime_data = get_upstream_resolv_files()
    if runtime_data:
        for label, servers in runtime_data.items():
            unique_servers = list(dict.fromkeys(servers))
            if unique_servers:
                results.append({
                    "source": label,
                    "interface": "N/A",
                    "servers": unique_servers,
                })

    # Method 4: Fallback to /etc/resolv.conf
    etc_servers = parse_resolv_file("/etc/resolv.conf")
    if etc_servers:
        unique_servers = list(dict.fromkeys(etc_servers))
        if unique_servers:
            results.append({
                "source": "/etc/resolv.conf",
                "interface": "N/A",
                "servers": unique_servers,
            })

    return results


def main():
    """
    Parse command-line arguments, trigger DNS discovery, and format output.
    Supports custom formats like TSV (--parse) and JSON (--json).
    """
    parser = argparse.ArgumentParser(
        description="Universal Upstream DNS Server Discovery Tool"
    )
    parser.add_argument(
        "-p",
        "--parse",
        action="store_true",
        help="output machine-parsable TSV format (source\\tiface\\tip)",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="output discovery results in JSON format",
    )

    args = parser.parse_args()
    dns_data = collect_dns_data()

    if args.json:
        print(json.dumps(dns_data, indent=2))
        return

    if args.parse:
        for entry in dns_data:
            source = entry["source"]
            iface = entry["interface"]
            for server in entry["servers"]:
                print(f"{source}\t{iface}\t{server}")
        return

    print("==================================================")
    print("          ACTIVE UPSTREAM DNS DISCOVERY           ")
    print("==================================================\n")

    if not dns_data:
        print("[-] Notice: Only local loopback resolver stubs (127.0.0.1 / 127.0.0.53)")
        print("    were detected in /etc/resolv.conf, and no active network managers")
        print("    reported upstream DNS servers.")
        return

    for entry in dns_data:
        source = entry["source"]
        iface = entry["interface"]
        servers = entry["servers"]

        if iface != "N/A":
            print(f"[+] Source: {source}")
            print(f"    Interface: {iface}")
        else:
            print(f"[+] Source: {source}")

        for s in servers:
            indent = "      " if iface != "N/A" else "    "
            print(f"{indent}- {s}")
        print()


if __name__ == "__main__":
    main()
