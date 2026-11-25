# SPDX-License-Identifier: GPL-3.0-or-later
"""Drop-downs, number boxes and sliders answer the wheel only when they have been picked (they have the focus); else the wheel
scrolls the page they are in. A notch meant to scroll used to change whatever field was under the pointer.

The same rule IngeTrazo is to apply to the whole program (issue #1483), here for this extension's own windows only, until
the program does it: with both, they agree."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QDial, QSlider, QWidget

#: Not QAbstractSlider: a scroll bar is one too, and the wheel is its job.
FIELDS = (QAbstractSpinBox, QComboBox, QSlider, QDial)


class _Guard(QObject):
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt)
        kind = event.type()
        if kind == QEvent.Wheel:
            if isinstance(obj, FIELDS) and not obj.hasFocus():
                event.ignore()                    # ignored, not swallowed: Qt hands it on, up to the scroll area
                return True
        elif kind == QEvent.ChildPolished:
            child = event.child()
            if isinstance(child, QWidget):
                watch(child)                      # a field made later (a list rebuilt, a new row)
        return False


_guard = None


def watch(root: QWidget) -> None:
    """Guard ``root``'s fields, those it has now and those added to it later."""
    global _guard
    if _guard is None:
        _guard = _Guard()
    for widget in (root, *root.findChildren(QWidget)):
        if isinstance(widget, FIELDS) and widget.focusPolicy() != Qt.NoFocus:
            widget.setFocusPolicy(Qt.StrongFocus)     # not WheelFocus: Qt would give the focus before the wheel is seen
        widget.installEventFilter(_guard)             # (asked twice, Qt keeps one)
