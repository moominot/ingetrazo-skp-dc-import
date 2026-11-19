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


def render(group, size: int = 96, base="#c8ccd2") -> QPixmap:
    """The preview of ``group`` as a ``size``-px square pixmap (transparent
    background). An empty or unreadable component gives a blank pixmap."""
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    try:
        from core.group import world_mesh
        mesh = world_mesh(group)
        faces = list(mesh.faces)
    except Exception:  # noqa: BLE001 - a preview must never break the panel
        return px
    if not faces:
        return px
    if len(faces) > _MAX_FACES:
        faces = faces[::len(faces) // _MAX_FACES + 1]
    polys = []
    for f in faces:
        pts = [_iso(v) for v in f.vertices]
        if len(pts) < 3:
            continue
        n = f.normal()
        # light from the upper left; keep a floor so back faces stay visible
        shade = 0.45 + 0.55 * abs(0.5 * n.x() - 0.35 * n.y() + 0.8 * n.z())
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
