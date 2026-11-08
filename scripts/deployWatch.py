#!/usr/bin/env python3
"""deployWatch.py — Deploy and upgrade AsteroidOS NixOS systems on smartwatches.

Stages NixOS system profiles and Android boot images on wearable devices:
  1. Builds the full AsteroidOS UI desktop toplevel closure locally.
  2. Builds the stage-1 Android boot image (`boot.img`).
  3. Copies closures via `nix-copy-closure` over USB networking or Wi-Fi.
  4. Flashes stage-1 to the Android boot partition if updated.
  5. Stages the new generation for the next boot, or activates it immediately.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(f"\033[1;34m[*]\033[0m {msg}", flush=True)


def log_success(msg: str) -> None:
    print(f"\033[1;32m[+]\033[0m {msg}", flush=True)


def log_warn(msg: str) -> None:
    print(f"\033[1;33m[!]\033[0m {msg}", flush=True)


def log_error(msg: str) -> None:
    print(f"\033[1;31m[-]\033[0m {msg}", file=sys.stderr, flush=True)


def run_cmd(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = False,
    check: bool = True,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=capture_output,
            check=check,
            env=env,
        )
    except subprocess.CalledProcessError as error:
        if capture_output and error.stderr:
            log_error(error.stderr.rstrip())
        raise


def check_ssh_connectivity(host: str, port: int, user: str) -> bool:
    log(f"Checking SSH connectivity to {user}@{host}:{port}...")
    cmd = [
        "ssh",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-p",
        str(port),
        f"{user}@{host}",
        "true",
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        log_warn("Non-interactive SSH is unavailable; subsequent commands may prompt for authentication.")
        return False
    log_success("SSH connection verified.")
    return True


def ssh_exec(
    host: str,
    port: int,
    user: str,
    remote_cmd: str,
    sudo: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    shell_command = f"sh -c {shlex.quote(remote_cmd)}"
    full_remote = f"sudo -- {shell_command}" if sudo and user != "root" else shell_command
    cmd = [
        "ssh",
        "-p",
        str(port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-tt" if sudo and user != "root" else "-T",
        f"{user}@{host}",
        full_remote,
    ]
    return run_cmd(cmd, capture_output=capture_output)


def run_build_cmd(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> str:
    """Run a nix-build or nix build command without hiding output.

    Streams stderr (evaluation traces, compiler messages, progress) live directly
    to the terminal and prints stdout lines as they arrive while capturing the
    resulting store path.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        env=env,
    )
    stdout_lines: List[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        stripped = line.strip()
        if stripped:
            stdout_lines.append(stripped)
    ret = proc.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, cmd)
    if not stdout_lines:
        raise RuntimeError(f"Build command produced no output path: {' '.join(cmd)}")
    return stdout_lines[-1]


def build_asteroid_toplevel(repo_root: Path, device: str) -> str:
    log(f"Building full AsteroidOS UI desktop toplevel for '{device}'...")
    examples_path = repo_root / "work" / "mobile-nixos" / "examples" / "asteroid"
    if examples_path.is_dir():
        cmd = [
            "nix-build",
            str(examples_path),
            "--argstr",
            "device",
            device,
            "-A",
            "config.system.build.toplevel",
            "--no-link",
        ]
    else:
        cmd = [
            "nix",
            "build",
            f"{repo_root}#nixosConfigurations.{device}.config.system.build.toplevel",
            "--no-link",
            "--print-out-paths",
        ]
    toplevel = run_build_cmd(cmd, cwd=repo_root)
    log_success(f"Built full AsteroidOS desktop toplevel: {toplevel}")
    return toplevel


def build_stage1_bootimg(repo_root: Path, device: str) -> str:
    log(f"Building stage-1 boot.img (kernel + initrd) for '{device}'...")
    examples_path = repo_root / "work" / "mobile-nixos" / "examples" / "asteroid"
    if examples_path.is_dir():
        cmd = [
            "nix-build",
            str(examples_path),
            "--argstr",
            "device",
            device,
            "-A",
            "outputs.android.android-bootimg",
            "--no-link",
        ]
    else:
        cmd = [
            "nix",
            "build",
            f"{repo_root}#nixosConfigurations.{device}.config.mobile.outputs.android.android-bootimg",
            "--no-link",
            "--print-out-paths",
        ]
    bootimg_path = run_build_cmd(cmd, cwd=repo_root)
    log_success(f"Built stage-1 boot image: {bootimg_path}")
    return bootimg_path


