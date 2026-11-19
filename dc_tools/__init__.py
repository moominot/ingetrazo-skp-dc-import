# SPDX-License-Identifier: GPL-3.0-or-later
"""Dynamic components for IngeTrazo: options, attributes and formulas.

«Component Options» changes a dynamic component's options and redraws it as
SketchUp's Dynamic Components do; «Component Attributes» makes components
dynamic and edits their attributes and formulas. It works on the data the
components carry in ``group.ext["skp_dc_import"]`` (SketchUp's own Dynamic
Components attributes, in its format), wherever it came from: drawn here, or
brought in with the *SketchUp import* extension (``skp_dc_import``), which is
a separate extension. This one needs neither OpenSKP nor any .skp file.
"""
from __future__ import annotations

__version__ = "0.3.3"

import logging

from .dc.apply import KEY   # the key the data lives under (kept for compatibility)

_log = logging.getLogger(__name__)


def setup(app):
    if getattr(app, "api_version", 0) < 2:
        raise RuntimeError("Requires IngeTrazo with Extension API 2")

    acts = {}
    # Component Options: a side-tray tab that follows the selection.
    from .ui import OptionsPanel, selected_root
    panel = OptionsPanel(app)
    dock = app.add_panel("Component Options", panel, start_hidden=True)

    def show_options():
        app.show_panel(dock)
        panel.show_group(selected_root(app.viewport.scene), force=True)

    acts["options"] = app.add_menu_action(
        "Dynamic component options…", show_options,
        tip="Options of the selected dynamic component.")

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

    acts["attributes"] = app.add_menu_action(
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
        return {"type": "Dynamic component", "props": props}

    if hasattr(app, "add_outliner_kind"):
        app.add_outliner_kind(kind)

    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
