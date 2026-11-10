#!/usr/bin/env sh
# Compatibility entry point; implementation lives in rebuildPatches.py.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/rebuildPatches.py" "$@"
