# SPDX-License-Identifier: GPL-3.0-or-later
"""Proxies in the drawing, from the right-click menu: make the selected
objects proxies, show their full model, and back. One undo step each.

* **Make proxy** — the selected top-level groups or components (every
  top-level copy of a component with it: they share one definition) keep
  their name, place, layer, paint and lights, but their geometry becomes
  the envelope (:func:`.proxy.envelope_mesh`); the full model goes to an
  .igz of its own (:func:`.proxy.write_original`).
* **Show original** — the full model comes back from its file (its
  materials registered in the drawing), still marked as a proxy.
* **Show proxy** — back to the envelope; an original edited meanwhile is
  written to its file again first.

The data is the one :mod:`.proxy` writes (the Proxies extension's format),
so proxies made by either extension answer to both.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from . import proxy
from .i18n import tr

_log = logging.getLogger(__name__)
#: The dynamic-components data: kept with the original, not on the envelope
#: (the options panel must not drive a proxy).
DC_KEY = "skp_dc_import"
_CMD: dict = {}


# --- what the menu offers --------------------------------------------------------
def selected_top(scene, selection) -> list:
    """The top-level groups among ``selection`` (a part picked inside one
    counts as its owner), in order, once each."""
    top = {id(g) for g in getattr(scene, "groups", ()) or ()}
    out, seen = [], set()
    for e in selection or ():
        g = getattr(e, "owner", None) or e
        if hasattr(g, "children") and id(g) in top and id(g) not in seen:
            seen.add(id(g))
            out.append(g)
    return out


def state(g) -> str | None:
    info = proxy.info_of(g)
    return None if info is None else info.get("state", "proxy")


def offers(scene, selection) -> dict:
    """``{"make": [...], "original": [...], "proxy": [...], "open": [...]}``:
    the selected top-level groups each command would act on."""
    gs = selected_top(scene, selection)
    return {"make": [g for g in gs if state(g) is None],
            "original": [g for g in gs if state(g) == "proxy"],
            "proxy": [g for g in gs if state(g) == "original"],
            "open": [g for g in gs if state(g) is not None]}


def open_originals(window, viewport, groups) -> tuple[list, list]:
    """Open the original file of each proxy in ``groups`` in a project tab of
    its own (one already open is brought to the front). Saved there, it is
    taken up by the proxy when its drawing comes back to the front
    (:func:`refresh_changed`). Returns (files opened, names not found)."""
    opened, missing, seen = [], [], set()
    for g in groups:
        info = proxy.info_of(g)
        if info is None:
            continue
        path = proxy.original_file(info, viewport)
        if path is None:
            missing.append(info.get("name") or g.name)
            continue
        if path in seen:
            continue
        seen.add(path)
        if window.open_path(Path(path)):
            opened.append(path)
    return opened, missing


def refresh_changed(viewport) -> list:
    """The proxies of the drawing in front whose original file was saved
    since they were made (opened in its own tab, edited, saved): their
    envelope is made again from the file, one undo step for all. Proxies
    showing their original are left alone (Show proxy decides). Returns the
    names updated."""
    scene = viewport.scene
    todo: dict = {}
    for g in getattr(scene, "groups", ()) or ():
        info = proxy.info_of(g)
        if info is None or state(g) != "proxy" or not info.get("mtime"):
            continue
        path = proxy.original_file(info, viewport)
        if path is None or proxy.file_date(path) == int(info["mtime"]):
            continue
        todo.setdefault(info["id"], (path, []))[1].append(g)
    if not todo:
        return []
    files: dict = {}
    items, names = [], []
    for pid, (path, fam) in todo.items():
        if path not in files:
            try:
                files[path] = _read(path)[0]
            except Exception:  # noqa: BLE001 - the envelope stays as it is
                _log.exception("could not read %s", path)
                files[path] = {}
        src = files[path].get(pid)
        info = dict(proxy.info_of(fam[0]))
        info["mtime"] = proxy.file_date(path)          # not asked again for this date
        mesh = proxy.envelope_mesh(proxy.points(src)) if src is not None else None
        if mesh is None:
            for g in fam:                               # the original is not in its file any more
                ext = dict(g.ext or {})
                ext[proxy.KEY] = dict(info)
                g.ext = ext
            continue
        info["faces"] = proxy.face_count(src)
        info["proxy_faces"] = len(mesh.faces)
        names.append(info.get("name") or fam[0].name)
        for g in fam:
            ext = dict(g.ext or {})
            ext[proxy.KEY] = dict(info)
            items.append((g, mesh, [], ext))
    if items:
        _execute(viewport, items, label=tr("Update proxy"))
    return names


# --- one undo step -----------------------------------------------------------------
def _swap_class():
    cls = _CMD.get("swap")
    if cls is not None:
        return cls
    from core.history import Command

    class SwapProxyCommand(Command):
        """Give each group a new mesh, nested placements and ext; register
        materials the drawing lacks. Undo and redo swap back."""

        def __init__(self, items, materials=None, label="Proxy"):
            self.items = [list(it) for it in items]     # [group, mesh, children, ext]
            self.materials = dict(materials or {})
            self.added: list = []
            self.label = label

        def _swap(self, scene):
            for it in self.items:
                g = it[0]
                was = (g.mesh, list(g.children or []), g.ext)
                g.mesh, g.children, g.ext = it[1], list(it[2] or []), it[3]
                it[1], it[2], it[3] = was
                g.mesh._chunk_dirty = True
                g.mesh._attrs_dirty = True
            scene.version += 1

        def do(self, scene):
            mats = getattr(scene, "materials", None)
            if mats is not None:
                self.added = [n for n in self.materials if n not in mats]
                for n in self.added:
                    mats[n] = self.materials[n]
            self._swap(scene)

        def undo(self, scene):
            self._swap(scene)
            mats = getattr(scene, "materials", None)
            for n in self.added:
                if mats is not None:
                    mats.pop(n, None)

    _CMD["swap"] = SwapProxyCommand
    return SwapProxyCommand


def _execute(viewport, items, materials=None, label="Proxy"):
    cmd = _swap_class()(items, materials, label)
    viewport.history.execute(cmd)
    try:
        from core.history import _dirty_group_chunks
        _dirty_group_chunks(viewport.scene)
    except Exception:  # noqa: BLE001
        pass
    for fn in ("notify_scene_changed", "update"):
        f = getattr(viewport, fn, None)
        if callable(f):
            f()
    return cmd


def _family(scene, g, same):
    """Every top-level group that goes with ``g``: the copies of a component
    (one definition), else ``g`` alone; ``same(other)`` filters them."""
    if getattr(g, "xform", None) is None:
        return [g]
    return [s for s in scene.groups if s.mesh is g.mesh and same(s)]


def _without_dc(ext):
    return {k: v for k, v in (ext or {}).items() if k != DC_KEY}


# --- the commands ------------------------------------------------------------------------
def make_proxies(viewport, groups, confirm=None) -> int:
    """Turn ``groups`` (top-level, not proxies yet) and their copies into
    proxies. ``confirm(names)`` is asked when any holds dynamic components;
    False/None cancels. Returns how many definitions became proxies."""
    scene = viewport.scene
    families, seen = [], set()
    for g in groups:
        fam = _family(scene, g, lambda s: state(s) is None)
        if id(fam[0]) in seen:
            continue
        seen.update(id(s) for s in fam)
        families.append(fam)
    if not families:
        return 0
    dyn = [f[0].name for f in families if proxy.has_dynamic(f[0])]
    if dyn and confirm is not None and not confirm(dyn):
        return 0
    folder = proxy.originals_folder(viewport)
    items = []
    for fam in families:
        g0 = fam[0]
        mesh = proxy.envelope_mesh(proxy.points(g0))
        if mesh is None:
            continue
        pid = uuid.uuid4().hex[:16]
        path = folder / f"{proxy._safe(g0.name)}_{pid[:6]}.igz"
        proxy.write_original(path, g0, getattr(scene, "materials", {}) or {}, pid)
        info = {"id": pid, "file": str(path), "rel": proxy._relative(path, viewport),
                "state": "proxy", "faces": proxy.face_count(g0), "proxy_faces": len(mesh.faces),
                "local": g0.xform is not None, "name": g0.name, "params": dict(proxy.PARAMS),
                "dynamic": proxy.has_dynamic(g0), "mtime": proxy.file_date(path)}
        for g in fam:
            ext = _without_dc(g.ext)
            ext[proxy.KEY] = dict(info)
            items.append((g, mesh, [], ext))
    if items:
        _execute(viewport, items, label=tr("Make proxy"))
    return len(families)


def _read(path: Path):
    from core.scene import Scene
    from formats import igz
    sc = Scene()
    igz.load_into(sc, path)
    found = {(proxy.info_of(g) or {}).get("id"): g for g in sc.groups}
    found.pop(None, None)
    return found, dict(getattr(sc, "materials", {}) or {})


def show_originals(viewport, groups) -> tuple[int, list]:
    """The full models of the proxies ``groups`` (and their copies) back from
    their files. Returns (how many definitions, names not found)."""
    from core.group import copy_group
    scene = viewport.scene
    files: dict = {}
    items, mats, missing, done = [], {}, [], set()
    for g in groups:
        info = proxy.info_of(g)
        if info is None or info["id"] in done or state(g) != "proxy":
            continue
        done.add(info["id"])
        fam = [s for s in scene.groups if (proxy.info_of(s) or {}).get("id") == info["id"]
               and state(s) == "proxy"]
        path = proxy.original_file(info, viewport)
        if path is not None and path not in files:
            try:
                files[path] = _read(path)
            except Exception:  # noqa: BLE001 - said below, the others still come
                _log.exception("could not read %s", path)
                files[path] = ({}, {})
        found, fmats = files.get(path, ({}, {}))
        src = found.get(info["id"])
        if src is None:
            missing.append(info.get("name") or g.name)
            continue
        mats.update(fmats)
        serial = int(getattr(src.mesh, "_mut_serial", 0))
        for n, s in enumerate(fam):
            kids = (list(src.children or []) if n == 0
                    else [copy_group(c, _in_definition=True) for c in (src.children or [])])
            ext = dict(s.ext or {})
            if (src.ext or {}).get(DC_KEY) is not None:
                ext[DC_KEY] = src.ext[DC_KEY]
            new = dict(info)
            new["state"] = "original"
            new["serial"] = serial
            ext[proxy.KEY] = new
            items.append((s, src.mesh, kids, ext))
    if items:
        _execute(viewport, items, mats, label=tr("Show original"))
    return len(done) - len(missing), missing


def show_proxies(viewport, groups) -> tuple[int, list]:
    """Back to the envelope for the proxies ``groups`` showing their full
    model (and their copies); an original edited meanwhile is written to its
    file first. Returns (how many definitions, names whose file could not
    be written — those stay as they are)."""
    scene = viewport.scene
    items, failed, done = [], [], set()
    for g in groups:
        info = proxy.info_of(g)
        if info is None or info["id"] in done or state(g) != "original":
            continue
        done.add(info["id"])
        fam = [s for s in scene.groups if (proxy.info_of(s) or {}).get("id") == info["id"]
               and state(s) == "original"]
        g0 = fam[0]
        if int(getattr(g0.mesh, "_mut_serial", 0)) != int(info.get("serial", -1)) \
                or proxy.original_file(info, viewport) is None:
            path = proxy.original_file(info, viewport) or Path(info.get("file") or "")
            try:
                proxy.write_original(path, g0, getattr(scene, "materials", {}) or {}, info["id"])
            except Exception:  # noqa: BLE001 - said below; it stays the full model
                _log.exception("could not write %s", path)
                failed.append(info.get("name") or g0.name)
                continue
        mesh = proxy.envelope_mesh(proxy.points(g0))
        if mesh is None:
            failed.append(info.get("name") or g0.name)
            continue
        new = dict(info)
        new["state"] = "proxy"
        new.pop("serial", None)
        new["faces"] = proxy.face_count(g0)
        new["proxy_faces"] = len(mesh.faces)
        new["mtime"] = proxy.file_date(proxy.original_file(new, viewport) or new.get("file") or "")
        for s in fam:
            ext = _without_dc(s.ext)
            ext[proxy.KEY] = dict(new)
            items.append((s, mesh, [], ext))
    if items:
        _execute(viewport, items, label=tr("Show proxy"))
    return len(done) - len(failed), failed
