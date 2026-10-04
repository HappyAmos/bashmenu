#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: ping.sh
# DESCRIPTION: Cross-platform ping utility wrapper with unprivileged fallback
#              for minimal containers and BusyBox environments (e.g. Alpine).
# ==============================================================================

TARGET="${1:-1.1.1.1}"
COUNT="${2:-4}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Resolve Python interpreter
PYTHON_BIN=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python3" ]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python3"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python3" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
fi

# Attempt native system ping
output=$(ping -c "$COUNT" "$TARGET" 2>&1)
ret=$?

if [ $ret -eq 0 ]; then
    echo "$output"
    exit 0
fi

# Check if failure was due to raw socket permission denial (BusyBox / container restriction)
if echo "$output" | grep -qiE "permission denied|not permitted|are you root"; then
    # Attempt privilege escalation if sudo or doas is available
    if [ "$(id -u)" != "0" ]; then
        if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
            if sudo ping -c "$COUNT" "$TARGET"; then
                exit 0
            fi
        elif command -v doas >/dev/null 2>&1 && doas -n true 2>/dev/null; then
            if doas ping -c "$COUNT" "$TARGET"; then
                exit 0
            fi
        fi
    fi

    echo "$output"
    echo ""
    echo "------------------------------------------------------------------"
    echo "Notice: System ICMP ping denied raw socket access."
    if command -v apk >/dev/null 2>&1; then
        echo "Tip: Install native unprivileged ping on Alpine via: apk add iputils"
    fi
    echo "Falling back to unprivileged TCP latency probe..."
    echo "------------------------------------------------------------------"

    if [ -n "$PYTHON_BIN" ]; then
        "$PYTHON_BIN" -c '
import socket, time, sys

host = sys.argv[1]
try:
    count = int(sys.argv[2])
except (IndexError, ValueError):
    count = 4

# Probe for responsive port (HTTPS 443, HTTP 80, DNS 53, SSH 22)
probe_ports = [443, 80, 53, 22]
target_port = 80
for p in probe_ports:
    try:
        s = socket.create_connection((host, p), timeout=1.0)
        s.close()
        target_port = p
        break
    except Exception:
        pass

print(f"Pinging {host} via port {target_port} (TCP handshake latency):")
successful = 0
times = []

for i in range(count):
    t0 = time.time()
    try:
        s = socket.create_connection((host, target_port), timeout=2.0)
        s.close()
        ms = (time.time() - t0) * 1000
        times.append(ms)
        successful += 1
        print(f"Reply from {host}: seq={i+1} time={ms:.2f} ms")
    except Exception as e:
        print(f"Timeout connecting to {host}: seq={i+1} ({e})")
    if i < count - 1:
        time.sleep(0.5)

loss = ((count - successful) / count) * 100
print(f"\n--- {host} ping statistics ---")
print(f"{count} packets transmitted, {successful} received, {loss:.0f}% packet loss")
if times:
    print(f"round-trip min/avg/max = {min(times):.2f}/{sum(times)/len(times):.2f}/{max(times):.2f} ms")
' "$TARGET" "$COUNT"
    fi
    exit 0
else
    echo "$output"
    exit $ret
fi
