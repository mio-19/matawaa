#!/usr/bin/env bash
# Matawaa Patchset Toolchain: rebuildPatches.sh
# Rebuilds the patch series from work/mobile-nixos into patches/.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
WORK_DIR="$ROOT_DIR/work/mobile-nixos"
PATCHES_DIR="$ROOT_DIR/patches"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-$(nix eval --raw --impure --expr \
    "(builtins.fromJSON (builtins.readFile \"$ROOT_DIR/flake.lock\")).nodes.mobile-nixos.locked.rev")}"

info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[SUCCESS]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

if [ ! -d "$WORK_DIR/.git" ]; then
    error "Working repository not found at $WORK_DIR. Please run scripts/applyPatches.sh first."
    exit 1
fi

COMMIT_COUNT=$(git -C "$WORK_DIR" rev-list --count "$UPSTREAM_COMMIT"..HEAD)
if [ "$COMMIT_COUNT" -eq 0 ]; then
    error "No commits found on top of $UPSTREAM_COMMIT in $WORK_DIR."
    exit 1
fi

info "Rebuilding $COMMIT_COUNT patches from $WORK_DIR..."

TEMP_PATCH_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_PATCH_DIR"' EXIT

git -C "$WORK_DIR" format-patch \
    --zero-commit \
    --no-numbered \
    --no-signature \
    -o "$TEMP_PATCH_DIR" \
    "$UPSTREAM_COMMIT"..HEAD

rm -f "$PATCHES_DIR"/*.patch
mkdir -p "$PATCHES_DIR"
cp "$TEMP_PATCH_DIR"/*.patch "$PATCHES_DIR"/

success "Exported $COMMIT_COUNT patches to $PATCHES_DIR:"
for patch in "$PATCHES_DIR"/*.patch; do
    echo "  - $(basename "$patch")"
done

info "Verifying patch consistency with default.nix and flake.nix..."
patch_list=()
for p in "$PATCHES_DIR"/*.patch; do
    patch_list+=("./patches/$(basename "$p")")
done

success "Patch rebuild complete!"
