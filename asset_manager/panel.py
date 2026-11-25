# SPDX-License-Identifier: GPL-3.0-or-later
"""The Library tray tab: three tabs (models, materials, backgrounds), each
looking in the drawing, the user's catalog folders or the free online sites
(``kind_page``); what is done with an item is here."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QMimeData, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDrag, QIcon, QPixmap, QVector3D
from PySide6.QtWidgets import (QApplication, QLabel, QListWidget, QMessageBox, QTabWidget,
                               QVBoxLayout, QWidget)

from . import wheel_guard
from . import catalog, export, inventory, kind_page, online, place, previews, stand_in, tags, thumbs
from .i18n import tr, translate_on_show

_log = logging.getLogger(__name__)
ICON = 80
PH_ICON = 96
DONE_ROLE = Qt.UserRole + 1
ORIGIN = QVector3D(0.0, 0.0, 0.0)
kind_page.ORIGIN = ORIGIN
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
        self._proxy_wanted = False          # «Insert as proxy» is under way
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

        self.pages = {}
        for kind, title in kind_page.TABS.items():
            page = self.pages[kind] = kind_page.KindPage(self, kind, DragList)
            self.tabs.addTab(page, title)
        self.tabs.currentChanged.connect(self._tab_shown)

        on_changed = getattr(app, "on_document_changed", None)
        if on_changed is not None:
            on_changed(self._document_changed)
        translate_on_show(self)
        QTimer.singleShot(2000, self._init_watch)
        wheel_guard.watch(self)          # (the wheel scrolls; it changes only a picked field)

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
        itself, or its proxy under «Insert as proxy». ``interactive``: a model
        with dynamic components asks first."""
        if not self._proxy_wanted:
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
        if self.isVisible() and self.current_page().is_drawing:
            QTimer.singleShot(0, self.refresh)

    def showEvent(self, ev):  # noqa: N802
        super().showEvent(ev)
        self._tab_shown(self.tabs.currentIndex())

    def current_page(self):
        return self.tabs.currentWidget()

    def _tab_shown(self, _index):
        if self.isVisible():
            self.current_page().shown()

    def show_online(self):
        """The tab in view looks at its first free online site."""
        page = self.current_page()
        for i in range(page.source.count()):
            if str(page.source.itemData(i) or "").startswith("online:"):
                page.source.setCurrentIndex(i)
                return

    # =========================================================================
    # In the drawing
    # =========================================================================
    def _icon_for(self, e):
        s = e.sample
        key = (e.key, id(getattr(s, "mesh", None)), len(getattr(s, "children", None) or ()))
        icon = self._thumb_cache.get(key)
        if icon is None:
            icon = self._thumb_cache[key] = QIcon(thumbs.render(s, ICON))
        return icon

    def refresh(self):
        """The drawing changed: the tabs that show it read it again."""
        self._dirty = False
        for page in self.pages.values():
            if page.is_drawing:
                page.fill()

    def set_stand_in(self, groups, on):
        """Mark ``groups`` as stand-ins (or not): one undo step."""
        n = stand_in.set_stand_in(self._vp, groups, on)
        self._say(tr("{n} marked as stand-in (not rendered, translucent).", n=n) if on and n
                  else tr("{n} back to normal: they render.", n=n) if n else "")

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

    def replace_all(self, e):
        """Replace Component for every placement of the chosen component: the
        window's own command, after the user picks the new one. Stand-ins are
        cleared first (so the swapped-in component does not keep their
        translucent paint) and put back when nothing was replaced."""
        from PySide6.QtWidgets import QInputDialog
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

    def edit_component(self, e):
        """Edit the chosen component (the double-click's road): what is drawn
        inside reaches every placement."""
        begin = getattr(self._vp, "begin_group_edit", None)
        if not callable(begin):
            self._say(tr("This IngeTrazo cannot edit a group from here."))
            return
        try:
            begin(e.sample)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not edit the component")
            self._say(tr("Could not edit it: {error}", error=exc))

    # =========================================================================
    # My catalog
    # =========================================================================
    def _fill_pages(self):
        for page in self.pages.values():
            if not page.is_online and not page.is_drawing:
                page.fill()

    def refresh_catalog(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._cat_items = catalog.scan()
        finally:
            QApplication.restoreOverrideCursor()
        self._known = {i.key for i in self._cat_items}
        self._new_paths &= self._known      # what arrived before the first look stays marked
        for page in self.pages.values():
            page.fill_sources()
        self._fill_pages()
        self.start_watching()

    def _init_watch(self):
        """At start: know what the watched folders hold, and watch them
        (without reading every catalog folder, which may be on a network)."""
        if self._watcher is not None:
            return
        for root in catalog.watched():
            self._known |= {i.key for i in catalog.scan(root)}
        self.start_watching()

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
        self.current_page().set_source("cat:" + str(path))
        live = catalog.is_watched(path)
        self._say(tr("Added {path}", path=path) + (" " + tr("(watched in real time).") if live else
                                                   " " + tr("(press Update to read it again).")))

    def remove_folder(self, folder):
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
        self._fill_pages()

    def _build_from(self, path, proxy=False):
        from . import progress
        with progress.window(self.window(), tr("Importing {name}…", name=Path(path).name)):
            self._proxy_wanted = proxy
            try:
                return self._model_group(path)
            finally:
                self._proxy_wanted = False

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

    def save_all_materials(self):
        self._save_scene_materials(list(getattr(self._app.scene, "materials", {}).values()))

    def save_component(self, entry, own_tags=()):
        """A component of the drawing into the catalog, as an .igz with its picture."""
        name = online.safe_name(entry.name)
        path = catalog.default_folder() / catalog.SAVE_DIRS["models"] / name / (name + ".igz")
        if path.is_file():
            self._say(tr("«{name}» is already in the catalog.", name=entry.name))
            return
        try:
            export.write_component(path, entry.sample, self._app.scene.materials)
            thumbs.render(entry.sample, 192).save(str(path.with_suffix(".png")))
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("could not save %s", entry.name)
            self._say(tr("Could not save «{name}»: {error}", name=entry.name, error=exc))
            return
        self._keep_tags(path, own_tags)
        self._after_catalog_save()
        self._say(tr("«{name}» saved to the catalog.", name=entry.name))

    def _keep_tags(self, path, values):
        """The categories of what was just saved at ``path`` go with it."""
        if not values:
            return
        tags.update({i.key: values for i in catalog.scan(catalog.default_folder()) if i.path == Path(path)})

    def _save_scene_materials(self, mats):
        new = have = 0
        errors = []
        for m in mats:
            try:
                path, fresh = catalog.save_scene_material(m, previews.png_bytes)
                if fresh:
                    self._keep_tags(path, tags.get(f"drawing:material:{m.name}"))
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
            self._keep_tags(_saved, e.get("categories") or [])
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
    def source_for(self, key):
        src = self._sources.get(key)
        if src is None:
            mod = next(m for m in kind_page.SOURCES if m.KEY == key)
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

    def _place_model(self, path, e, src=None, proxy=False):
        g = self._build_from(path, proxy=proxy)
        self._place(g, ORIGIN)
