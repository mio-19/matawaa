"""Shared patch-folder discovery for the apply and rebuild commands."""

from __future__ import annotations

import re
from pathlib import Path


CATEGORY_PREFIX = re.compile(r"^\d{2}-")


def discover_categories(patches: Path) -> list[str]:
    """Discover category folders; their numeric prefixes define apply order."""
    if not patches.is_dir():
        raise ValueError(f"Patch directory is missing: {patches}")
    categories = sorted(
        entry.name
        for entry in patches.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )
    if not categories:
        raise ValueError(f"No patch category folders found in {patches}")
    invalid = [name for name in categories if not CATEGORY_PREFIX.match(name)]
    if invalid:
        raise ValueError(
            "Patch category folders must start with a two-digit numeric ordering prefix: "
            + ", ".join(invalid)
        )
    return categories


def patches_in_order(patches: Path, categories: list[str]) -> list[tuple[str, Path]]:
    """Return patch files in category order and lexical filename order."""
    return [
        (category, patch)
        for category in categories
        for patch in sorted((patches / category).glob("*.patch"))
    ]
