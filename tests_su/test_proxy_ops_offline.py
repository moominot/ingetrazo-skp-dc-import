"""asset_manager: Make proxy / Show original / Show proxy from the right-click menu.
Offscreen, IngeTrazo's own undo history.
argv: <ingetrazo-src> <extension repo> [proxy_tool.py of the Proxies extension]"""
import importlib.util, os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = tempfile.mkdtemp(); os.environ["ASSET_MANAGER_HOME"] = home
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PROXIES = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMenu, QWidget
QCoreApplication.setOrganizationName("asset_manager_test")
QCoreApplication.setApplicationName(f"t{os.getpid()}")
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QMatrix4x4, QVector3D
from core.group import Group, copy_group, iter_placements
from core.history import History
from core.materials import Material
from core.mesh import Mesh
from core.scene import Scene
from formats import igz
from asset_manager import proxy, proxy_ops

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

def box(w, d, h, mat=None):
    m = Mesh(); P = lambda a, b, c: QVector3D(a, b, c)
    for q in ([P(0,0,0),P(0,d,0),P(w,d,0),P(w,0,0)], [P(0,0,h),P(w,0,h),P(w,d,h),P(0,d,h)],
              [P(0,0,0),P(w,0,0),P(w,0,h),P(0,0,h)], [P(0,d,0),P(0,d,h),P(w,d,h),P(w,d,0)],
              [P(0,0,0),P(0,0,h),P(0,d,h),P(0,d,0)], [P(w,0,0),P(w,d,0),P(w,d,h),P(w,0,h)]):
        f = m.add_face(q)
        if mat:
            f.attrs["mat"] = mat; f.attrs["color"] = (0.6, 0.4, 0.2, 1.0)
    return m

def faces(g): return sum(len(pg.mesh.faces) for pg, _m in iter_placements(g))

work = Path(tempfile.mkdtemp())
doc = work / "pati.igz"

class Win:
    _current_path = doc

class VP:
    def __init__(self):
        self.scene = Scene(); self.history = History(self.scene); self.messages = []
    def window(self): return Win()
    def flash_status(self, text, ms=0): self.messages.append(text)
    def notify_scene_changed(self): pass
    def update(self): pass

vp = VP(); scene = vp.scene
scene.materials["Fusta"] = Material("Fusta", color=(0.6, 0.4, 0.2))
arbre = Group(box(1, 1, 3, "Fusta"), name="Arbre")
arbre.xform = QMatrix4x4(); arbre.xform.translate(2, 0, 0)
fulla = Group(box(0.5, 0.5, 0.5), name="Fulla"); fulla.xform = QMatrix4x4(); fulla.xform.translate(0.25, 0.25, 3)
arbre.children = [fulla]
arbre.ext = {"render_studio": {"lights": [{"id": "l1"}]}}
copia = copy_group(arbre, QVector3D(3, 0, 0))
banc = Group(box(2, 0.5, 0.5), name="Banc")                      # a classic group (no matrix)
barana = Group(box(3, 0.1, 1), name="Barana"); barana.xform = QMatrix4x4()
barana.ext = {"skp_dc_import": {"definition": "Barana", "definition_attributes": {"lenx": 3},
                                "instance_attributes": {}}}
scene.groups += [arbre, copia, banc, barana]

# --- what the menu offers -------------------------------------------------------------
face = arbre.mesh.faces[0]
ok(proxy_ops.offers(scene, [fulla])["make"] == [], "a part not at top level offers nothing by itself")
ok(proxy_ops.offers(scene, [arbre, banc])["make"] == [arbre, banc], "plain objects: Make proxy")

# --- Make proxy -----------------------------------------------------------------------------
full_mesh, n_undo = arbre.mesh, len(vp.history.undo_stack)
ok(proxy_ops.make_proxies(vp, [arbre]) == 1, "Make proxy on one copy of a component")
info = proxy.info_of(arbre)
ok(info and proxy.info_of(copia) and proxy.info_of(copia)["id"] == info["id"] and arbre.mesh is copia.mesh,
   "every copy becomes the same proxy (one envelope)")
