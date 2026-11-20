# SPDX-License-Identifier: GPL-3.0-or-later
"""SketchUp files that keep components and their Dynamic Components data.

Extensions ▸ «Import SketchUp keeping components…» brings a .skp in with its
component tree intact (every part a nested component instance, shared
geometry for repeated parts) and, on each part that is dynamic, SketchUp's
own Dynamic Components attributes, formulas and options in
``group.ext["skp_dc_import"]``. «Export SketchUp (.skp)…» writes them back.
Editing those components (options, attributes, formulas) is the job of the
separate *dc_tools* extension, which reads the same data.
"""
from __future__ import annotations

__version__ = "0.6.3"

import logging
from pathlib import Path

from .builder import KEY  # noqa: F401 - the data key shared with dc_tools

_log = logging.getLogger(__name__)
_TITLE = "Import .skp keeping components"


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
            app.window, _TITLE, "", ".skp files (*.skp)")
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

    acts = {}
    acts["import"] = app.add_menu_action(
        "Import .skp keeping components…", ask,
        tip="Import a .skp keeping its components nested, with their "
            "dynamic attributes and formulas.")

    def export_skp():
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from PySide6.QtCore import Qt
        title = "Export .skp with dynamic components"
        from .ui_settings import ensure_template
        if not ensure_template(app.window):
            return
        path, _ = QFileDialog.getSaveFileName(app.window, title, "", ".skp files (*.skp)")
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
        app.viewport.flash_status(f"Exported {Path(path).name} (.skp 2017 format).", 5000)

    acts["export"] = app.add_menu_action(
        "Export .skp with dynamic components…", export_skp,
        tip="Write the document as a .skp (2017 format) with groups, "
            "components and their dynamic attributes.")

    def settings():
        from .ui_settings import SettingsDialog
        SettingsDialog(app.window).exec()

    acts["settings"] = app.add_menu_action(
        ".skp settings…", settings,
        tip="Credits, and the blank .skp the exporter needs (not bundled).")

    def show_help():
        from . import ui_help
        ui_help.show(app.window, "files")

    acts["help"] = app.add_menu_action(
        ".skp files help…", show_help,
        tip="How importing and exporting .skp files works, and the blank file export needs.")

    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
