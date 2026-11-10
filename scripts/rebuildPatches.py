#!/usr/bin/env python3
"""Export work/mobile-nixos commits into the categorized patch series."""

from __future__ import annotations

import argparse
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
        command, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE
    )
    return result.stdout.strip()


def fail(message: str) -> "NoReturn":
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    work = root / "work" / "mobile-nixos"
    patches = root / "patches"

    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the patch series while retaining each known patch's category. "
            "Pass --category for newly added or renamed commits."
        )
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        help="category for commits that do not match an existing patch by subject",
    )
    args = parser.parse_args()

    if not (work / ".git").exists():
        fail(f"Working repository not found at {work}. Run scripts/applyPatches.sh first.")

    try:
        upstream = run(
            [
                "nix", "eval", "--raw", "--impure", "--expr",
                f'(builtins.fromJSON (builtins.readFile {root / "flake.lock"})).nodes.mobile-nixos.locked.rev',
            ],
            cwd=root,
        )
        count = int(run(["git", "rev-list", "--count", f"{upstream}..HEAD"], cwd=work))
    except subprocess.CalledProcessError as exc:
        fail(f"Could not determine the locked upstream revision or worktree commits ({exc}).")

    if count == 0:
        fail(f"No commits found on top of {upstream} in {work}.")

    # Index existing patches by their subject-derived filename suffix. This keeps
    # category assignments stable even as format-patch renumbers the full series.
    existing: dict[str, str] = {}
    for category in CATEGORIES:
        category_dir = patches / category
        if not category_dir.is_dir():
            fail(f"Expected patch category directory is missing: {category_dir}")
        for path in category_dir.glob("*.patch"):
            match = PATCH_RE.match(path.name)
            if not match:
                fail(f"Cannot identify patch subject from filename: {path}")
            key = match.group("subject")
            if key in existing:
                fail(f"Duplicate patch subject suffix makes category ambiguous: {key}")
            existing[key] = category

    print(f"[INFO] Rebuilding {count} patches from {work}...")
    with tempfile.TemporaryDirectory(prefix="matawaa-patches-") as temp_name:
        temp = Path(temp_name)
        try:
            run(
                [
                    "git", "format-patch", "--zero-commit", "--numbered",
                    "--no-signature", "--filename-max-length=110", "-o", str(temp),
                    f"{upstream}..HEAD",
                ],
                cwd=work,
            )
        except subprocess.CalledProcessError as exc:
            fail(f"git format-patch failed ({exc}).")

        exported = sorted(temp.glob("*.patch"))
        if len(exported) != count:
            fail(f"Expected {count} exported patches, found {len(exported)}.")

        assignments: list[tuple[Path, str]] = []
        unassigned: list[str] = []
        for patch in exported:
            match = PATCH_RE.match(patch.name)
            if not match:
                fail(f"Unexpected format-patch filename: {patch.name}")
            category = existing.get(match.group("subject"), args.category)
            if category is None:
                unassigned.append(patch.name)
            else:
                assignments.append((patch, category))

        if unassigned:
            print("[ERROR] These patches have no existing category:", file=sys.stderr)
            for name in unassigned:
                print(f"  {name}", file=sys.stderr)
            print(
                "Choose a category for new or renamed commits with --category CATEGORY.",
                file=sys.stderr,
            )
            return 1

        # Build the complete new layout beside patches/ first, then replace the
        # old patch files only after all commits have a valid destination.
        staged = temp / "categorized"
        for category in CATEGORIES:
            (staged / category).mkdir(parents=True)
        for patch, category in assignments:
            shutil.copy2(patch, staged / category / patch.name)

        for category in CATEGORIES:
            category_dir = patches / category
            for old_patch in category_dir.glob("*.patch"):
                old_patch.unlink()
            for new_patch in (staged / category).glob("*.patch"):
                shutil.copy2(new_patch, category_dir / new_patch.name)

    print(f"[SUCCESS] Exported {count} categorized patches:")
    for category in CATEGORIES:
        for patch in sorted((patches / category).glob("*.patch")):
            print(f"  {category}/{patch.name}")
    print("[SUCCESS] Patch rebuild complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
