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


_DRAW = {
    "comp_import": _comp_import, "comp_export": _comp_export,
    "comp_settings": _comp_settings, "comp_help": _comp_help,
    "comp_options": _comp_options, "comp_attributes": _comp_attributes,
    "comp_manager": _comp_manager, "comp_online": _comp_online,
    "render_studio": _render_studio,
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
        if mode == QIcon.Disabled:
            ink.setAlpha(90)
        painter.save()
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
