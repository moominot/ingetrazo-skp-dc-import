# SPDX-License-Identifier: GPL-3.0-or-later
"""The Library tray tab: what the drawing holds, the user's catalog
folders, and Poly Haven's free HDRIs, materials and models."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDrag, QIcon, QPixmap, QVector3D
from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPushButton, QStyle, QTabWidget, QToolButton, QVBoxLayout,
                               QWidget)

from . import (ambientcg, catalog, inventory, online, online_tab, place, polyhaven, previews,
               stand_in, thumbs)
from .i18n import tr, translate_on_show
SOURCES = (polyhaven, ambientcg)
NEW_MARK = "● "
DRAWING = "@drawing"      # the folder box's entry for the drawing's own materials

_log = logging.getLogger(__name__)
ICON = 64
PH_ICON = 96
DYN_MARK = "⚙ "          # dynamic components wear this in the list
DONE_ROLE = Qt.UserRole + 1
ORIGIN = QVector3D(0.0, 0.0, 0.0)
PROXY_TIP = ("Insert a light envelope (its outer shape, without detail) in the model's place; the full model is kept in an .igz file "
             "next to the drawing (folder «<drawing>_proxies») and the render uses it. "
             "Good for heavy models such as trees and furniture. Dynamic components inside "
             "cannot be changed while the model is a proxy.")


class DragList(QListWidget):
    """A list whose items can be dragged onto the 3-D view. ``provider(item)``
    returns a callable building ``(group, anchor)``, or None when the item
    cannot be dragged now (``refused(item)`` is then called)."""

    def __init__(self, drop, icon=ICON, grid=False):
        super().__init__()
        self.drop = drop
        self.provider = None
        self.refused = None
        self.icon_loader = None
        self.setIconSize(QSize(icon, icon))
        if grid:
            self.setViewMode(QListWidget.IconMode)
            self.setResizeMode(QListWidget.Adjust)
            self.setMovement(QListWidget.Static)
            self.setGridSize(QSize(icon + 28, icon + 40))
            self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragOnly)
        self._lazy = QTimer(self)
        self._lazy.setSingleShot(True)
        self._lazy.setInterval(60)
        self._lazy.timeout.connect(self._fill_visible)
        self.verticalScrollBar().valueChanged.connect(lambda _v: self._lazy.start())

    def resizeEvent(self, ev):  # noqa: N802
        super().resizeEvent(ev)
        self._lazy.start()

    def showEvent(self, ev):  # noqa: N802
        super().showEvent(ev)
        self._lazy.start()

    def schedule_icons(self):
        self._lazy.start()

    def _fill_visible(self):
        if self.icon_loader is None or not self.isVisible():
            return
        area = self.viewport().rect()
        for i in range(self.count()):
            it = self.item(i)
            if it.isHidden() or it.data(DONE_ROLE):
                continue
            if self.visualItemRect(it).intersects(area):
                it.setData(DONE_ROLE, True)
                try:
                    self.icon_loader(it)
                except Exception:  # noqa: BLE001 - an icon must never break the list
                    _log.exception("icon failed")

    def startDrag(self, actions):  # noqa: N802 - Qt override
        it = self.currentItem()
        if it is None or self.provider is None:
            return
        build = self.provider(it)
        if build is None:
            if self.refused:
                self.refused(it)
            return
        mime = QMimeData()
        mime.setData(place.MIME, b"1")
        drag = QDrag(self)
        drag.setMimeData(mime)
        pm = it.icon().pixmap(self.iconSize())
        if not pm.isNull():
            drag.setPixmap(pm)
        self.drop.begin(build)
        try:
            drag.exec(Qt.CopyAction)
        finally:
            self.drop.end()


def _row(*widgets, stretch_first=False):
    row = QHBoxLayout()
    for i, w in enumerate(widgets):
        row.addWidget(w, 1 if (stretch_first and i == 0) else 0)
    return row


def _button(text, tip, fn):
    b = QPushButton(text)
    b.setToolTip(tip)
    b.clicked.connect(fn)
    return b


class _Size:
    """The real size in metres a material is painted at (a catalog material
    keeps the one it was saved with, 1 × 1 m when it says none; the
    materials tray can change it)."""

    def __init__(self, w=1.0, h=1.0):
        self.w, self.h = w, h

    def tile_size_m(self, _e):
        return self.w, self.h


def _swatch(rgb, size=PH_ICON) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor.fromRgbF(*[max(0.0, min(1.0, float(c))) for c in tuple(rgb)[:3]]))
    return QIcon(pm)


STAND_IN_TIP = ("A place-holder: it shows in the drawing, translucent, and the render leaves it out. "
                "Swap it for a component of your own or draw into it; clear this when the real thing is there. "
                "A face with a paint of its own keeps it.")


class AssetPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self._app = app
        self._entries: list = []
        self._thumb_cache: dict = {}
        self._dirty = True
        self._cat_items = None
        self._sources: dict = {}
        self._known: set = set()
        self._new_paths: set = set()
        self._watcher = None
        self._proxy_boxes: list = []
        self._note = ""
        self._watch_timer = QTimer(self)
        self._watch_timer.setSingleShot(True)
        self._watch_timer.setInterval(1200)     # a download lands in several steps
        self._watch_timer.timeout.connect(self._watched_changed)
        self.drop = place.DropOnView(app.window, self)
        self.drop.on_error = self._say
        self.drop.watch_all()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.status)

        self._build_drawing_tab()
        self._build_catalog_tab()
        self._build_online_tabs()
        self.tabs.currentChanged.connect(self._tab_shown)

        on_changed = getattr(app, "on_document_changed", None)
        if on_changed is not None:
            on_changed(self._document_changed)
        self.refresh()
        translate_on_show(self)
        QTimer.singleShot(2000, self._init_watch)

    # --- helpers -----------------------------------------------------------------
    def _say(self, text):
        self.status.setText(text)

    @property
    def _vp(self):
        return self._app.viewport

    def _place(self, group, anchor):
        note, self._note = self._note, ""
        if group is None:
            if not note:
                self._say(tr("The model has no geometry."))
            return
        place.start_place(self._app.window, group, anchor)
        self._say((note + " " if note else "") + tr("Click in the view to place it (Esc cancels). "
                                                    "You can also drag it from the list onto the view."))

    # --- as a proxy ------------------------------------------------------------------
    def _proxy_box(self):
        """An «As proxy» check box; every tab's shows the same setting."""
        box = QCheckBox("As proxy")
        box.setToolTip(tr(PROXY_TIP))
        box.setChecked(catalog.as_proxy())
        box.toggled.connect(self._proxy_toggled)
        self._proxy_boxes.append(box)
        return box

    def _proxy_toggled(self, on):
        catalog.set_as_proxy(on)
        for b in self._proxy_boxes:
            if b.isChecked() != on:
                b.blockSignals(True)
                b.setChecked(on)
                b.blockSignals(False)

    def _confirm_dynamic(self, name):
        """Asked before a model with dynamic components goes in as a proxy."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("Insert as proxy"))
        box.setText(tr("«{name}» holds dynamic components.", name=name))
        box.setInformativeText(
            tr("As a proxy, its options and formulas cannot be changed: the drawing holds only "
               "its envelope until the original is shown again. Insert it as a proxy anyway?"))
        as_proxy = box.addButton(tr("Insert as proxy"), QMessageBox.AcceptRole)
        normal = box.addButton(tr("Insert the full model"), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(normal)
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        try:
            box.exec()
        finally:
            QApplication.restoreOverrideCursor()
        clicked = box.clickedButton()
        return "proxy" if clicked is as_proxy else "normal" if clicked is normal else None

    def confirm_dynamic_many(self, names):
        """Asked before objects holding dynamic components become proxies."""
        shown = ", ".join(f"«{n}»" for n in names[:4]) + ("…" if len(names) > 4 else "")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(tr("Make proxy"))
        box.setText(tr("{names} holds dynamic components.", names=shown) if len(names) == 1
                    else tr("{names} hold dynamic components.", names=shown))
        box.setInformativeText(
            tr("As a proxy, their options and formulas cannot be changed: the drawing holds only "
               "the envelope until the original is shown again (right-click ▸ Show original). "
               "Make proxies anyway?"))
        yes = box.addButton(tr("Make proxy"), QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        try:
            box.exec()
        finally:
            QApplication.restoreOverrideCursor()
        return box.clickedButton() is yes

    def _model_group(self, path, interactive=True):
        """The component to place for the model file ``path``: the model
        itself, or its proxy when «As proxy» is on. ``interactive``: a model
        with dynamic components asks first (not while dragging: it then
        goes in as a proxy and the status line says so)."""
        if not catalog.as_proxy():
            return place.group_from_file(self._vp, path)
        g, kind, dynamic = place.proxy_from_file(
            self._vp, path, self._confirm_dynamic if interactive else None)
        if g is None:
            self._note = tr("Cancelled.") if dynamic else ""
        elif kind == "normal":
            self._note = tr("«{name}» goes in as the full model.", name=g.name)
        else:
            from . import proxy
            info = proxy.info_of(g) or {}
            where = Path(info.get("file") or "").parent
            self._note = tr("«{name}» goes in as a proxy (its envelope; the full model, "
                            "{faces} faces, is kept in {where}).",
                            name=g.name, faces=f"{info.get('faces', 0):,}", where=where)
            if dynamic:
                self._note += " " + tr("Its dynamic components cannot be changed while it is a proxy.")
        if not interactive and self._note:
            self._say(self._note)
            self._note = ""
        return g

    def _document_changed(self, *_a):
        self.drop.watch_all()               # a new project tab has a new view
        self._dirty = True
        if self.isVisible() and self.tabs.currentIndex() == 0:
            QTimer.singleShot(0, self.refresh)

    def showEvent(self, ev):  # noqa: N802
        super().showEvent(ev)
        self._tab_shown(self.tabs.currentIndex())

    def _tab_shown(self, index):
        if index == 0 and self._dirty:
            self.refresh()
        elif index == 1:
            if self._cat_items is None:
                self.refresh_catalog()
            else:
                self._fill_catalog()            # the drawing's materials may have changed
        elif index >= 2:
            tab = self.tabs.widget(index)
            if getattr(tab, "loaded", 1) is None:
                tab.load()

    # =========================================================================
    # In the drawing
    # =========================================================================
    def _build_drawing_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)
        self.scene_list = DragList(self.drop)
        self.scene_list.setToolTip("Drag a component onto the view to place a copy of it")
        self.scene_list.provider = self._drawing_provider
        self.scene_list.itemDoubleClicked.connect(lambda _i: self.select_current())
        v.addWidget(self.scene_list, 1)
        self.stand_box = QCheckBox("Stand-in: not rendered, shown translucent")
        self.stand_box.setToolTip(tr(STAND_IN_TIP))
        self.stand_box.setEnabled(False)
        self.stand_box.clicked.connect(self._stand_in_clicked)
        self.scene_list.currentItemChanged.connect(lambda *_a: self._sync_stand_box())
        v.addWidget(self.stand_box)
        v.addLayout(_row(
            _button("Refresh", "List the components again", self.refresh),
            _button("Select all", "Select every placement of the chosen component", self.select_current),
            _button("Place copy", "A copy of the chosen component follows the cursor; "
                    "a click places it", self.place_copy)))
        v.addLayout(_row(
            _button("Replace all…", "Swap every placement of the chosen component for another "
                    "component of the model (Replace Component); each keeps its place, turn and "
                    "scale. Stand-ins are cleared first.", self.replace_all),
            _button("Edit", "Open the chosen component to edit it: a change reaches every "
                    "placement", self.edit_current)))
        self.summary = QLabel()
        v.addWidget(self.summary)
        self.tabs.addTab(page, "In drawing")

    def _icon_for(self, e):
        s = e.sample
        key = (e.key, id(getattr(s, "mesh", None)), len(getattr(s, "children", None) or ()))
        icon = self._thumb_cache.get(key)
        if icon is None:
            icon = self._thumb_cache[key] = QIcon(thumbs.render(s, ICON))
        return icon

    def refresh(self):
        self._dirty = False
        current = self.scene_list.currentItem()
        keep = current.data(Qt.UserRole).key if current is not None else None
        self.scene_list.clear()
        try:
            self._entries = inventory.components_in(self._app.scene)
        except Exception:  # noqa: BLE001 - never break the window for a list
            _log.exception("could not list the components")
            self._entries = []
        for e in self._entries:
            label = f"{DYN_MARK if e.dynamic else ''}{e.name}  ×{e.count}"
            it = QListWidgetItem(self._icon_for(e), label)
            it.setData(Qt.UserRole, e)
            it.setToolTip(tr("Dynamic component") if e.dynamic else tr("Component"))
            self.scene_list.addItem(it)
            if e.key == keep:
                self.scene_list.setCurrentItem(it)
        n = len(self._entries)
        dyn = sum(e.dynamic for e in self._entries)
        self.summary.setText(tr("{n} component, {d} dynamic", n=n, d=dyn) if n == 1
                                 else tr("{n} components, {d} dynamic", n=n, d=dyn))

    def _sync_stand_box(self):
        e = self._current_entry()
        box = self.stand_box
        box.blockSignals(True)
        box.setEnabled(e is not None)
        state = stand_in.state_of(e.instances) if e is not None else False
        box.setTristate(state is None)
        box.setCheckState(Qt.PartiallyChecked if state is None
                          else Qt.Checked if state else Qt.Unchecked)
        box.blockSignals(False)

    def _stand_in_clicked(self, checked):
        e = self._current_entry()
        if e is not None:
            self.stand_box.setTristate(False)
            self.set_stand_in(list(e.instances), bool(checked))

    def set_stand_in(self, groups, on):
        """Mark ``groups`` as stand-ins (or not): one undo step."""
        n = stand_in.set_stand_in(self._vp, groups, on)
        self._say(tr("{n} marked as stand-in (not rendered, translucent).", n=n) if on and n
                  else tr("{n} back to normal: they render.", n=n) if n else "")
        self._sync_stand_box()

    def _current_entry(self):
        it = self.scene_list.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def select_current(self):
        e = self._current_entry()
        if e is not None:
            self.select_like(e.sample)

    def select_like(self, group):
        """Select every placement of ``group``'s component that can be
        selected where the user is editing; say how many there are in all."""
        scene = self._app.scene
        here, total = inventory.instances_of(scene, inventory.definition_key(group))
        scene.selection.clear()
        scene.selection.update(here)
        notify = getattr(self._vp, "notify_selection_changed", None)
        if callable(notify):
            notify()
        self._vp.update()
        name = inventory.display_name(group)
        if len(here) < total:
            self._say(tr("Selected {n} of the {total} «{name}»: the others are "
                         "inside other groups (open one to select its own).",
                         n=len(here), total=total, name=name))
        else:
            self._say(tr("Selected the {total} «{name}».", total=total, name=name))
        return here, total

    def _drawing_provider(self, it):
        e = it.data(Qt.UserRole)

        def build():
            g = place.copy_of(e.sample)
            return g, place.origin_of(g)
        return build

    def replace_all(self):
        """Replace Component for every placement of the chosen component: the
        window's own command, after the user picks the new one. Stand-ins are
        cleared first (so the swapped-in component does not keep their
        translucent paint) and put back when nothing was replaced."""
        from PySide6.QtWidgets import QInputDialog
        e = self._current_entry()
        if e is None:
            self._say(tr("Choose a component in the list first."))
            return
        window = self._app.window
        needed = ("_replacement_choices", "replace_selection_with")
        if not all(hasattr(window, n) for n in needed):
            self._say(tr("This IngeTrazo has no Replace Component."))
            return
        here, _total = self.select_like(e.sample)
        targets = [g for g in here if getattr(g, "is_component", None) and g.is_component()]
        if not targets:
            self._say(tr("Nothing to replace here: select the component's placements first."))
            return
        choices = window._replacement_choices(list(self._app.scene.selection))
        if not choices:
            self._say(tr("There is no other component in the model to replace it with."))
            return
        labels = [lb for lb, _g in choices]
        label, ok = QInputDialog.getItem(
            window, tr("Replace Component"),
            tr("Replace {n} selected instances with:", n=len(targets)), labels, 0, False)
        if not ok or label not in labels:
            return
        cleared = stand_in.set_stand_in(self._vp, targets, False)
        done = 0
        try:
            done = window.replace_selection_with(choices[labels.index(label)][1])
        finally:
            if cleared and not done:
                self._vp.history.undo()          # the stand-ins come back
                self._vp.update()
        self.refresh()

    def edit_current(self):
        """Edit the chosen component (the double-click's road): what is drawn
        inside reaches every placement."""
        e = self._current_entry()
        if e is None:
            self._say(tr("Choose a component in the list first."))
            return
        begin = getattr(self._vp, "begin_group_edit", None)
        if not callable(begin):
            self._say(tr("This IngeTrazo cannot edit a group from here."))
            return
        try:
            begin(e.sample)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not edit the component")
            self._say(tr("Could not edit it: {error}", error=exc))

    def place_copy(self):
        e = self._current_entry()
        if e is None:
            self._say(tr("Choose a component in the list first."))
            return
        g = place.copy_of(e.sample)
        self._place(g, place.origin_of(g))

    # =========================================================================
    # My catalog
    # =========================================================================
    def _build_catalog_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)
        self.folder_box = QComboBox()
        self.folder_box.setToolTip("Which catalog folder to show")
        self.folder_box.currentIndexChanged.connect(lambda _i: self._fill_catalog())
        add = QToolButton()
        add.setText("+")
        add.setToolTip("Add a folder of your own models (.igz, .skp) to the catalog")
        add.clicked.connect(self.add_folder)
        rem = QToolButton()
        rem.setText("−")
        rem.setToolTip("Take the shown folder off the catalog (its files are not touched)")
        rem.clicked.connect(self.remove_folder)
        gear = QToolButton()
        gear.setText("⚙")
        gear.setToolTip("Settings: model sites, and which folders are watched in real time")
        gear.clicked.connect(self.open_settings)
        v.addLayout(_row(self.folder_box, add, rem, gear, stretch_first=True))
        self.cat_search = QLineEdit()
        self.cat_search.setPlaceholderText("Search by name…")
        self.cat_search.setClearButtonEnabled(True)
        self.cat_search.textChanged.connect(lambda _t: self._fill_catalog())
        self.cat_type = QComboBox()
        self.cat_type.setToolTip("Show only one kind of thing")
        for label, key in ((tr("All types"), ""), (tr("Models"), "model"),
                           (tr("Materials"), "material"), (tr("Backgrounds"), "background")):
            self.cat_type.addItem(label, key)
        self.cat_type.currentIndexChanged.connect(lambda _i: self._fill_catalog())
        v.addLayout(_row(self.cat_search, self.cat_type, stretch_first=True))
        self.cat_list = DragList(self.drop)
        self.cat_list.setToolTip("Double-click or drag onto the view to insert")
        self.cat_list.provider = self._catalog_provider
        self.cat_list.refused = lambda it: self.insert_current(it)
        self.cat_list.icon_loader = self._catalog_icon
        self.cat_list.itemDoubleClicked.connect(lambda _i: self.insert_current())
        v.addWidget(self.cat_list, 1)
        self.site_btn = QToolButton()
        self.site_btn.setText("Open a model site")
        self.site_btn.setToolTip("Open a model site in your browser (add sites in ⚙ Settings). "
                                 "Download into a watched folder and the model shows here.")
        self.site_btn.setPopupMode(QToolButton.InstantPopup)
        self.site_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.site_btn.setMenu(QMenu(self.site_btn))
        self.site_btn.menu().aboutToShow.connect(self._fill_sites_menu)
        v.addLayout(_row(
            _button("Update", "Read the folders again (the watched ones update by themselves)",
                    self.refresh_catalog),
            _button("Insert", "The chosen model follows the cursor, a click places it; a material "
                    "loads the paint bucket; a background becomes the 360° background",
                    self.insert_current),
            self.site_btn))
        v.addLayout(_row(
            _button("Save to catalog", "Keep the chosen material «(drawing)» in your catalog "
                    "(its image, or a simple picture of its colour, plus translucency and finish)",
                    self.save_current_item),
            _button("Save all", "Keep every material of the drawing that is not in the catalog yet",
                    self.save_all_materials),
            self._proxy_box()))
        self.cat_info = QLabel()
        self.cat_info.setWordWrap(True)
        v.addWidget(self.cat_info)
        self.tabs.addTab(page, "My catalog")

    def _fill_folders(self):
        keep = self.folder_box.currentData()
        self.folder_box.blockSignals(True)
        self.folder_box.clear()
        self.folder_box.addItem(tr("All folders"), "")
        self.folder_box.addItem(tr("Materials of this drawing"), DRAWING)
        watched = catalog.watched()
        for i, f in enumerate(catalog.folders()):
            label = tr("Extension's own folder") if i == 0 else (f.name or str(f))
            live = any(f == w for w in watched)
            self.folder_box.addItem(label + ("  " + tr("(live)") if live else ""), str(f))
            self.folder_box.setItemData(
                self.folder_box.count() - 1,
                f"{f}\n" + (tr("Watched in real time") if live else tr("Read again with Update")),
                Qt.ToolTipRole)
        idx = self.folder_box.findData(keep) if keep is not None else 0
        self.folder_box.setCurrentIndex(max(0, idx))
        self.folder_box.blockSignals(False)

    def refresh_catalog(self):
        self._fill_folders()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._cat_items = catalog.scan()
        finally:
            QApplication.restoreOverrideCursor()
        self._known = {i.key for i in self._cat_items}
        self._new_paths &= self._known      # what arrived before the first look stays marked
        self._fill_catalog()
        self.start_watching()

    def _init_watch(self):
        """At start: know what the watched folders hold, and watch them
        (without reading every catalog folder, which may be on a network)."""
        if self._watcher is not None:
            return
        for root in catalog.watched():
            self._known |= {i.key for i in catalog.scan(root)}
        self.start_watching()

    def _fill_catalog(self):
        if self._cat_items is None:
            return
        folder = self.folder_box.currentData() or ""
        text = self.cat_search.text().strip().lower()
        generic = self.style().standardIcon(QStyle.SP_FileIcon)
        keep = self.cat_list.currentItem()
        keep = keep.data(Qt.UserRole).key if keep is not None else None
        self.cat_list.clear()
        shown = 0
        bold = QFont(self.cat_list.font())
        bold.setBold(True)
        kind = self.cat_type.currentData() or ""
        saved = {i.name.lower() for i in self._cat_items if i.is_material}
        pool = list(self._cat_items)
        if folder in ("", DRAWING):         # the drawing's materials, but not the ones already kept
            pool += [i for i in self._drawing_items() if folder == DRAWING or i.name.lower() not in saved]
        if folder == DRAWING:
            pool = [i for i in pool if i.scene_mat is not None]
        pool.sort(key=lambda i: (i.name.lower(), i.key.lower()))
        total = len(pool)
        for item in pool:
            if folder and folder != DRAWING and str(item.folder) != folder:
                continue
            if kind and item.type_key != kind:
                continue
            if text and not all(w in item.name.lower() for w in text.split()):
                continue
            new = item.key in self._new_paths
            it = QListWidgetItem(generic, f"{NEW_MARK if new else ''}{item.label}")
            it.setData(Qt.UserRole, item)
            it.setToolTip(self._item_tip(item) + ("\nNew" if new else ""))
            if new:
                it.setFont(bold)
            self.cat_list.addItem(it)
            if item.key == keep:
                self.cat_list.setCurrentItem(it)
            shown += 1
        self.cat_list.schedule_icons()
        own = catalog.default_folder()
        if not self._cat_items and not pool:
            self.cat_info.setText(tr("No models yet. Add a folder with «+», or put .igz/.skp files "
                                     "(and a .png with the same name as preview) in\n{folder}",
                                     folder=own))
        else:
            mats = sum(1 for i in pool if i.is_material)
            hdris = sum(1 for i in pool if i.is_hdri)
            self.cat_info.setText(tr("{shown} of {total} ({models} models, {mats} materials, "
                                     "{hdris} backgrounds)",
                                     shown=shown, total=total,
                                     models=total - mats - hdris, mats=mats, hdris=hdris))

    @staticmethod
    def _item_tip(item) -> str:
        tip = AssetPanel._tip_base(item)
        if item.size:
            tip += "\n" + tr("Size: {size}", size=catalog.size_text(item.size))
        if item.heavy:
            tip += "\n" + tr("Heavy: it may take long to open and slow the drawing down. "
                             "As a proxy only a light envelope stays in the drawing.")
        return tip

    @staticmethod
    def _tip_base(item) -> str:
        where = str(item.path) + (f"\n› {item.member}" if item.member else "")
        if item.scene_mat is not None:
            m = item.scene_mat
            parts = [f"{item.name} (in this drawing, not in the catalog yet)"]
            tex = getattr(m, "texture", None) or {}
            parts.append(f"{tex.get('sw', 1):g} × {tex.get('sh', 1):g} m" if tex else "Plain colour")
            if getattr(m, "opacity", None) is not None:
                parts.append(f"Opacity {m.opacity:g}")
            if getattr(m, "finish", None):
                parts.append(f"Finish: {m.finish}")
            return "\n".join(parts + ["Double-click or Insert: paint with it"])
        if item.is_material:
            what = ", ".join(sorted(item.maps)) if item.maps else "plain colour"
            return (f"{where}\nMaterial: {what}\n"
                    "Double-click or Insert: paint with it")
        if item.is_hdri:
            return f"{where}\nDouble-click or Insert: use as the 360° background"
        return where

    def _catalog_icon(self, it):
        item = it.data(Qt.UserRole)
        pm = QPixmap()
        plain = (item.spec is not None and not item.maps) or (
            item.scene_mat is not None and not getattr(item.scene_mat, "texture", None))
        if item.scene_mat is not None and not plain:
            pm.load(str(item.path))                           # the drawing's picture
        elif plain and (item.preview is None or not item.preview.is_file()):
            src = item.scene_mat if item.scene_mat is not None else None
            spec = item.spec or {}
            pm = previews.render(getattr(src, "color", None) or spec.get("rgb"),
                                 getattr(src, "opacity", None) if src is not None else spec.get("opacity"),
                                 getattr(src, "finish", None) if src is not None else spec.get("finish"),
                                 ICON)
        elif item.preview is not None and not item.maps:
            pm.load(str(item.preview))
        if pm.isNull():
            data = catalog.preview_bytes(item)
            if data:
                pm.loadFromData(data)
        if not pm.isNull():
            it.setIcon(QIcon(pm.scaled(ICON, ICON, Qt.KeepAspectRatio, Qt.SmoothTransformation)))

    def add_folder(self):
        from . import ui_settings
        path = ui_settings.choose_and_add_folder(self)
        if path is None:
            return
        self.refresh_catalog()
        self.folder_box.setCurrentIndex(max(0, self.folder_box.findData(str(path))))
        live = catalog.is_watched(path)
        self._say(tr("Added {path}", path=path) + (" " + tr("(watched in real time).") if live else
                                                   " " + tr("(press Update to read it again).")))

    def remove_folder(self):
        folder = self.folder_box.currentData() or ""
        if not folder:
            self._say(tr("Show one folder first (not «All folders»)."))
            return
        if catalog.remove_folder(folder):
            self.refresh_catalog()
            self._say(tr("Taken off the catalog: {folder}", folder=folder))
        else:
            self._say(tr("The extension's own folder stays in the catalog."))

    def open_settings(self):
        from . import ui_settings
        d = ui_settings.SettingsDialog(self.window())
        d.exec()
        if d.changed or self._cat_items is not None:
            self.refresh_catalog()

    # --- model sites ---------------------------------------------------------------
    def _fill_sites_menu(self):
        menu = self.site_btn.menu()
        menu.clear()
        for name, url in catalog.sites():
            act = menu.addAction(name)
            act.setToolTip(url)
            act.triggered.connect(lambda _c=False, u=url: self.open_site(u))
        if menu.actions():
            menu.addSeparator()
        menu.addAction("Add or edit sites…", self.open_settings)

    def open_site(self, url):
        QDesktopServices.openUrl(QUrl(url))
        live = [str(w) for w in catalog.watched()]
        if live:
            self._say(tr("Opened in your browser. Models downloaded into a watched folder show "
                         "here at once: ") + "; ".join(live))
        else:
            self._say(tr("Opened in your browser. Tip: add your Downloads folder to the catalog "
                         "with «+» and watch it, so downloaded models show here at once."))

    # --- watching folders ----------------------------------------------------------
    def start_watching(self):
        """Watch the folders marked «real time» (and the folders inside
        them); a change reads them again a moment later."""
        if self._watcher is None:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.directoryChanged.connect(lambda _p: self._watch_timer.start())
        old = self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        dirs = []
        for root in catalog.watched():
            dirs += [str(d) for d in catalog.subfolders(root)]
        if dirs:
            self._watcher.addPaths(dirs)
        return dirs

    def _watched_changed(self):
        """A watched folder changed: read the watched folders again and
        mark what is new."""
        roots = catalog.watched()
        if not roots:
            return
        fresh = []
        for root in roots:
            fresh += catalog.scan(root)
        fresh_paths = {i.key for i in fresh}
        added = [i for i in fresh if i.key not in self._known]
        if added:
            names = ", ".join(i.name for i in added[:4]) + (" …" if len(added) > 4 else "")
            self._say(tr("New in the catalog: {names}", names=names))
        if self._cat_items is None:         # the catalog tab was not opened yet
            self._known |= fresh_paths
            self._new_paths |= {i.key for i in added}
            self.start_watching()
            return
        root_strs = {str(r) for r in roots}
        others = [i for i in (self._cat_items or []) if str(i.folder) not in root_strs]
        self._cat_items = sorted(others + fresh, key=lambda i: (i.name.lower(), i.key.lower()))
        self._known = {i.key for i in self._cat_items}
        self._new_paths = (self._new_paths & fresh_paths) | {i.key for i in added}
        self.start_watching()               # a new subfolder is watched too
        self._fill_catalog()

    def _build_from(self, path):
        from . import progress
        with progress.window(self.window(), tr("Importing {name}…", name=Path(path).name)):
            return self._model_group(path)

    @staticmethod
    def _model_file(item):
        """The model's file: itself, or taken out of its zip."""
        return catalog.extract(item) if item.member else item.path

    def insert_current(self, it=None):
        it = it if it is not None else self.cat_list.currentItem()
        if it is None:
            self._say(tr("Choose a model in the list first."))
            return
        item = it.data(Qt.UserRole)
        if item.scene_mat is not None:
            self.paint_scene_material(item.scene_mat)
            return
        if item.is_material:
            self.paint_with_item(item)
            return
        if item.is_hdri:
            self._use_hdri(item.path, {"name": item.name})
            return
        try:
            g = self._build_from(self._model_file(item))
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not insert %s", item.key)
            self._say(tr("Could not insert {name}: {error}", name=item.name, error=exc))
            return
        self._place(g, ORIGIN)

    def paint_scene_material(self, obj):
        """A material of the drawing: the paint bucket takes it."""
        try:
            tex = obj.texture or {}
            if tex.get("path"):
                self._paint_with(tex["path"], {"name": obj.name},
                                 _Size(float(tex.get("sw") or 1.0), float(tex.get("sh") or 1.0)))
                self._stamp_recipe(obj.name, texture=True)
            else:
                self._paint_color(obj.color or (0.8, 0.8, 0.8), obj.name, obj.opacity, obj.finish)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not use %s", obj.name)
            self._say(tr("Could not use {name}: {error}", name=obj.name, error=exc))

    def paint_with_item(self, item):
        """A material from the catalog: its maps copied to the extension's
        folder with a manifest, and the paint bucket loaded with it."""
        try:
            spec = item.spec or {}
            if item.scene_mat is not None:
                self.paint_scene_material(item.scene_mat)
            elif item.maps:
                color, _maps = catalog.material_files(item)
                self._paint_with(color, {"name": item.name}, _Size(*catalog.material_size(item)))
                self._stamp_recipe(item.name, texture=True, opacity=spec.get("opacity"),
                                   finish=spec.get("finish"))
            else:
                self._paint_color(spec.get("rgb") or (0.8, 0.8, 0.8), item.name,
                                  spec.get("opacity"), spec.get("finish"))
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not use %s", item.key)
            self._say(tr("Could not use {name}: {error}", name=item.name, error=exc))

    def _catalog_provider(self, it):
        item = it.data(Qt.UserRole)
        if item.is_material or item.is_hdri:
            return None                     # a material is painted, a background is set
        return place.from_file(
            lambda: (self._model_group(self._model_file(item), interactive=False), ORIGIN))

    # =========================================================================
    # Materials of the drawing, listed in the catalog beside the saved ones
    # =========================================================================
    def _drawing_items(self):
        """The drawing's materials as catalog items (not saved anywhere yet)."""
        out = []
        for m in getattr(self._app.scene, "materials", {}).values():
            tex = getattr(m, "texture", None) or {}
            path = Path(tex["path"]) if tex.get("path") else Path("drawing")
            out.append(catalog.Item(m.name, path, None, None, scene_mat=m))
        return out

    def _after_catalog_save(self):
        """The catalog holds something new: read it again where it is shown."""
        if self._cat_items is not None:
            self.refresh_catalog()

    def save_current_item(self):
        """«Save to catalog» for the chosen material of the drawing."""
        it = self.cat_list.currentItem()
        item = it.data(Qt.UserRole) if it is not None else None
        if item is None or item.scene_mat is None:
            self._say(tr("Choose a material «(drawing)» in the list first."))
            return
        self._save_scene_materials([item.scene_mat])

    def save_all_materials(self):
        self._save_scene_materials(list(getattr(self._app.scene, "materials", {}).values()))

    def _save_scene_materials(self, mats):
        new = have = 0
        errors = []
        for m in mats:
            try:
                _path, fresh = catalog.save_scene_material(m, previews.png_bytes)
            except Exception as exc:  # noqa: BLE001 - say it, never crash the app
                _log.exception("could not save %s", m.name)
                errors.append(f"{m.name}: {exc}")
                continue
            new += fresh
            have += not fresh
        if new:
            self._after_catalog_save()
        msg = tr("{n} saved to the catalog ({folder}).", n=new, folder=catalog.default_folder() / "Materials")
        if have:
            msg += " " + tr("{n} already there.", n=have)
        if errors:
            msg += " " + tr("Could not save: {names}.", names="; ".join(errors[:3]))
        self._say(msg)

    def save_online(self, kind, e, path, src):
        """What an online library gave (already downloaded to ``path``) into
        the catalog."""
        try:
            _saved, fresh = catalog.save_online(kind, e["name"], path, src.tile_size_m(e), src.key,
                                                e["id"], preview=src.thumb_path(e))
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not save %s", e.get("id"))
            self._say(tr("Could not save «{name}»: {error}", name=e["name"], error=exc))
            return
        if fresh:
            self._after_catalog_save()
            self._say(tr("«{name}» saved to the catalog.", name=e["name"]))
        else:
            self._say(tr("«{name}» is already in the catalog.", name=e["name"]))

    # --- painting -------------------------------------------------------------------
    def _materials_tray(self):
        try:
            from views.tray import MaterialsPanel
            return next((w for w in QApplication.allWidgets() if isinstance(w, MaterialsPanel)), None)
        except Exception:  # noqa: BLE001
            return None

    def _stamp_recipe(self, name, texture=False, opacity=None, finish=None):
        """The paint bucket's material keeps what the material was saved with
        (translucency, finish) — the drawing's own entry when it has one."""
        try:
            from core.materials import Material
            from tools.paint import PaintTool
        except Exception:  # noqa: BLE001
            return
        have = self._app.scene.materials.get(name)
        if have is not None:
            PaintTool.current_material = have
            PaintTool.current_opacity = have.opacity
            return
        mat = PaintTool.current_material
        if mat is None:
            return
        mat.opacity = opacity
        mat.finish = finish or mat.finish
        PaintTool.current_opacity = opacity

    def _paint_color(self, rgb, name, opacity=None, finish=None):
        mats = self._materials_tray()
        from core.materials import Material
        from tools.paint import PaintTool
        rgb = tuple(float(c) for c in rgb[:3])
        if mats is not None and hasattr(mats, "_apply_color"):
            mats._apply_color(rgb, name=name)
        else:
            PaintTool.current_is_default = False
            PaintTool.current_color = rgb
            PaintTool.current_texture = None
            PaintTool.current_material = Material(name, color=rgb)
            act = getattr(self._app.window, "_activate_tool", None)
            if callable(act):
                act("paint")
        have = self._app.scene.materials.get(name)
        PaintTool.current_material = have or Material(name, color=rgb, opacity=opacity, finish=finish)
        PaintTool.current_opacity = PaintTool.current_material.opacity
        self._say(tr("Paint bucket loaded with «{name}»: click the faces to paint.", name=name))

    # =========================================================================
    # Online: Poly Haven, ambientCG
    # =========================================================================
    def _build_online_tabs(self):
        """One tab per kind of free online asset: 360° backgrounds, materials, models."""
        self.online_tabs = {}
        for kind, title in online_tab.TABS.items():
            tab = online_tab.OnlineTab(self, kind, SOURCES, DragList, PH_ICON, _row, _button, ORIGIN)
            self.online_tabs[kind] = tab
            self.tabs.addTab(tab, title)

    def source_for(self, key):
        src = self._sources.get(key)
        if src is None:
            mod = next(m for m in SOURCES if m.KEY == key)
            src = self._sources[key] = mod.Source(self)
        return src

    def all_sources(self):
        return list(self._sources.values())

    def _use_hdri(self, path, e, src=None):
        studio = next((w for w in QApplication.allWidgets()
                       if type(w).__name__ == "StudioPanel" and hasattr(w, "set_hdri_path")), None)
        if studio is None:
            QApplication.clipboard().setText(str(path))
            self._say(tr("Downloaded «{name}» to {path} (path copied). The Render Studio "
                         "extension can use it as the 360° background.", name=e["name"], path=path))
            return
        studio.set_hdri_path(str(path))
        dock = studio
        while dock is not None and not hasattr(dock, "setFloating"):
            dock = dock.parentWidget()
        if dock is not None:
            dock.show()
            dock.raise_()
        self._say(tr("«{name}» is now Render Studio's 360° background.", name=e["name"]))

    def _paint_with(self, path, e, src=None):
        sw, sh = (src or self._source()).tile_size_m(e)
        name = e["name"]
        win = self._app.window
        mats = self._materials_tray()
        if mats is not None and hasattr(mats, "_apply_texture"):
            mats._apply_texture(str(path), sw=sw, sh=sh, name=name)
        else:
            from core.materials import Material
            from tools.paint import PaintTool
            PaintTool.current_is_default = False
            PaintTool.current_texture = {"path": str(path), "sw": sw, "sh": sh, "rot": 0.0}
            PaintTool.current_opacity = None
            PaintTool.current_material = Material(name, texture=dict(PaintTool.current_texture))
            act = getattr(win, "_activate_tool", None)
            if callable(act):
                act("paint")
        maps = len([k for k in (online.read_manifest(Path(path)) or {}) if k in online.MAP_KEYS]) - 1
        extra = tr(", with {n} more maps for the render", n=maps) if maps > 0 else ""
        self._say(tr("Paint bucket loaded with «{name}» ({w:g} × {h:g} m{extra}): click the "
                     "faces to paint.", name=name, w=sw, h=sh, extra=extra))

    def _place_model(self, path, e, src=None):
        g = self._build_from(path)
        self._place(g, ORIGIN)
