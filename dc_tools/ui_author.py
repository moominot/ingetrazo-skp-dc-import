# SPDX-License-Identifier: GPL-3.0-or-later
"""«Component Attributes»: make a component dynamic and edit its parts'
attributes and formulas, like SketchUp's window of the same name. Every
change redraws the component and is one undo step."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMenu, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .dc import apply as A
from .dc import author as AU
from .dc import formula as F
from .dc import options as O
from .dc.evaluate import _num
from .dc.model import INCH
from .dc.redraw import _LiveEvaluator
from .ui import context_members, redraw_in_document, replace_in_document

_log = logging.getLogger(__name__)

UNITS = ("CENTIMETERS", "MILLIMETERS", "METERS", "INCHES", "FEET")
VALUE_UNITS = ("DEFAULT", "CENTIMETERS", "MILLIMETERS", "METERS", "INCHES", "FEET",
               "DEGREES", "PERCENT", "INTEGER", "FLOAT", "STRING")
ACCESS_LABELS = (("NONE", "Users cannot see this attribute"),
                 ("VIEW", "Users can see this attribute"),
                 ("TEXTBOX", "Users can edit as a textbox"),
                 ("LIST", "Users can select from a list"))


def selected_top(scene):
    """The one selected group or component of the current context (the
    top level, or the open group's parts), else None."""
    members = context_members(scene)
    found = None
    for e in getattr(scene, "selection", ()) or ():
        g = getattr(e, "owner", None) or e
        if any(g is m for m in members):
            if found is not None and found is not g:
                return None
            found = g
    return found


def part_at(root, path):
    g = root
    for i in path:
        kids = g.children or []
        if i >= len(kids):
            return None
        g = kids[i]
    return g


def _units_of(attrs: dict, name: str, part_unit: str) -> str:
    """How a value of ``name`` is read and shown."""
    if name in ("x", "y", "z", "lenx", "leny", "lenz"):
        return part_unit
    if name in ("rotx", "roty", "rotz"):
        return "DEGREES"
    u = str(attrs.get(f"_{name}_units") or "").upper()
    if u in ("", "DEFAULT"):
        fu = str(attrs.get(f"_{name}_formulaunits") or "").upper()
        return fu if fu in INCH else "STRING"
    return u


def _copies_of(root, part):
    """The copies (Copy > 0) of ``part`` among its siblings."""
    name = AU.merged(part).get("_name") or part.name

    def parent_of(g):
        for c in g.children or ():
            if c is part:
                return g
            hit = parent_of(c)
            if hit is not None:
                return hit
        return None

    parent = parent_of(root)
    out = []
    for c in (parent.children if parent is not None else ()) or ():
        if c is part:
            continue
        a = AU.merged(c)
        copy = _num(a.get("copy"))
        if isinstance(copy, float) and copy > 0 and (a.get("_name") or c.name) == name:
            out.append(c)
    return out


class OptionsDialog(QDialog):
    """SketchUp's «Display rule» for one attribute: label, who sees it,
    units, and the choices of a list."""

    def __init__(self, parent, name: str, attrs: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Attribute options — {name}")
        form = QFormLayout(self)
        self.label = QLineEdit(str(attrs.get(f"_{name}_formlabel") or attrs.get(f"_{name}_label") or name))
        form.addRow("Display label", self.label)
        self.access = QComboBox()
        for key, text in ACCESS_LABELS:
            self.access.addItem(text, key)
        cur = str(attrs.get(f"_{name}_access") or "NONE").upper()
        self.access.setCurrentIndex(max(0, [k for k, _ in ACCESS_LABELS].index(cur) if cur in [k for k, _ in ACCESS_LABELS] else 0))
        form.addRow("Access", self.access)
        self.units = QComboBox()
        for u in VALUE_UNITS:
            self.units.addItem(u.capitalize(), u)
        cu = str(attrs.get(f"_{name}_units") or "DEFAULT").upper()
        self.units.setCurrentIndex(max(0, self.units.findData(cu)))
        form.addRow("Display in", self.units)
        self.choices = QTableWidget(0, 2)
        self.choices.setHorizontalHeaderLabels(["Option", "Value"])
        self.choices.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for label, value in O.parse_choices(attrs.get(f"_{name}_options")):
            self._add_choice(label, value)
        row = QHBoxLayout()
        add, rem = QPushButton("+"), QPushButton("−")
        add.clicked.connect(lambda: self._add_choice("", ""))
        rem.clicked.connect(lambda: self.choices.removeRow(self.choices.currentRow())
                            if self.choices.currentRow() >= 0 else None)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.choices)
        lay.addLayout(row)
        form.addRow("List options", box)
        self.access.currentIndexChanged.connect(
            lambda _i: box.setEnabled(self.access.currentData() == "LIST"))
        box.setEnabled(self.access.currentData() == "LIST")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _add_choice(self, label, value):
        r = self.choices.rowCount()
        self.choices.insertRow(r)
        self.choices.setItem(r, 0, QTableWidgetItem(str(label)))
        self.choices.setItem(r, 1, QTableWidgetItem(str(value)))

    def changes(self, name: str) -> dict:
        choices = []
        for r in range(self.choices.rowCount()):
            l = (self.choices.item(r, 0) or QTableWidgetItem("")).text().strip()
            v = (self.choices.item(r, 1) or QTableWidgetItem("")).text().strip()
            if l:
                choices.append((l, v if v else l))
        access = self.access.currentData()
        units = self.units.currentData()
        return AU.set_changes(name, formlabel=self.label.text().strip() or "",
                              access=access, units=units if units != "DEFAULT" else "",
                              options=choices if access == "LIST" else [])


class AttributesPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.root = None             # the top-level group shown
        self.path = ()               # the part being edited, as child indices
        self._filling = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.title = QLabel("Select a component or group.")
        self.title.setWordWrap(True)
        outer.addWidget(self.title)
        mk = QHBoxLayout()
        self.make_btn = QPushButton("Make dynamic")
        self.make_btn.setToolTip("Give the selected component or group dynamic attributes")
        self.make_btn.clicked.connect(self.make_dynamic)
        self.units = QComboBox()
        for u in UNITS:
            self.units.addItem(u.capitalize(), u)
        self.units.setToolTip("The units its formulas are written in")
        mk.addWidget(self.make_btn)
        mk.addWidget(self.units)
        self.help_btn = QToolButton()
        self.help_btn.setText("?")
        self.help_btn.setToolTip("How this panel works, and what each function does")
        self.help_btn.clicked.connect(self.show_help)
        mk.addWidget(self.help_btn)
        outer.addLayout(mk)
        split = QSplitter(Qt.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._tree_changed)
        split.addWidget(self.tree)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Attribute", "Value or =formula", "Result"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self._cell_changed)
        split.addWidget(self.table)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, 1)
        row = QHBoxLayout()
        self.add_btn = QToolButton()
        self.add_btn.setText("Add attribute")
        self.add_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.add_btn)
        for name, _u in AU.PREDEFINED:
            menu.addAction(AU.LABELS[name], lambda n=name: self.add_attribute(n))
        menu.addSeparator()
        menu.addAction("Custom…", self.add_custom)
        self.add_btn.setMenu(menu)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self.delete_attribute)
        self.opt_btn = QPushButton("Options…")
        self.opt_btn.setToolTip("Label, who can see or edit it, units, list choices")
        self.opt_btn.clicked.connect(self.edit_options)
        for w in (self.add_btn, self.del_btn, self.opt_btn):
            row.addWidget(w)
        outer.addLayout(row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._refresh_enabled()

    def show_help(self):
        """The «?» button: the shared help window, at this panel's section."""
        from . import ui_help
        ui_help.show(self.window(), "attributes")

    # -- selection -------------------------------------------------------------
    def _poll(self):
        if not self.isVisible():
            return
        try:
            g = selected_top(self.app.viewport.scene)
        except Exception:  # noqa: BLE001
            return
        if g is not self.root:
            self.show_root(g, ())

    def _refresh_enabled(self):
        dyn = self.root is not None and A.is_dynamic_root(self.root)
        self.make_btn.setEnabled(self.root is not None and not dyn)
        self.units.setEnabled(self.root is not None and not dyn)
        for w in (self.add_btn, self.del_btn, self.opt_btn, self.table, self.tree):
            w.setEnabled(dyn)

    def show_root(self, root, path=()):
        self.root, self.path = root, tuple(path)
        self.status.setText("")
        self._filling = True
        try:
            self.tree.clear()
            if root is None:
                self.title.setText("Select a component or group.")
            else:
                name = AU.merged(root).get("_name") or root.name
                dyn = A.is_dynamic_root(root)
                self.title.setText(f"<b>{name}</b>" + ("" if dyn else
                                   " — not dynamic yet: «Make dynamic» to give it attributes."))
                self._fill_tree(root, None, ())
                self.tree.expandAll()
                self._select_tree(self.path)
        finally:
            self._filling = False
        self._refresh_enabled()
        self.show_part()

    def _fill_tree(self, g, parent_item, path):
        a = AU.merged(g)
        label = str(a.get("_name") or g.name or "(part)")
        copy = _num(a.get("copy"))
        if isinstance(copy, float) and copy > 0:
            label += f"  (copy {int(copy)})"
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.UserRole, path)
        if isinstance(copy, float) and copy > 0:
            f = QFont()
            f.setItalic(True)
            item.setFont(0, f)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setToolTip(0, "A copy made by Copies: edit the original")
        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        for i, c in enumerate(g.children or ()):
            self._fill_tree(c, item, path + (i,))

    def _select_tree(self, path):
        def find(item):
            if tuple(item.data(0, Qt.UserRole) or ()) == tuple(path):
                return item
            for i in range(item.childCount()):
                hit = find(item.child(i))
                if hit is not None:
                    return hit
            return None
        if self.tree.topLevelItemCount():
            hit = find(self.tree.topLevelItem(0)) or self.tree.topLevelItem(0)
            self.tree.setCurrentItem(hit)

    def _tree_changed(self, cur, _prev):
        if self._filling or cur is None:
            return
        self.path = tuple(cur.data(0, Qt.UserRole) or ())
        self.show_part()

    # -- the table ---------------------------------------------------------------
    def _part(self):
        return part_at(self.root, self.path) if self.root is not None else None

    def _part_unit(self, attrs):
        u = str(attrs.get("_lengthunits") or "").upper()
        if u in INCH:
            return u
        root_u = str(AU.merged(self.root).get("_lengthunits") or "").upper()
        return root_u if root_u in INCH else "CENTIMETERS"

    def show_part(self):
        self._filling = True
        try:
            self.table.setRowCount(0)
            g = self._part()
            if g is None or not A.is_dynamic_root(self.root):
                return
            attrs = AU.merged(g)
            unit = self._part_unit(attrs)
            try:
                tree = A.part_in_context(self.app.viewport.scene, self.root)[0]
                part = tree
                for i in self.path:
                    part = part.children[i]
                ev = _LiveEvaluator(tree)
            except Exception:  # noqa: BLE001
                part, ev = None, None
            for name in AU.attribute_names(attrs):
                r = self.table.rowCount()
                self.table.insertRow(r)
                head = QTableWidgetItem(AU.LABELS.get(name, name))
                head.setData(Qt.UserRole, name)
                head.setFlags(head.flags() & ~Qt.ItemIsEditable)
                f = attrs.get(f"_{name}_formula")
                units = _units_of(attrs, name, unit)
                opt = O.Option(name, name, "TEXTBOX", units, attrs.get(name))
                text = f"={f}" if f not in (None, "") else O.display(opt)
                cell = QTableWidgetItem(text)
                result = ""
                if part is not None and ev is not None:
                    try:
                        result = O.display(opt, ev.value(part, name))
                    except Exception:  # noqa: BLE001
                        result = "?"
                res = QTableWidgetItem(result)
                res.setFlags(res.flags() & ~Qt.ItemIsEditable)
                access = str(attrs.get(f"_{name}_access") or "").upper()
                if access and access != "NONE":
                    head.setToolTip(f"Shown to users ({access.lower()})")
                    fh = QFont()
                    fh.setBold(True)
                    head.setFont(fh)
                self.table.setItem(r, 0, head)
                self.table.setItem(r, 1, cell)
                self.table.setItem(r, 2, res)
            self.table.resizeColumnToContents(0)
        finally:
            self._filling = False

    def _selected_name(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 0)
        return it.data(Qt.UserRole) if it else None

    # -- editing -------------------------------------------------------------------
    def _commit(self, changes: dict, message: str):
        g = self._part()
        if g is None or not changes:
            return
        attrs = AU.merged(g)
        # Like SketchUp's window: a part it edits gets its name and the
        # units its formulas are written in.
        if not attrs.get("_name"):
            changes.setdefault("_name", g.name or "part")
        if not attrs.get("_lengthunits"):
            changes.setdefault("_lengthunits", self._part_unit(attrs))
        # The part's copies (Copies) get the same change: in SketchUp they are
        # the original again, so a formula added later reaches them too.
        targets = [g] + _copies_of(self.root, g)
        try:
            new, problems = redraw_in_document(self.app.viewport, self.root, {},
                                               {id(t): dict(changes) for t in targets})
        except Exception as exc:  # noqa: BLE001
            _log.exception("attribute edit failed")
            self.status.setText(f"Could not apply: {exc}")
            return
        self.show_root(new, self.path)
        self.status.setText(message + (f" {len(problems)} formula(s) failed and kept their "
                                       "value." if problems else ""))

    def _cell_changed(self, item):
        if self._filling or item.column() != 1:
            return
        head = self.table.item(item.row(), 0)
        name = head.data(Qt.UserRole) if head else None
        if not name:
            return
        text = item.text().strip()
        g = self._part()
        attrs = AU.merged(g)
        if text.startswith("="):
            try:
                F.parse(text[1:])
            except F.FormulaError as exc:
                self.status.setText(f"{name}: {getattr(exc, 'msg', exc)}")
                QTimer.singleShot(0, self.show_part)
                return
            self._commit(AU.set_changes(name, formula=text), f"{name} {text}")
            return
        units = _units_of(attrs, name, self._part_unit(attrs))
        opt = O.Option(name, name, "TEXTBOX", units, attrs.get(name))
        try:
            value = O.parse(opt, text) if text else ""
        except ValueError:
            self.status.setText(f"{name}: «{text}» is not a number")
            QTimer.singleShot(0, self.show_part)
            return
        if isinstance(value, float):
            value = repr(value)               # SketchUp keeps option values as text
        self._commit(AU.set_changes(name, value=value, formula=""), f"{name} set.")

    def add_attribute(self, name: str):
        g = self._part()
        if g is None:
            return
        attrs = AU.merged(g)
        if name in AU.attribute_names(attrs):
            self.status.setText(f"{AU.LABELS.get(name, name)} is already there.")
            return
        value = ""
        if name in ("x", "y", "z", "lenx", "leny", "lenz"):
            # Starts at what the part measures now, as SketchUp does.
            try:
                tree = A.part_in_context(self.app.viewport.scene, self.root)[0]
                part = tree
                for i in self.path:
                    part = part.children[i]
                v = _LiveEvaluator(tree).value(part, name)
                value = repr(float(v))
            except Exception:  # noqa: BLE001
                value = "0"
        elif name in ("rotx", "roty", "rotz", "copies", "hidden"):
            value = "0"
        self._commit(AU.set_changes(name, value=value), f"{AU.LABELS.get(name, name)} added.")

    def add_custom(self):
        name, ok = QInputDialog.getText(self, "Add attribute", "Name (letters, digits, _):")
        if not ok:
            return
        name = name.strip().lower()
        if not AU.valid_name(name) or name in AU.PREDEFINED_NAMES:
            self.status.setText(f"«{name}» cannot be an attribute name.")
            return
        self._commit(AU.set_changes(name, value="", label=name), f"{name} added.")

    def delete_attribute(self):
        name = self._selected_name()
        g = self._part()
        if not name or g is None:
            return
        self._commit(AU.delete_changes(AU.merged(g), name), f"{name} deleted.")

    def edit_options(self):
        name = self._selected_name()
        g = self._part()
        if not name or g is None:
            self.status.setText("Pick an attribute first.")
            return
        dlg = OptionsDialog(self, name, AU.merged(g))
        if dlg.exec() == QDialog.Accepted:
            self._commit(dlg.changes(name), f"{name}: options saved.")

    def make_dynamic(self):
        g = self.root
        if g is None or A.is_dynamic_root(g):
            return
        name, ok = QInputDialog.getText(self, "Make dynamic", "Component name:",
                                        text=g.name or "Component")
        if not ok or not name.strip():
            return
        units = self.units.currentData()
        try:
            new = replace_in_document(self.app.viewport, g,
                                      lambda _sc: A.make_dynamic_tree(g, name.strip(), units))
        except Exception as exc:  # noqa: BLE001
            _log.exception("make dynamic failed")
            self.status.setText(f"Could not make it dynamic: {exc}")
            return
        self.show_root(new, ())
        self.status.setText("Dynamic. Add attributes to it and to its parts.")
