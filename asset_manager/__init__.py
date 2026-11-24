# SPDX-License-Identifier: GPL-3.0-or-later
"""Library for IngeTrazo: what the drawing holds (with previews,
a mark on dynamic components, select every instance, drag a copy onto the
view), catalog folders of your own models (.igz, .skp), and free online
assets: Poly Haven's HDRIs, materials and 3-D models, ambientCG's HDRIs and materials.

It reads the dynamic-component data (``group.ext["skp_dc_import"]``) when
there is any; inserting a .skp keeping its components uses the ``.skp
files`` extension (skp_dc_import) when it is installed. A model can go in
as a proxy (a light envelope; the full model in an .igz of its own), in the data
format of the Proxies extension (``group.ext["proxy_tool"]``).
"""
from __future__ import annotations

__version__ = "0.6.0"

import logging

_log = logging.getLogger(__name__)


def setup(app):
    if getattr(app, "api_version", 0) < 2:
        raise RuntimeError("Requires IngeTrazo with Extension API 2")
    from PySide6.QtCore import QTimer

    from . import inventory
    from .i18n import tr
    from .icons import panel_icon
    from .panel import STAND_IN_TIP, AssetPanel
    panel = AssetPanel(app)
    dock = app.add_panel(tr("Library"), panel, name="components",
                          **panel_icon(app, "comp_manager"))

    def show(tab=None):
        app.show_panel(dock)
        if tab is not None:
            panel.tabs.setCurrentIndex(tab)

    acts = {
        "open": app.add_menu_action(
            tr("Library…"), show,
            tip=tr("The components in the drawing, your catalog folders and free online assets.")),
        "polyhaven": app.add_menu_action(
            tr("Online assets: HDRIs, materials and models…"), lambda: show(2),
            tip=tr("Free CC0 360° backgrounds, materials and 3-D models from Poly Haven and ambientCG.")),
        "settings": app.add_menu_action(
            tr("Library settings…"), panel.open_settings,
            tip=tr("Model sites to open, and which catalog folders are watched in real time.")),
    }

    def context_menu(menu, selection):
        g = inventory.selected_component(selection)
        if g is not None:
            name = inventory.display_name(g)
            menu.addAction(tr("Select all instances of «{name}»", name=name),
                           lambda: QTimer.singleShot(0, lambda: panel.select_like(g)))
        try:
            stand_in_menu(menu, selection)
        except Exception:  # noqa: BLE001 - a menu entry must never break the menu
            _log.exception("stand-in menu entry failed")
        try:
            proxy_menu(menu, selection)
        except Exception:  # noqa: BLE001 - a menu entry must never break the menu
            _log.exception("proxy menu entries failed")

    def stand_in_menu(menu, selection):
        from . import stand_in
        groups = stand_in.selected_groups(selection)
        if not groups:
            return
        flag = stand_in.state_of(groups)
        n = f" ({len(groups)})" if len(groups) > 1 else ""
        act = menu.addAction(tr("Stand-in: not rendered, shown translucent") + n)
        act.setToolTip(tr(STAND_IN_TIP))
        act.setCheckable(True)
        act.setChecked(bool(flag))
        want = not bool(flag)       # mixed selection: mark them all

        def toggle():
            QTimer.singleShot(0, lambda: panel.set_stand_in(groups, want))
        act.triggered.connect(toggle)

    def proxy_menu(menu, selection):
        from . import proxy_ops
        can = proxy_ops.offers(app.viewport.scene, selection)

        def later(fn, groups):
            # From the event loop, once the menu is gone.
            return lambda: QTimer.singleShot(0, lambda: run(fn, groups))

        def n(groups):
            return f" ({len(groups)})" if len(groups) > 1 else ""

        if can["make"]:
            menu.addAction(tr("Make proxy") + n(can["make"]), later("make", can["make"]))
        if can["original"]:
            menu.addAction(tr("Show original") + n(can["original"]), later("original", can["original"]))
        if can["proxy"]:
            menu.addAction(tr("Show proxy") + n(can["proxy"]), later("proxy", can["proxy"]))
        if can["open"]:
            menu.addAction(tr("Open original in a new tab") + n(can["open"]), later("open", can["open"]))

    def run(what, groups):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        from . import proxy_ops
        vp = app.viewport
        say = getattr(vp, "flash_status", None) or (lambda text, ms=0: panel._say(text))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if what == "make":
                n = proxy_ops.make_proxies(vp, groups, confirm=panel.confirm_dynamic_many)
                if n:
                    say(tr("{n} object(s) made proxies: an envelope in the drawing, the full model "
                           "in {folder}.", n=n, folder=proxy_folder(vp)), 6000)
            elif what == "open":
                QApplication.restoreOverrideCursor()        # the tab may ask (recovered copy…)
                QApplication.setOverrideCursor(Qt.ArrowCursor)
                opened, missing = proxy_ops.open_originals(app.window, vp, groups)
                if missing:
                    say(tr("Original not found: {names}.", names=", ".join(missing)), 8000)
                elif opened:
                    front_say = getattr(app.viewport, "flash_status", None) or say
                    front_say(tr("Original opened in its own tab. Save it there: the proxy takes the "
                                 "change when you come back to its drawing."), 8000)
            elif what == "original":
                n, missing = proxy_ops.show_originals(vp, groups)
                say(tr("Full model shown: {n}.", n=n) + (" " + tr("Not found: {names}.", names=", ".join(missing)) if missing else ""),
                    8000 if missing else 5000)
            else:
                n, failed = proxy_ops.show_proxies(vp, groups)
                say(tr("Back to the proxy: {n}.", n=n) + (" " + tr("Could not save: {names}.", names=", ".join(failed)) if failed else ""),
                    8000 if failed else 5000)
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("proxy command failed")
            say(tr("Proxy: {error}", error=exc), 8000)
        finally:
            QApplication.restoreOverrideCursor()

    def proxy_folder(vp):
        from . import proxy
        return proxy.originals_folder(vp)

    if hasattr(app, "add_context_menu"):
        app.add_context_menu(context_menu)

    # An original opened in its own tab and saved there: its proxies take the
    # change when their drawing comes back to the front (or is opened).
    front = {"scene": None}

    def check_originals():
        try:
            scene = app.scene
        except Exception:  # noqa: BLE001
            return
        if scene is front["scene"]:
            return
        front["scene"] = scene
        QTimer.singleShot(0, lambda: refresh_originals(scene))

    def refresh_originals(scene):
        from . import proxy_ops
        vp = app.viewport
        if vp.scene is not scene:
            return
        try:
            names = proxy_ops.refresh_changed(vp)
        except Exception:  # noqa: BLE001 - never in the way of a tab switch
            _log.exception("proxy refresh failed")
            return
        if names and hasattr(vp, "flash_status"):
            vp.flash_status(tr("Proxy updated from its saved original: {names}",
                               names=", ".join(names[:4]) + ("…" if len(names) > 4 else "")), 6000)

    if hasattr(app, "on_document_changed"):
        app.on_document_changed(check_originals)
    try:
        from . import ui_toolbar
        ui_toolbar.build(app, acts)
    except Exception:  # noqa: BLE001 - a toolbar must never stop the extension loading
        _log.exception("could not build the toolbar")
