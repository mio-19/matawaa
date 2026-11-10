#!/usr/bin/env python3
"""Apply the categorized patch series to the locked Mobile NixOS revision."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from patch_series import discover_categories, patches_in_order

UPSTREAM_URL = "https://github.com/NixOS/mobile-nixos.git"
BRANCH_NAME = "matawaa-work"


class ApplyError(Exception):
    """A recoverable problem applying or preparing the patch series."""


def info(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def success(message: str) -> None:
    print(f"[SUCCESS] {message}", flush=True)


def git(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        check=check,
    )


def git_output(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    work = root / "work" / "mobile-nixos"
    patches = root / "patches"

    try:
        lock = json.loads((root / "flake.lock").read_text())
        locked_commit: str = lock["nodes"]["mobile-nixos"]["locked"]["rev"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ApplyError(f"Could not read the locked Mobile NixOS revision: {exc}") from exc

    upstream_commit = os.environ.get("UPSTREAM_COMMIT", locked_commit)
    upstream_url = os.environ.get("UPSTREAM_URL", UPSTREAM_URL)
    branch_name = os.environ.get("BRANCH_NAME", BRANCH_NAME)
    try:
        categories = discover_categories(patches)
        ordered_patches = patches_in_order(patches, categories)
    except ValueError as exc:
        raise ApplyError(str(exc)) from exc
    work.parent.mkdir(parents=True, exist_ok=True)

    if not (work / ".git").exists():
        if work.exists() and any(work.iterdir()):
            raise ApplyError(f"Refusing to clone over a nonempty directory: {work}")
        info(f"Cloning upstream Mobile NixOS into {work}...")
        git(["clone", upstream_url, str(work)], cwd=root)
    else:
        dirty = git_output(["status", "--porcelain"], cwd=work)
        if dirty:
            raise ApplyError(
                f"Refusing to replace a worktree with uncommitted or untracked files: {work}"
            )

    info(f"Checking out locked upstream commit {upstream_commit}...")
    fetch = subprocess.run(
        ["git", "fetch", "origin", upstream_commit],
        cwd=work,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if fetch.returncode != 0:
        # A local clone may already contain the locked object and have no network
        # access. Checkout below provides the definitive availability check.
        info("Fetch did not complete; checking whether the locked commit is already local.")
    git(["checkout", "-B", branch_name, upstream_commit], cwd=work)

    info(f"Applying categorized patch series from {patches}...")
    patch_count = 0
    for category, patch in ordered_patches:
        relative_name = f"{category}/{patch.name}"
        info(f"Applying {relative_name}...")
        result = git(
            ["-C", str(work), "am", "--3way", "--ignore-whitespace", str(patch)],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            print(f"[ERROR] Failed to apply patch: {relative_name}", file=sys.stderr)
            print(
                "Resolve the conflict in work/mobile-nixos and run "
                "'git am --continue', or run 'git am --abort'.",
                file=sys.stderr,
            )
            return result.returncode
        patch_count += 1

    success(f"Applied {patch_count} patches to {work} on branch {branch_name}.")
    info("Edit and commit changes in work/mobile-nixos, then run scripts/rebuildPatches.sh.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApplyError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Command failed with exit code {exc.returncode}: {exc.cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1) from exc
