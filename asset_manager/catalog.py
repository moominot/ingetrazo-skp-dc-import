# SPDX-License-Identifier: GPL-3.0-or-later
"""The user's own catalog: a folder of IngeTrazo documents (.igz) with an
optional preview next to each (same name, .png). No database: the folder is
the catalog, so it can be synced, shared or kept in version control."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PREVIEW_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass
class Item:
    name: str
    path: Path
    preview: Path | None


def default_folder() -> Path:
    override = os.environ.get("ASSET_MANAGER_HOME")
    if override:
        return Path(override) / "catalog"
    try:
        from PySide6.QtCore import QStandardPaths
        loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        base = Path(loc) if loc else Path.home() / ".ingetrazo"
    except Exception:  # noqa: BLE001
        base = Path.home() / ".ingetrazo"
    return base / "asset_manager" / "catalog"


def scan(folder: Path | None = None) -> list[Item]:
    """The .igz files under ``folder`` (subfolders included), by name."""
    root = Path(folder) if folder else default_folder()
    items = []
    if root.is_dir():
        for p in sorted(root.rglob("*.igz"), key=lambda q: q.name.lower()):
            prev = next((p.with_suffix(s) for s in PREVIEW_SUFFIXES
                         if p.with_suffix(s).is_file()), None)
            items.append(Item(p.stem, p, prev))
    return items
