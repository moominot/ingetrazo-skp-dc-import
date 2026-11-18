# SPDX-License-Identifier: GPL-3.0-or-later
"""The «Component Options» panel: the selected dynamic component's options,
as SketchUp's dialog shows them, and Apply to redraw it (one undo step)."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from .dc import apply as A
from .dc import formula as F
from .dc import options as O
from .dc.evaluate import _num
from .dc.redraw import LEN, _LiveEvaluator, live_value

_log = logging.getLogger(__name__)


def selected_root(scene):
    """The one selected top-level dynamic component, else None."""
    found = None
    for e in getattr(scene, "selection", ()) or ():
        g = getattr(e, "owner", None) or e
        if g in getattr(scene, "groups", ()) and A.is_dynamic_root(g):
            if found is not None and found is not g:
                return None
            found = g
    return found


def redraw_in_document(viewport, group, options: dict):
    """Redraw ``group`` with ``options`` as ONE undo step; the new tree takes
    its place in the document and in the selection. Returns the new group."""
    from core.history import SnapshotImport
    box = {}

    def mutate(scene):
        new, ev = A.redraw_group(group, options, scene)
        i = scene.groups.index(group)
        scene.groups[i] = new
        scene.selection.discard(group)
        scene.selection.add(new)
        box["new"], box["errors"] = new, list(ev.errors)

    viewport.history.execute(SnapshotImport(mutate))
    error = getattr(viewport.history, "last_error", None)
    if error and "new" not in box:
        raise RuntimeError(error)
    notify = getattr(viewport, "notify_scene_changed", None)
    if callable(notify):
        notify()
    viewport.update()
    return box.get("new"), box.get("errors", [])


class OptionsPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.group = None
        self.rows = []                      # (Option, widget, initial)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.title = QLabel("Select a dynamic component imported from SketchUp.")
        self.title.setWordWrap(True)
        outer.addWidget(self.title)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.scroll.setWidget(self.form_host)
        outer.addWidget(self.scroll, 1)
        buttons = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setToolTip("Redraw the component with these options (one undo step)")
        self.apply_btn.clicked.connect(self.apply)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setToolTip("Put back the values the component has now")
        self.revert_btn.clicked.connect(lambda: self.show_group(self.group, force=True))
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.revert_btn)
        outer.addLayout(buttons)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self._set_enabled(False)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    # -- following the selection ------------------------------------------------
    def _poll(self):
        if not self.isVisible():
            return
        try:
            g = selected_root(self.app.viewport.scene)
        except Exception:  # noqa: BLE001 - a tab switching underneath
            return
        if g is not self.group:
            self.show_group(g)

    def _set_enabled(self, on: bool):
        self.apply_btn.setEnabled(on)
        self.revert_btn.setEnabled(on)

    def _clear(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.rows = []

    def show_group(self, group, force=False):
        if group is self.group and not force:
            return
        self.group = group
        self._clear()
        self.status.setText("")
        if group is None:
            self.title.setText("Select a dynamic component imported from SketchUp.")
            self._set_enabled(False)
            return
        root = A.part_tree(group)
        ev = _LiveEvaluator(root)
        opts = O.options_of(root.attrs)
        self.title.setText(f"<b>{root.name}</b> — {len(opts)} options")
        for opt in opts:
            if opt.name in LEN:
                opt.value = live_value(root, opt.name)
            elif opt.access == "VIEW" or root.formula(opt.name):
                try:
                    opt.value = ev.value(root, opt.name)
                except Exception:  # noqa: BLE001 - show what is stored
                    pass
            if opt.access == "LIST" and opt.choices:
                w = QComboBox()
                for label, raw in opt.choices:
                    w.addItem(label, raw)
                idx = O.current_choice(opt)
                if idx < 0:
                    w.addItem(O.display(opt), None)
                    idx = w.count() - 1
                w.setCurrentIndex(idx)
                initial = idx
            elif opt.access == "VIEW":
                w = QLabel(O.display(opt))
                w.setTextInteractionFlags(Qt.TextSelectableByMouse)
                initial = None
            else:
                w = QLineEdit(O.display(opt))
                w.returnPressed.connect(self.apply)
                initial = w.text()
            label = QLabel(opt.label)
            label.setWordWrap(True)
            self.form.addRow(label, w)
            self.rows.append((opt, w, initial))
        self._set_enabled(True)

    # -- applying -------------------------------------------------------------------
    def _collect(self):
        options, errors = {}, []
        root = None
        for opt, w, initial in self.rows:
            if opt.access == "VIEW":
                continue
            if isinstance(w, QComboBox):
                if w.currentIndex() == initial:
                    continue
                raw = w.currentData()
                if raw is None:
                    continue
                if str(raw).startswith("="):
                    # A choice whose value is a formula (SketchUp: «=e3_angle»).
                    root = root or A.part_tree(self.group)
                    ev = _LiveEvaluator(root)
                    try:
                        v = F.evaluate(F.parse(str(raw)[1:]), ev._lookup(root))
                        raw = ev.from_formula(root, opt.name, v)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{opt.label}: {exc}")
                        continue
                n = _num(raw)
                options[opt.name] = n if isinstance(n, float) else raw
            else:
                if w.text() == initial:
                    continue
                try:
                    options[opt.name] = O.parse(opt, w.text())
                except ValueError:
                    errors.append(f"{opt.label}: «{w.text()}» is not a number")
        return options, errors

    def apply(self):
        if self.group is None:
            return
        options, errors = self._collect()
        if errors:
            self.status.setText("<br>".join(errors))
            return
        try:
            new, problems = redraw_in_document(self.app.viewport, self.group, options)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("redraw failed")
            self.status.setText(f"Could not redraw: {exc}")
            return
        self.show_group(new, force=True)
        if problems:
            self.status.setText(f"Redrawn. {len(problems)} formula(s) could not be "
                                "evaluated and kept their value, as in SketchUp.")
        else:
            self.status.setText("Redrawn." if options else "Redrawn (no option changed).")
