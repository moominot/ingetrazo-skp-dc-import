"""Offscreen: build the panel for the window, change two options as a user
would (type 3 leaves, pick PRACTICABLE), Apply, and compare with SketchUp.
argv: <ingetrazo-src> <extension repo> <skp> <dump dir>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP, DUMPS = [os.path.abspath(a) for a in sys.argv[1:5]]
sys.path[:0] = [SRC, EXT, os.path.dirname(os.path.abspath(__file__))]
os.chdir(DUMPS)
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit
app = QApplication.instance() or QApplication([])
from core.scene import Scene
from skp_dc_import import builder, reader
from dc_tools import ui
from dc_tools.dc import apply as A
import dc_harness as H

class History:
    last_error = None
    def execute(self, cmd):
        try:
            cmd.do(self.scene) if hasattr(cmd, "do") else cmd(self.scene)
        except TypeError:
            cmd.redo(self.scene)

class VP:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(); self.history.scene = scene
    def update(self): pass

class FakeApp:
    def __init__(self, vp): self.viewport = vp

scene = Scene(); builder.build(scene, reader.parse(SKP), SKP)
root = next(g for g in scene.groups if ((g.ext or {}).get(A.KEY) or {}).get("definition") == 'FINESTRA SIMPLE#34')
scene.selection.add(root)
vp = VP(scene)
panel = ui.OptionsPanel(FakeApp(vp))
panel.show_group(ui.selected_root(scene))
labels = {opt.label: (opt, w) for opt, w, _ in panel.rows}
print('rows:', len(panel.rows), '| AMPLE shows', labels['AMPLE'][1].text(), '| NUM FULLES', labels['NUM FULLES'][1].text())
labels['NUM FULLES'][1].setText('3')
combo = labels['TIPUS DE FINESTRA'][1]
combo.setCurrentIndex([combo.itemText(i) for i in range(combo.count())].index('PRACTICABLE'))
opts, errs = panel._collect()
print('collected', opts, errs)
