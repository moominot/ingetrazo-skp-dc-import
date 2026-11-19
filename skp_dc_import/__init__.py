# SPDX-License-Identifier: GPL-3.0-or-later
"""SketchUp import that keeps components and their Dynamic Components data.

Extensions ▸ «Import SketchUp keeping components…» brings a .skp in with its
component tree intact (every part a nested component instance, shared
geometry for repeated parts) and, on each part that is dynamic, SketchUp's
own Dynamic Components attributes, formulas and options in
``group.ext["skp_dc_import"]``. «Component Options» changes a dynamic
component's options and redraws it as SketchUp does; «Component Attributes»
makes components dynamic and edits their attributes and formulas.
"""
from __future__ import annotations

__version__ = "0.3.0"

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

    def export_skp():
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from PySide6.QtCore import Qt
        title = "Export SketchUp (.skp) with dynamic components"
        path, _ = QFileDialog.getSaveFileName(app.window, title, "", "SketchUp (*.skp)")
        if not path:
            return
        if not path.lower().endswith(".skp"):
            path += ".skp"
        from . import skp_export
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            skp_export.save_skp(app.viewport.scene, path)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("export to %s failed", path)
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(app.window, title, f"Could not export:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        app.viewport.flash_status(f"Exported {Path(path).name} (SketchUp 2017 format).", 5000)

    app.add_menu_action(
        "Export SketchUp (.skp) with dynamic components…", export_skp,
        tip="Write the document as a .skp (SketchUp 2017 format) with groups, "
            "components and their Dynamic Components attributes.")

    # Component Options: a side-tray tab that follows the selection.
    from .ui import OptionsPanel, selected_root
    panel = OptionsPanel(app)
    dock = app.add_panel("Component Options", panel, start_hidden=True)

    def show_options():
        app.show_panel(dock)
        panel.show_group(selected_root(app.viewport.scene), force=True)

    app.add_menu_action(
        "Dynamic component options…", show_options,
        tip="Options of the selected SketchUp dynamic component.")

    # Component Attributes: make dynamic, edit parts' attributes/formulas.
    from .ui_author import AttributesPanel, selected_top
    attr_panel = AttributesPanel(app)
    # A second panel of this extension needs its own name, or add_panel
    # hands back the first one (Component Options).
    attr_dock = app.add_panel("Component Attributes", attr_panel, name="attributes",
                              start_hidden=True)

    def show_attributes():
        app.show_panel(attr_dock)
        attr_panel.show_root(selected_top(app.viewport.scene), ())

    app.add_menu_action(
        "Component attributes…", show_attributes,
        tip="Make the selected component dynamic and edit its attributes and formulas.")

    if hasattr(app, "add_context_menu"):
        def context(menu, selection):
            scene = app.viewport.scene
            dyn = selected_root(scene) is not None
            top = selected_top(scene) is not None
            if not (dyn or top):
                return
            from PySide6.QtCore import QTimer
            menu.addSeparator()
            if dyn:
                menu.addAction("Dynamic component options…",
                               lambda: QTimer.singleShot(0, show_options))
            menu.addAction("Component attributes…",
                           lambda: QTimer.singleShot(0, show_attributes))
        app.add_context_menu(context)

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
