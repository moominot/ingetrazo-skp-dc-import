# SPDX-License-Identifier: GPL-3.0-or-later
"""Expert mode and Help, at the top of the panel: in the row where IngeTrazo writes the tray's name («Render Studio»).

That row is IngeTrazo's own (its tray header), and its extension API offers no way into it: the buttons are put in it by
what it is made of (a label named ``dock_header_name`` in a row). IngeTrazo makes the header anew when the trays are
rearranged, so the buttons are taken out before the old one goes and put in the new one. Where there is no such header
(another IngeTrazo, a test), they stay in a row of their own at the top of the panel: they are never lost."""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QWidget

_log = logging.getLogger(__name__)
HEADER_NAME = "dock_header_name"                  # IngeTrazo's name for the tray's name in its header


class HeaderTools(QObject):
    def __init__(self, panel: QWidget, buttons):
        """``buttons``: the widgets to show, left to right. ``self.own_row`` is the panel's row for them: add it at its top."""
        super().__init__(panel)
        self.panel = panel
        self.box = QWidget()
        row = QHBoxLayout(self.box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for button in buttons:
            row.addWidget(button)
        self.own_row = QWidget()
        own = QHBoxLayout(self.own_row)
        own.setContentsMargins(0, 0, 0, 2)
        own.addStretch(1)
        own.addWidget(self.box)
        self._header = None                       # IngeTrazo's header the buttons are in
        self._dock = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)                # after the program has finished making its header
        self._timer.timeout.connect(self.place)
        panel.installEventFilter(self)

    # -- watching ---------------------------------------------------------------------------
    def eventFilter(self, obj, ev) -> bool:  # noqa: N802 (Qt)
        kind = ev.type()
        if obj is self.panel:
            if kind in (QEvent.Show, QEvent.ParentChange):
                self._timer.start()
        elif obj is self._dock:
            if kind in (QEvent.ChildAdded, QEvent.Show, QEvent.LayoutRequest):
                self._timer.start()               # (a new header, perhaps)
        elif obj is self._header and kind == QEvent.DeferredDelete:
            self._take_back()                     # the old header goes: not with the buttons in it
            self._timer.start()
        return False

    # -- placing ----------------------------------------------------------------------------
    def _find_dock(self):
        node = self.panel.parentWidget()
        while node is not None and not isinstance(node, QDockWidget):
            node = node.parentWidget()
        return node

    def _take_back(self) -> None:
        if self._header is not None:
            self._header.removeEventFilter(self)
            self._header = None
        if self.box.parentWidget() is not self.own_row:
            self.own_row.layout().addWidget(self.box)
        self.own_row.setVisible(True)

    def place(self) -> None:
        """Into the tray's header when there is one; else in the panel's own row."""
        try:
            dock = self._find_dock()
            if dock is not self._dock:
                if self._dock is not None:
                    self._dock.removeEventFilter(self)
                self._dock = dock
                if dock is not None:
                    dock.installEventFilter(self)
            header = dock.titleBarWidget() if dock is not None else None
            label = header.findChild(QLabel, HEADER_NAME) if header is not None else None
            layout = header.layout() if label is not None else None
            if not isinstance(layout, QHBoxLayout) or layout.indexOf(label) < 0:
                self._take_back()
                return
            if header is self._header and self.box.parentWidget() is header:
                return
            self._take_back()
            layout.insertWidget(layout.indexOf(label) + 1, self.box)        # after the name, which takes what is left
            self.box.show()
            self.own_row.setVisible(False)
            self._header = header
            header.installEventFilter(self)
        except RuntimeError:                      # a header or a tray already gone
            _log.debug("header gone", exc_info=True)
            self._header = None
