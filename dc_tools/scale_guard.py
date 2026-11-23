# SPDX-License-Identifier: GPL-3.0-or-later
"""Scaling a dynamic component the way the .skp dynamic components do:

* the ``ScaleTool`` attribute hides the scale handles it names (the same
  bit mask the format keeps as the definition's «no scale» mask):
  1 X, 2 Y, 4 Z, 8 XZ (red/blue plane), 16 YZ (green/blue), 32 XY (red/green),
  64 uniform (the corners) — the order of SketchUp's Component Attributes
  dialog (a mur_gelosia stores 119: only the red/blue plane is left);
* once a dynamic component has been scaled — with the handles, a typed
  value or anything else — it is redrawn at its new size (copies, parts
  that keep their size, formulas) instead of being stretched, in the same
  undo step as the scale.
"""
from __future__ import annotations

import logging

from .dc.apply import KEY, is_dynamic_root

_log = logging.getLogger(__name__)

AXIS_BITS = {(0,): 1, (1,): 2, (2,): 4, (0, 2): 8, (1, 2): 16, (0, 1): 32, (0, 1, 2): 64}
_EPS = 1e-6


def scale_mask(group) -> int:
    """The component's ScaleTool value as an int (0: every handle)."""
    data = (getattr(group, "ext", None) or {}).get(KEY) or {}
    for src in ("instance_attributes", "definition_attributes"):
        v = (data.get(src) or {}).get("scaletool")
        if v not in (None, ""):
            try:
                return int(float(str(v).strip().lstrip("=")))
            except ValueError:
                return 0
    return 0


def handle_allowed(mask: int, axes: tuple) -> bool:
    """Whether the handle that scales ``axes`` (component axes 0, 1, 2) is
    available under ``mask``."""
    bit = AXIS_BITS.get(tuple(sorted(axes)))
    return not (bit and mask & bit)


def _scale_of(group) -> tuple:
    m = getattr(group, "xform", None)
    if m is None:
        return (1.0, 1.0, 1.0)
    cols = [m.column(i) for i in range(3)]
    return tuple(round((c.x() ** 2 + c.y() ** 2 + c.z() ** 2) ** 0.5, 6) for c in cols)


# --- the Scale tool's handles ----------------------------------------------------
def patch_scale_tool() -> bool:
    """Wrap IngeTrazo's Scale tool so a selected dynamic component only
    offers the handles its ScaleTool allows. Returns False when the tool
    is not the one this was written for (then nothing is changed)."""
    try:
        from core.group import Group
        from tools import scale as scale_mod
    except Exception:  # noqa: BLE001
        return False
    tool = getattr(scale_mod, "ScaleTool", None)
    original = getattr(tool, "_refresh_box", None)
    if tool is None or original is None:
        return False
    if getattr(original, "_dc_scaletool", False):
        return True

    def _refresh_box(self, viewport):
        original(self, viewport)
        try:
            sel = list(viewport.scene.selection)
            if len(sel) != 1 or not isinstance(sel[0], Group) or not self._grips:
                return
            # One group selected: the box stands in its own axes, so a grip's
            # axes are the component's (0 red, 1 green, 2 blue).
            mask = scale_mask(sel[0])
            if mask:
                self._grips = [g for g in self._grips if handle_allowed(mask, g.mask)]
        except Exception:  # noqa: BLE001 - never break the Scale tool
            _log.exception("ScaleTool mask")

    _refresh_box._dc_scaletool = True
    tool._refresh_box = _refresh_box
    return True


# --- redraw after a scale -------------------------------------------------------------
class _Merged:
    """Several commands as one undo step (the scale and its redraw)."""

    def __init__(self, cmds):
        self.cmds = list(cmds)
        self._history_mesh = getattr(self.cmds[0], "_history_mesh", None)

    def do(self, scene):
        for c in self.cmds:
            c.do(scene)

    def undo(self, scene):
        for c in reversed(self.cmds):
            c.undo(scene)

    def __getattr__(self, name):              # anything else the history asks for
        return getattr(self.cmds[-1], name)


class RedrawOnScale:
    """Watches the dynamic components where the user is editing; one whose
    scale changed is redrawn at its new size."""

    def __init__(self, app):
        self.app = app
        self.seen: dict = {}                  # id -> (group, scale it had)
        self._busy = False

    def changed(self, *_a):
        from PySide6.QtCore import QTimer
        if not self._busy:
            QTimer.singleShot(0, self.check)

    def _members(self, scene):
        ctx = getattr(scene, "edit_group", None)
        if ctx is not None and is_dynamic_root(ctx):
            return []                          # inside a dynamic component: left alone
        return list(ctx.children if ctx is not None else scene.groups)

    def check(self):
        if self._busy:
            return
        try:
            vp = self.app.viewport
            scene = vp.scene
        except Exception:  # noqa: BLE001
            return
        todo = []
        for g in self._members(scene):
            if not is_dynamic_root(g) or getattr(g, "xform", None) is None:
                continue
            now = _scale_of(g)
            known = self.seen.get(id(g))
            if known is None or known[0] is not g:
                self.seen[id(g)] = (g, now)
                continue
            if any(abs(a - b) > _EPS for a, b in zip(now, known[1])) and g.children:
                todo.append(g)
        if not todo:
            return
        self._busy = True
        try:
            self._redraw(vp, todo)
        finally:
            self._busy = False

    def _redraw(self, vp, groups):
        from .ui import redraw_in_document
        hist = vp.history
        start = len(hist.undo_stack) - 1          # the command that scaled
        for g in groups:
            try:
                new, problems = redraw_in_document(vp, g, {})
            except Exception:  # noqa: BLE001 - leave it scaled, say it in the log
                _log.exception("redraw after scaling failed")
                continue
            self.seen[id(new)] = (new, _scale_of(new))
            if problems:
                _log.info("%s: %d formula(s) kept their value", g.name, len(problems))
        cmds = hist.undo_stack[start:]
        if start >= 0 and len(cmds) > 1:
            del hist.undo_stack[start:]
            hist.undo_stack.append(_Merged(cmds))


def install(app):
    patched = patch_scale_tool()
    watcher = RedrawOnScale(app)
    if hasattr(app, "on_document_changed"):
        app.on_document_changed(watcher.changed)
    return patched, watcher