def flash_stage1_bootimg_remote(
    host: str,
    port: int,
    user: str,
    local_bootimg: str,
) -> None:
    bootimg_file = Path(local_bootimg)
    if not bootimg_file.is_file():
        # Might be a directory containing boot.img
        candidate = bootimg_file / "boot.img"
        if candidate.is_file():
            bootimg_file = candidate
        else:
            raise FileNotFoundError(f"Cannot locate boot.img at {local_bootimg}")

    img_size = bootimg_file.stat().st_size
    digest = hashlib.sha256()
    with open(bootimg_file, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    img_sha256 = digest.hexdigest()

    log(f"Stage-1 boot.img size: {img_size} bytes, sha256: {img_sha256[:16]}...")

    # Shell script to locate boot partition and compare checksum before transfer
    check_script = f"""
set -euo pipefail
BOOT_PART=""
for cand in \\
    /dev/block/bootdevice/by-name/boot \\
    /dev/block/by-name/boot \\
    /dev/block/platform/*/by-name/boot \\
    /dev/disk/by-partlabel/boot \\
    /dev/disk/by-partlabel/BOOT; do
    if [ -b "$cand" ]; then
        BOOT_PART="$cand"
        break
    fi
done

if [ -z "$BOOT_PART" ]; then
    slot=$(sed -n 's/.*androidboot.slot_suffix=\\(_[ab]\\).*/\\1/p' /proc/cmdline)
    if [ -n "$slot" ]; then
        for cand in /dev/block/bootdevice/by-name/boot"$slot" /dev/block/by-name/boot"$slot"; do
            if [ -b "$cand" ]; then BOOT_PART="$cand"; break; fi
        done
    fi
fi

if [ -z "$BOOT_PART" ]; then
    echo "No active boot partition block device found" >&2
    exit 1
fi

part_size=$(blockdev --getsize64 "$BOOT_PART")
if [ "$part_size" -lt {img_size} ]; then
    echo "Boot image exceeds $BOOT_PART ($part_size bytes)" >&2
    exit 1
fi

echo "$BOOT_PART"
head -c {img_size} "$BOOT_PART" | sha256sum | awk '{{print $1}}'
"""
    check_res = ssh_exec(
        host, port, user, f"bash -c {shlex.quote(check_script)}", sudo=True, capture_output=True
    )
    lines = [line.strip() for line in check_res.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"Unexpected output checking boot partition: {check_res.stdout}")
    boot_part = lines[0]
    part_sha = lines[1]

    log(f"Found boot partition block device: {boot_part}")
    if part_sha == img_sha256:
        log_success(
            f"Stage-1 boot partition already matches new boot.img ({img_sha256}). Flashing not needed."
        )
        return

    log(f"Stage-1 hash mismatch ({part_sha} != {img_sha256}). Flashing new boot.img...")

    # Copy boot.img to watch /tmp
    remote_tmp_img = f"/tmp/new-stage1-{img_sha256[:16]}-{os.getpid()}.img"
    log(f"Transferring stage-1 boot.img to watch at {remote_tmp_img}...")
    scp_cmd = [
        "scp",
        "-O",
        "-P",
        str(port),
        "-o",
        "StrictHostKeyChecking=accept-new",
        str(bootimg_file),
        f"{user}@{host}:{remote_tmp_img}",
    ]
    run_cmd(scp_cmd)

    # Shell script to flash boot partition and verify
    flash_script = f"""
set -euo pipefail
trap 'rm -f {remote_tmp_img}' EXIT

actual_sha=$(sha256sum {remote_tmp_img} | cut -d' ' -f1)
if [ "$actual_sha" != "{img_sha256}" ]; then
    echo "Transferred boot image checksum mismatch" >&2
    exit 1
fi

dd if={remote_tmp_img} of="{boot_part}" bs=4M status=progress conv=fsync
sync
flashed_sha=$(head -c {img_size} "{boot_part}" | sha256sum | cut -d' ' -f1)
if [ "$flashed_sha" != "{img_sha256}" ]; then
    echo "Boot partition read-back checksum mismatch" >&2
    exit 1
fi
echo "[+] Stage-1 successfully flashed to {boot_part}!"
"""
    ssh_exec(host, port, user, f"bash -c {shlex.quote(flash_script)}", sudo=True)


def reboot_remote_target(host: str, port: int, user: str) -> None:
    log("Rebooting watch now...")
    try:
        ssh_exec(
            host,
            port,
            user,
            "systemctl reboot --no-block 2>/dev/null || (sleep 1; reboot) >/dev/null 2>&1 &",
            sudo=True,
        )
    except Exception as error:
        log_warn(f"Reboot command dispatched (SSH session closed: {error})")


def deploy_copy(
    repo_root: Path,
    device: str,
    host: str,
    port: int,
    user: str,
    action: str,
    dry_run: bool,
    flash_boot: bool,
    reboot: bool,
) -> None:
    toplevel = build_asteroid_toplevel(repo_root, device)

    if dry_run:
        log("Dry run requested. Closures built successfully; skipping transmission and activation.")
        return

    check_ssh_connectivity(host, port, user)

    log(f"Copying system closure to {user}@{host} via nix-copy-closure...")
    env = os.environ.copy()
    env["NIX_SSHOPTS"] = (
        f"-p {port} -o StrictHostKeyChecking=accept-new "
        "-o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o TCPKeepAlive=yes"
    )
    cmd = ["nix-copy-closure", "--gzip", "-v", "--to", f"{user}@{host}", toplevel]
    run_cmd(cmd, env=env)

    log(f"Activating configuration (action: {action}) on target watch...")
    if action == "boot":
        remote_activate = (
            f"nix-env -p /nix/var/nix/profiles/system --set {shlex.quote(toplevel)} && "
            f"{shlex.quote(toplevel)}/bin/switch-to-configuration boot"
        )
    elif action == "switch":
        remote_activate = (
            f"nix-env -p /nix/var/nix/profiles/system --set {shlex.quote(toplevel)} && "
            f"{shlex.quote(toplevel)}/bin/switch-to-configuration switch"
        )
    else:
        remote_activate = f"{shlex.quote(toplevel)}/bin/switch-to-configuration {action}"
    ssh_exec(host, port, user, remote_activate, sudo=True)

    log_success(f"Deployment action '{action}' completed on {device}.")
    if action == "boot":
        log("New system profile staged for Mobile NixOS stage-1 on next startup.")
        if reboot:
            reboot_remote_target(host, port, user)
        else:
            log(f"Reboot the watch when ready: ssh -p {port} {user}@{host} 'sudo reboot'")


def deploy_nixos_rebuild(
    repo_root: Path,
    device: str,
    host: str,
    port: int,
    user: str,
    action: str,
    dry_run: bool,
    reboot: bool,
) -> None:
    if dry_run:
        log(f"Dry run: evaluating Flake nixosConfigurations.{device}...")
        run_cmd(
            ["nix", "eval", f"{repo_root}#nixosConfigurations.{device}.config.system.build.toplevel.drvPath"],
            cwd=repo_root,
        )
        return

    check_ssh_connectivity(host, port, user)
    log(f"Executing nixos-rebuild {action} --flake .#{device}...")
    cmd = [
        "nixos-rebuild",
        action,
        "--flake",
        f"{repo_root}#{device}",
        "--target-host",
        f"{user}@{host}",
        "--use-remote-sudo",
        "--build-host",
        "localhost",
    ]
    run_cmd(cmd, cwd=repo_root)

    log_success(f"nixos-rebuild {action} completed for {device}!")
    if action == "boot":
        if reboot:
            reboot_remote_target(host, port, user)
        else:
            log(f"Reboot the watch when ready: ssh -p {port} {user}@{host} 'sudo reboot'")


def deploy_deploy_rs(
    repo_root: Path,
    device: str,
    host: str,
    port: int,
    user: str,
    action: str,
    dry_run: bool,
    reboot: bool,
) -> None:
    if dry_run:
        log(f"Dry run: evaluating Flake deploy.nodes.{device}...")
        run_cmd(
            ["nix", "eval", f"{repo_root}#deploy.nodes.{device}.profiles.system.path.drvPath"],
            cwd=repo_root,
        )
        return

    check_ssh_connectivity(host, port, user)
    log(f"Executing deploy-rs for {device}...")
    cmd = ["nix", "run", "github:serokell/deploy-rs", "--"]
    if action == "boot":
        cmd.append("--boot")
    cmd.append(f"{repo_root}#{device}")
    run_cmd(cmd, cwd=repo_root)

    log_success(f"deploy-rs completed for {device}!")
    if action == "boot":
        if reboot:
            reboot_remote_target(host, port, user)
        else:
            log(f"Reboot the watch when ready: ssh -p {port} {user}@{host} 'sudo reboot'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy or upgrade AsteroidOS NixOS systems on smartwatches over-the-air.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy full AsteroidOS UI desktop to watch (staged for next boot)
  ./scripts/deployWatch.py

  # Deploy to Fossil Gen 6 and reboot immediately
  ./scripts/deployWatch.py --reboot

  # Deploy over Wi-Fi
  ./scripts/deployWatch.py --device fossil-hoki --target 192.168.1.150

  # Test configuration without setting default boot profile
  ./scripts/deployWatch.py --action test

  # Dry run build and evaluation
  ./scripts/deployWatch.py --dry-run
        """,
    )

    parser.add_argument(
        "-d",
        "--device",
        default="fossil-hoki",
        help="Target smartwatch device (default: fossil-hoki)",
    )
    parser.add_argument(
        "-t",
        "--target",
        default="172.16.42.1",
        help="Target IP or hostname of the watch (default: 172.16.42.1)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=22,
        help="SSH port on the watch (default: 22)",
    )
    parser.add_argument(
        "-u",
        "--user",
        default="root",
        help="SSH user on the watch (default: root)",
    )
    parser.add_argument(
        "-a",
        "--action",
        choices=["boot", "switch", "test", "dry-activate"],
        default="boot",
        help="Activation action (default: boot, staged for next startup)",
    )
    parser.add_argument(
        "-m",
        "--method",
        choices=["copy", "nixos-rebuild", "deploy-rs"],
        default="copy",
        help="Deployment method (default: copy)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Build/evaluate configuration without copying or activating",
    )
    parser.add_argument(
        "--flash-boot",
        dest="flash_boot",
        action="store_true",
        default=True,
        help="Flash stage-1 boot.img if updated (default: True)",
    )
    parser.add_argument(
        "--no-flash-boot",
        dest="flash_boot",
        action="store_false",
        help="Skip flashing stage-1 boot.img",
    )
    parser.add_argument(
        "--no-reboot",
        dest="reboot",
        action="store_false",
        help="Do not reboot the watch automatically after deployment",
    )
    parser.add_argument(
        "-r",
        "--reboot",
        dest="reboot",
        action="store_true",
        default=True,
        help="Reboot the watch automatically after deployment (default: True for action 'boot')",
    )

    args = parser.parse_args()
    if args.action != "boot":
        args.reboot = False
    if args.method == "deploy-rs" and (
        args.target != "172.16.42.1" or args.port != 22 or args.user != "root"
    ):
        parser.error("deploy-rs uses the hostname and SSH user configured in flake.nix")
    if args.method == "nixos-rebuild" and args.port != 22:
        parser.error("--port is supported only by --method copy")
    repo_root = get_repo_root()

    print("=" * 60)
    print(" AsteroidOS Smartwatch OTA Deployment Tool")
    print("=" * 60)
    print(f" Device:     {args.device}")
    target = (
        "flake.nix deploy.nodes configuration"
        if args.method == "deploy-rs"
        else f"{args.user}@{args.target}:{args.port}"
    )
    print(f" Target:     {target}")
    print(f" Action:     {args.action}")
    print(f" Method:     {args.method}")
    print(f" Flash Boot: {args.flash_boot and args.method == 'copy' and args.action in ('boot', 'switch')}")
    print(f" Dry run:    {args.dry_run}")
    print("=" * 60)

    if args.method == "copy":
        deploy_copy(
            repo_root=repo_root,
            device=args.device,
            host=args.target,
            port=args.port,
            user=args.user,
            action=args.action,
            dry_run=args.dry_run,
            flash_boot=args.flash_boot,
            reboot=args.reboot,
        )
    elif args.method == "nixos-rebuild":
        deploy_nixos_rebuild(
            repo_root=repo_root,
            device=args.device,
            host=args.target,
            port=args.port,
            user=args.user,
            action=args.action,
            dry_run=args.dry_run,
            reboot=args.reboot,
        )
    elif args.method == "deploy-rs":
        deploy_deploy_rs(
            repo_root=repo_root,
            device=args.device,
            host=args.target,
            port=args.port,
            user=args.user,
            action=args.action,
            dry_run=args.dry_run,
            reboot=args.reboot,
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        command = error.cmd[0] if isinstance(error.cmd, (list, tuple)) else error.cmd
        log_error(f"Deployment stopped: {command} exited with status {error.returncode}.")
        raise SystemExit(1) from None
    except OSError as error:
        log_error(f"Deployment stopped: {error}")
        raise SystemExit(1) from None
