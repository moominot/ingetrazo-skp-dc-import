# SPDX-License-Identifier: GPL-3.0-or-later
"""The cut plane of a window or a door: which side of the component is
flush with the wall, and so the way its hole is cut.

IngeTrazo's «Cut opening» cuts what the component has on its own base plane
(local ``z = 0``, the blue axis coming OUT of the wall). A component built
standing up — every dynamic component — has its blue axis vertical, so that
plane is the floor and it never cuts a wall.

Here a component can say which of its sides is the wall's: front (−Y), back
(+Y), left (−X), right (+X), top or bottom. It is kept with the mark, in
``ext["opening"]["plane"] = {"n": normal out of the wall, "d": distance of
the plane from the component's origin along it}``, and :func:`footprint`
takes the outline on that plane instead of ``z = 0``. A dynamic component
marked «Cut opening» with no plane says nothing, so it takes its front.

The component stays what it is (a dynamic component keeps its options, its
scale handles and its redraws); the arrow over a selected one shows where its
hole will go, and the flip reverses it.

This is a drop-in for ``core.openings.footprint`` (installed by
:func:`install`); the core's follow-up, which asks for it by name after every
command, then cuts and moves the hole as it always does.
"""
from __future__ import annotations

import copy
import math

SIDES = {                       # normal out of the wall, in the component's axes
    "front": (0.0, -1.0, 0.0), "back": (0.0, 1.0, 0.0),
    "left": (-1.0, 0.0, 0.0), "right": (1.0, 0.0, 0.0),
    "top": (0.0, 0.0, 1.0), "bottom": (0.0, 0.0, -1.0),
}
ARROW_LENGTH = 0.5              # metres
_EPS = 1e-4


def _core():
    import core.openings as o
    return o


def _is_dynamic(group) -> bool:
    from .dc.apply import KEY
    return bool((getattr(group, "ext", None) or {}).get(KEY))


def _entry(group) -> dict:
    ext = getattr(group, "ext", None)
    e = ext.get("opening") if isinstance(ext, dict) else None
    return e if isinstance(e, dict) else {}


def _local_points(group):
    """Every point of the component's geometry in its own axes."""
    from core.group import iter_placements
    o = _core()
    inv, ok = o._frame(group).inverted()
    if not ok:
        return []
    pts = []
    for g, m in iter_placements(group):
        for f in g.mesh.faces:
            pts += [inv.map(m.map(p) if m is not None else p) for p in f.vertices]
        for e in g.mesh.edges:
            pts += [inv.map(m.map(p) if m is not None else p) for p in (e.a, e.b)]
    return pts


def _distance_out(group, n) -> float:
    """How far the component reaches along ``n``: where its flush face is."""
    from PySide6.QtGui import QVector3D
    nv = QVector3D(*n)
    pts = _local_points(group)
    return max((QVector3D.dotProduct(p, nv) for p in pts), default=0.0)


#: (group, depth) tried in place of the plane's own, while a wall is searched.
_TRY: list = []


def plane_of(group):
    """``(n, d)`` — the normal out of the wall (component axes) and the
    plane's distance along it — or None for the core's own ``z = 0``."""
    for g, depth_plane in _TRY:
        if g is group:
            return depth_plane
    p = _entry(group).get("plane")
    if isinstance(p, dict) and isinstance(p.get("n"), (list, tuple)):
        return tuple(float(c) for c in p["n"]), float(p.get("d", 0.0))
    if _is_dynamic(group):
        n = SIDES["front"]
        return n, _distance_out(group, n)
    return None


def side_of(group) -> str | None:
    pl = plane_of(group)
    if pl is None:
        return None
    for name, v in SIDES.items():
        if all(abs(a - b) < 1e-6 for a, b in zip(v, pl[0])):
            return name
    return None


def _plane_matrix(n, d):
    """The matrix from the plane's own axes (x along the wall, y up it, z out
    of it) to the component's."""
    from PySide6.QtGui import QMatrix4x4, QVector3D
    nv = QVector3D(*n).normalized()
    if abs(nv.z()) < 0.9:
        x = QVector3D.crossProduct(QVector3D(0, 0, 1), nv).normalized()
    else:
        x = QVector3D(1, 0, 0)
    y = QVector3D.crossProduct(nv, x).normalized()
    c = nv * d
    return QMatrix4x4(x.x(), y.x(), nv.x(), c.x(),
                      x.y(), y.y(), nv.y(), c.y(),
                      x.z(), y.z(), nv.z(), c.z(),
                      0, 0, 0, 1)


