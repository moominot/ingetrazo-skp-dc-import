# SPDX-License-Identifier: GPL-3.0-or-later
"""The user's own categories: any number of tags for a model, a material or a
background of the catalog or of the drawing. Kept in one small file in the
extension's folder (``tags.json``: item key -> tags), so the catalog's folders
are left as they are. Online assets bring their site's categories, and keep
them as tags when they are saved to the catalog. Pure Python."""
from __future__ import annotations

import json

from . import catalog


def _file():
    return catalog.home() / "tags.json"


def load() -> dict:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): clean(v) for k, v in data.items() if isinstance(v, list)}


def clean(values) -> list[str]:
    """Trimmed tags, each once (whatever its capitals), by name."""
    seen: dict[str, str] = {}
    for v in values or ():
        t = " ".join(str(v).split())
        if t:
            seen.setdefault(t.lower(), t)
    return sorted(seen.values(), key=str.lower)


def parse(text: str) -> list[str]:
    """«trees, outdoor» -> the two tags."""
    return clean(str(text).replace(";", ",").split(","))


def get(key: str) -> list[str]:
    return load().get(key, [])


def update(changes: dict) -> None:
    """``{key: tags}`` into the file; a key left with no tags is dropped."""
    data = load()
    for key, values in changes.items():
        values = clean(values)
        if values:
            data[key] = values
        else:
            data.pop(key, None)
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def set_tags(key: str, values) -> None:
    update({key: values})
