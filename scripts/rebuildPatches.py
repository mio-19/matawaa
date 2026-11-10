#!/usr/bin/env python3
"""Add committed worktree changes to the categorized Mobile NixOS patch series."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CATEGORIES = (
    "00-mobile-nixos-upstream-candidates",
    "10-asteroidos-upstream-nightly",
    "20-our-customizations-apps",
    "25-asteroidos-upstream-nightly-apps",
    "30-our-customizations-devices",
    "40-our-experimental-customizations",
    "50-upstream-unmerged-development",
)
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


def fail(message: str) -> "NoReturn":
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    work = root / "work" / "mobile-nixos"
    patches = root / "patches"
    state_path = patches / ".rebuild-state.json"

    parser = argparse.ArgumentParser(
        description=(
            "Append new committed changes to the categorized patch series. "
            "Existing consolidated patches and their categories are retained."
        )
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        help="category for all new commits (required when there are new commits)",
    )
    args = parser.parse_args()

    if not (work / ".git").exists():
        fail(f"Working repository not found at {work}. Run scripts/applyPatches.sh first.")
    if not state_path.is_file():
        fail(f"Patch baseline metadata is missing: {state_path}")

    try:
        lock = json.loads((root / "flake.lock").read_text())
        upstream = lock["nodes"]["mobile-nixos"]["locked"]["rev"]
        state = json.loads(state_path.read_text())
        head = run(["git", "rev-parse", "HEAD"], cwd=work)
        tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=work)
        dirty = run(["git", "status", "--porcelain"], cwd=work)
    except (OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        fail(f"Could not read patch/worktree state ({exc}).")

    if dirty:
        fail(f"Commit or discard worktree changes before rebuilding: {work}")
    if state.get("upstream_commit") != upstream:
        fail("The locked Mobile NixOS revision changed; rebuild the patch baseline first.")
    if state.get("version") != 1:
        fail("Unsupported patch rebuild-state version.")

    baseline = state.get("source_commit")
    baseline_tree = state.get("source_tree")
    if not baseline or not baseline_tree:
        fail("Patch rebuild-state is incomplete.")

    # applyPatches.sh creates fresh commits from the patch files, so its HEAD
    # differs from the original source history. Matching tree IDs safely adopts
    # that equivalent history as the new baseline.
    same_tree = tree == baseline_tree
    if same_tree:
        state["source_commit"] = head
        state["source_tree"] = tree
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print("[SUCCESS] Categorized patches already match the worktree; baseline synchronized.")
        return 0

    is_descendant = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, "HEAD"], cwd=work
    ).returncode == 0
    if not is_descendant:
        fail(
            "The worktree has diverged from the recorded patch baseline. "
            "Restore the baseline or apply the categorized patches into a fresh worktree."
        )

    try:
        count = int(run(["git", "rev-list", "--count", f"{baseline}..HEAD"], cwd=work))
    except subprocess.CalledProcessError as exc:
        fail(f"Could not inspect commits after the patch baseline ({exc}).")
    if count == 0:
        fail("Worktree tree changed without any new commits.")
    if args.category is None:
        fail(
            f"Found {count} new commit(s). Choose their category with --category CATEGORY; "
            "the existing 43 consolidated patches will remain untouched."
        )

    for category in CATEGORIES:
        if not (patches / category).is_dir():
            fail(f"Expected patch category directory is missing: {patches / category}")

    existing_numbers = [
        int(match.group("number"))
        for category in CATEGORIES
        for patch in (patches / category).glob("*.patch")
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
                    f"{baseline}..HEAD",
                ],
                cwd=work,
            )
        except subprocess.CalledProcessError as exc:
            fail(f"git format-patch failed ({exc}).")

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
            destination = staged / name
            shutil.copy2(patch, destination)
            names.append(name)

        target_dir = patches / args.category
        for name in names:
            destination = target_dir / name
            if destination.exists():
                fail(f"Refusing to overwrite existing patch: {destination}")
        for name in names:
            shutil.copy2(staged / name, target_dir / name)

    state["source_commit"] = head
    state["source_tree"] = tree
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    for name in names:
        print(f"  {args.category}/{name}")
    print(f"[SUCCESS] Added {count} patch(es); existing categories and patches were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
