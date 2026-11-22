# SPDX-License-Identifier: GPL-3.0-or-later
"""One tab of free online assets: 360° backgrounds, materials or 3-D models.

Each kind has its own tab (the same list, search, category and size controls),
with a source box when more than one site offers that kind. The panel keeps the
sources (one object per site, shared by the tabs) and the three actions that
use a download (a background, a paint, a placed model).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QComboBox, QLabel, QLineEdit, QListWidgetItem, QToolButton,
                               QVBoxLayout, QWidget)

from . import place, polyhaven
from .i18n import tr

_log = logging.getLogger(__name__)

#: What each kind's tab is called.
TABS = {
    "hdris": "360° backgrounds",
    "materials": "Materials",
    "models": "Models",
}
#: What each tab's main button says and does.
ACTIONS = {
    "hdris": ("Use as 360° background",
              "Download it and set it as Render Studio's 360° background"),
    "materials": ("Paint with it",
                  "Download the material (colour, relief, roughness… maps) and "
                  "load the paint bucket with it, at its real size"),
    "models": ("Place",
               "Download it; it follows the cursor and a click places it "
               "(once downloaded it can also be dragged onto the view)"),
}


class OnlineTab(QWidget):
    def __init__(self, panel, kind, sources, drag_list, icon_size, row, button, origin):
        super().__init__()
        self.panel, self.kind, self.icon_size, self.origin = panel, kind, icon_size, origin
        self.sources = [m for m in sources if any(k == kind for _l, k in m.KINDS)]
        self.items: list = []
        self.loaded = None
        v = QVBoxLayout(self)
        self.source = QComboBox()
        for mod in self.sources:
            self.source.addItem(mod.LABEL, mod.KEY)
        self.source.setToolTip("Where the free assets come from")
        self.source.currentIndexChanged.connect(lambda _i: self._source_changed())
        self.res = QComboBox()
        for r in polyhaven.RESOLUTIONS:
            self.res.addItem(r.upper(), r)
        self.res.setToolTip("Size of the images to download: 1K is light, 4K is sharp")
        reload_ = QToolButton()
        reload_.setText("↻")
        reload_.setToolTip("Fetch the list again")
        reload_.clicked.connect(lambda: self.load(refresh=True))
        top = [self.source, self.res, reload_] if len(self.sources) > 1 else [self.res, reload_]
        v.addLayout(row(*top, stretch_first=True))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (name, tag)…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.filter())
        self.cat = QComboBox()
        self.cat.setMinimumContentsLength(14)
        self.cat.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cat.currentIndexChanged.connect(lambda _i: self.filter())
        v.addLayout(row(self.search, self.cat, stretch_first=True))
        self.list = drag_list(panel.drop, icon=icon_size, grid=True)
        self.list.provider = self._provider
        self.list.refused = lambda it: self.use(it)
        self.list.icon_loader = self._icon
        self.list.itemDoubleClicked.connect(self.use)
        v.addWidget(self.list, 1)
        text, tip = ACTIONS[kind]
        self.action = button(text, tip, lambda: self.use(self.list.currentItem()))
        web = button("Web page", "Open the asset's page on its site", self._web)
        controls = [self.action]
        self.proxy = None
        if kind == "models":
            self.proxy = panel._proxy_box()
            controls.append(self.proxy)
        controls.append(web)
        v.addLayout(row(*controls, stretch_first=True))
        self.credit = QLabel()
        self.credit.setOpenExternalLinks(True)
        self.credit.setWordWrap(True)
        v.addWidget(self.credit)
        self._source_changed(load=False)

    # --- the site this tab reads ------------------------------------------------
    def current_source(self):
        return self.panel.source_for(self.source.currentData())

    def _module(self):
        return next(m for m in self.sources if m.KEY == self.source.currentData())

    def _source_changed(self, load=True):
        self.credit.setText(tr(self._module().CREDIT) + " " + tr("Downloads are kept and reused."))
        if load:
            self.load()

    # --- the list ---------------------------------------------------------------
    def load(self, refresh=False):
        src, kind = self.current_source(), self.kind
        self.loaded = (src.key, kind)
        self.list.clear()
        for s in self.panel.all_sources():
            s.forget_thumbs()
        self.panel._say(tr("Getting the list from {source}…", source=src.label))

        def got(items, err):
            if self.loaded != (src.key, kind):
                return
            if err and not items:
                self.panel._say(tr("Could not get the list from {source}: {error}",
                                   source=src.label, error=err))
                return
            self.items = items
            self.cat.blockSignals(True)
            self.cat.clear()
            self.cat.addItem(tr("All categories"), "")
            for c in polyhaven.categories(items):
                self.cat.addItem(c, c)
            self.cat.blockSignals(False)
            self.panel._say("")
            self.filter()

        src.listing(kind, got, refresh=refresh)

    def filter(self):
        text, cat = self.search.text(), self.cat.currentData() or ""
        self.current_source().forget_thumbs()
        self.list.clear()
        blank = QPixmap(self.icon_size, self.icon_size)
        blank.fill(Qt.transparent)
        blank_icon = QIcon(blank)
        n = 0
        for e in self.items:
            if not polyhaven.matches(e, text, cat):
                continue
            it = QListWidgetItem(blank_icon, e["name"])
            it.setData(Qt.UserRole, e)
            it.setToolTip(f"{e['name']}\n{', '.join(e['categories'][:6])}")
            self.list.addItem(it)
            n += 1
        self.list.schedule_icons()
        self.panel._say(f"{n} of {len(self.items)}")

    def _icon(self, it):
        e = it.data(Qt.UserRole)
        size = self.icon_size

        def done(path, it=it):
            try:
                pm = QPixmap(str(path))
                if not pm.isNull():
                    it.setIcon(QIcon(pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            except RuntimeError:            # the item was cleared meanwhile
                pass

        self.current_source().thumbnail(e, done)

    def _web(self):
        it = self.list.currentItem()
        if it is not None:
            QDesktopServices.openUrl(QUrl(self.current_source().site(it.data(Qt.UserRole))))

    # --- using an asset ---------------------------------------------------------
    def _provider(self, it):
        """Only models that are already downloaded can be dragged."""
        e = it.data(Qt.UserRole)
        if self.kind != "models":
            return None
        main = self.current_source().cached("models", e, self.res.currentData())
        if main is None:
            return None
        return place.from_file(lambda: (self.panel._model_group(main, interactive=False), self.origin))

    def use(self, it):
        panel = self.panel
        if it is None:
            panel._say(tr("Choose an asset in the list first."))
            return
        e = it.data(Qt.UserRole)
        src = self.current_source()
        kind, res = self.kind, self.res.currentData()
        panel._say(tr("Downloading «{name}» ({res})…", name=e["name"], res=res.upper()))

        def progress(i, n):
            panel._say(tr("Downloading «{name}» ({res})… {i}/{n}", name=e["name"], res=res.upper(), i=i, n=n))

        def done(path, err):
            if path is None:
                panel._say(tr("Could not download «{name}»: {error}", name=e["name"], error=err))
                return
            try:
                {"hdris": panel._use_hdri, "materials": panel._paint_with,
                 "models": panel._place_model}[kind](path, e, src)
            except Exception as exc:  # noqa: BLE001 - say it, never crash the app
                _log.exception("could not use %s", path)
                panel._say(tr("Could not use «{name}»: {error}", name=e["name"], error=exc))

        src.download(kind, e, res, done, progress)
