"""The three-tab Library, offscreen, no network. argv: <ingetrazo-src> <folder holding asset_manager> [png dir]"""
import os, sys, tempfile, pathlib, zipfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = tempfile.mkdtemp(); os.environ["ASSET_MANAGER_HOME"] = home
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtWidgets import QApplication, QWidget, QFileDialog, QInputDialog
QCoreApplication.setOrganizationName("asset_manager_test")
QCoreApplication.setApplicationName(f"t{os.getpid()}")
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, home)
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QMatrix4x4, QVector3D, QImage, QColor
from core.scene import Scene
from core.group import Group, copy_group
from core.mesh import Mesh
from core.materials import Material
from asset_manager import catalog, export, tags, kind_page, stand_in, polyhaven
from asset_manager.panel import AssetPanel

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

def box():
    m = Mesh(); P = QVector3D
    for q in ([P(0,0,0),P(0,1,0),P(1,1,0),P(1,0,0)], [P(0,0,1),P(1,0,1),P(1,1,1),P(0,1,1)],
              [P(0,0,0),P(1,0,0),P(1,0,1),P(0,0,1)], [P(0,1,0),P(0,1,1),P(1,1,1),P(1,1,0)],
              [P(0,0,0),P(0,0,1),P(0,1,1),P(0,1,0)], [P(1,0,0),P(1,1,0),P(1,1,1),P(1,0,1)]):
        m.add_face(q)
    return m

def comp(name, x):
    g = Group(box(), name=name); t = QMatrix4x4(); t.translate(QVector3D(x, 0, 0)); g.xform = t; g.component = True
    return g

scene = Scene()
taula = comp("Taula", 0)
scene.groups += [taula, copy_group(taula, QVector3D(2, 0, 0)), comp("Cadira", 5)]
scene.materials["Vermell"] = Material("Vermell", color=(1.0, 0.0, 0.0))

cat = catalog.default_folder(); cat.mkdir(parents=True)
(cat / "porta.igz").write_bytes(b"x")
img = QImage(8, 8, QImage.Format_RGB32); img.fill(QColor(10, 80, 200))
(cat / "cel.hdr").write_bytes(b"hdr")
catalog.save_material("Blau", rgb=(0.0, 0.0, 1.0))

class Win(QWidget):
    def __init__(self):
        super().__init__(); self.placed = []
    def _activate_tool(self, name): pass
    def _start_place(self, group, anchor=None): self.placed.append(group)
    def _replacement_choices(self, sel): return [("Other  (1×)", scene.groups[-1])]
    def replace_selection_with(self, source): self.replaced = len(scene.selection); return self.replaced
class History:
    def execute(self, cmd): cmd.do(scene)
    def undo(self): pass
class VP(QWidget):
    def __init__(self, win): super().__init__(win); self.scene = scene; self.history = History()
    def set_active_tool(self, t): pass
    def flash_status(self, *a): pass
    def notify_scene_changed(self): pass
    def end_group_edit(self): pass
    def begin_group_edit(self, g): self.edited = g
    def update(self): pass
win = Win(); vp = VP(win); win.viewport = vp
class App:
    api_version = 2
    def __init__(self): self.scene = scene; self.window = win; self.viewport = vp
    def on_document_changed(self, fn): pass

panel = AssetPanel(App())
panel.resize(340, 600); panel.show(); qa.processEvents()
ok([panel.tabs.tabText(i) for i in range(panel.tabs.count())] == ["Models", "Materials", "Backgrounds"], "three tabs only")
models, mats, hdris = (panel.pages[k] for k in ("models", "materials", "hdris"))
def sources(p): return [p.source.itemData(i) for i in range(p.source.count()) if p.source.itemData(i)]
ok(sources(models)[:2] == ["drawing", "cat:"] and "cat:" + str(cat) in sources(models) and "online:polyhaven" in sources(models),
   f"models' sources: drawing, catalog and its folders, online ({sources(models)})")
ok("drawing" not in sources(hdris) and {"online:polyhaven", "online:ambientcg"} <= set(sources(hdris))
   and {"online:polyhaven", "online:ambientcg"} <= set(sources(mats)), "backgrounds have no drawing source; both sites where they offer the kind")
