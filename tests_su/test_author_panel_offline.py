"""Offscreen: drive the Component Attributes panel like a user on a plain
group of three boards — Make dynamic, add attributes and formulas through
the table, set an option's display rule — then check the result with the
evaluator and the Component Options panel, and that one undo restores.
argv: <ingetrazo-src> <extension repo> <dump dir>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, DUMPS = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT, os.path.dirname(os.path.abspath(__file__))]
from PySide6.QtWidgets import QApplication, QInputDialog
app = QApplication.instance() or QApplication([])
from core.scene import Scene
from core.history import History
from core.group import Group
from core.mesh import Mesh
from dc_tools import ui, ui_author
from dc_tools.dc import apply as A, author as AU
from test_author_offline import part  # noqa: E402  (reuses the board builder; runs its own check too)

scene = Scene()
root = Group(Mesh(), name="armari")
root.adopt([part("lateral", 0, 0, 0, 1.8, 40, 100), part("lateral2", 78.2, 0, 0, 1.8, 40, 100),
            part("prestatge", 1.8, 0, 50, 76.4, 40, 1.8)])
# As IngeTrazo leaves a group of groups (adopt: an identity matrix), and
# drawn away from the origin, so the axes must move to its corner.
from PySide6.QtGui import QMatrix4x4, QVector3D
off = QMatrix4x4(); off.translate(QVector3D(-2.0, 0.5, 0.0))
for c in root.children:
    c.xform = off * c.xform
scene.groups.append(root)
scene.selection.add(root)

class VP:
    def __init__(self, sc):
        self.scene = sc
        self.history = History(sc) if History.__init__.__code__.co_argcount > 1 else History()
    def update(self): pass
    def notify_scene_changed(self): pass
vp = VP(scene)
class FakeApp: viewport = vp
panel = ui_author.AttributesPanel(FakeApp())
panel.show_root(ui_author.selected_top(scene))
print("1 not dynamic yet:", panel.make_btn.isEnabled(), "| title:", panel.title.text()[:60])

QInputDialog.getText = staticmethod(lambda *a, **k: ("armari", True))
panel.make_dynamic()
print("2 made dynamic:", A.is_dynamic_root(panel.root), "| axes at corner:", panel.root.xform is not None)

def select(path):
    panel._select_tree(path); panel.path = tuple(path); panel.show_part()
def set_cell(label, text):
    for r in range(panel.table.rowCount()):
        if panel.table.item(r, 0).text() == label:
            panel.table.item(r, 1).setText(text)
            return
    raise KeyError(label)

QInputDialog.getText = staticmethod(lambda *a, **k: ("n", True))
panel.add_custom(); set_cell("n", "3")
select((1,)); panel.add_attribute("x"); set_cell("X", "=parent!lenx-lenx")
select((2,)); panel.add_attribute("x"); set_cell("X", "=1.8")
panel.add_attribute("lenx"); set_cell("LenX", "=parent!lenx-3.6")
panel.add_attribute("copies"); set_cell("Copies", "=parent!n-1")
panel.add_attribute("z"); set_cell("Z", "=(copy+1)*parent!lenz/parent!n")
print("3 status:", panel.status.text())
print("   shelf rows:", [(panel.table.item(r, 0).text(), panel.table.item(r, 1).text(), panel.table.item(r, 2).text())
                         for r in range(panel.table.rowCount())])

# The option shown to users: n as an editable textbox, labelled.
select(())
for r in range(panel.table.rowCount()):
    if panel.table.item(r, 0).text() == "n":
        panel.table.setCurrentCell(r, 1)
dlg = ui_author.OptionsDialog(panel, "n", AU.merged(panel.root))
dlg.label.setText("Number of shelves"); dlg.access.setCurrentIndex(2); dlg.units.setCurrentIndex(dlg.units.findData("INTEGER"))
panel._commit(dlg.changes("n"), "n: options saved.")
g = scene.groups[0]
def n(g): return 1 + sum(n(c) for c in g.children or ())
print("4 parts now:", n(g), "| shelves:", sum(1 for c in g.children if (AU.merged(c).get("_name") == "prestatge")))

op = ui.OptionsPanel(FakeApp())
op.show_group(ui.selected_root(scene), force=True)
print("5 options a user sees:", [(o.label, w.text() if hasattr(w, "text") else "") for o, w, _ in op.rows])
op.rows[0][1].setText("5"); op.apply()
g = scene.groups[0]
print("6 after typing 5 shelves:", sum(1 for c in g.children if AU.merged(c).get("_name") == "prestatge"), "shelves |", op.status.text())
def wpos(c):
    d = (g.xform * c.xform).data()
    return (round(d[12] * 100, 2), round(d[13] * 100, 2), round(d[14] * 100, 2))
got = sorted((AU.merged(c).get("_name") or c.name, wpos(c)) for c in g.children)
want = sorted([("lateral", (-200.0, 50.0, 0.0)), ("lateral2", (-121.8, 50.0, 0.0))] +
              [("prestatge", (-198.2, 50.0, z)) for z in (20.0, 40.0, 60.0, 80.0, 100.0)])
print("6b world positions (cm):", "OK" if got == want else f"BAD {got}")
steps = 0
while vp.history.undo() if hasattr(vp.history, "undo") else False:
    steps += 1
print("7 undo steps:", steps, "| back to the plain group:", scene.groups[0] is root, "| dynamic:", A.is_dynamic_root(scene.groups[0]))
