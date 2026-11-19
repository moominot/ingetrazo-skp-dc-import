# SPDX-License-Identifier: GPL-3.0-or-later
"""Components manager for IngeTrazo: what the drawing holds (with previews
and a mark on dynamic components) and a catalog of your own models.

It reads the components in the document and the Dynamic Components data
(``group.ext["skp_dc_import"]``) when there is any; it needs neither of the
other extensions (``skp_dc_import``, ``dc_tools``) to be installed.
"""
from __future__ import annotations

__version__ = "0.1.0"

import logging

_log = logging.getLogger(__name__)


def setup(app):
    if getattr(app, "api_version", 0) < 2:
        raise RuntimeError("Requires IngeTrazo with Extension API 2")
    from .panel import AssetPanel
    panel = AssetPanel(app)
    dock = app.add_panel("Components", panel, name="components")

    def show():
        app.show_panel(dock)
        panel.refresh()
        panel.refresh_catalog()

    acts = {"open": app.add_menu_action(
        "Components manager…", show,
        tip="The components in the drawing (dynamic ones marked) and your catalog.")}
    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
