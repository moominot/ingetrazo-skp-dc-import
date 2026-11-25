# SPDX-License-Identifier: GPL-3.0-or-later
"""Icons in the style of IngeTrazo's own: thin ink outlines on a 48-unit
canvas, accent colour for fills and handles, drawn by code (no image files).

They follow the theme: the ink and the accent are read when the icon is
painted, so a change of theme or accent colour redraws them without the
extension doing anything. Outside IngeTrazo (tests) they fall back to a
dark grey and orange.

This file is the same in every extension of the repository (each ships
alone, so it cannot import the others'); keep the copies identical.

    icon("comp_import")           -> QIcon, for a toolbar button
    app.add_panel(..., **panel_icon(app, "comp_manager"))   -> a tab icon
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF)
from PySide6.QtWidgets import QApplication

_PX = 48
#: Line width as IngeTrazo draws it (3.0 at 65 %): about 1 px at 24 px.
_WIDTH = 3.0 * 0.65


def _ink() -> QColor:
    try:
        from views.theme import icon_ink
        return icon_ink()
    except Exception:  # noqa: BLE001 - outside the app
        app = QApplication.instance()
        if app is not None:
            c = app.palette().windowText().color()
            return QColor(c.red(), c.green(), c.blue())
        return QColor(40, 44, 52)


def _accent() -> QColor:
    try:
        from views.theme import accent_color
        return accent_color()
    except Exception:  # noqa: BLE001
        return QColor(232, 116, 42)


def _pen(color: QColor, width: float = _WIDTH, style=Qt.SolidLine) -> QPen:
    pen = QPen(color, width, style)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _fill(p: QPainter, shape, alpha: int) -> None:
    """``shape`` (a polygon or path) filled with the accent, no outline."""
    p.save()
    p.setPen(Qt.NoPen)
    c = _accent()
    c.setAlpha(alpha)
    p.setBrush(c)
    if isinstance(shape, QPainterPath):
        p.drawPath(shape)
    else:
        p.drawPolygon(shape)
    p.restore()


def _dot(p: QPainter, x: float, y: float, r: float = 3.0) -> None:
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(_accent())
    p.drawEllipse(QPointF(x, y), r, r)
    p.restore()


def _cube(p: QPainter, ink: QColor, cx: float, cy: float, r: float) -> None:
    """A cube seen corner-on, ``r`` from its centre to its top vertex,
    its faces tinted as IngeTrazo's boxes are."""
    k = 0.866 * r
    t, b = QPointF(cx, cy - r), QPointF(cx, cy + r)
    ul, ur = QPointF(cx - k, cy - r / 2), QPointF(cx + k, cy - r / 2)
    ll, lr = QPointF(cx - k, cy + r / 2), QPointF(cx + k, cy + r / 2)
    c = QPointF(cx, cy)
    left, right, lid = (QPolygonF([ul, c, b, ll]), QPolygonF([c, ur, lr, b]),
                        QPolygonF([t, ur, c, ul]))
    _fill(p, left, 150)
    _fill(p, right, 90)
    _fill(p, lid, 50)
    p.setBrush(Qt.NoBrush)
    for face in (left, right, lid):
        p.drawPolygon(face)


def _arrow_head(p: QPainter, tip: QPointF, dx: float, dy: float,
                size: float = 6.0) -> None:
    """A filled accent arrow head at ``tip`` pointing along (dx, dy)."""
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    base = QPointF(tip.x() - dx * size, tip.y() - dy * size)
    px, py = -dy * size * 0.7, dx * size * 0.7
    _fill(p, QPolygonF([tip, QPointF(base.x() + px, base.y() + py),
                        QPointF(base.x() - px, base.y() - py)]), 255)


# ---- the drawings: (painter, ink) into the 8..40 box --------------------------

def _comp_import(p, ink):
    # An arrow comes down into a tray holding a cube.
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(8, 30), QPointF(8, 40), QPointF(40, 40),
                              QPointF(40, 30)]))
    _cube(p, ink, 24, 31, 7)
    p.drawLine(QPointF(24, 6), QPointF(24, 17))
    _arrow_head(p, QPointF(24, 21), 0, 1)


def _comp_export(p, ink):
    # The same tray, the arrow leaving it.
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(8, 30), QPointF(8, 40), QPointF(40, 40),
                              QPointF(40, 30)]))
    _cube(p, ink, 24, 31, 7)
    p.drawLine(QPointF(24, 9), QPointF(24, 20))
    _arrow_head(p, QPointF(24, 5), 0, -1)


