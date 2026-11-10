#!/usr/bin/env sh
# Compatibility entry point; implementation lives in applyPatches.py.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/applyPatches.py" "$@"
