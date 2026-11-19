"""Toolbar and settings dialog, offscreen. argv: <ingetrazo-src> <extension repo> [png dir]"""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SKP_DC_IMPORT_HOME"] = tempfile.mkdtemp()
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar
from PySide6.QtGui import QAction
qa = QApplication.instance() or QApplication([])
from skp_dc_import import ui_toolbar, ui_settings
from dc_tools import ui_toolbar as dc_toolbar

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

class App:
    def __init__(self):
        self.window = QMainWindow(); self.restored = 0
    def restore_toolbar_layout(self): self.restored += 1

app = App()
acts = {k: QAction(k, app.window) for k in ("import", "export", "settings")}
bar = ui_toolbar.build(app, acts)
ok(bar is not None and bar.objectName() == ui_toolbar.OBJECT_NAME, "toolbar built with a stable objectName")
ok([a for a in bar.actions() if not a.isSeparator()] == list(acts.values()), "three buttons, in order")
ok(sum(a.isSeparator() for a in bar.actions()) == 1, "one separator")
ok(all(not a.icon().isNull() and a.toolTip() for a in acts.values()), "every button has an icon and a tooltip")
ok(app.restored == 1, "restore_toolbar_layout called once")
ok(ui_toolbar.build(app, {"import": None}) is not None, "missing actions (no Extensions menu) are skipped")
dacts = {k: QAction(k, app.window) for k in ("options", "attributes")}
dbar = dc_toolbar.build(app, dacts)
ok(dbar is not None and dbar.objectName() == "dc_tools_toolbar" != bar.objectName(), "dc_tools toolbar has its own objectName")
ok([a for a in dbar.actions() if not a.isSeparator()] == list(dacts.values()), "dc_tools: options and attributes")
class NoWin: window = None
ok(ui_toolbar.build(NoWin(), acts) is None, "no window -> no toolbar, no crash")

d = ui_settings.SettingsDialog()
ok("Export template" in d.state.text() and "No blank" in d.state.text(), "dialog shows the template is missing")
if PNG:
    app.window.resize(420, 80); app.window.show(); qa.processEvents()
    app.window.grab().save(os.path.join(PNG, "toolbar.png"))
    d.show(); qa.processEvents(); d.grab().save(os.path.join(PNG, "dialog.png"))
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
