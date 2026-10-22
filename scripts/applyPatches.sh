#!/usr/bin/env bash
# Matawaa Patchset Toolchain: applyPatches.sh
# Applies the patch series onto upstream mobile-nixos in work/mobile-nixos.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
WORK_DIR="$ROOT_DIR/work/mobile-nixos"
PATCHES_DIR="$ROOT_DIR/patches"

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/NixOS/mobile-nixos.git}"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-$(nix eval --raw --impure --expr \
    "(builtins.fromJSON (builtins.readFile \"$ROOT_DIR/flake.lock\")).nodes.mobile-nixos.locked.rev")}"
BRANCH_NAME="matawaa-work"

# Color helpers
info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

mkdir -p "$ROOT_DIR/work"

if [ ! -d "$WORK_DIR/.git" ]; then
    info "Worktree not found. Initializing upstream mobile-nixos in $WORK_DIR..."
    git clone "$UPSTREAM_URL" "$WORK_DIR"
fi

info "Checking out base upstream commit $UPSTREAM_COMMIT..."
git -C "$WORK_DIR" fetch origin "$UPSTREAM_COMMIT" 2>/dev/null || true
git -C "$WORK_DIR" checkout -B "$BRANCH_NAME" "$UPSTREAM_COMMIT"
git -C "$WORK_DIR" reset --hard "$UPSTREAM_COMMIT"
git -C "$WORK_DIR" clean -fdx

info "Applying patchset from $PATCHES_DIR..."

PATCH_COUNT=0
for patch in "$PATCHES_DIR"/*.patch; do
    [ -f "$patch" ] || continue
    patch_name="$(basename "$patch")"
    info "Applying $patch_name..."
    if ! git -C "$WORK_DIR" am --3way --ignore-whitespace "$patch" 2>/dev/null; then
        warn "Direct git-am encountered an issue, trying with fallback 3-way application..."
        if ! git -C "$WORK_DIR" apply --3way "$patch" && git -C "$WORK_DIR" commit -a -C HEAD@{1} 2>/dev/null; then
            error "Failed to apply patch: $patch_name"
            error "Resolve conflict in $WORK_DIR and run 'git am --continue', or run 'git am --abort'."
            exit 1
        fi
    fi
    PATCH_COUNT=$((PATCH_COUNT + 1))
done

success "Successfully applied $PATCH_COUNT patches to $WORK_DIR on branch $BRANCH_NAME."
info "You can now edit code in $WORK_DIR, commit changes, and run scripts/rebuildPatches.sh."