def _comp_settings(p, ink):
    # Three sliders, their knobs in the accent.
    for y, x in ((14, 17), (24, 31), (34, 22)):
        p.drawLine(QPointF(8, y), QPointF(40, y))
        _dot(p, x, y, 3.6)


def _comp_help(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 24), 16, 16)
    q = QPainterPath()
    q.moveTo(18.5, 19)
    q.cubicTo(18.5, 10.5, 30.5, 10.5, 30.5, 18.5)
    q.cubicTo(30.5, 23, 24, 23, 24, 28.5)
    p.drawPath(q)
    _dot(p, 24, 34, 2.4)


def _comp_options(p, ink):
    # A component and the options it offers: two sliders under it.
    _cube(p, ink, 24, 16, 9)
    for y, x in ((33, 18), (41, 31)):
        p.drawLine(QPointF(8, y), QPointF(40, y))
        _dot(p, x, y, 3.0)


def _comp_attributes(p, ink):
    # A component over a table of attributes: its first column tinted.
    _cube(p, ink, 24, 14, 8)
    p.setBrush(Qt.NoBrush)
    _fill(p, QPolygonF([QPointF(8, 27), QPointF(20, 27),
                        QPointF(20, 40), QPointF(8, 40)]), 110)
    p.drawRect(QRectF(8, 27, 32, 13))
    p.drawLine(QPointF(20, 27), QPointF(20, 40))
    p.drawLine(QPointF(8, 33.5), QPointF(40, 33.5))


def _comp_manager(p, ink):
    # The library: three components stacked like a pyramid.
    _cube(p, ink, 15, 16, 7.5)
    _cube(p, ink, 33, 16, 7.5)
    _cube(p, ink, 24, 32, 7.5)


def _comp_online(p, ink):
    # A globe — its meridian tinted — for what comes from the web.
    globe = QPainterPath()
    globe.addEllipse(QPointF(24, 24), 7, 16)
    _fill(p, globe, 70)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 24), 16, 16)
    p.drawEllipse(QPointF(24, 24), 7, 16)
    p.drawLine(QPointF(8, 24), QPointF(40, 24))
    p.drawLine(QPointF(11, 15), QPointF(37, 15))
    p.drawLine(QPointF(11, 33), QPointF(37, 33))


def _render_studio(p, ink):
    # A camera: its lens lit in the accent, the flash above.
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(7, 15, 34, 24), 4, 4)
    p.drawPolyline(QPolygonF([QPointF(16, 15), QPointF(18.5, 10),
                              QPointF(29.5, 10), QPointF(32, 15)]))
    lens = QPainterPath()
    lens.addEllipse(QPointF(24, 27), 7, 7)
    _fill(p, lens, 130)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 27), 7, 7)
    _dot(p, 35, 20, 1.8)


def _clock(p, ink):
    # A stopwatch: its crown and button, the dial with the elapsed quarter in the accent, and the hand.
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 27), 14, 14)
    p.drawLine(QPointF(19, 8), QPointF(29, 8))
    p.drawLine(QPointF(24, 8), QPointF(24, 13))
    p.drawLine(QPointF(35, 14), QPointF(38.5, 10.5))
    wedge = QPainterPath()
    wedge.moveTo(24, 27)
    wedge.arcTo(QRectF(10, 13, 28, 28), 90, -90)
    wedge.closeSubpath()
    _fill(p, wedge, 120)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(24, 27), QPointF(24, 18))
    _dot(p, 24, 27, 2.2)


def _arc_arrow(p, start: float, span: float, r: float = 15.0) -> None:
    """An arc of the circle of radius ``r`` about (24, 24), from ``start`` degrees (counter-clockwise, as Qt counts)
    over ``span``, with an accent arrow head at its end."""
    p.setBrush(Qt.NoBrush)
    q = QPainterPath()
    q.arcMoveTo(QRectF(24 - r, 24 - r, 2 * r, 2 * r), start)
    q.arcTo(QRectF(24 - r, 24 - r, 2 * r, 2 * r), start, span)
    p.drawPath(q)
    a = math.radians(start + span)
    sign = 1.0 if span >= 0 else -1.0
    _arrow_head(p, QPointF(24 + r * math.cos(a), 24 - r * math.sin(a)),
                -sign * math.sin(a), -sign * math.cos(a), 7.0)


