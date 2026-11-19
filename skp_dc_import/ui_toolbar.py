# SPDX-License-Identifier: GPL-3.0-or-later
"""The extension's toolbar: one button per command, with generated icons
(no image files to ship)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QToolBar

OBJECT_NAME = "skp_dc_import_toolbar"   # stable: the saved layout keys on it

# (glyph, kind): kind picks the badge colour so the buttons read as groups.
_FILE, _EDIT, _CFG = "#2f6fb0", "#3f8f4f", "#777777"


def make_icon(glyph: str, color: str, size: int = 32) -> QIcon:
    """A rounded square with a short glyph, drawn at 2x for sharp edges."""
    px = QPixmap(size * 2, size * 2)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    r = QRectF(3, 3, size * 2 - 6, size * 2 - 6)
    p.drawRoundedRect(r, 12, 12)
    p.setPen(QPen(QColor("white")))
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(size * (1.0 if len(glyph) == 1 else 0.78)))
    p.setFont(f)
    p.drawText(r, Qt.AlignCenter, glyph)
    p.end()
    return QIcon(px)


def build(app, actions: dict) -> QToolBar | None:
    """Create the toolbar from ``actions`` {key: QAction or None} and place
    it. Returns None when the window cannot hold one."""
    window = getattr(app, "window", None)
    if window is None or not hasattr(window, "addToolBar"):
        return None
    spec = (("import", "In", _FILE, "Import .skp keeping components"),
            ("export", "Out", _FILE, "Export .skp with dynamic components"),
            ("settings", "…", _CFG, ".skp settings"),
            ("help", "?", _CFG, "How importing and exporting .skp files works"))
    bar = QToolBar(".skp files", window)
    bar.setObjectName(OBJECT_NAME)
    sep_after = {"export"}
    for key, glyph, color, tip in spec:
        act = actions.get(key)
        if act is None:
            continue
        act.setIcon(make_icon(glyph, color))
        act.setToolTip(tip)
        bar.addAction(act)
        if key in sep_after:
            bar.addSeparator()
    window.addToolBar(bar)
    restore = getattr(app, "restore_toolbar_layout", None)
    if restore is not None:
        restore()
    return bar
