# SPDX-License-Identifier: GPL-3.0-or-later
"""The extension's toolbar: one button per command, with icons drawn in
IngeTrazo's own style (icons.py: thin ink lines, accent fills, theme-aware)."""
from __future__ import annotations

from PySide6.QtWidgets import QToolBar

from .icons import icon
from .i18n import tr

OBJECT_NAME = "asset_manager_toolbar"   # stable: the saved layout keys on it

def build(app, actions: dict) -> QToolBar | None:
    """Create the toolbar from ``actions`` {key: QAction or None} and place
    it. Returns None when the window cannot hold one."""
    window = getattr(app, "window", None)
    if window is None or not hasattr(window, "addToolBar"):
        return None
    spec = (("open", "comp_manager", "Library"),
            ("polyhaven", "comp_online", "Online assets: HDRIs, materials and models"))
    bar = QToolBar(tr("Library"), window)
    bar.setObjectName(OBJECT_NAME)
    sep_after = set()
    for key, icon_key, tip in spec:
        act = actions.get(key)
        if act is None:
            continue
        act.setIcon(icon(icon_key))
        act.setToolTip(tr(tip))
        bar.addAction(act)
        if key in sep_after:
            bar.addSeparator()
    window.addToolBar(bar)
    restore = getattr(app, "restore_toolbar_layout", None)
    if restore is not None:
        restore()
    return bar
