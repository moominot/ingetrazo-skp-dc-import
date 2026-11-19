"""asset_manager: inventory, thumbnails, catalog, panel. Offscreen.
argv: <ingetrazo-src> <extension repo> [png dir]"""
import os, sys, tempfile, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = tempfile.mkdtemp(); os.environ["ASSET_MANAGER_HOME"] = home
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QVector3D, QMatrix4x4
from core.scene import Scene
from core.group import Group
from core.mesh import Mesh
from asset_manager import inventory, thumbs, catalog
from asset_manager.panel import AssetPanel

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

def box(w, d, h):
    m = Mesh(); P = lambda a, b, c: QVector3D(a, b, c)
    for q in ([P(0,0,0),P(0,d,0),P(w,d,0),P(w,0,0)], [P(0,0,h),P(w,0,h),P(w,d,h),P(0,d,h)],
              [P(0,0,0),P(w,0,0),P(w,0,h),P(0,0,h)], [P(0,d,0),P(0,d,h),P(w,d,h),P(w,d,0)],
              [P(0,0,0),P(0,0,h),P(0,d,h),P(0,d,0)], [P(w,0,0),P(w,d,0),P(w,d,h),P(w,0,h)]):
        m.add_face(q)
    return m

def comp(name, x, dyn=False):
    g = Group(box(1, 1, 2), name=name)
    t = QMatrix4x4(); t.translate(QVector3D(x, 0, 0)); g.xform = t
    if dyn:
        g.ext = {"skp_dc_import": {"definition": name, "definition_attributes": {"lenx": 1},
                                   "instance_attributes": {}}}
    return g

scene = Scene()
scene.groups += [comp("Armari", 0, True), comp("Armari", 3, True), comp("Taula", 6)]
entries = inventory.components_in(scene)
ok([ (e.name, e.count, e.dynamic) for e in entries] == [("Armari", 2, True), ("Taula", 1, False)],
   "inventory groups by name, counts and flags dynamic")
ok(inventory.components_in(Scene()) == [], "empty scene -> no components")
px = thumbs.render(entries[0].sample, 64)
img = px.toImage()
painted = sum(1 for x in range(64) for y in range(64) if img.pixelColor(x, y).alpha() > 0)
ok(painted > 300, f"thumbnail has content ({painted} px)")
ok(thumbs.render(Group(Mesh(), name="buit"), 64).toImage().pixelColor(32, 32).alpha() == 0, "empty component -> blank thumbnail")

# catalog
cat = catalog.default_folder(); cat.mkdir(parents=True)
(cat / "porta.igz").write_bytes(b"x"); (cat / "porta.png").write_bytes(b"")
(cat / "sub").mkdir(); (cat / "sub" / "finestra.igz").write_bytes(b"x")
items = catalog.scan()
ok([i.name for i in items] == ["finestra", "porta"], "catalog lists .igz files, subfolders included")
ok(items[1].preview is not None and items[0].preview is None, "sidecar preview found only where it exists")

class VP:
    def update(self): pass
class App:
    api_version = 2; viewport = VP(); inserted = []
    def __init__(self, s): self.scene = s
    def on_document_changed(self, fn): pass
    def import_igz(self, path): self.inserted.append(path)
app = App(scene)
panel = AssetPanel(app)
ok(panel.scene_list.count() == 2 and "⚙" in panel.scene_list.item(0).text() and "×2" in panel.scene_list.item(0).text(),
   "panel lists components, dynamic marked, with counts")
ok(panel.summary.text() == "2 components, 1 dynamic", "summary line")
panel.scene_list.setCurrentRow(0); panel.select_current()
ok(len(scene.selection) == 2, "Select picks every placement")
ok(panel.cat_list.count() == 2, "panel lists the catalog")
panel.cat_list.setCurrentRow(1); panel.insert_current()
ok(app.inserted and app.inserted[0].endswith("porta.igz"), "Insert calls app.import_igz with the file")
if PNG:
    panel.resize(300, 340); panel.show(); qa.processEvents(); panel.grab().save(os.path.join(PNG, "components.png"))
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
