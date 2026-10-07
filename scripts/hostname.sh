#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: hostname.sh
# DESCRIPTION: Hostname and system identity discovery tool. Reports hostname,
#              FQDN/domain, kernel, architecture, OS distribution, and container.
# ==============================================================================

echo "=========================================="
echo "          Hostname Information            "
echo "=========================================="

# 1. Resolve Hostname
host=""
if command -v hostname >/dev/null 2>&1; then
    host=$(hostname 2>/dev/null)
fi
if [ -z "$host" ] && [ -r "/proc/sys/kernel/hostname" ]; then
    host=$(cat /proc/sys/kernel/hostname 2>/dev/null)
fi
if [ -z "$host" ]; then
    host=$(uname -n 2>/dev/null || echo "${HOSTNAME:-unknown}")
fi
echo "Hostname:         $host"

# 2. Resolve Domain / FQDN (if available)
fqdn=""
if command -v hostname >/dev/null 2>&1; then
    fqdn=$(hostname -f 2>/dev/null || hostname -d 2>/dev/null || true)
fi
if [ -z "$fqdn" ] || [ "$fqdn" = "$host" ]; then
    if [ -r "/proc/sys/kernel/domainname" ]; then
        dom=$(cat /proc/sys/kernel/domainname 2>/dev/null)
        [ -n "$dom" ] && [ "$dom" != "(none)" ] && [ "$dom" != "$host" ] && fqdn="${host}.${dom}"
    fi
fi
if [ -n "$fqdn" ] && [ "$fqdn" != "$host" ] && [ "$fqdn" != "(none)" ]; then
    echo "Domain / FQDN:    $fqdn"
fi

# 3. Kernel & Architecture
echo "Kernel:           $(uname -s 2>/dev/null) $(uname -r 2>/dev/null)"
echo "Architecture:     $(uname -m 2>/dev/null)"

# 4. OS Distribution Identification
if [ -f /etc/os-release ]; then
    os_name=$(grep -E '^PRETTY_NAME=' /etc/os-release 2>/dev/null | head -n 1 | cut -d= -f2- | tr -d '"')
    [ -n "$os_name" ] && echo "Operating System: $os_name"
elif [ -f /etc/lsb-release ]; then
    os_name=$(grep -E '^DISTRIB_DESCRIPTION=' /etc/lsb-release 2>/dev/null | head -n 1 | cut -d= -f2- | tr -d '"')
    [ -n "$os_name" ] && echo "Operating System: $os_name"
elif command -v sw_vers >/dev/null 2>&1; then
    echo "Operating System: $(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null)"
fi

# 5. Container Environment (if applicable)
if [ -n "$container" ]; then
    echo "Container:        $container"
elif [ -f /.dockerenv ]; then
    echo "Container:        docker"
fi

echo "=========================================="