def _follow_camera(p, ink):
    # The viewport's frame (corner marks) with a cube in it: the preview follows the 3D view.
    p.setBrush(Qt.NoBrush)
    for pts in ((8, 16, 8, 8, 16, 8), (32, 8, 40, 8, 40, 16),
                (40, 32, 40, 40, 32, 40), (16, 40, 8, 40, 8, 32)):
        p.drawPolyline(QPolygonF([QPointF(pts[0], pts[1]), QPointF(pts[2], pts[3]),
                                  QPointF(pts[4], pts[5])]))
    _cube(p, ink, 24, 24, 9)


def _follow_changes(p, ink):
    # Two arrows chasing each other round a dot: it updates by itself.
    _arc_arrow(p, 30, 130)
    _arc_arrow(p, 210, 130)
    _dot(p, 24, 24, 3.0)


def _refresh(p, ink):
    # One heavy arrow round, its head large: update now. (With the thin arc and small head of the others it read as a «C».)
    r, end = 13.0, math.radians(70)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(ink, _WIDTH * 1.7))
    q = QPainterPath()
    q.arcMoveTo(QRectF(24 - r, 24 - r, 2 * r, 2 * r), 10)
    q.arcTo(QRectF(24 - r, 24 - r, 2 * r, 2 * r), 10, -300)       # clockwise, round to near the top
    p.drawPath(q)
    dx, dy = math.sin(end), math.cos(end)                          # the way it goes there (clockwise, y down)
    _arrow_head(p, QPointF(24 + r * math.cos(end) + 10 * dx, 24 - r * math.sin(end) + 10 * dy), dx, dy, 14.0)


def _capture(p, ink):
    # A camera's diaphragm: six blades round its opening, which is in the accent. The picture is taken.
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 24), 17, 17)
    corners = [QPointF(24 + 8 * math.cos(math.radians(60 * i)), 24 - 8 * math.sin(math.radians(60 * i))) for i in range(6)]
    _fill(p, QPolygonF(corners), 220)
    for i, corner in enumerate(corners):                          # each side goes on to the ring: a blade's edge
        before = corners[i - 1]
        dx, dy = corner.x() - before.x(), corner.y() - before.y()
        n = math.hypot(dx, dy)
        dx, dy = dx / n, dy / n
        rx, ry = corner.x() - 24, corner.y() - 24
        along = rx * dx + ry * dy
        reach = -along + math.sqrt(max(0.0, along * along - (rx * rx + ry * ry - 17 * 17)))
        p.drawLine(before, QPointF(corner.x() + dx * reach, corner.y() + dy * reach))


def _path(p, *points):
    p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in points]))


def _grp_presets(p, ink):
    # Four little pictures: the looks to choose from.
    p.setBrush(Qt.NoBrush)
    for x, y in ((8, 8), (27, 8), (8, 27), (27, 27)):
        p.drawRoundedRect(QRectF(x, y, 13, 13), 2, 2)
    _fill(p, QPolygonF([QPointF(27, 8), QPointF(40, 8), QPointF(40, 21), QPointF(27, 21)]), 200)


def _grp_camera(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(6, 15, 36, 23), 4, 4)
    _path(p, (16, 15), (19, 9), (29, 9), (32, 15))
    _dot(p, 24, 26.5, 6.0)


def _grp_quality(p, ink):
    # Three rising bars: how fine.
    p.setBrush(Qt.NoBrush)
    for x, top, alpha in ((9, 28, 90), (20, 19, 150), (31, 9, 230)):
        _fill(p, QPolygonF([QPointF(x, top), QPointF(x + 8, top), QPointF(x + 8, 40), QPointF(x, 40)]), alpha)
        p.drawRect(QRectF(x, top, 8, 40 - top))


def _grp_surface(p, ink):
    _cube(p, ink, 24, 24, 16)


def _grp_outline(p, ink):
    # A square drawn by hand: its lines run past the corners.
    for a, b in (((8, 12), (41, 12)), ((36, 7), (36, 41)), ((41, 36), (7, 36)), ((12, 41), (12, 7))):
        _path(p, a, b)


