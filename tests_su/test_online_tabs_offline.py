"""Offscreen: the Components manager has one online tab per kind (360° backgrounds,
materials, models), each loading its own list. argv: <ingetrazo-src> <extension repo>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
qa = QApplication.instance() or QApplication([])
from core.scene import Scene
from asset_manager import panel as P

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

class Win:  # enough of a window for the panel
    pass
class VP:
    def __init__(s, sc): s.scene = sc
    def update(s): pass
    def flash_status(s, *a): pass
sc = Scene()
from PySide6.QtWidgets import QWidget
win = QWidget(); vp = VP(sc)
class App:
    api_version = 2
    def __init__(s): s.scene = sc; s.window = win; s.viewport = vp
    def on_document_changed(s, fn): pass
panel = P.AssetPanel(App())
titles = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
ok(titles[2:] == ["360° backgrounds", "Materials", "Models"] or titles[2:] == ["Fons 360°", "Materials", "Models"],
   "one online tab per kind: %s" % titles)
tabs = panel.online_tabs
ok(set(tabs) == {"hdris", "materials", "models"}, "three tabs")
ok([tabs["hdris"].source.count(), tabs["materials"].source.count(), tabs["models"].source.count()] == [2, 2, 1],
   "backgrounds and materials come from two sites; models from one")
ok(tabs["models"].proxy is not None and tabs["materials"].proxy is None and tabs["hdris"].proxy is None,
   "only the models tab has the «As proxy» box")
ok(all(t.loaded is None for t in tabs.values()), "nothing is fetched until a tab is shown")
# showing a tab starts its own load
loads = []
for k, t in tabs.items():
    t.load = (lambda kind: (lambda refresh=False: loads.append(kind)))(k)
for i in (2, 3, 4):
    panel._tab_shown(i)
ok(loads == ["hdris", "materials", "models"], "each tab loads its own kind when shown: %s" % loads)
print("FAILS:", fails); sys.exit(1 if fails else 0)
