# SPDX-License-Identifier: GPL-3.0-or-later
"""A simple picture for a material that has no image of its own: a lit
sphere in its colour, with a highlight that tells the finish (matte, satin,
gloss, metal) and a checker behind it when it is translucent (glass, water).
Meant for lists and for the preview saved with a catalog material; it does
not light the material as the render does."""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QRadialGradient

SIZE = 96


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _rgb(color) -> tuple:
    try:
        return tuple(_clamp(c) for c in tuple(color)[:3]) if color is not None else (0.8, 0.8, 0.8)
    except TypeError:
        return (0.8, 0.8, 0.8)


def render(color=None, opacity=None, finish=None, size: int = SIZE) -> QPixmap:
    r, g, b = _rgb(color)
    alpha = _clamp(1.0 if opacity is None else opacity)
    if finish == "glass":
        alpha = min(alpha, 0.45)
    elif finish == "water":
        alpha = min(alpha, 0.6)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    if alpha < 0.999:                                    # a checker shows through
        cell = max(4, size // 8)
        for y in range(0, size, cell):
            for x in range(0, size, cell):
                grey = 215 if ((x // cell) + (y // cell)) % 2 == 0 else 245
                p.fillRect(x, y, cell, cell, QColor(grey, grey, grey))
    pad = size * 0.08
    rect = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
    base = QColor.fromRgbF(r, g, b, alpha)
    lit = QColor.fromRgbF(min(1.0, r * 0.6 + 0.4), min(1.0, g * 0.6 + 0.4), min(1.0, b * 0.6 + 0.4), alpha)
    dark = QColor.fromRgbF(r * 0.35, g * 0.35, b * 0.35, alpha)
    grad = QRadialGradient(QPointF(rect.left() + rect.width() * 0.35, rect.top() + rect.height() * 0.3),
                           rect.width() * 0.85)
    if finish == "metal":                                # a hard band of light
        grad.setColorAt(0.0, QColor.fromRgbF(min(1.0, r * 0.4 + 0.6), min(1.0, g * 0.4 + 0.6),
                                             min(1.0, b * 0.4 + 0.6), alpha))
        grad.setColorAt(0.35, base)
        grad.setColorAt(0.6, dark)
        grad.setColorAt(1.0, base)
    else:
        grad.setColorAt(0.0, lit)
        grad.setColorAt(0.45, base)
        grad.setColorAt(1.0, dark)
    p.setPen(QPen(QColor(0, 0, 0, 60), 1))
    p.setBrush(QBrush(grad))
    p.drawEllipse(rect)
    shine = {"gloss": 170, "glass": 200, "water": 150, "satin": 70}.get(finish or "", 0)
    if shine:
        hl = QRadialGradient(QPointF(rect.left() + rect.width() * 0.33, rect.top() + rect.height() * 0.27),
                             rect.width() * 0.22)
        hl.setColorAt(0.0, QColor(255, 255, 255, shine))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(hl))
        p.drawEllipse(rect)
    p.end()
    return pm


def png_bytes(color=None, opacity=None, finish=None, size: int = SIZE) -> bytes | None:
    """The preview as PNG bytes (to save beside the material), or None."""
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    ok = render(color, opacity, finish, size).save(buf, "PNG")
    return bytes(buf.data()) if ok else None