def _grp_finish(p, ink):
    # A brush and the wash it leaves.
    _path(p, (40, 8), (24, 24))
    tip = QPainterPath(QPointF(24, 24))
    tip.cubicTo(16, 22, 14, 34, 8, 40)
    tip.cubicTo(20, 41, 28, 34, 24, 24)
    _fill(p, tip, 210)
    p.drawPath(tip)


def _grp_corrections(p, ink):
    for y, x in ((12, 30), (24, 16), (36, 27)):
        _path(p, (8, y), (40, y))
        _dot(p, x, y, 4.4)


def _grp_effects(p, ink):
    _fill(p, QPolygonF([QPointF(x, y) for x, y in ((24, 6), (28, 20), (42, 24), (28, 28), (24, 42), (20, 28), (6, 24), (20, 20))]), 200)
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in ((24, 6), (28, 20), (42, 24), (28, 28), (24, 42), (20, 28), (6, 24), (20, 20))]))


def _grp_sky(p, ink):
    # The sun half behind a cloud.
    _dot(p, 31, 17, 8.0)
    cloud = QPainterPath(QPointF(13, 38))
    cloud.cubicTo(4, 38, 5, 25, 14, 26)
    cloud.cubicTo(15, 16, 29, 16, 30, 27)
    cloud.cubicTo(40, 25, 41, 38, 32, 38)
    cloud.closeSubpath()
    p.setBrush(QApplication.palette().base().color() if QApplication.instance() else Qt.NoBrush)
    p.drawPath(cloud)


def _grp_shadows(p, ink):
    _fill(p, QPolygonF([QPointF(22, 36), QPointF(42, 36), QPointF(34, 42), QPointF(12, 42)]), 190)
    _cube(p, ink, 19, 22, 13)


def _grp_background(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(7, 10, 34, 28), 3, 3)
    _fill(p, QPolygonF([QPointF(9, 36), QPointF(19, 23), QPointF(26, 31), QPointF(31, 26), QPointF(39, 36)]), 210)
    _dot(p, 31, 18, 3.5)


def _grp_ground(p, ink):
    # A floor running away to the horizon.
    for a, b in (((5, 40), (43, 40)), ((13, 29), (35, 29)), ((18, 21), (30, 21))):
        _path(p, a, b)
    for a, b in (((18, 21), (5, 40)), ((30, 21), (43, 40)), ((24, 21), (24, 40))):
        _path(p, a, b)


def _grp_horizon(p, ink):
    _fill(p, QPolygonF([QPointF(5, 36), QPointF(18, 16), QPointF(27, 28), QPointF(33, 21), QPointF(43, 36)]), 160)
    _path(p, (5, 36), (18, 16), (27, 28), (33, 21), (43, 36))
    _path(p, (4, 36), (44, 36))


def _grp_fog(p, ink):
    for y, a, b in ((13, 12, 40), (21, 7, 34), (29, 14, 42), (37, 8, 32)):
        _path(p, (a, y), (b, y))


def _pin(p, ink):
    drop = QPainterPath(QPointF(24, 42))
    drop.cubicTo(18, 33, 11, 27, 11, 19)
    drop.cubicTo(11, 3, 37, 3, 37, 19)
    drop.cubicTo(37, 27, 30, 33, 24, 42)
    p.setBrush(Qt.NoBrush)
    p.drawPath(drop)
    _dot(p, 24, 19, 5.0)


def _save(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(9, 9), QPointF(33, 9), QPointF(39, 15), QPointF(39, 39), QPointF(9, 39)]))
    _fill(p, QPolygonF([QPointF(15, 27), QPointF(33, 27), QPointF(33, 39), QPointF(15, 39)]), 200)
    _path(p, (16, 10), (16, 18), (30, 18), (30, 10))


def _more(p, ink):
    for x in (12, 24, 36):
        _dot(p, x, 24, 4.0)


def _undo(p, ink):
    # Back to what it was: an arrow turning back.
    q = QPainterPath(QPointF(15, 18))
    q.lineTo(29, 18)
    q.cubicTo(43, 18, 43, 37, 29, 37)
    q.lineTo(17, 37)
    p.setBrush(Qt.NoBrush)
    p.drawPath(q)
    _arrow_head(p, QPointF(8, 18), -1, 0, 11.0)


