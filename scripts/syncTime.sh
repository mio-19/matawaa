#!/usr/bin/env bash
#
# syncTime.sh — Synchronize system time and timezone from host to AsteroidOS smartwatch over USB SSH.
#
# Default target: root@172.16.42.1:22
#

set -euo pipefail

HOST="${WATCH_HOST:-172.16.42.1}"
PORT="${WATCH_PORT:-22}"
USER="${WATCH_USER:-root}"
TARGET_TZ=""
SSH_OPTS=(-o "StrictHostKeyChecking=accept-new" -o "ConnectTimeout=5")

usage() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Synchronizes current host time and timezone to an AsteroidOS watch over USB SSH.

Options:
  -h, --host <host>       Target watch hostname or IP (default: 172.16.42.1)
  -p, --port <port>       SSH port (default: 22)
  -u, --user <user>       SSH user (default: root)
  -z, --timezone <tz>     Timezone to set (default: detect from host, e.g. Australia/Canberra)
  --help                  Show this help message

Environment variables:
  WATCH_HOST              Overrides default host
  WATCH_PORT              Overrides default port
  WATCH_USER              Overrides default user
EOF
  exit 0
}

# Parse options
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--host)
      HOST="$2"
      shift 2
      ;;
    -p|--port)
      PORT="$2"
      shift 2
      ;;
    -u|--user)
      USER="$2"
      shift 2
      ;;
    -z|--timezone)
      TARGET_TZ="$2"
      shift 2
      ;;
    --help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

detect_host_timezone() {
  if [ -n "${TZ:-}" ]; then
    echo "$TZ"
    return
  fi
  if command -v timedatectl >/dev/null 2>&1; then
    local tz
    tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
    if [ -n "$tz" ]; then
      echo "$tz"
      return
    fi
  fi
  if [ -f /etc/timezone ]; then
    head -n 1 /etc/timezone && return
  fi
  if [ -L /etc/localtime ]; then
    local link
    link="$(readlink -f /etc/localtime 2>/dev/null || true)"
    if [[ "$link" =~ zoneinfo/(.+) ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi
  date +%Z
}

if [ -z "$TARGET_TZ" ]; then
  TARGET_TZ="$(detect_host_timezone)"
fi

EPOCH="$(date +%s)"
UTC_STR="$(date -u +"%Y-%m-%d %H:%M:%S")"
LOCAL_STR="$(date)"

echo "============================================================"
echo "[*] AsteroidOS Time Synchronization"
echo "    Target:   ${USER}@${HOST}:${PORT}"
echo "    Timezone: ${TARGET_TZ}"
echo "    Time:     ${LOCAL_STR} (${UTC_STR} UTC)"
echo "============================================================"

echo "[*] Connecting to ${USER}@${HOST}:${PORT}..."

# Execute configuration remotely on the watch
ssh -p "$PORT" "${SSH_OPTS[@]}" "${USER}@${HOST}" bash -s -- "$TARGET_TZ" "$EPOCH" "$UTC_STR" << 'REMOTE_EOF'
set -euo pipefail

TARGET_TZ="$1"
TARGET_EPOCH="$2"
TARGET_UTC="$3"

echo "[*] Setting timezone to ${TARGET_TZ}..."

# 1. Update systemd timedatectl timezone if available
if command -v timedatectl >/dev/null 2>&1; then
  timedatectl set-timezone "$TARGET_TZ" 2>/dev/null || true
fi

# 2. Update AsteroidOS timed daemon timezone if timedclient is installed
if command -v timedclient-qt6 >/dev/null 2>&1; then
  timedclient-qt6 --set-info="timezoneManual=${TARGET_TZ}" 2>/dev/null || true
elif command -v timedclient >/dev/null 2>&1; then
  timedclient --set-info="timezoneManual=${TARGET_TZ}" 2>/dev/null || true
fi

# 3. Direct symlink fallback for /etc/localtime
for tzdir in /etc/zoneinfo /usr/share/zoneinfo /nix/var/nix/profiles/system/sw/share/zoneinfo; do
  if [ -f "${tzdir}/${TARGET_TZ}" ]; then
    ln -sfn "${tzdir}/${TARGET_TZ}" /etc/localtime 2>/dev/null || true
    break
  fi
done

echo "[*] Setting system clock to ${TARGET_UTC} UTC (epoch: ${TARGET_EPOCH})..."

# 4. Set kernel wall-clock time
if ! date -s "@${TARGET_EPOCH}" 2>/dev/null; then
  date -u -s "${TARGET_UTC}" 2>/dev/null || true
fi

# 5. Notify AsteroidOS timed daemon of manual time update
if command -v timedclient-qt6 >/dev/null 2>&1; then
  timedclient-qt6 --set-info="timeManual=${TARGET_EPOCH}" 2>/dev/null || true
elif command -v timedclient >/dev/null 2>&1; then
  timedclient --set-info="timeManual=${TARGET_EPOCH}" 2>/dev/null || true
fi

# 6. Synchronize hardware RTC if available
if command -v hwclock >/dev/null 2>&1; then
  hwclock --systohc 2>/dev/null || true
fi

echo "[+] Watch time synchronized successfully:"
echo "    Watch Time: $(date)"
echo "    Timezone:   $(date +%Z)"
REMOTE_EOF

echo "[+] Done."