def footprint(group):
    """The opening's outline in world coordinates, counter-clockwise seen
    from the blue axis of its plane (the side the wall's face looks to):
    the outer loop of the largest face on the plane, or with none there (or
    when it is dynamic, made of parts) the rectangle the component covers on
    it."""
    from PySide6.QtGui import QVector3D
    from core.group import iter_placements
    o = _core()
    plane = plane_of(group)
    if plane is None:
        return o._footprint_core(group)
    frame = o._frame(group) * _plane_matrix(*plane)
    inv, ok = frame.inverted()
    if not ok:
        return None
    # A dynamic component is made of parts (a frame's bars...): its opening is
    # the rectangle it covers, not its largest single face.
    use_faces = not _is_dynamic(group)
    best, best_area = None, 0.0
    lo = [float("inf")] * 2
    hi = [float("-inf")] * 2
    for g, m in iter_placements(group):
        for f in g.mesh.faces:
            loop = [m.map(p) if m is not None else QVector3D(p) for p in f.vertices]
            local = [inv.map(p) for p in loop]
            for p in local:
                lo[0], lo[1] = min(lo[0], p.x()), min(lo[1], p.y())
                hi[0], hi[1] = max(hi[0], p.x()), max(hi[1], p.y())
            if (use_faces and len(local) >= 3
                    and all(abs(p.z()) < o._PLANE_EPS for p in local)):
                area = abs(o._area2d([(p.x(), p.y()) for p in local]))
                if area > best_area:
                    best, best_area = local, area
        for e in g.mesh.edges:
            for p in (e.a, e.b):
                q = inv.map(m.map(p) if m is not None else QVector3D(p))
                lo[0], lo[1] = min(lo[0], q.x()), min(lo[1], q.y())
                hi[0], hi[1] = max(hi[0], q.x()), max(hi[1], q.y())
    if best is None:
        if not (hi[0] - lo[0] > 1e-4 and hi[1] - lo[1] > 1e-4):
            return None
        best = [QVector3D(lo[0], lo[1], 0), QVector3D(hi[0], lo[1], 0),
                QVector3D(hi[0], hi[1], 0), QVector3D(lo[0], hi[1], 0)]
    flat = [QVector3D(p.x(), p.y(), 0.0) for p in best]
    if o._area2d([(p.x(), p.y()) for p in flat]) < 0:
        flat.reverse()
    return [frame.map(p) for p in flat]


# ---- where along that side the wall is ---------------------------------------

def _depths(group, n, d) -> list:
    """The depths along ``n`` the wall's face may be at, the likeliest first:
    the stored one, the component's own origin, then every level its corners
    lie on, from the outermost in. A window rarely ends flat on the wall: a
    sill, a trim or a handle sticks out a few millimetres past the face it
    was drawn against."""
    from PySide6.QtGui import QVector3D
    nv = QVector3D(*n)
    levels = sorted({round(QVector3D.dotProduct(p, nv), 5)
                     for p in _local_points(group)}, reverse=True)
    out = []
    for depth in [0.0] + levels:
        inside = bool(levels) and levels[-1] - _EPS <= depth <= levels[0] + _EPS
        if inside and abs(depth - d) > _EPS and all(abs(depth - x) > _EPS for x in out):
            out.append(depth)
    return out


def find_host(scene, group):
    """``core.openings.find_host``, trying every depth of the chosen side
    (:func:`_depths`) until one lies on a wall's face."""
    o = _core()
    found = o._find_host_core(scene, group)
    plane = plane_of(group)
    if found[0] is not None or plane is None:
        return found
    n, d = plane
    for depth in _depths(group, n, d):
        _TRY.append((group, (n, depth)))
        try:
            found = o._find_host_core(scene, group)
        finally:
            _TRY.pop()
        # Only from the wall's outer side: a face looking the other way is
        # reached from inside the wall, and only its skin would be cut.
        if found[0] is not None and _looks_out(o, *found):
            return found
    return None, None


def _looks_out(o, host, prism) -> bool:
    from PySide6.QtGui import QVector3D
    face = o._host_face(host.mesh, prism["a"])
    return face is not None and (
        QVector3D.dotProduct(face.normal(), o._normal(prism["a"])) > 0
        or prism.get("b") is not None)


def install() -> None:
    """Put :func:`footprint` in place of the core's (once; the core's own
    stays as ``_footprint_core``, for a component with no plane)."""
    o = _core()
    if not hasattr(o, "_footprint_core"):
        o._footprint_core = o.footprint
    o.footprint = footprint
    if not hasattr(o, "_find_host_core"):
        o._find_host_core = o.find_host
    o.find_host = find_host


def uninstall() -> None:
    o = _core()
    if hasattr(o, "_footprint_core"):
        o.footprint = o._footprint_core
        del o._footprint_core
    if hasattr(o, "_find_host_core"):
        o.find_host = o._find_host_core
        del o._find_host_core


# ---- changing the plane ------------------------------------------------------