def _bars(p, ink, filled):
    for i, (x, top) in enumerate(((10, 28), (20, 20), (30, 12))):
        if i < filled:
            _fill(p, QPolygonF([QPointF(x, top), QPointF(x + 7, top), QPointF(x + 7, 38), QPointF(x, 38)]), 230)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x, top, 7, 38 - top))


def _q_draft(p, ink):
    _bars(p, ink, 1)


def _q_medium(p, ink):
    _bars(p, ink, 2)


def _q_high(p, ink):
    _bars(p, ink, 3)


def _tools(p, ink):
    # A wrench and a screwdriver, crossed.
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(ink, _WIDTH * 2.2))
    p.drawLine(QPointF(13, 37), QPointF(28, 22))                 # the wrench's handle
    p.setPen(_pen(ink))
    jaw = QRectF(23, 7, 18, 18)
    p.drawArc(jaw, 80 * 16, 290 * 16)                            # its open jaw, towards the upper right
    p.drawLine(QPointF(33.6, 7.2), QPointF(32, 16))
    p.drawLine(QPointF(40.8, 14.4), QPointF(32, 16))
    p.drawLine(QPointF(10, 10), QPointF(31, 31))                 # the screwdriver's shaft
    p.drawLine(QPointF(8, 13), QPointF(13, 8))
    p.setPen(_pen(_accent(), _WIDTH * 3.0))
    p.drawLine(QPointF(30, 30), QPointF(39, 39))                 # and its handle


def _grp_section(p, ink):
    # A box cut by a plane.
    _cube(p, ink, 22, 26, 13)
    p.setPen(_pen(_accent(), _WIDTH * 1.6))
    p.drawLine(QPointF(6, 33), QPointF(42, 13))


def _grp_cap(p, ink):
    # The face of the cut, hatched.
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(9, 9, 30, 30))
    p.save()
    p.setPen(_pen(_accent(), _WIDTH))
    for a, b in (((9, 21), (21, 9)), ((9, 33), (33, 9)), ((15, 39), (39, 15)), ((27, 39), (39, 27))):
        p.drawLine(QPointF(*a), QPointF(*b))
    p.restore()


def _grp_size(p, ink):
    # A frame and the two ways it is measured.
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(9, 9, 30, 30))
    p.drawLine(QPointF(15, 33), QPointF(33, 15))
    _arrow_head(p, QPointF(35, 13), 1, -1, 10.0)
    _arrow_head(p, QPointF(13, 35), -1, 1, 10.0)


def _grp_file(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(12, 7), QPointF(29, 7), QPointF(37, 15), QPointF(37, 41), QPointF(12, 41)]))
    _fill(p, QPolygonF([QPointF(29, 7), QPointF(37, 15), QPointF(29, 15)]), 220)
    for y in (24, 30, 36):
        _path(p, (18, y), (31, y))


def _pencil(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(9, 39), QPointF(12, 30), QPointF(31, 11), QPointF(37, 17), QPointF(18, 36)]))
    _fill(p, QPolygonF([QPointF(31, 11), QPointF(35, 7), QPointF(41, 13), QPointF(37, 17)]), 220)


def _trash(p, ink):
    p.setBrush(Qt.NoBrush)
    _path(p, (9, 13), (39, 13))
    _path(p, (19, 13), (19, 8), (29, 8), (29, 13))
    p.drawPolyline(QPolygonF([QPointF(13, 13), QPointF(15, 40), QPointF(33, 40), QPointF(35, 13)]))
    for x in (20, 28):
        _path(p, (x, 19), (x, 34))


def _folder(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(QPolygonF([QPointF(6, 12), QPointF(19, 12), QPointF(23, 17), QPointF(42, 17), QPointF(42, 38), QPointF(6, 38)]))
    _fill(p, QPolygonF([QPointF(6, 22), QPointF(42, 22), QPointF(42, 38), QPointF(6, 38)]), 110)


def _swap(p, ink):
    _path(p, (8, 17), (35, 17))
    _arrow_head(p, QPointF(42, 17), 1, 0, 11.0)
    _path(p, (13, 31), (40, 31))
    _arrow_head(p, QPointF(6, 31), -1, 0, 11.0)


def _check_all(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(9, 9, 30, 30), 4, 4)
    p.setPen(_pen(_accent(), _WIDTH * 1.7))
    _path(p, (15, 25), (22, 32), (34, 16))


def _check_none(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(9, 9, 30, 30), 4, 4)


def _preview(p, ink):
    # A screen with a play mark: the picture, live.
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(7, 10, 34, 24), 3, 3)
    p.drawLine(QPointF(17, 41), QPointF(31, 41))
    p.drawLine(QPointF(24, 34), QPointF(24, 41))
    _fill(p, QPolygonF([QPointF(20, 16), QPointF(31, 22), QPointF(20, 28)]), 220)


