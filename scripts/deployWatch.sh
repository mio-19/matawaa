#!/usr/bin/env bash
#
# deployWatch.sh — Deploy or upgrade AsteroidOS NixOS systems on smartwatches over-the-air
#
# Supports multiple deployment backends:
#   1. copy (default): builds the cross-compiled system toplevel locally, transfers
#      the closure via nix-copy-closure, and remotely switches the running watch.
#   2. nixos-rebuild: standard NixOS rebuild invocation via Flakes and remote sudo.
#   3. deploy-rs: uses deploy-rs for atomic Flake-based profile deployments.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
DEVICE="fossil-hoki"
TARGET_HOST="172.16.42.1"
SSH_USER="ceres"
ACTION="boot"
METHOD="copy"
DRY_RUN=false
PORT="22"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Deploy or upgrade a running AsteroidOS smartwatch over USB networking or Wi-Fi.
By default, the new system configuration is activated as 'boot' (staged for next
startup) to avoid abruptly terminating the running Lipstick compositor, hybris
display services, or USB gadget networking session mid-switch.

Options:
  -d, --device <name>     Target smartwatch device (default: $DEVICE)
                          Examples: fossil-hoki, oppo-beluga
  -t, --target <host>     Target IP or hostname of the watch (default: $TARGET_HOST)
  -p, --port <port>       SSH port on the watch (default: $PORT)
  -u, --user <user>       SSH user on the watch (default: $SSH_USER)
  -a, --action <action>   Activation action: boot | switch | test | dry-activate (default: $ACTION)
  -m, --method <method>   Deployment method: copy | nixos-rebuild | deploy-rs (default: $METHOD)
  -n, --dry-run           Build/evaluate configuration without copying or activating
  -h, --help              Show this help message

Methods:
  copy          (Recommended) Local cross-build + nix-copy-closure + remote activation.
                Extremely lightweight, does not require Flakes or nix-daemon on the watch.
  nixos-rebuild Standard nixos-rebuild boot/switch --flake .#<device> --target-host ...
  deploy-rs     Declarative deploy-rs multi-profile runner via Flakes.

Examples:
  # Deploy full AsteroidOS UI desktop to watch (staged for next boot)
  $(basename "$0")

  # Deploy to Fossil Gen 6 over Wi-Fi
  $(basename "$0") --device fossil-hoki --target 192.168.1.150

  # Immediately switch running services in-place
  $(basename "$0") --action switch

  # Test configuration without permanently setting the bootloader entry
  $(basename "$0") --action test

  # Deploy using deploy-rs
  $(basename "$0") --method deploy-rs
EOF
  exit 0
}

# Parse command line options
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--device)
      DEVICE="$2"
      shift 2
      ;;
    -t|--target)
      TARGET_HOST="$2"
      shift 2
      ;;
    -p|--port)
      PORT="$2"
      shift 2
      ;;
    -u|--user)
      SSH_USER="$2"
      shift 2
      ;;
    -a|--action)
      ACTION="$2"
      shift 2
      ;;
    -m|--method)
      METHOD="$2"
      shift 2
      ;;
    -n|--dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Error: Unknown option '$1'" >&2
      usage
      ;;
  esac
done

# Validate action
case "$ACTION" in
  switch|boot|test|dry-activate) ;;
  *)
    echo "Error: Invalid action '$ACTION'. Must be one of: switch, boot, test, dry-activate." >&2
    exit 1
    ;;
esac

# Validate method
case "$METHOD" in
  copy|nixos-rebuild|deploy-rs) ;;
  *)
    echo "Error: Invalid method '$METHOD'. Must be one of: copy, nixos-rebuild, deploy-rs." >&2
    exit 1
    ;;
esac

cd "$REPO_ROOT"

echo "============================================================"
echo " AsteroidOS Smartwatch OTA Deployment Tool"
echo "============================================================"
echo " Device:    $DEVICE"
echo " Target:    $SSH_USER@$TARGET_HOST:$PORT"
echo " Action:    $ACTION"
echo " Method:    $METHOD"
echo " Dry run:   $DRY_RUN"
echo "============================================================"

# Pre-flight check: ensure target host is reachable via SSH unless dry-run
check_connectivity() {
  echo "[*] Checking SSH connectivity to $SSH_USER@$TARGET_HOST:$PORT..."
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -p "$PORT" "$SSH_USER@$TARGET_HOST" true 2>/dev/null; then
    echo "[!] Note: Batch SSH authentication failed or target is unreachable."
    echo "    Continuing with interactive SSH / password prompt ('1234' is default for 'ceres')."
  else
    echo "[+] SSH connection established successfully."
  fi
}

