# SPDX-License-Identifier: GPL-3.0-or-later
"""Putting things in the drawing: a component built from a file (.igz,
.skp, .gltf) or a copy of one already there, handed to IngeTrazo's own
placement tool — it follows the cursor and a click drops it, one undo step
— or dragged from the panel and dropped on the view."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QTimer
from PySide6.QtGui import QVector3D

from .i18n import tr

_log = logging.getLogger(__name__)

MIME = "application/x-ingetrazo-asset-manager"
SKP_EXT = "ingetrazo_plugin_skp_dc_import"


# --- building -----------------------------------------------------------------
def clean_layers(groups) -> int:
    """Drop every layer label that is not a name (a reader that gives a
    layer as a number broke IngeTrazo's layers panel while it painted, and
    Qt aborted). Returns how many were dropped."""
    from core.group import iter_placements
    dropped = 0
    for top in groups or ():
        for g, _m in iter_placements(top):
            if not isinstance(getattr(g, "layer", None) or "", str):
                g.layer = None
                dropped += 1
            for f in g.mesh.faces:
                if not isinstance(f.attrs.get("layer", ""), str):
                    del f.attrs["layer"]
                    dropped += 1
            for e in g.mesh.edges:
                if not isinstance(getattr(e, "layer", None) or "", str):
                    e.layer = None
                    dropped += 1
    return dropped


def _from_scene(dst, temp, name):
    """``temp``'s contents ready to place in ``dst``: its one top-level
    group as it is (a dynamic component stays the root that the options
    panel recognises), or everything wrapped in one component."""
    from core.insert import ensure_layers, import_document_as_component, merge_materials
    groups = list(getattr(temp, "groups", ()) or ())
    if clean_layers(groups):
        _log.warning("%s: layer labels that were not names were dropped", name)
    temp.layers[:] = [ly for ly in temp.layers if isinstance(getattr(ly, "name", None), str)]
    if len(groups) == 1 and getattr(groups[0], "xform", None) is not None:
        g = groups[0]
        merge_materials(getattr(temp, "materials", {}) or {}, dst.materials, g)
        ensure_layers(dst, g)
        return g
    return import_document_as_component(dst, temp, name)


def group_from_file(viewport, path):
    """A new component (not yet in the drawing) read from ``path``; its
    anchor is the file's origin. None when the file has no geometry."""
    path = Path(path)
    temp = read_file(viewport, path)
    return _from_scene(viewport.scene, temp, path.stem)


def proxy_from_file(viewport, path, confirm=None):
    """``(group, kind, dynamic)`` for the model in ``path`` inserted as a
    proxy: a new component holding a light envelope, the full model written to an
    .igz of its own (see :mod:`.proxy`). ``dynamic`` = the model holds
    dynamic components, which cannot be changed while it is a proxy.

    ``kind``: ``"proxy"``; ``"copy"`` when that model is already in the
    drawing as a proxy (placed again as a copy of it: one definition,
    nothing read); ``"normal"`` when ``confirm`` chose the full model.
    ``confirm(name)`` is asked only for a model with dynamic components and
    answers ``"proxy"``, ``"normal"`` or None (cancel: group None); without
    it such a model goes in as a proxy. group None also = no geometry."""
    from . import proxy
    path = Path(path)
    same = proxy.find_in(viewport.scene, proxy.proxy_id(path))
    if same is not None:
        return copy_of(same), "copy", bool(proxy.info_of(same).get("dynamic"))
    temp = read_file(viewport, path)
    groups = list(getattr(temp, "groups", ()) or ())
    if clean_layers(groups):
        _log.warning("%s: layer labels that were not names were dropped", path.name)
    if len(groups) == 1 and getattr(groups[0], "xform", None) is not None:
        g = groups[0]
    else:
        from core.insert import component_from_scene
        g = component_from_scene(temp, path.stem)
    if g is None:
        return None, "proxy", False
    dynamic = proxy.has_dynamic(g)
    if dynamic and confirm is not None:
        answer = confirm(g.name or path.stem)
        if answer is None:
            return None, "proxy", True
        if answer == "normal":
            from core.insert import ensure_layers, merge_materials
            merge_materials(getattr(temp, "materials", {}) or {}, viewport.scene.materials, g)
            ensure_layers(viewport.scene, g)
            return g, "normal", True
    # The file's materials stay with the original: the drawing gets none
    # until the original is shown.
    return proxy.make(viewport, g, getattr(temp, "materials", {}) or {}, path), "proxy", dynamic


