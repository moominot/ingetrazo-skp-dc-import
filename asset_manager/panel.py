# SPDX-License-Identifier: GPL-3.0-or-later
"""The Components tray tab: what the drawing holds, and the user's catalog."""
from __future__ import annotations

import logging

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from . import catalog, inventory, thumbs

_log = logging.getLogger(__name__)
ICON = 64
DYN_MARK = "⚙ "          # dynamic components wear this in the list


class AssetPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self._app = app
        self._entries: list = []
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # --- In the drawing -------------------------------------------------
        page = QWidget()
        v = QVBoxLayout(page)
        self.scene_list = self._list()
        self.scene_list.itemDoubleClicked.connect(lambda _i: self.select_current())
        v.addWidget(self.scene_list)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        sel = QPushButton("Select")
        sel.setToolTip("Select every placement of the chosen component")
        sel.clicked.connect(self.select_current)
        row.addWidget(refresh)
        row.addWidget(sel)
        v.addLayout(row)
        self.summary = QLabel()
        v.addWidget(self.summary)
        tabs.addTab(page, "In drawing")

        # --- My catalog -----------------------------------------------------
        page2 = QWidget()
        v2 = QVBoxLayout(page2)
        self.cat_list = self._list()
        self.cat_list.itemDoubleClicked.connect(lambda _i: self.insert_current())
        v2.addWidget(self.cat_list)
        row2 = QHBoxLayout()
        reload_ = QPushButton("Reload")
        reload_.clicked.connect(self.refresh_catalog)
        ins = QPushButton("Insert")
        ins.setToolTip("Insert the chosen model; a click places it")
        ins.clicked.connect(self.insert_current)
        row2.addWidget(reload_)
        row2.addWidget(ins)
        v2.addLayout(row2)
        self.cat_info = QLabel()
        self.cat_info.setWordWrap(True)
        v2.addWidget(self.cat_info)
        tabs.addTab(page2, "My catalog")

        on_changed = getattr(app, "on_document_changed", None)
        if on_changed is not None:
            on_changed(lambda *_a: self.refresh())
        self.refresh()
        self.refresh_catalog()

    @staticmethod
    def _list() -> QListWidget:
        w = QListWidget()
        w.setViewMode(QListWidget.ListMode)
        w.setIconSize(QSize(ICON, ICON))
        w.setUniformItemSizes(True)
        return w

    # --- In the drawing ------------------------------------------------------
    def refresh(self):
        self.scene_list.clear()
        try:
            self._entries = inventory.components_in(self._app.scene)
        except Exception:  # noqa: BLE001 - never break the window for a list
            _log.exception("could not list the components")
            self._entries = []
        for e in self._entries:
            label = f"{DYN_MARK if e.dynamic else ''}{e.name}  ×{e.count}"
            it = QListWidgetItem(QIcon(thumbs.render(e.sample, ICON)), label)
            it.setData(Qt.UserRole, e)
            it.setToolTip("Dynamic component" if e.dynamic else "Component")
            self.scene_list.addItem(it)
        dyn = sum(e.dynamic for e in self._entries)
        self.summary.setText(f"{len(self._entries)} components, {dyn} dynamic")

    def select_current(self):
        it = self.scene_list.currentItem()
        if it is None:
            return
        e = it.data(Qt.UserRole)
        scene = self._app.scene
        scene.selection.clear()
        scene.selection.update(g for g in e.instances if g in scene.groups)
        vp = self._app.viewport
        notify = getattr(vp, "notify_selection_changed", None)
        if callable(notify):
            notify()
        vp.update()
        top = sum(g in scene.groups for g in e.instances)
        if top < e.count:
            self.summary.setText(f"Selected {top} of {e.count}: the rest are inside "
                                 f"other components.")

    # --- My catalog ----------------------------------------------------------
    def refresh_catalog(self):
        self.cat_list.clear()
        folder = catalog.default_folder()
        items = catalog.scan(folder)
        for item in items:
            icon = QIcon(QPixmap(str(item.preview))) if item.preview else QIcon()
            it = QListWidgetItem(icon, item.name)
            it.setData(Qt.UserRole, item)
            it.setToolTip(str(item.path))
            self.cat_list.addItem(it)
        self.cat_info.setText(
            f"{len(items)} models in {folder}" if items else
            f"Empty. Put .igz files (and a .png with the same name as preview) in\n{folder}")

    def insert_current(self):
        it = self.cat_list.currentItem()
        if it is None:
            return
        item = it.data(Qt.UserRole)
        try:
            self._app.import_igz(str(item.path))
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not insert %s", item.path)
            self.cat_info.setText(f"Could not insert {item.name}: {exc}")