def names(p): return [p.list.item(i).text() for i in range(p.list.count())]
ok(names(models) == ["porta"], f"catalog models only ({names(models)})")
ok(models.proxy_action is not None and mats.proxy_action is None and hdris.proxy_action is None
   and models.insert_btn.menu() is not None, "Insert has «Insert as proxy» under its arrow, for models only")
panel.tabs.setCurrentIndex(1); qa.processEvents()
ok(names(mats) == ["Blau"], f"materials tab ({names(mats)})")
panel.tabs.setCurrentIndex(2); qa.processEvents()
ok(names(hdris) == ["cel"], f"backgrounds tab ({names(hdris)})")

panel.tabs.setCurrentIndex(0); models.set_source("drawing"); qa.processEvents()
ok(names(models) == ["Cadira  ×1", "Taula  ×2"], f"the drawing's components ({names(models)})")
models.list.setCurrentRow(1); entry = models.list.currentItem().data(Qt.UserRole)
ok(models.save_btn.isEnabled() and models.export_btn.isEnabled() and not models.proxy_action.isEnabled(), "buttons for a drawing component")
models.insert()
ok(win.placed and win.placed[-1].mesh is taula.mesh, "Insert places a copy of it")
acts = [a.text() for a in models.context_menu_for(models.list.currentItem()).actions() if a.text()]
ok(acts == ["Insert", "Categories…", "Select all", "Replace all…", "Edit", "Stand-in: not rendered, shown translucent"], f"right-click ({acts})")
panel.select_like(entry.sample); ok(len(scene.selection) == 2, "Select all")
panel.edit_component(entry); ok(vp.edited is entry.sample, "Edit")
QInputDialog.getItem = staticmethod(lambda *a, **k: ("Other  (1×)", True))
panel.replace_all(entry); ok(win.replaced == 2, "Replace all")
models.list.setCurrentRow(1)

# categories
tags.update({"drawing:model:Taula": ["Mobles", "Cuina"]}); models.fill()
cats = [models.category.itemData(i) for i in range(models.category.count())]
ok(cats == ["", "Cuina", "Mobles"], f"category filter lists the tags ({cats})")
models.category.setCurrentIndex(models.category.findData("Cuina"))
ok(names(models) == ["Taula  ×2"], "filtered by category")
models.category.setCurrentIndex(0)
models.search.setText("cad"); ok(names(models) == ["Cadira  ×1"], "search by name"); models.search.setText("")
dlg = kind_page.TagsDialog(panel, [["Mobles"], []], ["Mobles", "Exterior"])
states = {dlg.list.item(i).text(): dlg.list.item(i).checkState() for i in range(dlg.list.count())}
ok(states == {"Exterior": Qt.Unchecked, "Mobles": Qt.PartiallyChecked}, "dialog: ticked, half-ticked")
dlg.list.item(0).setCheckState(Qt.Checked); dlg.new.setText("nova, Nova ;altra")
ok(dlg.result_for(["Mobles"]) == ["altra", "Exterior", "Mobles", "nova"] and dlg.result_for([]) == ["altra", "Exterior", "nova"],
   "…new and ticked ones added, a half-ticked one stays as it was")

# save a component to the catalog, with its categories; export it
models.list.setCurrentRow(1); models.save()
saved = cat / "Models" / "Taula" / "Taula.igz"
ok(saved.is_file() and saved.with_suffix(".png").is_file(), "Save to catalog: an .igz with its picture")
ok(any(tags.get(i.key) == ["Cuina", "Mobles"] for i in catalog.scan() if i.path == saved), "…keeping its categories")
from formats import igz
back = Scene(); igz.load_into(back, saved)
ok(len(back.groups) == 1 and len(back.groups[0].mesh.faces) == 6 and "proxy_tool" not in (back.groups[0].ext or {}), "…that reads back as the component")
out = pathlib.Path(tempfile.mkdtemp())
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out / "exportada"), ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(out))
models.export(); ok((out / "exportada.igz").is_file(), "Export a component as .igz")
models.set_source("cat:"); models.list.setCurrentRow(0)
ok(not models.save_btn.isEnabled() and models.export_btn.isEnabled() and models.proxy_action.isEnabled(), "buttons for a catalog model")