def read_file(viewport, path):
    """The model in ``path`` as a scene of its own (not the drawing's)."""
    from core.scene import Scene
    path = Path(path)
    suffix = path.suffix.lower()
    temp = Scene()
    if suffix == ".igz":
        from formats import igz
        igz.load_into(temp, path)
    elif suffix == ".skp":
        ext = sys.modules.get(SKP_EXT)
        if ext is None:
            raise RuntimeError(tr("Inserting a .skp keeping its components needs the "
                                  "«.skp files» extension (skp_dc_import)."))
        import importlib
        reader = importlib.import_module(SKP_EXT + ".reader")
        builder = importlib.import_module(SKP_EXT + ".builder")
        builder.build(temp, reader.parse(path), path)
    elif suffix in (".gltf", ".glb"):
        from formats import glb
        glb.load_glb(temp, path)
    else:
        raise ValueError(tr("{name}: not a model this panel can insert", name=path.name))
    end = getattr(viewport, "end_group_edit", None)
    if callable(end):
        end()
    return temp


def copy_of(group):
    """A new placement of the same component as ``group`` (sharing its
    definition, as Copy and Paste do)."""
    from core.group import copy_group
    return copy_group(group)


def origin_of(group):
    """The point the cursor holds: the component's own axes."""
    from PySide6.QtGui import QVector3D
    m = getattr(group, "xform", None)
    return m.map(QVector3D(0, 0, 0)) if m is not None else None


# --- placing ---------------------------------------------------------------------
def start_place(window, group, anchor=None):
    """Hand ``group`` to the placement tool: it follows the cursor and a
    click drops it (Esc cancels)."""
    fn = getattr(window, "_start_place", None)
    if callable(fn):
        fn(group, anchor=anchor)
        return
    from tools.place_group import PlaceGroupTool
    vp = window.viewport
    vp.set_active_tool(PlaceGroupTool(group, anchor=anchor))
    vp.update()


def skp_from_urls(mime):
    """The one local .skp a drag from the file explorer carries, when the
    .skp extension (skp_dc_import) is there to read it; else None."""
    if SKP_EXT not in sys.modules or not mime.hasUrls():
        return None
    urls = mime.urls()
    if len(urls) != 1 or not urls[0].isLocalFile():
        return None
    path = Path(urls[0].toLocalFile())
    return path if path.suffix.lower() == ".skp" and path.is_file() else None


