# SPDX-License-Identifier: GPL-3.0-or-later
"""Small previews of components, drawn on the CPU: an isometric view with
flat shading and the painter's algorithm. No OpenGL, so it also works
offscreen; meant for 64–128 px icons, not for rendering."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF

_MAX_FACES = 4000          # past this, draw a sample: it is only an icon


def _iso(p):
    """Project a world point (x right, y into the screen, z up) to 2-D,
    returning (sx, sy, depth)."""
    a, b = math.radians(45), math.radians(35.264)
    x, y, z = p.x(), p.y(), p.z()
    rx = x * math.cos(a) - y * math.sin(a)
    ry = x * math.sin(a) + y * math.cos(a)
    return rx, -(z * math.cos(b) - ry * math.sin(b)), ry * math.cos(b) + z * math.sin(b)


def _normal(pts):
    """Unit normal of a polygon from its first three corners, as (x, y, z);
    (0, 0, 1) when they are collinear (only the shade depends on it)."""
    a, b, c = pts[0], pts[1], pts[2]
    ux, uy, uz = b.x() - a.x(), b.y() - a.y(), b.z() - a.z()
    vx, vy, vz = c.x() - a.x(), c.y() - a.y(), c.z() - a.z()
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / ln, ny / ln, nz / ln) if ln > 1e-12 else (0.0, 0.0, 1.0)


def _sample(group, limit=_MAX_FACES):
    """About ``limit`` faces of ``group`` in WORLD space, evenly spread over
    its placements, as ``[(corners, normal)]``.

    Never merges the placements into one mesh: ``world_mesh`` over a tree of
    3.6 million faces (a model's terrain, its building shell) took tens of
    seconds of a window that does not answer, to keep 4 000 faces for a
    64-px icon. Counting and slicing each shared mesh costs milliseconds."""
    from itertools import islice
    from core.group import iter_placements
    parts = [(g.mesh.faces, m) for g, m in iter_placements(group)]
    total = sum(len(faces) for faces, _m in parts)
    if not total:
        return []
    step = total // limit + 1
    out, seen = [], 0
    for faces, m in parts:
        first = (-seen) % step
        seen += len(faces)
        picked = faces[first::step] if isinstance(faces, list) \
            else islice(faces, first, None, step)
        for f in picked:
            pts = list(f.vertices)
            if len(pts) < 3:
                continue
            if m is not None:
                pts = [m.map(v) for v in pts]
            out.append((pts, _normal(pts)))
    return out


def render(group, size: int = 96, base="#c8ccd2") -> QPixmap:
    """The preview of ``group`` as a ``size``-px square pixmap (transparent
    background). An empty or unreadable component gives a blank pixmap."""
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    try:
        sample = _sample(group)
    except Exception:  # noqa: BLE001 - a preview must never break the panel
        return px
    if not sample:
        return px
    polys = []
    for corners, n in sample:
        pts = [_iso(v) for v in corners]
        # light from the upper left; keep a floor so back faces stay visible
        shade = 0.45 + 0.55 * abs(0.5 * n[0] - 0.35 * n[1] + 0.8 * n[2])
        polys.append((sum(p[2] for p in pts) / len(pts), pts, min(1.0, shade)))
    if not polys:
        return px
    xs = [p[0] for _d, pts, _s in polys for p in pts]
    ys = [p[1] for _d, pts, _s in polys for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = (size - 8) / max(w, h, 1e-9)
    ox = (size - w * scale) / 2 - min(xs) * scale
    oy = (size - h * scale) / 2 - min(ys) * scale
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    c = QColor(base)
    for _d, pts, shade in sorted(polys, key=lambda t: t[0]):
        col = QColor(int(c.red() * shade), int(c.green() * shade), int(c.blue() * shade))
        painter.setBrush(col)
        painter.setPen(col.darker(150))
        painter.drawPolygon(QPolygonF([QPointF(p[0] * scale + ox, p[1] * scale + oy)
                                       for p in pts]))
    painter.end()
    return px