def _command(groups, planes):
    """One undo step that sets the plane of each group (and marks it «Cut
    opening»); the hole it had is marked out of date so the history's
    follow-up closes it and cuts the new one."""
    from core.history import Command

    class SetPlaneCommand(Command):
        keeps_paint = True
        keeps_groups = True

        def __init__(self):
            self._before = None

        def do(self, scene):
            self._before = [(g, copy.deepcopy(g.ext)) for g in groups]
            for g, plane in zip(groups, planes):
                ext = copy.deepcopy(g.ext) if g.ext else {}
                entry = dict(ext.get("opening") or {})
                entry["on"] = True
                entry["plane"] = {"n": list(plane[0]), "d": plane[1]}
                made = entry.get("made")
                if isinstance(made, dict):
                    entry["made"] = dict(made, xf=None)
                ext["opening"] = entry
                g.ext = ext
            scene.version += 1

        def undo(self, scene):
            for g, ext in self._before or ():
                g.ext = copy.deepcopy(ext) if ext else None
            scene.version += 1

    return SetPlaneCommand()


def set_side(viewport, group, side: str):
    """Make ``side`` the component's wall side, on it and its copies."""
    n = SIDES[side]
    targets = _core().siblings(viewport.scene, group)
    planes = [(n, _distance_out(g, n)) for g in targets]
    viewport.history.execute(_command(targets, planes))
    _report(viewport, targets)
    viewport.update()


def _report(viewport, targets) -> None:
    """Say why nothing was cut, when nothing was."""
    from .i18n import tr
    o = _core()
    flash = getattr(viewport, "flash_status", None)
    if flash is None or any((o.made(g) or {}).get("a") for g in targets):
        return
    if all(o.footprint(g) is None for g in targets):
        flash(tr("That side of the component has no area to cut with: choose another side"), 8000)
    else:
        flash(tr("No wall face under that side: place it against a wall, whole within its face"), 8000)


def flip(viewport, group):
    """Reverse the cut: the opposite side becomes the wall's."""
    cur = side_of(group)
    if cur is None:
        return False
    opposite = {"front": "back", "back": "front", "left": "right",
                "right": "left", "top": "bottom", "bottom": "top"}[cur]
    set_side(viewport, group, opposite)
    return True


# ---- the arrow ---------------------------------------------------------------

def selected_cutters(scene):
    o = _core()
    out = []
    for e in getattr(scene, "selection", ()) or ():
        g = getattr(e, "owner", None) or e
        if o.wants_opening(g) and all(g is not x for x in out):
            out.append(g)
    return out


def _where_cut(group):
    """The footprint at the depth the hole was cut at, when it was found away
    from the side's own depth; None otherwise."""
    from PySide6.QtGui import QVector3D
    o = _core()
    rec = o.made(group)
    plane = plane_of(group)
    if not rec or not rec.get("a") or plane is None:
        return None
    if rec.get("host") is not None:      # kept in the wall's own frame
        return None
    return [QVector3D(*p) for p in rec["a"]]


def draw_arrow(app, viewport, painter) -> None:
    """Over each selected window or door: an arrow from the middle of its wall
    side into the wall, the way its hole is cut."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF
    from .i18n import tr
    o = _core()
    for g in selected_cutters(viewport.scene):
        fp = _where_cut(g) or o.footprint(g)
        if not fp:
            continue
        n = o._normal(fp)
        c = o._centroid(fp)
        a = viewport._world_to_pixel(c)
        b = viewport._world_to_pixel(c - n * ARROW_LENGTH)
        if a is None or b is None:
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        color = QColor(232, 116, 42)
        painter.setPen(QPen(color, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(*a), 3.5, 3.5)
        if length < 6:                 # seen head on: only the label
            painter.drawText(QPointF(a[0] + 8, a[1] - 8), tr("Cut direction"))
            continue
        painter.drawLine(QPointF(*a), QPointF(*b))
        ux, uy = dx / length, dy / length
        head = 11.0
        left = QPointF(b[0] - head * (ux * 0.87 - uy * 0.5),
                       b[1] - head * (uy * 0.87 + ux * 0.5))
        right = QPointF(b[0] - head * (ux * 0.87 + uy * 0.5),
                        b[1] - head * (uy * 0.87 - ux * 0.5))
        painter.drawPolygon(QPolygonF([QPointF(*b), left, right]))
        painter.drawText(QPointF(b[0] + 8, b[1] - 6), tr("Cut direction"))


def flip_icon():
    """A small two-headed arrow, drawn in the palette's text colour."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    ink = app.palette().windowText().color() if app else QColor(40, 44, 52)
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(ink, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(8, 24), QPointF(40, 24))
    p.setBrush(ink)
    p.drawPolygon(QPolygonF([QPointF(6, 24), QPointF(16, 17), QPointF(16, 31)]))
    p.drawPolygon(QPolygonF([QPointF(42, 24), QPointF(32, 17), QPointF(32, 31)]))
    p.setPen(QPen(QColor(232, 116, 42), 2.4))
    p.drawLine(QPointF(24, 8), QPointF(24, 40))
    p.end()
    return QIcon(pm)
