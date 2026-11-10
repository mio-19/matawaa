#!/usr/bin/env python3
"""Append committed worktree changes to the categorized Mobile NixOS series."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

sys.dont_write_bytecode = True

from patch_series import discover_categories, patches_in_order


PATCH_RE = re.compile(r"^(?P<number>\d{4,})-(?P<subject>.+)\.patch$")


def run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def fail(message: str) -> NoReturn:
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def patch_baseline_tree(
    work: Path,
    upstream: str,
    ordered_patches: list[tuple[str, Path]],
) -> str:
    """Replay the current series in a disposable clone and return its tree ID."""
    with tempfile.TemporaryDirectory(prefix="matawaa-patch-baseline-") as temp_name:
        replay = Path(temp_name) / "mobile-nixos"
        try:
            run(["git", "clone", "--quiet", "--shared", str(work), str(replay)])
            run(["git", "checkout", "--quiet", "-B", "patch-series-baseline", upstream], cwd=replay)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() if exc.stderr else str(exc)
            fail(f"Could not prepare a disposable upstream worktree: {detail}")

        for category, patch in ordered_patches:
            result = subprocess.run(
                ["git", "am", "--3way", "--ignore-whitespace", str(patch)],
                cwd=replay,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                subprocess.run(["git", "am", "--abort"], cwd=replay, capture_output=True)
                detail = (result.stderr or result.stdout).strip()
                fail(f"Existing patch does not replay ({category}/{patch.name}): {detail}")
        try:
            return run(["git", "rev-parse", "HEAD^{tree}"], cwd=replay)
        except subprocess.CalledProcessError as exc:
            fail(f"Could not read the replayed patch tree ({exc}).")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    work = root / "work" / "mobile-nixos"
    patches = root / "patches"

    if not (work / ".git").exists():
        fail(f"Working repository not found at {work}. Run scripts/applyPatches.sh first.")

    try:
        lock = json.loads((root / "flake.lock").read_text())
        upstream = lock["nodes"]["mobile-nixos"]["locked"]["rev"]
        dirty = run(["git", "status", "--porcelain"], cwd=work)
        categories = discover_categories(patches)
        ordered_patches = patches_in_order(patches, categories)
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as exc:
        fail(f"Could not read patch/worktree configuration ({exc}).")

    if dirty:
        fail(f"Commit or discard worktree changes before rebuilding: {work}")
    if not ordered_patches:
        fail(f"No .patch files found in category folders under {patches}.")

    parser = argparse.ArgumentParser(
        description=(
            "Append new committed changes to the categorized patch series. "
            "Existing patches and their folder assignments are retained."
        )
    )
    parser.add_argument(
        "--category",
        choices=categories,
        help="folder for new commits (required when the worktree has new commits)",
    )
    args = parser.parse_args()

    print("[INFO] Replaying categorized patches to locate their source-tree baseline...", flush=True)
    baseline_tree = patch_baseline_tree(work, upstream, ordered_patches)
    try:
        history = run(["git", "log", "--format=%H%x09%T", "HEAD"], cwd=work)
        baseline_commit = next(
            commit
            for line in history.splitlines()
            for commit, commit_tree in [line.split("\t", 1)]
            if commit_tree == baseline_tree
        )
        head = run(["git", "rev-parse", "HEAD"], cwd=work)
        count = int(
            run(["git", "rev-list", "--count", f"{baseline_commit}..HEAD"], cwd=work)
        )
    except (subprocess.CalledProcessError, StopIteration, ValueError) as exc:
        fail(
            "The worktree history does not contain the tree produced by the current patch "
            f"folders ({exc}). Apply the current series before rebuilding."
        )

    if count == 0:
        print("[SUCCESS] Categorized patches already match the worktree.")
        return 0
    if args.category is None:
        fail(
            f"Found {count} new commit(s). Choose their destination folder with "
            "--category FOLDER."
        )

    existing_numbers = [
        int(match.group("number"))
        for _, patch in ordered_patches
        if (match := PATCH_RE.match(patch.name))
    ]
    next_number = max(existing_numbers, default=0) + 1

    print(f"[INFO] Exporting {count} new commit(s) into {args.category}...", flush=True)
    with tempfile.TemporaryDirectory(prefix="matawaa-patches-") as temp_name:
        temp = Path(temp_name)
        try:
            run(
                [
                    "git", "format-patch", "--zero-commit", "--numbered",
                    "--no-signature", "--filename-max-length=110", "-o", str(temp),
                    f"{baseline_commit}..HEAD",
                ],
                cwd=work,
            )
        except subprocess.CalledProcessError as exc:
            fail(f"git format-patch failed ({exc.stderr.strip()}).")

        exported = sorted(temp.glob("*.patch"))
        if len(exported) != count:
            fail(f"Expected {count} exported patches, found {len(exported)}.")

        staged = temp / "categorized"
        staged.mkdir()
        names: list[str] = []
        for index, patch in enumerate(exported):
            match = PATCH_RE.match(patch.name)
            if not match:
                fail(f"Unexpected format-patch filename: {patch.name}")
            name = f"{next_number + index:04d}-{match.group('subject')}.patch"
            shutil.copy2(patch, staged / name)
            names.append(name)

        target_dir = patches / args.category
        for name in names:
            if (target_dir / name).exists():
                fail(f"Refusing to overwrite existing patch: {target_dir / name}")
        for name in names:
            shutil.copy2(staged / name, target_dir / name)

    for name in names:
        print(f"  {args.category}/{name}")
    print(f"[SUCCESS] Added {count} patch(es); existing categorized patches were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
