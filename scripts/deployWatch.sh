#!/usr/bin/env bash
#
# deployWatch.sh — Deploy or upgrade AsteroidOS NixOS systems on smartwatches over-the-air
#
# Wrapper around scripts/deployWatch.py for safe, atomic, over-the-air deployments.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 2>/dev/null || echo "")"

if [ -z "$PYTHON_BIN" ]; then
  echo "Error: python3 is required to run deployWatch. Please install Python 3." >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/deployWatch.py" "$@"
