# SPDX-License-Identifier: GPL-3.0-or-later
"""The «Component Options» panel: the selected dynamic component's options,
as SketchUp's dialog shows them, and Apply to redraw it (one undo step)."""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QToolButton, QVBoxLayout,
                               QWidget)

from .dc import apply as A
from .i18n import tr, translate_on_show
from .dc import formula as F
from .dc import options as O
from .dc.evaluate import _num
from .dc.redraw import LEN, _LiveEvaluator, live_value

_log = logging.getLogger(__name__)

# What SketchUp's Component Options puts in its header and window, not in the
# form: the picture, the name, the summary and the description.
HEADER_ONLY = ("name", "summary", "description", "imageurl", "dialogwidth", "dialogheight")


def context_members(scene):
    """The groups the user can pick where they are editing: the top-level
    ones, or the parts of the open group (SketchUp's active context). A
    component inside a group is only selectable with that group open."""
    ctx = getattr(scene, "edit_group", None)
    if ctx is None:
        return getattr(scene, "groups", None) or []
    return getattr(ctx, "children", None) or []


def selected_root(scene):
    """The one selected dynamic component of the current context, else None."""
    members = context_members(scene)
    found = None
    for e in getattr(scene, "selection", ()) or ():
        g = getattr(e, "owner", None) or e
        if any(g is m for m in members) and A.is_dynamic_root(g):
            if found is not None and found is not g:
                return None
            found = g
    return found


def _swap_command(old, make_new):
    """One undo step that puts ``make_new(scene)`` where ``old`` is — the
    top-level list or the ``children`` of the group that holds it, at any
    depth — keeping its place and the selection; undo puts ``old`` back.
    (SnapshotImport only tracks ``scene.groups``: a part swapped inside an
    open group was out of its reach, and ``scene.groups.index`` failed.)"""
    from core.history import Command, group_owner_list

    class SwapGroupCommand(Command):
        def __init__(self):
            self.new = None
            self.owner = None

        def _swap(self, scene, out, into):
            i = next(k for k, g in enumerate(self.owner) if g is out)
            self.owner[i] = into
            scene.selection.discard(out)
            scene.selection.add(into)
            scene.version += 1

        def do(self, scene):
            if self.new is None:
                owner = group_owner_list(scene, old)
                if owner is None:
                    raise ValueError("the component is not in the document any more")
                self.owner = owner
                self.new = make_new(scene)
            self._swap(scene, old, self.new)

        def undo(self, scene):
            self._swap(scene, self.new, old)

    return SwapGroupCommand()


def swap_in_document(viewport, group, make_new):
    """Swap ``group`` for ``make_new(scene)`` as ONE undo step, wherever it
    is (top level or inside a group, open or not). Returns the command
    (``.new`` is the new group)."""
    cmd = _swap_command(group, make_new)
    viewport.history.execute(cmd)
    if cmd.new is None or not any(g is cmd.new for g in (cmd.owner or ())):
        raise RuntimeError(getattr(viewport.history, "last_error", None)
                           or "the component could not be replaced")
    notify = getattr(viewport, "notify_scene_changed", None)
    if callable(notify):
        notify()
    viewport.update()
    return cmd


def replace_in_document(viewport, group, make_new):
    """Swap ``group`` for ``make_new(scene)`` (a new group) as ONE undo
    step, keeping its place in the document and in the selection."""
    return swap_in_document(viewport, group, make_new).new


def redraw_in_document(viewport, group, options: dict, edits: dict | None = None):
    """Redraw ``group`` with ``options`` (and authoring ``edits``) as ONE
    undo step; the new tree takes its place in the document and in the
    selection. Returns (the new group, formula problems)."""
    errors = []

    def make_new(scene):
        new, ev = A.redraw_group(group, options, scene, edits)
        errors[:] = list(ev.errors)
        return new

    return swap_in_document(viewport, group, make_new).new, errors


class OptionsPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.group = None
        self.rows = []                      # (Option, widget, initial)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.title = QLabel(tr("Select a dynamic component."))
        self.title.setWordWrap(True)
        outer.addWidget(self.title)
        # SketchUp's header: picture, big name, bold summary, description.
        self.header = QWidget()
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(0, 0, 0, 4)
        self.thumb = QLabel()
        self.thumb.setFixedSize(96, 72)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("border: 1px solid palette(mid);")
        hl.addWidget(self.thumb)
        texts = QVBoxLayout()
        self.h_name = QLabel()
        self.h_name.setStyleSheet("font-size: 15pt; font-weight: bold;")
        self.h_summary = QLabel()
        self.h_summary.setStyleSheet("font-weight: bold;")
        self.h_description = QLabel()
        for w in (self.h_name, self.h_summary, self.h_description):
            w.setWordWrap(True)
            texts.addWidget(w)
        texts.addStretch(1)
        hl.addLayout(texts, 1)
        self.header.hide()
        outer.addWidget(self.header)
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
        self.help_btn = QToolButton()
        self.help_btn.setText("?")
        self.help_btn.setToolTip("How Component Options works, and what each control does")
        self.help_btn.clicked.connect(self.show_help)
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.revert_btn)
        buttons.addWidget(self.help_btn)
        outer.addLayout(buttons)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self._set_enabled(False)
        translate_on_show(self)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def show_help(self):
        """The «?» button: the shared help window, at this panel's section."""
        from . import ui_help
        ui_help.show(self.window(), "options")

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
        # Taken out of the form now, deleted once control is back in the
        # event loop: the row being cleared may be the very field whose
        # Enter key is still being handled (removeRow deleted it under
        # Qt's feet — an access violation, or a hang).
        while self.form.rowCount():
            taken = self.form.takeRow(0)
            for item in (taken.labelItem, taken.fieldItem):
                w = item.widget() if item is not None else None
                if w is not None:
                    w.hide()            # still owned by the form host until then
                    w.deleteLater()
        self.rows = []

    def show_group(self, group, force=False):
        if group is self.group and not force:
            return
        self.group = group
        self._clear()
        self.status.setText("")
        if group is None:
            self.title.setText(tr("Select a dynamic component."))
            self.title.show()
            self.header.hide()
            self._set_enabled(False)
            return
        root, _frame = A.part_in_context(self.app.viewport.scene, group)
        ev = _LiveEvaluator(root)
        opts = [o for o in O.options_of(root.attrs) if o.name not in HEADER_ONLY]
        self.title.setText(tr("<b>{name}</b> — {n} options", name=root.name, n=len(opts)))
        self._fill_header(root, ev)
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
                # After the key press is done with this field: applying
                # rebuilds the form, this field included.
                w.returnPressed.connect(lambda: QTimer.singleShot(0, self.apply))
                initial = w.text()
            label = QLabel(opt.label)
            label.setWordWrap(True)
            self.form.addRow(label, w)
            self.rows.append((opt, w, initial))
        self._set_enabled(True)

    def _fill_header(self, root, ev):
        """Name, summary, description and picture the component has, unless
        the author set one to «Users cannot see this attribute»."""
        def text(name):
            # Hidden only when the author said so (NONE); a value nobody
            # marked is shown, as SketchUp's header shows it.
            access = str(root.attrs.get(f"_{name}_access") or "").upper()
            if access == "NONE":
                return ""
            try:
                v = ev.value(root, name) if root.formula(name) else root.attrs.get(name)
            except Exception:  # noqa: BLE001
                v = root.attrs.get(name)
            return "" if v is None else str(v).strip()
        name, summary, desc = text("name"), text("summary"), text("description")
        pix = QPixmap()
        image = text("imageurl")
        if image and not image.lower().startswith(("http:", "https:")):
            path = image[7:] if image.lower().startswith("file:") else image
            if os.path.isfile(path):
                pix = QPixmap(path)
        for label, value in ((self.h_name, name), (self.h_summary, summary),
                             (self.h_description, desc)):
            label.setText(value)
            label.setVisible(bool(value))
        if not pix.isNull():
            self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation))
        self.thumb.setVisible(not pix.isNull())
        shown = bool(name or summary or desc or not pix.isNull())
        self.header.setVisible(shown)
        self.title.setVisible(not shown)

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
                    root = root or A.part_in_context(self.app.viewport.scene, self.group)[0]
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
                    errors.append(tr("{label}: «{text}» is not a number", label=opt.label, text=w.text()))
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
            self.status.setText(tr("Could not redraw: {error}", error=exc))
            return
        self.show_group(new, force=True)
        if problems:
            self.status.setText(tr("Redrawn. {n} formula(s) could not be evaluated "
                                   "and kept their value.", n=len(problems)))
        else:
            self.status.setText(tr("Redrawn.") if options else tr("Redrawn (no option changed)."))
