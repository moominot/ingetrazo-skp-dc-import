"""asset_manager: insert as a proxy. Offscreen, no network.
argv: <ingetrazo-src> <extension repo> [proxy_tool.py of the Proxies extension]

With the Proxies extension's file, also checks that its Show Originals /
Show Proxies work on what the panel inserts."""
import importlib.util, os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = tempfile.mkdtemp(); os.environ["ASSET_MANAGER_HOME"] = home
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PROXIES = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget
QCoreApplication.setOrganizationName("asset_manager_test")
QCoreApplication.setApplicationName(f"t{os.getpid()}")
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QMatrix4x4, QVector3D
from core.scene import Scene
from core.group import Group, iter_placements
from core.mesh import Mesh
from core.materials import Material
from formats import igz
from asset_manager import catalog, place, proxy

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

def box(w, d, h, z=0.0):
    m = Mesh(); P = lambda a, b, c: QVector3D(a, b, c + z)
    for q in ([P(0,0,0),P(0,d,0),P(w,d,0),P(w,0,0)], [P(0,0,h),P(w,0,h),P(w,d,h),P(0,d,h)],
              [P(0,0,0),P(w,0,0),P(w,0,h),P(0,0,h)], [P(0,d,0),P(0,d,h),P(w,d,h),P(w,d,0)],
              [P(0,0,0),P(0,0,h),P(0,d,h),P(0,d,0)], [P(w,0,0),P(w,d,0),P(w,d,h),P(w,0,h)]):
        m.add_face(q)
    return m

work = Path(tempfile.mkdtemp())

def model_file(name, dyn=False):
    """An .igz holding one component: a 1 × 1 × 2 box painted «Fusta» with a
    nested 0.5 m cube on top, 3 m to the right (its frame starts at x = 3)."""
    sc = Scene()
    body = box(1, 1, 2)
    for f in body.faces:
        f.attrs["mat"] = "Fusta"; f.attrs["color"] = (0.6, 0.4, 0.2, 1.0)
    g = Group(body, name=name)
    t = QMatrix4x4(); t.translate(QVector3D(3, 0, 0)); g.xform = t
    kid = Group(box(0.5, 0.5, 0.5), name="Tap")
    k = QMatrix4x4(); k.translate(QVector3D(0.25, 0.25, 2.0)); kid.xform = k
    g.children = [kid]
    if dyn:
        kid.ext = {"skp_dc_import": {"definition": "Tap", "definition_attributes": {"lenx": 1},
                                     "instance_attributes": {}}}
    sc.groups.append(g)
    sc.materials["Fusta"] = Material("Fusta", color=(0.6, 0.4, 0.2))
    path = work / f"{name}.igz"
    igz.save_scene(sc, path)
    return path

class Win:
    def __init__(self, doc): self._current_path = doc

class History:
    def execute(self, cmd): cmd.do(VP.scene)

class VP:
    scene = None
    def __init__(self, doc=None):
        VP.scene = self.scene = Scene(); self._win = Win(doc); self.history = History()
        self.messages = []
    def window(self): return self._win
    def flash_status(self, text, ms=0): self.messages.append(text)
    def notify_scene_changed(self): pass
    def update(self): pass

def faces(g): return sum(len(pg.mesh.faces) for pg, _m in iter_placements(g))

# --- a saved drawing: originals next to it ---------------------------------------
doc = work / "projecte" / "casa.igz"; doc.parent.mkdir()
vp = VP(doc)
src = model_file("Arbre")
g, kind, dyn = place.proxy_from_file(vp, src)
info = proxy.info_of(g)
ok(kind == "proxy" and not dyn, "a model goes in as a proxy")
ok(not g.children and all(len(e.faces) == 2 for e in g.mesh.edges) and len(g.mesh.faces) >= 8,
   f"the proxy is a closed envelope with no parts ({len(g.mesh.faces)} triangles)")
import numpy as np
P_all = proxy.points(Group(box(1, 1, 2)))
P_all = np.vstack([P_all, P_all[:0], np.array([[0.25, 0.25, 2.5], [0.75, 0.75, 2.5], [0.25, 0.75, 2.5], [0.75, 0.25, 2.5]])])
out_by = max(float(np.dot(f.normal().toTuple(), p - np.array(f.loop[0].position.toTuple())))
             for f in g.mesh.faces for p in P_all)
ok(out_by < 1e-6, f"every corner of the model is inside the envelope (worst {out_by:.2e} m outside)")
ok(sum(1 for e in g.mesh.edges if e.soft) > 0 and any(not e.soft for e in g.mesh.edges),
   "its gentle folds are soft, its sharp ones are not")
ok(g.is_component() and g.xform.map(QVector3D(0, 0, 0)) == QVector3D(3, 0, 0),
   "the proxy keeps the model's place (its own axes)")
b = proxy.bounds(g)
ok([round(float(v), 6) for v in (*b[0], *b[1])] == [0, 0, 0, 1, 1, 2.5],
   "the envelope covers the parts too (the cube on top: 2.5 m)")
f = Path(info["file"])
ok(f.parent == doc.parent / "casa_proxies" and f.is_file(), "the original goes to «casa_proxies»")
ok(info["rel"] == os.path.join("casa_proxies", f.name), "its path is kept relative to the drawing")
ok(info["state"] == "proxy" and info["faces"] == 12 and info["proxy_faces"] == len(g.mesh.faces)
   and info["params"]["type"] == "hull" and info["params"]["hull_points"] == 64,
   "proxy data as the Proxies extension writes it (a convex hull)")