def _materials(p, ink):
    # A sample ball, half of it in the accent, its shine.
    half = QPainterPath()
    half.moveTo(24, 8)
    half.arcTo(QRectF(8, 8, 32, 32), 90, -180)
    half.closeSubpath()
    _fill(p, half, 130)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 24), 16, 16)
    p.drawLine(QPointF(24, 8), QPointF(24, 40))
    shine = QPainterPath()
    shine.arcMoveTo(QRectF(13, 13, 22, 22), 110)
    shine.arcTo(QRectF(13, 13, 22, 22), 110, 55)
    p.drawPath(shine)


def _lights(p, ink):
    # A bulb, lit.
    glass = QPainterPath()
    glass.addEllipse(QPointF(24, 19), 11, 11)
    _fill(p, glass, 90)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(24, 19), 11, 11)
    p.drawLine(QPointF(19, 33), QPointF(29, 33))
    p.drawLine(QPointF(20, 38), QPointF(28, 38))
    p.drawLine(QPointF(22, 42), QPointF(26, 42))
    p.drawPolyline(QPolygonF([QPointF(21, 29), QPointF(21, 22), QPointF(24, 25), QPointF(27, 22), QPointF(27, 29)]))


def _sun_at(p, cx, cy, r, rays, long=5.0):
    disc = QPainterPath()
    disc.addEllipse(QPointF(cx, cy), r, r)
    _fill(p, disc, 190)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r, r)
    for deg in rays:
        a = math.radians(deg)
        p.drawLine(QPointF(cx + (r + 3) * math.cos(a), cy - (r + 3) * math.sin(a)),
                   QPointF(cx + (r + 3 + long) * math.cos(a), cy - (r + 3 + long) * math.sin(a)))


def _cloud_path(x, y):
    q = QPainterPath()
    q.moveTo(x + 6, y + 22)
    q.cubicTo(x - 3, y + 22, x - 2, y + 10, x + 8, y + 11)
    q.cubicTo(x + 9, y - 1, x + 26, y - 1, x + 27, y + 10)
    q.cubicTo(x + 36, y + 8, x + 38, y + 22, x + 28, y + 22)
    q.closeSubpath()
    return q


def _amb_sunny(p, ink):
    _sun_at(p, 24, 24, 9, range(0, 360, 45))


def _amb_cloudy(p, ink):
    cloud = _cloud_path(7, 14)
    _fill(p, cloud, 70)
    p.setBrush(Qt.NoBrush)
    p.drawPath(cloud)


def _amb_golden(p, ink):
    # A low sun, half under the horizon.
    half = QPainterPath()
    half.moveTo(13, 32)
    half.arcTo(QRectF(13, 21, 22, 22), 180, -180)
    half.closeSubpath()
    _fill(p, half, 200)
    p.setBrush(Qt.NoBrush)
    p.drawPath(half)
    p.drawLine(QPointF(6, 32), QPointF(42, 32))
    p.drawLine(QPointF(14, 39), QPointF(34, 39))
    for a, b in (((24, 15), (24, 9)), ((13, 20), (9, 15)), ((35, 20), (39, 15))):
        p.drawLine(QPointF(*a), QPointF(*b))


def _amb_night(p, ink):
    moon = QPainterPath()
    moon.moveTo(27, 9)
    moon.cubicTo(8, 8, 5, 38, 27, 39)
    moon.cubicTo(34, 39, 39, 35, 41, 30)
    moon.cubicTo(26, 33, 17, 20, 27, 9)
    _fill(p, moon, 110)
    p.setBrush(Qt.NoBrush)
    p.drawPath(moon)
    _dot(p, 35, 13, 2.2)
    _dot(p, 40, 21, 1.6)


def _amb_interior(p, ink):
    # A room with its window lit.
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(7, 22), QPointF(24, 8), QPointF(41, 22)]))
    p.drawPolyline(QPolygonF([QPointF(11, 20), QPointF(11, 40), QPointF(37, 40), QPointF(37, 20)]))
    window = QPolygonF([QPointF(18, 24), QPointF(30, 24), QPointF(30, 34), QPointF(18, 34)])
    _fill(p, window, 160)
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(window)
    p.drawLine(QPointF(24, 24), QPointF(24, 34))