deploy_copy() {
  echo "[*] Building cross-compiled AsteroidOS desktop toplevel for $DEVICE..."
  if [ -d "$REPO_ROOT/work/mobile-nixos/examples/asteroid" ]; then
    TOPLEVEL="$(nix-build "$REPO_ROOT/work/mobile-nixos/examples/asteroid" \
      --argstr device "$DEVICE" \
      -A config.system.build.toplevel \
      --no-link)"
  else
    TOPLEVEL="$(nix build "$REPO_ROOT#nixosConfigurations.$DEVICE.config.system.build.toplevel" --no-link --print-out-paths)"
  fi

  echo "[+] Built full AsteroidOS desktop toplevel: $TOPLEVEL"

  if [ "$DRY_RUN" = true ]; then
    echo "[*] Dry run requested. Built closure ready; skipping transmission and activation."
    return 0
  fi

  check_connectivity

  echo "[*] Copying system closure to $SSH_USER@$TARGET_HOST..."
  NIX_SSHOPTS="-p $PORT -o StrictHostKeyChecking=accept-new" \
    nix-copy-closure --to "$SSH_USER@$TARGET_HOST" "$TOPLEVEL"

  echo "[*] Activating configuration ($ACTION) on target watch..."
  # If connected as non-root user (e.g. ceres), invoke with sudo
  if [ "$SSH_USER" = "root" ]; then
    SUDO_CMD=""
  else
    SUDO_CMD="sudo"
  fi

  ssh -p "$PORT" -o StrictHostKeyChecking=accept-new -t "$SSH_USER@$TARGET_HOST" \
    "$SUDO_CMD nix-env -p /nix/var/nix/profiles/system --set $TOPLEVEL && $SUDO_CMD $TOPLEVEL/bin/switch-to-configuration $ACTION"

  echo "[+] Deployment ($ACTION) successfully completed on $DEVICE!"
  if [ "$ACTION" = "boot" ]; then
    echo "[*] New generation staged for next startup. Reboot the watch when ready:"
    echo "    ssh -p $PORT $SSH_USER@$TARGET_HOST '$SUDO_CMD reboot'"
  fi
}

deploy_nixos_rebuild() {
  if [ "$DRY_RUN" = true ]; then
    echo "[*] Dry run: evaluating Flake nixosConfigurations.$DEVICE..."
    nix eval "$REPO_ROOT#nixosConfigurations.$DEVICE.config.system.build.toplevel.drvPath"
    return 0
  fi

  check_connectivity

  echo "[*] Executing nixos-rebuild $ACTION --flake .#$DEVICE..."
  nixos-rebuild "$ACTION" \
    --flake "$REPO_ROOT#$DEVICE" \
    --target-host "$SSH_USER@$TARGET_HOST" \
    --use-remote-sudo \
    --build-host localhost

  if [ "$ACTION" = "boot" ]; then
    echo "[*] New generation staged for next startup. Reboot the watch when ready:"
    echo "    ssh -p $PORT $SSH_USER@$TARGET_HOST 'sudo reboot'"
  fi
}

deploy_deploy_rs() {
  if [ "$DRY_RUN" = true ]; then
    echo "[*] Dry run: evaluating Flake deploy.nodes.$DEVICE..."
    nix eval "$REPO_ROOT#deploy.nodes.$DEVICE.profiles.system.path.drvPath"
    return 0
  fi

  check_connectivity

  echo "[*] Executing deploy-rs for $DEVICE..."
  DEPLOY_ARGS=()
  if [ "$ACTION" = "boot" ]; then
    DEPLOY_ARGS+=(--boot)
  fi
  nix run github:serokell/deploy-rs -- "${DEPLOY_ARGS[@]}" "$REPO_ROOT#$DEVICE"

  if [ "$ACTION" = "boot" ]; then
    echo "[*] New generation staged for next startup. Reboot the watch when ready:"
    echo "    ssh -p $PORT $SSH_USER@$TARGET_HOST 'sudo reboot'"
  fi
}

case "$METHOD" in
  copy)
    deploy_copy
    ;;
  nixos-rebuild)
    deploy_nixos_rebuild
    ;;
  deploy-rs)
    deploy_deploy_rs
    ;;
esac