ok("Fusta" not in vp.scene.materials, "the model's materials stay out of the drawing")
back = Scene(); igz.load_into(back, f)
orig = back.groups[0]
ok(len(back.groups) == 1 and proxy.info_of(orig) == {"id": info["id"]}, "the original file: one tagged component")
ok(faces(orig) == 12 and len(orig.children) == 1 and orig.xform.isIdentity(),
   "the original keeps its parts, at identity (its definition)")
ok("Fusta" in back.materials, "the original file carries its materials")

vp.scene.groups.append(g)
g2, kind2, _d = place.proxy_from_file(vp, src)
ok(kind2 == "copy" and g2.mesh is g.mesh and proxy.info_of(g2)["id"] == info["id"],
   "the same model again: a copy of the proxy (one definition, nothing read)")
vp.scene.groups.append(g2)

# --- dynamic components: asked first -------------------------------------------------
dsrc = model_file("Barana", dyn=True)
asked = []
gc, kc, dc = place.proxy_from_file(vp, dsrc, lambda name: asked.append(name))
ok(gc is None and dc and asked == ["Barana"], "a model with dynamic components asks; Cancel inserts nothing")
gn, kn, dn = place.proxy_from_file(vp, dsrc, lambda name: "normal")
ok(kn == "normal" and faces(gn) == 12 and proxy.info_of(gn) is None and "Fusta" in vp.scene.materials,
   "«Insert the full model»: the model itself, materials registered")
gp, kp, dp = place.proxy_from_file(vp, dsrc, lambda name: "proxy")
ok(kp == "proxy" and dp and proxy.info_of(gp)["dynamic"], "«Insert as proxy»: a proxy, marked dynamic")
gd, kd, dd = place.proxy_from_file(VP(doc), dsrc)
ok(kd == "proxy" and dd, "while dragging (no question) it goes in as a proxy")

# --- a drawing never saved: the extension's own folder ------------------------------
vp0 = VP(None)
g0, _k, _d = place.proxy_from_file(vp0, src)
i0 = proxy.info_of(g0)
ok(Path(i0["file"]).parent == Path(home) / "proxies" and i0["rel"] is None,
   "unsaved drawing: originals in the extension's folder, absolute path")

# --- flat and empty models ----------------------------------------------------------
m = Mesh(); m.add_face([QVector3D(0,0,0), QVector3D(2,0,0), QVector3D(2,1,0), QVector3D(0,1,0)])
flat = proxy.envelope_mesh(proxy.points(Group(m)))
ok(flat is not None and len(flat.faces) == 1, "a flat model: one rectangle")
ok(proxy.envelope_mesh(proxy.points(Group(Mesh()))) is None, "an empty model: nothing")
rng = np.random.default_rng(1)
cloud = rng.normal(size=(20000, 3)); cloud /= np.linalg.norm(cloud, axis=1)[:, None]
ball = proxy.envelope_mesh(cloud)
nv = len({v for f in ball.faces for v in map(id, f.loop)})
ok(all(len(e.faces) == 2 for e in ball.edges) and nv <= 64 + 6 and len(ball.faces) == 2 * nv - 4,
   f"20,000 points on a sphere: a closed envelope of {nv} points, {len(ball.faces)} triangles")
ok(sum(e.soft for e in ball.edges) == len(ball.edges), "a round model's envelope is smooth (every edge soft)")

# --- the panel: «As proxy» ----------------------------------------------------------
class App:
    def __init__(self):
        self.window = QWidget(); self.window.viewport = None; self.viewport = VP(doc)
        self.scene = self.viewport.scene
    def on_document_changed(self, fn): pass
from asset_manager.panel import AssetPanel
catalog.set_as_proxy(False)
panel = AssetPanel(App())
ok(len(panel._proxy_boxes) == 2 and not any(b.isChecked() for b in panel._proxy_boxes),
   "an «As proxy» box on the catalog and online tabs, off by default")
panel._proxy_boxes[0].setChecked(True)
ok(catalog.as_proxy() and panel._proxy_boxes[1].isChecked(), "one box sets both, and is remembered")
gg = panel._model_group(src, interactive=False)
ok(proxy.info_of(gg) is not None and "as a proxy" in panel.status.text(), "with the box on, a drag inserts the proxy and says so")
panel._proxy_boxes[1].setChecked(False)
ok(proxy.info_of(panel._model_group(src)) is None, "with the box off, the model itself")

# --- the Proxies extension on what was inserted -------------------------------------
if PROXIES:
    spec = importlib.util.spec_from_file_location("proxy_tool_under_test", PROXIES)
    pt = importlib.util.module_from_spec(spec); spec.loader.exec_module(pt)
    ok(pt.proxy_info(g) is not None and pt._resolve(pt.proxy_info(g), vp) == str(f),
       "Proxies: recognises the proxy and finds its original")
    vp.scene.selection.clear()
    vp.scene.materials.pop("Fusta", None)     # registered above by «Insert the full model»
    VP.scene = vp.scene
    n = pt.show_originals(vp)
    ok(n >= 1 and faces(g) == 12 and faces(g2) == 12 and g.mesh is g2.mesh
       and proxy.info_of(g)["state"] == "original", "Proxies: Show Originals brings the model back (both copies)")
    ok("Fusta" in vp.scene.materials, "Proxies: the original's materials come with it")
    pt.show_proxies(vp)
    ok(not g.children and proxy.info_of(g)["state"] == "proxy" and faces(g) != 12,
       f"Proxies: Show Proxies swaps a stand-in back ({len(g.mesh.faces)} faces, its own hull)")

print("ALL OK" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
