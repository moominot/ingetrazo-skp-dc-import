# SPDX-License-Identifier: GPL-3.0-or-later
"""Taking something out of the library as files of its own: a component as an
.igz, a material as an .igmat (or its folder of maps), a model or a background
as the files it is made of."""
from __future__ import annotations

import shutil
from pathlib import Path

from . import catalog, online


def write_component(path: Path, group, materials: dict) -> None:
    """``path``: an .igz holding ``group``'s component alone, at identity,
    with the materials it uses."""
    from PySide6.QtGui import QMatrix4x4

    from core.group import Group
    from core.scene import Scene
    from formats import igz

    from . import proxy
    entry = Group(group.mesh, name=group.name)
    entry.xform = QMatrix4x4()
    entry.component = True
    entry.children = list(getattr(group, "children", None) or [])
    entry.layer = getattr(group, "layer", None)
    entry.material = getattr(group, "material", None)
    ext = dict(getattr(group, "ext", None) or {})
    ext.pop(proxy.KEY, None)
    entry.ext = ext
    out = Scene()
    out.groups = [entry]
    out.materials.update(proxy._used_materials(materials, group))
    path.parent.mkdir(parents=True, exist_ok=True)
    igz.save_scene(out, path)


def folder_for(dest: Path, name: str) -> Path:
    """A new folder for ``name`` inside ``dest`` (never one that exists)."""
    base = online.safe_name(name)
    out, n = Path(dest) / base, 2
    while out.exists():
        out, n = Path(dest) / f"{base} {n}", n + 1
    return out


def copy_tree(main: Path, dest: Path, name: str) -> Path:
    """The folder ``main`` is in (a downloaded model or material with all its
    files), copied into a new folder of ``dest``."""
    out = folder_for(dest, name)
    shutil.copytree(Path(main).parent, out, ignore=shutil.ignore_patterns(".complete"))
    return out


def model_files(item) -> Path:
    """The model file of a catalog item (taken out of its zip when in one)."""
    return catalog.extract(item) if item.member else item.path


def material_form(item) -> str:
    """How a catalog material is exported: ``file`` (it is one file already:
    .igmat, .skm) or ``folder`` (its maps with their manifest, or a colour)."""
    if item.path.suffix.lower() in (catalog.IGMAT, catalog.SKM):
        return "file"
    return "folder"


def material_folder(item, dest: Path) -> Path:
    """A catalog material's maps and manifest (or its colour's manifest) in a
    new folder of ``dest``; the catalog reads it back."""
    if item.maps:
        color, _paths = catalog.material_files(item)
        return copy_tree(color, dest, item.name)
    spec = item.spec or {}
    manifest, _new = catalog.save_material(
        item.name, rgb=spec.get("rgb") or (0.8, 0.8, 0.8), opacity=spec.get("opacity"),
        finish=spec.get("finish"), dest=folder_for(dest, item.name))
    return manifest.parent