ok(not arbre.children and arbre.mesh is not full_mesh and len(arbre.mesh.faces) >= 8, "the envelope, no parts")
ok(arbre.ext.get("render_studio") == {"lights": [{"id": "l1"}]}, "its lights stay on it")
ok(Path(info["file"]).parent == work / "pati_proxies" and Path(info["file"]).is_file(), "the original goes next to the drawing")
ok(len(vp.history.undo_stack) == n_undo + 1, "one undo step")
vp.history.undo()
ok(arbre.mesh is full_mesh and arbre.children == [fulla] and proxy.info_of(arbre) is None and proxy.info_of(copia) is None,
   "undo: the model as it was")
vp.history.redo()
ok(proxy.info_of(arbre) is not None and not arbre.children, "redo: a proxy again")
ok(proxy_ops.offers(scene, [arbre])["original"] == [arbre], "a proxy offers Show original")

# --- Show original ----------------------------------------------------------------------------
scene.materials.pop("Fusta")                    # a drawing that has not got the material
n, missing = proxy_ops.show_originals(vp, [copia])
ok(n == 1 and not missing and faces(arbre) == 12 and faces(copia) == 12 and arbre.mesh is copia.mesh,
   "Show original: the full model back, both copies sharing it")
ok(len(arbre.children) == 1 and len(copia.children) == 1 and arbre.children[0] is not copia.children[0],
   "each copy gets its parts back")
ok("Fusta" in scene.materials, "the original's material is registered again")
ok(proxy_ops.state(arbre) == "original" and proxy_ops.offers(scene, [arbre])["proxy"] == [arbre],
   "still a proxy, showing its original: offers Show proxy")
vp.history.undo()
ok(not arbre.children and "Fusta" not in scene.materials, "undo: the envelope again, the material taken back")
vp.history.redo()

# --- Edit the original, then Show proxy: the file gets the edit -------------------------------------
arbre.mesh.add_face([QVector3D(0, 0, 5), QVector3D(1, 0, 5), QVector3D(1, 1, 5)])
n, failed = proxy_ops.show_proxies(vp, [arbre])
ok(n == 1 and not failed and not arbre.children and proxy_ops.state(copia) == "proxy", "Show proxy: back to the envelope")
b = proxy.bounds(arbre)
ok(abs(float(b[1][2]) - 5.0) < 1e-6, "the envelope follows the edit (5 m tall now)")
back = Scene(); igz.load_into(back, proxy.original_file(proxy.info_of(arbre), vp))
ok(faces(back.groups[0]) == 13, "the edited original was written to its file")
proxy_ops.show_originals(vp, [arbre])
ok(faces(arbre) == 13, "shown again: the edit is there")
proxy_ops.show_proxies(vp, [arbre])

# --- A classic group --------------------------------------------------------------------------
w0 = proxy.bounds(banc)
proxy_ops.make_proxies(vp, [banc])
ok(banc.xform is None and proxy.info_of(banc)["local"] is False
   and [round(float(v), 6) for v in (*proxy.bounds(banc)[0], *proxy.bounds(banc)[1])]
   == [round(float(v), 6) for v in (*w0[0], *w0[1])], "a classic group: its envelope where it was")
proxy_ops.show_originals(vp, [banc])
ok(faces(banc) == 6 and banc.xform is None, "and its full model back in place")

# --- Dynamic components ------------------------------------------------------------------------
asked = []
ok(proxy_ops.make_proxies(vp, [barana], confirm=lambda names: asked.append(names) or False) == 0
   and asked == [["Barana"]] and proxy.info_of(barana) is None, "dynamic components: asked; No leaves it")
proxy_ops.make_proxies(vp, [barana], confirm=lambda names: True)
ok(proxy.info_of(barana) is not None and "skp_dc_import" not in barana.ext and proxy.info_of(barana)["dynamic"],
   "Yes: a proxy, its dynamic data put away (the options panel leaves it alone)")
proxy_ops.show_originals(vp, [barana])
ok(barana.ext.get("skp_dc_import", {}).get("definition_attributes") == {"lenx": 3},
   "Show original: the dynamic data comes back with it")

# --- A missing file -----------------------------------------------------------------------------
proxy_ops.show_proxies(vp, [banc])
os.remove(proxy.original_file(proxy.info_of(banc), vp))
n, missing = proxy_ops.show_originals(vp, [banc])
ok(n == 0 and missing == ["Banc"] and proxy_ops.state(banc) == "proxy", "an original whose file is gone: named, left as it is")

