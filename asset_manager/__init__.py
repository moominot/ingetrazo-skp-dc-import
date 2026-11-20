# SPDX-License-Identifier: GPL-3.0-or-later
"""Components manager for IngeTrazo: what the drawing holds (with previews,
a mark on dynamic components, select every instance, drag a copy onto the
view), catalog folders of your own models (.igz, .skp), and free online
assets: Poly Haven's HDRIs, materials and 3-D models, ambientCG's materials.

It reads the dynamic-component data (``group.ext["skp_dc_import"]``) when
there is any; inserting a .skp keeping its components uses the ``.skp
files`` extension (skp_dc_import) when it is installed.
"""
from __future__ import annotations

__version__ = "0.2.0"

import logging

_log = logging.getLogger(__name__)


def setup(app):
    if getattr(app, "api_version", 0) < 2:
        raise RuntimeError("Requires IngeTrazo with Extension API 2")
    from PySide6.QtCore import QTimer

    from . import inventory
    from .panel import AssetPanel
    panel = AssetPanel(app)
    dock = app.add_panel("Components", panel, name="components")

    def show(tab=None):
        app.show_panel(dock)
        if tab is not None:
            panel.tabs.setCurrentIndex(tab)

    acts = {
        "open": app.add_menu_action(
            "Components manager…", show,
            tip="The components in the drawing, your catalog folders and free online assets."),
        "polyhaven": app.add_menu_action(
            "Online assets: HDRIs, materials and models…", lambda: show(2),
            tip="Free CC0 360° backgrounds, materials and 3-D models from Poly Haven and ambientCG."),
        "settings": app.add_menu_action(
            "Components manager settings…", panel.open_settings,
            tip="Model sites to open, and which catalog folders are watched in real time."),
    }

    def context_menu(menu, selection):
        g = inventory.selected_component(selection)
        if g is None:
            return
        name = inventory.display_name(g)
        menu.addAction(f"Select all instances of «{name}»",
                       lambda: QTimer.singleShot(0, lambda: panel.select_like(g)))

    if hasattr(app, "add_context_menu"):
        app.add_context_menu(context_menu)
    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
