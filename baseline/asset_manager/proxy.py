# SPDX-License-Identifier: GPL-3.0-or-later
"""Insert a model as a proxy: a light envelope (its convex hull, through a
few dozen of its outermost points; a box when it is flat) stands in the
drawing while the full model is kept in an .igz file of its own.

The data follows the Proxies extension (PESI3D/ingetrazo-proxies,
GPL-3.0-or-later), so its Show Originals / Show Proxies work on what this
panel inserts, and a renderer that knows the format can swap the original
back in:

* in the drawing, the proxy is a component whose mesh is the envelope, with
  ``group.ext["proxy_tool"] = {"id", "file", "rel", "state": "proxy",
  "faces", "proxy_faces", "local", "name", "params", "source"}``;
* the original file holds one component at identity (its definition), with
  ``ext["proxy_tool"] = {"id"}`` and the materials it uses.

Only the data format is shared; no code is taken from that extension.

The proxy id comes from the source file (path, size, date): the same model
inserted again shares the proxy already in the drawing (one definition,
nothing read) and its original file.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path

_log = logging.getLogger(__name__)

KEY = "proxy_tool"
#: The proxy's settings, in the Proxies extension's terms (its Show Proxies
#: rebuilds a stand-in from these): a convex hull through ``hull_points``
#: outermost points, in its orange.
PARAMS = {"type": "hull", "hull_points": 64, "color": [0.95, 0.55, 0.15], "see_through": False}
#: Edges between envelope faces flatter than this are soft (a smooth surface).
SOFT_DEG = 30.0
FOLDER_SUFFIX = "_proxies"
#: A model with more faces than this is not written to its original file when
#: it goes in as a proxy (minutes for a tree of leaves): it is read again from
#: its source file at Show original, and written then if it is needed.
LAZY_FACES = 200_000


# --- what is a proxy ----------------------------------------------------------
def info_of(group) -> dict | None:
    info = (getattr(group, "ext", None) or {}).get(KEY)
    return info if isinstance(info, dict) and info.get("id") else None


def proxy_id(path) -> str:
    """A stable id for the model file ``path``: the same file (same size and
    date) gives the same id."""
    p = Path(path)
    try:
        st = p.stat()
        sig = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        sig = str(p)
    return hashlib.sha1(sig.encode("utf-8", "replace")).hexdigest()[:16]


def find_in(scene, pid: str):
    """A placement in the drawing (top level) of the proxy ``pid`` while it
    shows its box, or None."""
    for g in getattr(scene, "groups", ()) or ():
        info = info_of(g)
        if info and info["id"] == pid and info.get("state") == "proxy":
            return g
    return None


def has_dynamic(group) -> bool:
    """Whether ``group`` or anything inside it is a dynamic component."""
    from core.group import iter_placements

    from .inventory import is_dynamic
    return any(is_dynamic(g) for g, _m in iter_placements(group))


# --- where the originals go -----------------------------------------------------
def document_path(viewport):
    win = viewport.window() if hasattr(viewport, "window") else None
    p = getattr(win, "_current_path", None)
    return Path(p) if p else None


def originals_folder(viewport) -> Path:
    """``<document>_proxies`` next to a saved drawing (the project folder
    moves as a whole, as with the Proxies extension); the extension's own
    folder while the drawing has never been saved."""
    doc = document_path(viewport)
    if doc is not None:
        return doc.with_name(doc.stem + FOLDER_SUFFIX)
    from .catalog import home
    return home() / "proxies"


def _safe(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name or "", flags=re.UNICODE).strip("_")
    return s[:48] or "model"


def original_file(info: dict, viewport) -> Path | None:
    """The original's file: relative to the drawing first (a project folder
    moved as a whole), then the path it was written to; None when neither
    exists."""
    doc = document_path(viewport)
    rel = info.get("rel")
    if rel and doc is not None:
        p = Path(os.path.normpath(doc.parent / rel))
        if p.is_file():
            return p
    p = Path(info.get("file") or "")
    return p if info.get("file") and p.is_file() else None


def file_date(path) -> int:
    """The file's date (ns), 0 when it is not there: a proxy remembers its
    original's, so an original saved meanwhile (opened in its own tab) is
    noticed."""
    try:
        return int(Path(path).stat().st_mtime_ns)
    except OSError:
        return 0


def _relative(path: Path, viewport):
    doc = document_path(viewport)
    if doc is None:
        return None
    try:
        return os.path.relpath(path, doc.parent)
    except ValueError:          # another drive (Windows)
        return None


# --- the geometry ---------------------------------------------------------------------
def points(group):
    """Every vertex of ``group`` in its own axes (nested placements folded
    in), as an ``(n, 3)`` array."""
    import numpy as np
    from PySide6.QtGui import QMatrix4x4

    from core.group import Group, iter_placements, np_affine
    root = Group.__new__(Group)        # the definition at identity
    root.mesh = group.mesh
    root.children = list(getattr(group, "children", None) or [])
    root.xform = QMatrix4x4()
    out = []
    cache: dict = {}
    for pg, m in iter_placements(root):
        P = cache.get(id(pg.mesh))
        if P is None:
            P = cache[id(pg.mesh)] = np.array(
                [v.position.toTuple() for v in pg.mesh.vertices], dtype=np.float64).reshape(-1, 3)
        if not len(P):
            continue
        if m is not None:
            rot, tr = np_affine(m)
            P = P @ rot.T + tr
        out.append(P)
    return np.vstack(out) if out else np.zeros((0, 3))


def islands(mesh):
    """The vertices of ``mesh`` grouped by the pieces of surface that touch
    (faces sharing a vertex), as a list of ``(n, 3)`` arrays."""
    import numpy as np
    index = {id(v): n for n, v in enumerate(mesh.vertices)}
    if not index:
        return []
    root = list(range(len(index)))

    def find(a):
        while root[a] != a:
            root[a] = root[root[a]]
            a = root[a]
        return a
    for f in mesh.faces:
        ids = [index[id(v)] for v in f.loop if id(v) in index]
        for b in ids[1:]:
            root[find(b)] = find(ids[0])
    used = {find(index[id(v)]) for f in mesh.faces for v in f.loop[:1] if id(v) in index}
    groups: dict = {}
    for v in mesh.vertices:
        r = find(index[id(v)])
        if r in used:
            groups.setdefault(r, []).append(v.position.toTuple())
    return [np.array(g, dtype=np.float64).reshape(-1, 3) for g in groups.values()]


#: Past this many faces a model is wrapped as a whole (one hull): splitting it
#: in pieces walks every face in Python, too slow for a tree of leaves.
SPLIT_FACES = 8000


def parts(group, limit: int = 6):
    """The points of ``group`` split by what it is made of: each separate piece
    of its own surface and each direct sub-component, as a list of ``(n, 3)`` arrays in the group's
    axes. One wrapped envelope per part follows the model much closer than a
    single hull (a table's legs are not filled in). A single array when there
    is nothing to split. More than ``limit`` parts are merged (the small ones
    into their nearest big one)."""
    import numpy as np

    from core.group import np_affine
    if face_count(group) > SPLIT_FACES:
        whole = points(group)
        return [whole] if len(whole) else []
    out = []
    out.extend(a for a in islands(group.mesh) if len(a))
    for ch in getattr(group, "children", None) or ():
        P = points(ch)
        if not len(P):
            continue
        xf = getattr(ch, "xform", None)
        if xf is not None:
            rot, tr = np_affine(xf)
            P = P @ rot.T + tr
        out.append(P)
    if not out:
        return []
    if len(out) > limit:
        out = _merge_small(out, limit)
    return out


def _merge_small(sets, limit: int):
    """At most ``limit`` point sets: the biggest (by the size of their box)
    stay, every other joins the nearest of them, so the envelope stays light
    (a few hulls, not one per screw)."""
    import numpy as np
    size = np.array([float(np.linalg.norm(a.max(axis=0) - a.min(axis=0))) for a in sets])
    order = np.argsort(-size)
    seeds = [sets[i] for i in order[:limit]]
    centres = np.array([(a.min(axis=0) + a.max(axis=0)) / 2 for a in seeds])
    joined = [[a] for a in seeds]
    for i in order[limit:]:
        c = (sets[i].min(axis=0) + sets[i].max(axis=0)) / 2
        joined[int(np.argmin(np.linalg.norm(centres - c, axis=1)))].append(sets[i])
    return [np.vstack(j) for j in joined]


def bounds(group):
    """``(lo, hi)`` of everything in ``group`` in its own axes, or None when
    it has no vertices."""
    P = points(group)
    return (P.min(axis=0), P.max(axis=0)) if len(P) else None


# --- the envelope ------------------------------------------------------------------------
def directions(k: int):
    """``k`` directions spread evenly over the sphere (a golden-angle spiral)."""
    import numpy as np
    i = np.arange(k) + 0.5
    z = 1.0 - 2.0 * i / k
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    a = i * np.pi * (3.0 - np.sqrt(5.0))
    return np.column_stack([r * np.cos(a), r * np.sin(a), z])


def outermost(P, k: int = 64):
    """The points of ``P`` farthest along ``k`` directions (and along the
    axes): the few a convex envelope goes through."""
    import numpy as np
    D = np.vstack([directions(k), np.eye(3), -np.eye(3)])
    idx = np.unique(np.argmax(P @ D.T, axis=0))
    return P[idx]


def hull(P):
    """The convex hull of a few points: ``(V, tris)``, the triangles wound
    counter-clockwise seen from outside. None when the points are flat (or a
    line, or one point): no volume to wrap."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64)
    if len(P) < 4:
        return None
    size = float(np.ptp(P, axis=0).max())
    if size <= 0.0:
        return None
    eps = 1e-9 * size
    # A first tetrahedron: a point at one end, the farthest from it, the
    # farthest from their line, the farthest from their plane.
    a = int(np.argmin(P[:, 0]))
    b = int(np.argmax(np.linalg.norm(P - P[a], axis=1)))
    ab = P[b] - P[a]
    c = int(np.argmax(np.linalg.norm(np.cross(P - P[a], ab), axis=1)))
    n = np.cross(ab, P[c] - P[a])
    if np.linalg.norm(n) <= eps * size:
        return None
    dist = (P - P[a]) @ (n / np.linalg.norm(n))
    d = int(np.argmax(np.abs(dist)))
    if abs(dist[d]) <= 1e-6 * size:
        return None
    inside = (P[a] + P[b] + P[c] + P[d]) / 4.0

    def face(i, j, k):
        nrm = np.cross(P[j] - P[i], P[k] - P[i])
        if np.dot(nrm, P[i] - inside) < 0:          # turned to face outward
            j, k = k, j
            nrm = -nrm
        return (i, j, k, nrm / (np.linalg.norm(nrm) or 1.0))

    faces = [face(a, b, c), face(a, b, d), face(a, c, d), face(b, c, d)]
    for p in range(len(P)):
        if p in (a, b, c, d):
            continue
        seen = [f for f in faces if np.dot(f[3], P[p] - P[f[0]]) > eps]
        if not seen:
            continue                                  # inside: nothing to wrap
        edges = set()
        for i, j, k, _n in seen:
            edges.update(((i, j), (j, k), (k, i)))
        horizon = [(i, j) for (i, j) in edges if (j, i) not in edges]
        gone = {id(f) for f in seen}
        faces = [f for f in faces if id(f) not in gone]
        for i, j in horizon:
            nrm = np.cross(P[j] - P[i], P[p] - P[i])
            ln = np.linalg.norm(nrm)
            faces.append((i, j, p, nrm / (ln or 1.0)))
    used = sorted({v for f in faces for v in f[:3]})
    where = {v: m for m, v in enumerate(used)}
    return P[used], [(where[i], where[j], where[k]) for i, j, k, _n in faces]


def envelope_mesh(P, colour=None, k: int = PARAMS["hull_points"]):
    """A mesh: the convex envelope of the points ``P`` through about ``k`` of
    the outermost ones, its gentle folds soft; the box when the points are
    flat. ``P`` may also be a list of point arrays (see :func:`parts`): each
    gets its own envelope, in one mesh. None when there is nothing to wrap."""
    import math

    import numpy as np
    from PySide6.QtGui import QVector3D

    from core.mesh import Mesh
    sets = [np.asarray(a, dtype=np.float64) for a in P] if isinstance(P, (list, tuple)) else [P]
    sets = [a for a in sets if len(a)]
    if not sets:
        return None
    kk = k if len(sets) == 1 else 20      # several parts: lighter each
    colour = tuple(list(colour or PARAMS["color"])[:3] + [1.0])
    mesh = Mesh()
    for a in sets:
        got = hull(outermost(a, kk))
        if got is None:
            box_mesh(a.min(axis=0), a.max(axis=0), colour, mesh)
            continue
        V, tris = got
        for i, j, m in tris:
            try:
                f = mesh.add_face([QVector3D(*V[i]), QVector3D(*V[j]), QVector3D(*V[m])])
            except Exception:  # noqa: BLE001 - a sliver too thin to be a face
                continue
            if f is not None:
                f.attrs["color"] = colour
    if not mesh.faces:
        return None
    lim = math.cos(math.radians(SOFT_DEG))
    normals: dict = {}
    for e in mesh.edges:
        if len(e.faces) != 2:
            continue
        n1, n2 = (normals.setdefault(id(f), f.normal()) for f in e.faces)
        if n1.x() * n2.x() + n1.y() * n2.y() + n1.z() * n2.z() >= lim:
            e.soft = True
    mesh._chunk_dirty = True
    return mesh


# --- the box ----------------------------------------------------------------------


def box_mesh(lo, hi, colour=None, mesh=None):
    """A mesh: the box from ``lo`` to ``hi`` (6 faces, outward), a single
    rectangle when it is flat. None when it is a line or a point. With ``mesh``,
    the faces are added to it (and it is returned)."""
    from PySide6.QtGui import QVector3D

    from core.mesh import Mesh
    colour = list(colour or PARAMS["color"])[:3] + [1.0]
    size = [float(hi[i] - lo[i]) for i in range(3)]
    tiny = 1e-6 * (max(size) or 1.0)
    flat = [s <= tiny for s in size]
    mesh = Mesh() if mesh is None else mesh

    def corner(x, y, z):
        return QVector3D(float((lo, hi)[x][0]), float((lo, hi)[y][1]), float((lo, hi)[z][2]))

    if sum(flat) >= 2:
        return None if mesh is None or not mesh.faces else mesh
    if sum(flat) == 1:
        k = flat.index(True)
        u, v = [i for i in range(3) if i != k]
        loop = []
        for cu, cv in ((0, 0), (1, 0), (1, 1), (0, 1)):
            idx = [0, 0, 0]
            idx[u], idx[v] = cu, cv
            loop.append(corner(*idx))
        loops = [loop]
    else:
        loops = [
            [corner(0, 0, 0), corner(0, 1, 0), corner(1, 1, 0), corner(1, 0, 0)],   # bottom
            [corner(0, 0, 1), corner(1, 0, 1), corner(1, 1, 1), corner(0, 1, 1)],   # top
            [corner(0, 0, 0), corner(1, 0, 0), corner(1, 0, 1), corner(0, 0, 1)],   # front
            [corner(0, 1, 0), corner(0, 1, 1), corner(1, 1, 1), corner(1, 1, 0)],   # back
            [corner(0, 0, 0), corner(0, 0, 1), corner(0, 1, 1), corner(0, 1, 0)],   # left
            [corner(1, 0, 0), corner(1, 1, 0), corner(1, 1, 1), corner(1, 0, 1)],   # right
        ]
    for loop in loops:
        f = mesh.add_face(loop)
        if f is not None:
            f.attrs["color"] = tuple(colour)
    mesh._chunk_dirty = True
    return mesh


def face_count(group) -> int:
    from core.group import iter_placements
    return sum(len(pg.mesh.faces) for pg, _m in iter_placements(group))


# --- the original file --------------------------------------------------------------
def _used_materials(materials: dict, group) -> dict:
    from core.group import iter_placements
    names = set()
    for pg, _m in iter_placements(group):
        for f in pg.mesh.faces:
            a = f.attrs or {}
            if a.get("mat"):
                names.add(a["mat"])
            back = a.get("back")
            if isinstance(back, dict) and back.get("mat"):
                names.add(back["mat"])
    return {n: m for n, m in (materials or {}).items() if n in names}


def write_original(path: Path, group, materials: dict, pid: str) -> None:
    """``path``: an .igz holding ``group``'s definition at identity, tagged
    with the proxy id (a file that exists keeps its other originals)."""
    from PySide6.QtGui import QMatrix4x4

    from core.group import Group
    from core.scene import Scene
    from formats import igz
    entry = Group(group.mesh, name=group.name)
    entry.xform = QMatrix4x4()
    entry.component = True
    entry.children = list(getattr(group, "children", None) or [])
    entry.layer = getattr(group, "layer", None)
    entry.material = getattr(group, "material", None)
    ext = dict(getattr(group, "ext", None) or {})
    ext[KEY] = {"id": pid}
    entry.ext = ext
    out = Scene()
    if path.is_file():
        old = Scene()
        igz.load_into(old, path)
        out.groups = [g for g in old.groups if (info_of(g) or {}).get("id") != pid]
        out.materials = dict(old.materials)
    out.groups = list(out.groups) + [entry]
    out.materials.update(_used_materials(materials, group))
    path.parent.mkdir(parents=True, exist_ok=True)
    igz.save_scene(out, path)


# --- the proxy ----------------------------------------------------------------------
def make(viewport, group, materials: dict, source) -> object:
    """The proxy of ``group`` (a component read from ``source``, not in the
    drawing; ``materials`` = its file's registry): writes the original file
    and returns a new component holding the box, at ``group``'s place."""
    from PySide6.QtGui import QMatrix4x4

    from core.group import Group
    from core.insert import ensure_layers
    pid = proxy_id(source)
    mesh = envelope_mesh(parts(group))
    if mesh is None:
        raise RuntimeError("the model is too thin for a proxy")
    path = originals_folder(viewport) / f"{_safe(group.name)}_{pid[:6]}.igz"
    faces = face_count(group)
    lazy = faces > LAZY_FACES and Path(source).is_file()
    if not lazy:
        write_original(path, group, materials, pid)
    g = Group(mesh, name=group.name)
    g.xform = QMatrix4x4(group.xform) if getattr(group, "xform", None) is not None else QMatrix4x4()
    g.component = True
    g.layer = getattr(group, "layer", None)
    g.material = getattr(group, "material", None)
    g.ext = {KEY: {
        "id": pid, "file": str(path), "rel": _relative(path, viewport), "state": "proxy",
        "faces": faces, "proxy_faces": len(mesh.faces), "local": True,
        "name": group.name, "params": dict(PARAMS), "source": str(source),
        "dynamic": has_dynamic(group), "mtime": 0 if lazy else file_date(path)}}
    if lazy:
        g.ext[KEY]["lazy"] = True          # the original file does not exist yet
    ensure_layers(viewport.scene, g)
    return g
