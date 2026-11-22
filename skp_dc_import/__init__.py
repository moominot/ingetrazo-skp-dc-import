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

__version__ = "0.8.0"

import logging
from pathlib import Path

from .builder import KEY  # noqa: F401 - the data key shared with dc_tools
from .i18n import tr

_log = logging.getLogger(__name__)
_TITLE = tr("Import .skp keeping components")


def import_file(viewport, path, progress=None) -> dict:
    """Import ``path`` into the viewport's document as ONE undo step.
    Returns the report (counts of placements, dynamic parts, …). Usable
    from the Python Console or the AI bridge, with no dialog.

    ``progress(fraction, text)`` (see :mod:`.progress`), when given, follows
    the three stages: reading the file (off the UI thread), building the
    parts, and preparing the drawing so the first orbit does not stall."""
    from core.history import SnapshotImport
    from . import builder, reader
    from .progress import in_thread, scaled

    name = Path(path).name
    # The heavy part, outside the history (off the UI thread with a window).
    model = in_thread(lambda: reader.parse(path), scaled(progress, 0.0, 0.45),
                      tr("Reading {name}…", name=name))
    report: dict = {}
    building = scaled(progress, 0.45, 0.85, tr("Building the parts…"))

    def mutate(scene):
        report.update(builder.build(scene, model, path, progress=building))

    viewport.history.execute(SnapshotImport(mutate))
    viewport.notify_scene_changed()
    prepare = getattr(viewport, "prepare_drawing", None)
    if progress is not None and callable(prepare):
        try:
            prepare(scaled(progress, 0.85, 1.0, tr("Preparing the drawing…")))
        except Exception:  # noqa: BLE001 - a display cache only; the first paint builds it
            _log.exception("preparing the drawing failed")
    if progress is not None:
        progress(1.0, tr("Done"))
    return report


def _summary(report: dict) -> str:
    roots = report.get("dynamic_roots") or []
    text = tr("{n} components and groups, {d} of them with dynamic attributes.",
              n=report.get("placements", 0), d=report.get("dynamic", 0))
    if report.get("scenes"):
        text += "\n" + tr("{n} scenes, as saved views.", n=report["scenes"])
    if report.get("stand_ins"):
        text += "\n" + tr("{n} library objects as stand-ins (translucent, not rendered).", n=report["stand_ins"])
    if report.get("lights"):
        text += "\n" + tr("{n} lights from the file, as Render Studio lights.", n=report["lights"])
    if roots:
        text += "\n" + tr("Dynamic components: ") + ", ".join(roots[:12])
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
            app.window, _TITLE, "", tr(".skp files (*.skp)"))
        if not path:
            return
        from .progress import window
        try:
            with window(app.window, tr("Importing {name}…", name=Path(path).name)) as cb:
                report = import_file(app.viewport, path, progress=cb)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("import of %s failed", path)
            QMessageBox.warning(app.window, _TITLE,
                                tr("Could not import {name}:\n{error}",
                                   name=Path(path).name, error=exc))
            return
        QMessageBox.information(app.window, _TITLE, _summary(report))

    acts = {}
    acts["import"] = app.add_menu_action(
        tr("Import .skp keeping components…"), ask,
        tip=tr("Import a .skp keeping its components nested, with their "
               "dynamic attributes and formulas."))

    def export_skp():
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        from PySide6.QtCore import Qt
        title = tr("Export .skp with dynamic components")
        from .ui_settings import ensure_template
        if not ensure_template(app.window):
            return
        path, _ = QFileDialog.getSaveFileName(app.window, title, "", tr(".skp files (*.skp)"))
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
            QMessageBox.warning(app.window, title, tr("Could not export:\n{error}", error=exc))
            return
        QApplication.restoreOverrideCursor()
        app.viewport.flash_status(
            tr("Exported {name} (.skp 2017 format).", name=Path(path).name), 5000)

    acts["export"] = app.add_menu_action(
        tr("Export .skp with dynamic components…"), export_skp,
        tip=tr("Write the document as a .skp (2017 format) with groups, "
               "components and their dynamic attributes."))

    def settings():
        from .ui_settings import SettingsDialog
        SettingsDialog(app.window).exec()

    acts["settings"] = app.add_menu_action(
        tr(".skp settings…"), settings,
        tip=tr("Credits, and the blank .skp the exporter needs (not bundled)."))

    def show_help():
        from . import ui_help
        ui_help.show(app.window, "files")

    acts["help"] = app.add_menu_action(
        tr(".skp files help…"), show_help,
        tip=tr("How importing and exporting .skp files works, and the blank file export needs."))

    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
