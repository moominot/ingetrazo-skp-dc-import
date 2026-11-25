# SPDX-License-Identifier: GPL-3.0-or-later
"""One of the Library's three tabs: models, materials or backgrounds.

Each has the same layout: a source box (the drawing, the catalog and its
folders, the free online sites), a small refresh button and a menu, a category
filter, a search box, the list, and at the bottom Insert (with «Insert as
proxy» under its arrow, for models), Save to catalog and Export.

Categories are tags: the user's own for what is in the catalog or the drawing
(any number each, right-click ▸ Categories…), the site's for online assets.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QStyle,
                               QToolButton, QVBoxLayout, QWidget)

from . import (ambientcg, catalog, export, inventory, online, place, polyhaven, previews,
               stand_in, tags, thumbs)
from .i18n import tr
from .icons import icon

_log = logging.getLogger(__name__)

SOURCES = (polyhaven, ambientcg)
TABS = {"models": "Models", "materials": "Materials", "hdris": "Backgrounds"}
#: the catalog's ``Item.type_key`` each tab shows
TYPE_KEYS = {"models": "model", "materials": "material", "hdris": "background"}
NEW_MARK = "● "
DYN_MARK = "⚙ "
ICON = 80
ORIGIN = None          # set by the panel (a QVector3D)
_SETTINGS = "asset_manager/source_"


class TagsDialog(QDialog):
    """The categories of one or several items: tick the ones they have, write new ones."""

    def __init__(self, parent, current: list[list[str]], known: list[str]):
        super().__init__(parent)
        self.setWindowTitle(tr("Categories"))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("Tick the categories ({n} selected):", n=len(current))))
        self.list = QListWidget()
        for t in tags.clean(known + [t for c in current for t in c]):
            have = sum(t.lower() in (x.lower() for x in c) for c in current)
            it = QListWidgetItem(t)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if have == len(current) else
                             Qt.PartiallyChecked if have else Qt.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list, 1)
        self.new = QLineEdit()
        self.new.setPlaceholderText(tr("New categories, separated by commas"))
        lay.addWidget(self.new)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.resize(300, 340)

    def result_for(self, old: list[str]) -> list[str]:
        """What an item that had ``old`` has now (a half-ticked category stays as it was)."""
        out = {t.lower(): t for t in old}
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.text().lower()
            if it.checkState() == Qt.Checked:
                out.setdefault(key, it.text())
            elif it.checkState() == Qt.Unchecked:
                out.pop(key, None)
        return tags.clean(list(out.values()) + tags.parse(self.new.text()))


def _tool(key: str, tip: str) -> QToolButton:
    b = QToolButton()
    b.setIcon(icon(key))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setAutoRaise(True)
    return b


class KindPage(QWidget):
    def __init__(self, panel, kind: str, drag_list):
        super().__init__()
        self.panel, self.kind = panel, kind
        self.online_items: list = []
        self.loaded = None                 # (site, kind) the online list was asked for
        self._cats: list = []
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 4, 2, 2)

        # -- source, refresh, menu
        top = QHBoxLayout()
        self.source = QComboBox()
        self.source.setToolTip("Where to look: the drawing, your catalog folders or a free online site")
        self.source.currentIndexChanged.connect(lambda _i: self._source_chosen())
        self.res = QComboBox()
        for r in polyhaven.RESOLUTIONS:
            self.res.addItem(r.upper(), r)
        self.res.setToolTip("Size of the images to download: 1K is light, 4K is sharp")
        self.refresh_btn = _tool("refresh", "Update: read the folders, the drawing or the online list again")
        self.refresh_btn.clicked.connect(self.reload)
        self.menu_btn = _tool("comp_settings", "Catalog folders, model sites and settings")
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.menu_btn.setMenu(QMenu(self.menu_btn))
        self.menu_btn.menu().aboutToShow.connect(self.fill_menu)
        top.addWidget(self.source, 1)
        for w in (self.res, self.refresh_btn, self.menu_btn):
            top.addWidget(w)
        v.addLayout(top)

        # -- category and search
        self.category = QComboBox()
        self.category.setToolTip("Show one category only. Right-click an item to give it categories.")
        self.category.setMinimumContentsLength(14)
        self.category.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.category.currentIndexChanged.connect(lambda _i: self.fill())
        v.addWidget(self.category)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.fill())
        v.addWidget(self.search)

        # -- the list
        self.list = drag_list(panel.drop, icon=ICON, grid=True)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.provider = self._provider
        self.list.refused = lambda it: self.insert(it)
        self.list.icon_loader = self._icon
        self.list.itemDoubleClicked.connect(lambda it: self.insert(it))
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.currentItemChanged.connect(lambda *_a: self._sync_buttons())
        v.addWidget(self.list, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: gray")
        self.info.setOpenExternalLinks(True)
        v.addWidget(self.info)

        # -- insert, save, export
        row = QHBoxLayout()
        self.insert_btn = QToolButton()
        self.insert_btn.setText("Insert")
        self.insert_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.insert_btn.setMinimumHeight(28)
        self.insert_btn.setToolTip({
            "models": "The chosen model follows the cursor, a click places it. The arrow: insert as a proxy.",
            "materials": "Loads the paint bucket with the chosen material",
            "hdris": "Sets the chosen picture as Render Studio's 360° background"}[kind])
        self.insert_btn.clicked.connect(lambda: self.insert())
        self.proxy_action = None
        if kind == "models":
            from .panel import PROXY_TIP
            menu = QMenu(self.insert_btn)
            menu.setToolTipsVisible(True)
            self.proxy_action = menu.addAction(tr("Insert as proxy"))
            self.proxy_action.setToolTip(tr(PROXY_TIP))
            self.proxy_action.triggered.connect(lambda _c=False: self.insert(proxy=True))
            self.insert_btn.setMenu(menu)
            self.insert_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.save_btn = QPushButton("Save to catalog")
        self.save_btn.setToolTip("Keep a copy in your catalog, with its categories, so it is there in every drawing and offline")
        self.save_btn.clicked.connect(lambda: self.save())
        self.export_btn = QPushButton("Export…")
        self.export_btn.setToolTip("Save the chosen item as files of its own, wherever you say")
        self.export_btn.clicked.connect(lambda: self.export())
        row.addWidget(self.insert_btn, 1)
        row.addWidget(self.save_btn)
        row.addWidget(self.export_btn)
        v.addLayout(row)

        self.fill_sources()

    # --- sources --------------------------------------------------------------------
    def fill_sources(self):
        """The source box: the drawing, the catalog (all, then each folder), the online sites."""
        combo = self.source
        keep = combo.currentData()
        if keep is None:
            keep = str(QSettings().value(_SETTINGS + self.kind, "cat:") or "cat:")
        combo.blockSignals(True)
        combo.clear()
        if self.kind != "hdris":
            combo.addItem(tr("In this drawing"), "drawing")
            combo.insertSeparator(combo.count())
        combo.addItem(tr("Catalog: all folders"), "cat:")
        watched = catalog.watched()
        for i, f in enumerate(catalog.folders()):
            label = tr("Extension's own folder") if i == 0 else (f.name or str(f))
            live = any(f == w for w in watched)
            combo.addItem("    " + label + ("  " + tr("(live)") if live else ""), "cat:" + str(f))
            combo.setItemData(combo.count() - 1,
                              f"{f}\n" + (tr("Watched in real time") if live else tr("Read again with Update")),
                              Qt.ToolTipRole)
        combo.insertSeparator(combo.count())
        for mod in SOURCES:
            if any(k == self.kind for _l, k in mod.KINDS):
                combo.addItem(tr("Online: {site}", site=mod.LABEL), "online:" + mod.KEY)
        index = combo.findData(keep)
        combo.setCurrentIndex(index if index >= 0 else combo.findData("cat:"))
        combo.blockSignals(False)
        self.res.setVisible(self.is_online)

    @property
    def where(self) -> str:
        return self.source.currentData() or "cat:"

    @property
    def is_online(self) -> bool:
        return self.where.startswith("online:")

    @property
    def is_drawing(self) -> bool:
        return self.where == "drawing"

    @property
    def folder(self) -> str:
        return self.where[4:] if self.where.startswith("cat:") else ""

    def set_source(self, data: str) -> None:
        index = self.source.findData(data)
        if index >= 0:
            self.source.setCurrentIndex(index)

    def _source_chosen(self):
        QSettings().setValue(_SETTINGS + self.kind, self.where)
        self.res.setVisible(self.is_online)
        self.category.blockSignals(True)
        self.category.clear()
        self.category.blockSignals(False)
        self.shown()

    # --- the list --------------------------------------------------------------------
    def shown(self):
        """The tab (or another source) came into view."""
        if self.is_online:
            if self.loaded != (self.where, self.kind):
                self.load_online()
            else:
                self.fill()
        elif not self.is_drawing and self.panel._cat_items is None:
            self.panel.refresh_catalog()
        else:
            self.fill()

    def reload(self):
        if self.is_online:
            self.load_online(refresh=True)
        elif self.is_drawing:
            self.fill()
        else:
            self.panel.refresh_catalog()

    def current_source(self):
        return self.panel.source_for(self.where.split(":", 1)[1])

    def _module(self):
        return next(m for m in SOURCES if m.KEY == self.where.split(":", 1)[1])

    def load_online(self, refresh=False):
        src, where = self.current_source(), self.where
        self.loaded = (where, self.kind)
        self.online_items = []
        self.list.clear()
        for s in self.panel.all_sources():
            s.forget_thumbs()
        self.panel._say(tr("Getting the list from {source}…", source=src.label))

        def got(items, err):
            if self.loaded != (where, self.kind) or self.where != where:
                return
            if err and not items:
                self.loaded = None
                self.panel._say(tr("Could not get the list from {source}: {error}", source=src.label, error=err))
                return
            self.online_items = items
            self.panel._say("")
            self.fill()

        src.listing(self.kind, got, refresh=refresh)

    def rows(self) -> list:
        """What the source holds for this tab: ``(name, payload, tags, key)``."""
        if self.is_online:
            return [(e["name"], e, list(e.get("categories") or []), None) for e in self.online_items]
        mine = tags.load()
        if self.is_drawing:
            if self.kind == "models":
                try:
                    entries = inventory.components_in(self.panel._app.scene)
                except Exception:  # noqa: BLE001 - never break the window for a list
                    _log.exception("could not list the components")
                    entries = []
                return [(e.name, e, mine.get(f"drawing:model:{e.name}", []), f"drawing:model:{e.name}")
                        for e in entries]
            return [(i.name, i, mine.get(f"drawing:material:{i.name}", []), f"drawing:material:{i.name}")
                    for i in sorted(self.panel._drawing_items(), key=lambda i: i.name.lower())]
        out = []
        for item in self.panel._cat_items or []:
            if item.type_key != TYPE_KEYS[self.kind]:
                continue
            if self.folder and str(item.folder) != self.folder:
                continue
            out.append((item.name, item, mine.get(item.key, []), item.key))
        return out

    def _fill_categories(self, rows):
        if self.is_online:
            cats = polyhaven.categories([p for _n, p, _t, _k in rows])
        else:
            cats = tags.clean([t for _n, _p, ts, _k in rows for t in ts])
        keep = self.category.currentData() or ""
        if cats == self._cats and self.category.count():
            return
        self._cats = cats
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem(tr("All categories"), "")
        for c in cats:
            self.category.addItem(c, c)
        self.category.setCurrentIndex(max(0, self.category.findData(keep)))
        self.category.blockSignals(False)

    def fill(self):
        rows = self.rows()
        self._fill_categories(rows)
        cat = (self.category.currentData() or "").lower()
        text = self.search.text().strip().lower()
        keep = self.list.currentItem()
        keep = self._identity(keep.data(Qt.UserRole)) if keep is not None else None
        if self.is_online:
            self.current_source().forget_thumbs()
        self.list.clear()
        blank = QPixmap(ICON, ICON)
        blank.fill(Qt.transparent)
        blank_icon = QIcon(blank)
        generic = self.style().standardIcon(QStyle.SP_FileIcon)
        bold = QFont(self.list.font())
        bold.setBold(True)
        shown = 0
        for name, payload, item_tags, key in rows:
            if cat and cat not in (t.lower() for t in item_tags):
                continue
            if self.is_online:
                if not polyhaven.matches(payload, text):
                    continue
            elif text and not all(w in name.lower() for w in text.split()):
                continue
            label, tip, new = self._describe(name, payload)
            if item_tags:
                tip += "\n" + tr("Categories: {names}", names=", ".join(item_tags[:8]))
            it = QListWidgetItem(blank_icon if self.is_online or self.is_drawing else generic,
                                 (NEW_MARK if new else "") + label)
            it.setData(Qt.UserRole, payload)
            it.setData(Qt.UserRole + 2, key)
            it.setToolTip(tip + ("\n" + tr("New") if new else ""))
            if new:
                it.setFont(bold)
            self.list.addItem(it)
            if keep is not None and self._identity(payload) == keep:
                self.list.setCurrentItem(it)
            shown += 1
        self.list.schedule_icons()
        self._tell(shown, len(rows))
        self._sync_buttons()

    @staticmethod
    def _identity(payload):
        if isinstance(payload, dict):
            return payload.get("id")
        return getattr(payload, "key", None)

    def _describe(self, name, payload):
        """(label, tooltip, new in a watched folder) of a row."""
        if self.is_online:
            return name, name, False
        if self.is_drawing and self.kind == "models":
            tip = tr("Dynamic component") if payload.dynamic else tr("Component")
            return f"{DYN_MARK if payload.dynamic else ''}{name}  ×{payload.count}", tip, False
        mark = catalog.HEAVY_MARK if payload.heavy else ""
        return mark + name, self.panel._item_tip(payload), payload.key in self.panel._new_paths

    def _tell(self, shown, total):
        if self.is_online:
            self.info.setText(f"{tr('{shown} of {total}', shown=shown, total=total)} · "
                              f"{tr(self._module().CREDIT)}")
        elif not total and not self.is_drawing:
            self.info.setText(tr("Nothing here yet. Add a folder with the menu button, or save things "
                                 "to the catalog ({folder}).", folder=catalog.default_folder()))
        else:
            self.info.setText(tr("{shown} of {total}", shown=shown, total=total))

    def _icon(self, it):
        payload = it.data(Qt.UserRole)
        if isinstance(payload, dict):
            def done(path, it=it):
                try:
                    pm = QPixmap(str(path))
                    if not pm.isNull():
                        it.setIcon(QIcon(pm.scaled(ICON, ICON, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                except RuntimeError:            # the item was cleared meanwhile
                    pass
            self.current_source().thumbnail(payload, done)
        elif self.is_drawing and self.kind == "models":
            it.setIcon(self.panel._icon_for(payload))
        else:
            self.panel._catalog_icon(it)

    def _sync_buttons(self):
        it = self.list.currentItem()
        self.insert_btn.setEnabled(it is not None)
        self.export_btn.setEnabled(it is not None)
        # what is in the catalog already has nothing to save
        self.save_btn.setEnabled(it is not None and (self.is_online or self.is_drawing))
        if self.proxy_action is not None:
            self.proxy_action.setEnabled(not self.is_drawing)

    def current(self, it=None):
        it = it if it is not None else self.list.currentItem()
        if it is None:
            self.panel._say(tr("Choose an item in the list first."))
            return None
        return it

    def _provider(self, it):
        """What a drag onto the view places (models only; online ones once downloaded)."""
        if self.kind != "models":
            return None
        payload = it.data(Qt.UserRole)
        if self.is_drawing:
            def build():
                g = place.copy_of(payload.sample)
                return g, place.origin_of(g)
            return build
        if self.is_online:
            main = self.current_source().cached("models", payload, self.res.currentData())
            if main is None:
                return None
            return place.from_file(lambda: (self.panel._model_group(main, interactive=False), ORIGIN))
        return place.from_file(
            lambda: (self.panel._model_group(export.model_files(payload), interactive=False), ORIGIN))

    # --- online downloads ------------------------------------------------------------
    def download(self, e, then):
        """Download the online asset ``e``, then ``then(path, source)``."""
        panel = self.panel
        src, kind, res = self.current_source(), self.kind, self.res.currentData()
        panel._say(tr("Downloading «{name}» ({res})…", name=e["name"], res=res.upper()))

        def progress(i, n):
            panel._say(tr("Downloading «{name}» ({res})… {i}/{n}", name=e["name"], res=res.upper(), i=i, n=n))

        def heavy(total):
            from PySide6.QtWidgets import QMessageBox
            return QMessageBox.question(
                panel, tr("Heavy download"),
                tr("«{name}» ({res}) is {size}. It can take long to download and open, and slow "
                   "the drawing down. Download it anyway?", name=e["name"], res=res.upper(),
                   size=catalog.size_text(total))) == QMessageBox.Yes

        def done(path, err):
            if err == "cancelled":
                panel._say(tr("Download of «{name}» cancelled.", name=e["name"]))
                return
            if path is None:
                panel._say(tr("Could not download «{name}»: {error}", name=e["name"], error=err))
                return
            try:
                then(path, src)
            except Exception as exc:  # noqa: BLE001 - say it, never crash the app
                _log.exception("could not use %s", path)
                panel._say(tr("Could not use «{name}»: {error}", name=e["name"], error=exc))

        src.download(kind, e, res, done, progress, confirm=heavy)

    # --- insert ------------------------------------------------------------------------
    def insert(self, it=None, proxy=False):
        it = self.current(it)
        if it is None:
            return
        panel, payload = self.panel, it.data(Qt.UserRole)
        if self.is_online:
            kind = self.kind

            def use(path, src):
                if kind == "hdris":
                    panel._use_hdri(path, payload, src)
                elif kind == "materials":
                    panel._paint_with(path, payload, src)
                else:
                    panel._place_model(path, payload, src, proxy=proxy)
            self.download(payload, use)
        elif self.is_drawing and self.kind == "models":
            g = place.copy_of(payload.sample)
            panel._place(g, place.origin_of(g))
        elif payload.scene_mat is not None:
            panel.paint_scene_material(payload.scene_mat)
        elif self.kind == "materials":
            panel.paint_with_item(payload)
        elif self.kind == "hdris":
            panel._use_hdri(payload.path, {"name": payload.name})
        else:
            try:
                g = panel._build_from(export.model_files(payload), proxy=proxy)
            except Exception as exc:  # noqa: BLE001 - say it, never crash the app
                _log.exception("could not insert %s", payload.key)
                panel._say(tr("Could not insert {name}: {error}", name=payload.name, error=exc))
                return
            panel._place(g, ORIGIN)

    # --- save to catalog ----------------------------------------------------------------
    def save(self, it=None):
        it = self.current(it)
        if it is None:
            return
        panel, payload = self.panel, it.data(Qt.UserRole)
        own = list(tags.get(it.data(Qt.UserRole + 2))) if it.data(Qt.UserRole + 2) else []
        if self.is_online:
            self.download(payload, lambda path, src: panel.save_online(self.kind, payload, path, src))
        elif self.is_drawing and self.kind == "models":
            panel.save_component(payload, own)
        elif self.is_drawing:
            panel._save_scene_materials([payload.scene_mat])
        else:
            panel._say(tr("It is in the catalog already."))

    # --- export -------------------------------------------------------------------------
    def export(self, it=None):
        it = self.current(it)
        if it is None:
            return
        payload = it.data(Qt.UserRole)
        try:
            if self.is_online:
                self.download(payload, lambda path, _src: self._export_download(payload, Path(path)))
            elif self.is_drawing and self.kind == "models":
                self._export_component(payload)
            elif self.kind == "materials":
                self._export_material(payload)
            else:
                self._export_file(export.model_files(payload), payload.name)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not export")
            self.panel._say(tr("Could not export: {error}", error=exc))

    def _ask_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("Export into which folder?"))
        return Path(path) if path else None

    def _ask_file(self, name: str, suffix: str):
        path, _f = QFileDialog.getSaveFileName(self, tr("Export"), online.safe_name(name) + suffix,
                                               f"{suffix.lstrip('.').upper()} (*{suffix})")
        if not path:
            return None
        path = Path(path)
        return path if path.suffix.lower() == suffix.lower() else path.with_name(path.name + suffix)

    def _exported(self, where):
        self.panel._say(tr("Exported to {path}.", path=where))

    def _export_component(self, entry):
        path = self._ask_file(entry.name, ".igz")
        if path is not None:
            export.write_component(path, entry.sample, self.panel._app.scene.materials)
            self._exported(path)

    def _export_file(self, source: Path, name: str):
        """A model or a background that is one file; a .gltf goes with the files it refers to."""
        source = Path(source)
        if source.suffix.lower() == ".gltf":
            dest = self._ask_folder()
            if dest is not None:
                self._exported(export.copy_tree(source, dest, name))
            return
        path = self._ask_file(name, source.suffix)
        if path is not None:
            shutil.copy2(source, path)
            self._exported(path)

    def _export_material(self, item):
        if item.scene_mat is None and export.material_form(item) == "file":
            self._export_file(item.path, item.name)
            return
        dest = self._ask_folder()
        if dest is None:
            return
        if item.scene_mat is not None:
            out = export.folder_for(dest, item.name)
            catalog.save_scene_material(item.scene_mat, previews.png_bytes, dest=out)
            self._exported(out)
        else:
            self._exported(export.material_folder(item, dest))

    def _export_download(self, e, main: Path):
        if self.kind == "hdris":
            self._export_file(main, e["name"])
            return
        dest = self._ask_folder()
        if dest is not None:
            self._exported(export.copy_tree(main, dest, e["name"]))

    # --- categories and the right-click menu -----------------------------------------------
    def edit_tags(self, items=None):
        items = items or self.list.selectedItems()
        keys = [i.data(Qt.UserRole + 2) for i in items if i.data(Qt.UserRole + 2)]
        if not keys:
            return
        mine = tags.load()
        current = [mine.get(k, []) for k in keys]
        known = [t for ts in mine.values() for t in ts]
        dlg = TagsDialog(self.window(), current, known)
        if dlg.exec() == QDialog.Accepted:
            tags.update({k: dlg.result_for(old) for k, old in zip(keys, current)})
            self.fill()

    def _context_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        if not it.isSelected():
            self.list.setCurrentItem(it)
        self.context_menu_for(it).exec(self.list.viewport().mapToGlobal(pos))

    def context_menu_for(self, it) -> QMenu:
        panel, payload = self.panel, it.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction(tr("Insert"), lambda: self.insert(it))
        if self.is_online:
            menu.addAction(tr("Web page"),
                           lambda: QDesktopServices.openUrl(QUrl(self.current_source().site(payload))))
            return menu
        menu.addAction(tr("Categories…"), lambda: self.edit_tags())
        if self.is_drawing and self.kind == "models":
            menu.addSeparator()
            menu.addAction(tr("Select all"), lambda: panel.select_like(payload.sample))
            menu.addAction(tr("Replace all…"), lambda: panel.replace_all(payload))
            menu.addAction(tr("Edit"), lambda: panel.edit_component(payload))
            act = menu.addAction(tr("Stand-in: not rendered, shown translucent"))
            act.setCheckable(True)
            act.setChecked(bool(stand_in.state_of(payload.instances)))
            act.triggered.connect(lambda on: panel.set_stand_in(list(payload.instances), bool(on)))
        return menu

    def fill_menu(self):
        panel = self.panel
        menu = self.menu_btn.menu()
        menu.clear()
        menu.addAction(tr("Add a catalog folder…"), panel.add_folder)
        act = menu.addAction(tr("Take the shown folder off the catalog"),
                             lambda: panel.remove_folder(self.folder))
        act.setEnabled(bool(self.folder))
        if self.kind == "materials":
            menu.addAction(tr("Save all the drawing's materials"), panel.save_all_materials)
        if self.kind == "models":
            sites = menu.addMenu(tr("Open a model site"))
            for name, url in catalog.sites():
                a = sites.addAction(name)
                a.setToolTip(url)
                a.triggered.connect(lambda _c=False, u=url: panel.open_site(u))
            if sites.actions():
                sites.addSeparator()
            sites.addAction(tr("Add or edit sites…"), panel.open_settings)
        menu.addSeparator()
        menu.addAction(tr("Settings…"), panel.open_settings)
