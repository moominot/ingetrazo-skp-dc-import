# SPDX-License-Identifier: GPL-3.0-or-later
"""SketchUp import that keeps components and their Dynamic Components data.

Extensions ▸ «Import SketchUp keeping components…» brings a .skp in with its
component tree intact (every part a nested component instance, shared
geometry for repeated parts) and, on each part that is dynamic, SketchUp's
own Dynamic Components attributes, formulas and options in
``group.ext["skp_dc_import"]``. Phase 1: the components arrive as they were
saved; making them respond to new values comes next.
"""
from __future__ import annotations

__version__ = "0.1.0"

import logging
from pathlib import Path

from .builder import KEY

_log = logging.getLogger(__name__)
_TITLE = "Import SketchUp keeping components"


def import_file(viewport, path) -> dict:
    """Import ``path`` into the viewport's document as ONE undo step.
    Returns the report (counts of placements, dynamic parts, …). Usable
    from the Python Console or the AI bridge, with no dialog."""
    from core.history import SnapshotImport
    from . import builder, reader

    model = reader.parse(path)            # the heavy part, outside the history
    report: dict = {}

    def mutate(scene):
        report.update(builder.build(scene, model, path))

    viewport.history.execute(SnapshotImport(mutate))
    viewport.notify_scene_changed()
    return report


def _summary(report: dict) -> str:
    roots = report.get("dynamic_roots") or []
    text = (f"{report.get('placements', 0)} components and groups, "
            f"{report.get('dynamic', 0)} of them with dynamic attributes.")
    if roots:
        text += "\nDynamic components: " + ", ".join(roots[:12])
        if len(roots) > 12:
            text += f" … (+{len(roots) - 12})"
    return text


def setup(app):
    if getattr(app, "api_version", 0) < 2:
        raise RuntimeError("Requires IngeTrazo with Extension API 2")

    def ask():
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from PySide6.QtCore import Qt
        path, _ = QFileDialog.getOpenFileName(
            app.window, _TITLE, "", "SketchUp (*.skp)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            report = import_file(app.viewport, path)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("import of %s failed", path)
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(app.window, _TITLE,
                                f"Could not import {Path(path).name}:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        QMessageBox.information(app.window, _TITLE, _summary(report))

    app.add_menu_action(
        "Import SketchUp keeping components…", ask,
        tip="Import a .skp keeping its components nested, with their "
            "SketchUp Dynamic Components attributes.")

    def kind(group):
        data = (group.ext or {}).get(KEY)
        if not data:
            return None
        da = dict(data.get("definition_attributes") or {})
        da.update(data.get("instance_attributes") or {})
        options = [k[1:-7] for k, v in da.items()
                   if k.endswith("_access") and v not in (None, "", "NONE")]
        props = [("Definition", data.get("definition", ""))]
        for name in options[:4]:
            label = da.get(f"_{name}_formlabel") or da.get(f"_{name}_label") or name
            props.append((str(label), str(da.get(name, ""))))
        return {"type": "SketchUp dynamic component", "props": props}

    if hasattr(app, "add_outliner_kind"):
        app.add_outliner_kind(kind)