# materials: drawing -> catalog, export
panel.tabs.setCurrentIndex(1); mats.set_source("drawing"); qa.processEvents()
ok(names(mats) == ["Vermell"], "the drawing's materials")
mats.list.setCurrentRow(0); mats.export()
ok(any(out.rglob("Vermell*")), f"Export a drawing material ({[p.name for p in out.rglob('Vermell*')]})")
tags.update({"drawing:material:Vermell": ["Pintura"]}); mats.fill(); mats.list.setCurrentRow(0); mats.save(); qa.processEvents()
mats.set_source("cat:")
item = next((i for i in panel._cat_items if i.name == "Vermell"), None)
ok(item is not None and tags.get(item.key) == ["Pintura"], "saved with its categories")
for r in range(mats.list.count()):
    if mats.list.item(r).text() == "Blau": mats.list.setCurrentRow(r)
n_before = len(list(out.iterdir())); mats.export()
ok(len(list(out.iterdir())) == n_before + 1 and any((out / "Blau").glob("*.pbr.json")), "Export a catalog material")
ok(not any(i.name == "Blau" and i.path.parent.parent == out for i in catalog.scan()), "…without adding it to the catalog")
panel.tabs.setCurrentIndex(2); hdris.list.setCurrentRow(0)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out / "fons.hdr"), ""))
hdris.export(); ok((out / "fons.hdr").read_bytes() == b"hdr", "Export a background")

# online (a fake site)
class Fake:
    key = "polyhaven"; label = "Poly Haven"
    def listing(self, kind, done, refresh=False):
        done([{"id": "a", "name": "Arbre", "categories": ["trees", "outdoor"], "tags": []},
              {"id": "b", "name": "Banc", "categories": ["furniture"], "tags": []}], None)
    def thumbnail(self, e, done): pass
    def forget_thumbs(self): pass
    def cached(self, *a): return None
    def site(self, e): return ""
    def tile_size_m(self, e): return (1.0, 1.0)
    def thumb_path(self, e): return None
    def download(self, kind, e, res, done, progress=None, confirm=None):
        d = pathlib.Path(tempfile.mkdtemp()) / "x"; d.mkdir(); (d / "arbre.gltf").write_text("{}"); (d / "arbre.bin").write_bytes(b"b")
        done(d / "arbre.gltf", None)
panel._sources["polyhaven"] = Fake()
panel.tabs.setCurrentIndex(0); models.set_source("online:polyhaven"); qa.processEvents()
ok(names(models) == ["Arbre", "Banc"] and models.res.isVisibleTo(panel), "online list, with the size box")
ok([models.category.itemData(i) for i in range(models.category.count())][0] == "" and models.category.findData("trees") > 0, "the site's categories")
models.category.setCurrentIndex(models.category.findData("furniture")); ok(names(models) == ["Banc"], "online filtered by category")
models.category.setCurrentIndex(0); models.list.setCurrentRow(0); models.save()
got = next((i for i in catalog.scan() if i.name == "arbre" or i.name == "Arbre"), None)
ok(got is not None and tags.get(got.key) == ["outdoor", "trees"], "saved online model keeps the site's categories")
before = {p.name for p in out.iterdir()}; models.export()
new = [p for p in out.iterdir() if p.name not in before]
ok(len(new) == 1 and {q.name for q in new[0].iterdir()} == {"arbre.gltf", "arbre.bin"}, "Export a downloaded model with its files")

# insert as proxy asks for the proxy; plain Insert does not
seen = []
panel._model_group = lambda path, interactive=True: (seen.append(panel._proxy_wanted), None)[1]
models.set_source("cat:"); models.list.setCurrentRow(0)
models.insert(); models.proxy_action.trigger()
ok(seen == [False, True] and panel._proxy_wanted is False, f"Insert / Insert as proxy ({seen})")
models.fill_menu()
ok([a.text() for a in models.menu_btn.menu().actions() if a.text()][:3] == ["Add a catalog folder…", "Take the shown folder off the catalog", "Open a model site"], "the menu button")

if PNG:
    tags.update({"drawing:model:Taula": ["Mobles"]})
    models.set_source("drawing"); panel.tabs.setCurrentIndex(0); qa.processEvents()
    for i in range(models.list.count()): models._icon(models.list.item(i))
    models.list.setCurrentRow(1); qa.processEvents()
    panel.grab().save(os.path.join(PNG, "library.png"))
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