class DropOnView(QObject):
    """Event filter for the 3-D views: a model dragged from the panel
    follows the cursor as the placement tool's preview while it is over the
    view, and dropping it places it there, snapped like a click."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.provider = None          # callable -> (group, anchor), set by the panel
        self._group = None
        self._anchor = None
        self._tool = None
        self._vp = None
        self._explorer = False        # this drag came from the file explorer
        self.on_error = None

    def watch(self, viewport):
        if viewport is not None and not viewport.property("asset_manager_drop"):
            viewport.setProperty("asset_manager_drop", True)
            viewport.setAcceptDrops(True)
            viewport.installEventFilter(self)

    def watch_all(self):
        vps = getattr(self.window, "all_viewports", None)
        for vp in (vps() if callable(vps) else [getattr(self.window, "viewport", None)]):
            self.watch(vp)

    def begin(self, provider):
        self.provider = provider
        self._group = self._anchor = None

    def end(self):
        self.provider = None
        self._group = self._anchor = None

    # -- the filter ------------------------------------------------------------------
    def eventFilter(self, obj, ev):  # noqa: N802 - Qt override
        t = ev.type()
        if t not in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop, QEvent.DragLeave):
            return False
        if t == QEvent.DragLeave:
            if self._tool is not None:
                self._cancel()
            if self._explorer:
                self._explorer = False
                self.end()
            return False
        mime = ev.mimeData()
        if mime is None:
            return False
        if t == QEvent.DragEnter and not mime.hasFormat(MIME) and self.provider is None:
            path = skp_from_urls(mime)
            if path is not None:
                # A .skp dragged from the file explorer: our importer, which
                # keeps the components and their dynamic data, instead of
                # the window's, which flattens them.
                self._explorer = True
                self.begin(lambda vp=obj, p=path: (group_from_file(vp, p),
                                                   QVector3D(0.0, 0.0, 0.0)))
        if not (mime.hasFormat(MIME) or self._explorer) or self.provider is None:
            return False
        try:
            return self._handle(t, obj, ev)
        finally:
            if self._explorer and t == QEvent.Drop:
                self._explorer = False
                self.end()

    def _handle(self, t, obj, ev):
        try:
            if t == QEvent.DragEnter:
                self._enter(obj)
            elif t == QEvent.DragMove:
                self._hover(obj, ev)
            else:
                self._drop(obj, ev)
        except Exception as exc:  # noqa: BLE001 - never break the view for a drop
            _log.exception("drop failed")
            self._cancel()
            if self._explorer:               # the enter was refused: no leave follows
                self._explorer = False
                self.end()
            if self.on_error:
                self.on_error(str(exc))
            ev.ignore()
            return True
        ev.setDropAction(Qt.CopyAction)
        ev.accept()
        return True

    def _enter(self, vp):
        from PySide6.QtWidgets import QApplication
        from tools.place_group import PlaceGroupTool
        if self._group is None:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self._group, self._anchor = self.provider()
            finally:
                QApplication.restoreOverrideCursor()
        if self._group is None:
            raise RuntimeError("the model has no geometry")
        self._vp = vp
        self._tool = PlaceGroupTool(self._group, anchor=self._anchor)
        vp.set_active_tool(self._tool)

    def _ctx(self, vp, ev):
        from tools.base import ToolContext
        pos = ev.position() if hasattr(ev, "position") else QPointF(ev.pos())
        mods = ev.modifiers() if hasattr(ev, "modifiers") else Qt.NoModifier
        snap = vp._snap_at(pos.x(), pos.y(), mods)
        if snap is None:
            return None
        return ToolContext(viewport=vp, world=snap.point, screen=pos, modifiers=mods, snap=snap)

    def _hover(self, vp, ev):
        if self._tool is None:
            self._enter(vp)
        ctx = self._ctx(vp, ev)
        if ctx is not None:
            self._tool.on_hover(ctx)

    def _drop(self, vp, ev):
        if self._tool is None:
            self._enter(vp)
        ctx = self._ctx(vp, ev)
        if ctx is None:
            self._cancel()
            return
        tool, self._tool = self._tool, None
        tool.on_hover(ctx)
        self._group = self._anchor = None  # placed: the next drag builds anew
        world = QVector3D(ctx.world)
        # Placed once the drop event is over, from the event loop: changing
        # the document inside the drag-and-drop dispatch aborted Qt a moment
        # later («Cannot destroy paint device that is being painted»).
        QTimer.singleShot(0, lambda: tool.place_at(vp, world))   # one undo step

    def _cancel(self):
        tool, vp = self._tool, self._vp
        self._tool = None
        if tool is not None and vp is not None:
            act = getattr(self.window, "_activate_tool", None)
            if callable(act):
                act("select")
            else:
                tool.on_cancel(vp)
            vp.update()