def _eye_outline():
    q = QPainterPath()
    q.moveTo(6, 24)
    q.cubicTo(14, 10, 34, 10, 42, 24)
    q.cubicTo(34, 38, 14, 38, 6, 24)
    return q


def _eye(p, ink):
    p.setBrush(Qt.NoBrush)
    p.drawPath(_eye_outline())
    _dot(p, 24, 24, 7.0)


def _eye_off(p, ink):
    faint = QColor(ink)
    faint.setAlpha(110)
    p.setPen(_pen(faint))
    p.setBrush(Qt.NoBrush)
    p.drawPath(_eye_outline())
    p.drawLine(QPointF(10, 40), QPointF(38, 8))


_DRAW = {
    "eye": _eye, "eye_off": _eye_off,
    "amb_sunny": _amb_sunny, "amb_cloudy": _amb_cloudy, "amb_golden": _amb_golden, "amb_night": _amb_night,
    "amb_interior": _amb_interior,
    "preview": _preview, "materials": _materials, "lights": _lights,
    "follow_camera": _follow_camera, "follow_changes": _follow_changes, "refresh": _refresh, "capture": _capture,
    "grp_section": _grp_section, "grp_cap": _grp_cap, "grp_size": _grp_size, "grp_file": _grp_file, "pencil": _pencil,
    "trash": _trash, "folder": _folder, "swap": _swap, "check_all": _check_all, "check_none": _check_none, "tools": _tools,
    "grp_presets": _grp_presets, "grp_camera": _grp_camera, "grp_quality": _grp_quality, "grp_surface": _grp_surface,
    "grp_outline": _grp_outline, "grp_finish": _grp_finish, "grp_corrections": _grp_corrections, "grp_effects": _grp_effects,
    "grp_sky": _grp_sky, "grp_shadows": _grp_shadows, "grp_background": _grp_background, "grp_ground": _grp_ground,
    "grp_horizon": _grp_horizon, "grp_fog": _grp_fog, "grp_light": _amb_sunny,
    "pin": _pin, "save": _save, "more": _more, "undo": _undo, "q_draft": _q_draft, "q_medium": _q_medium,
    "q_high": _q_high,
    "comp_import": _comp_import, "comp_export": _comp_export,
    "comp_settings": _comp_settings, "comp_help": _comp_help,
    "comp_options": _comp_options, "comp_attributes": _comp_attributes,
    "comp_manager": _comp_manager, "comp_online": _comp_online,
    "render_studio": _render_studio, "clock": _clock,
}


class _Engine(QIconEngine):
    """Paints the drawing at whatever size is asked, with the ink and the
    accent of the moment (so a theme change needs no redrawing)."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self._key = key

    def clone(self):
        return _Engine(self._key)

    def key(self):
        return "ingetrazo-ext-icon"

    def paint(self, painter, rect, mode, state):
        draw = _DRAW.get(self._key)
        if draw is None:
            return
        ink = _ink()
        painter.save()
        if mode == QIcon.Disabled:
            painter.setOpacity(painter.opacity() * 0.35)      # all of it, the accent too: half of it lit looked usable
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width() / _PX, rect.height() / _PX)
        painter.setPen(_pen(ink))
        painter.setBrush(Qt.NoBrush)
        draw(painter, ink)
        painter.restore()

    def pixmap(self, size, mode, state):
        pm = QPixmap(size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        self.paint(p, QRect(QPoint(0, 0), size), mode, state)
        p.end()
        return pm


def icon(key: str) -> QIcon:
    """The icon for ``key`` (a null icon for an unknown key)."""
    if key not in _DRAW:
        return QIcon()
    return QIcon(_Engine(key))


def panel_icon(app, key: str) -> dict:
    """``{"icon": icon(key)}`` to splat into ``app.add_panel(...)`` when
    this IngeTrazo takes one (older versions would refuse the argument
    and keep showing the title's initial)."""
    import inspect
    try:
        if "icon" in inspect.signature(app.add_panel).parameters:
            return {"icon": icon(key)}
    except (TypeError, ValueError):
        pass
    return {}