# --- Open the original in its own tab; saved there, the proxy takes it -----------------------------
class Window:
    def __init__(self): self.opened = []
    def open_path(self, path): self.opened.append(Path(path)); return True
win = Window()
ok(proxy_ops.offers(scene, [arbre])["open"] == [arbre], "a proxy offers Open original in a new tab")
opened, missing = proxy_ops.open_originals(win, vp, [arbre, copia, banc])
f_arbre = proxy.original_file(proxy.info_of(arbre), vp)
ok(opened == [f_arbre] and win.opened == [f_arbre] and missing == ["Banc"],
   "one tab per original file (the copies share it), the missing one named")
ok(proxy_ops.refresh_changed(vp) == [], "nothing saved meanwhile: nothing to update")
# What the user does in that tab: edit the original and save it.
tab = Scene(); igz.load_into(tab, f_arbre)
tab.groups[0].mesh.add_face([QVector3D(0, 0, 8), QVector3D(1, 0, 8), QVector3D(1, 1, 8)])
import time; time.sleep(0.05)
igz.save_scene(tab, f_arbre)
n_undo = len(vp.history.undo_stack)
names = proxy_ops.refresh_changed(vp)
ok(names == ["Arbre"] and abs(float(proxy.bounds(arbre)[1][2]) - 8.0) < 1e-6 and arbre.mesh is copia.mesh,
   "back in the drawing: the envelope follows the saved original (8 m now), both copies")
ok(len(vp.history.undo_stack) == n_undo + 1 and proxy.info_of(arbre)["faces"] == 14, "one undo step, its data updated")
ok(proxy_ops.refresh_changed(vp) == [], "and only once")
proxy_ops.show_originals(vp, [arbre])
ok(faces(arbre) == 14, "Show original brings the saved edit")
proxy_ops.show_proxies(vp, [arbre])
ok(proxy_ops.refresh_changed(vp) == [], "Show proxy's own save is not taken for an outside edit")

# --- The right-click menu -------------------------------------------------------------------------
class App:
    api_version = 2
    def __init__(self, vp):
        self.viewport = vp; self.scene = vp.scene; self.window = QWidget(); self.window.viewport = None
        self.menus = []
    def add_panel(self, *a, **k): return QWidget()
    def show_panel(self, dock): pass
    def add_menu_action(self, *a, **k): return None
    def add_context_menu(self, fn): self.menus.append(fn)
    def on_document_changed(self, fn): pass
import asset_manager
vp2 = VP(); s2 = vp2.scene
t1 = Group(box(1, 1, 2), name="Taula"); t1.xform = QMatrix4x4(); s2.groups.append(t1)
app = App(vp2); asset_manager.setup(app)
def entries(sel):
    m = QMenu()
    for fn in app.menus:
        fn(m, sel)
    return [a.text() for a in m.actions()]
ok("Make proxy" in entries([t1]), f"the menu offers Make proxy ({entries([t1])})")
proxy_ops.make_proxies(vp2, [t1])
ok("Show original" in entries([t1]) and "Make proxy" not in entries([t1])
   and "Open original in a new tab" in entries([t1]), "on a proxy: Show original, Open original in a new tab")
proxy_ops.show_originals(vp2, [t1])
ok("Show proxy" in entries([t1]), "on a shown original: Show proxy")
ok(not any("proxy" in e.lower() or "original" in e.lower() for e in entries([])), "nothing selected: no proxy entries")

# --- The Proxies extension on proxies made here -------------------------------------------------------
if PROXIES:
    spec = importlib.util.spec_from_file_location("proxy_tool_under_test", PROXIES)
    pt = importlib.util.module_from_spec(spec); spec.loader.exec_module(pt)
    scene.selection.clear()
    pt.show_originals(vp)
    ok(faces(arbre) == 14 and proxy.info_of(arbre)["state"] == "original", "Proxies: Show Originals works on them")
    pt.show_proxies(vp)
    ok(not arbre.children and proxy.info_of(arbre)["state"] == "proxy", "Proxies: Show Proxies too")
    ok(proxy_ops.show_originals(vp, [arbre])[0] == 1 and faces(arbre) == 14, "and ours after theirs")

print("ALL OK" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
