"""asset_manager: inventory, instances, thumbnails, catalog folders, Poly
Haven logic, drag-and-drop placement, settings. Offscreen, no network.
argv: <ingetrazo-src> <extension repo> [png dir]"""
import os, sys, tempfile, pathlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = tempfile.mkdtemp(); os.environ["ASSET_MANAGER_HOME"] = home
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtCore import QCoreApplication, QMimeData, QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QWidget
QCoreApplication.setOrganizationName("asset_manager_test")
QCoreApplication.setApplicationName(f"t{os.getpid()}")
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMatrix4x4, QVector3D
from core.scene import Scene
from core.group import Group, copy_group
from core.mesh import Mesh
from asset_manager import catalog, inventory, place, polyhaven, thumbs
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

def comp(name, x, dyn=False, mesh=None):
    g = Group(mesh or box(1, 1, 2), name=name)
    t = QMatrix4x4(); t.translate(QVector3D(x, 0, 0)); g.xform = t
    if dyn:
        g.ext = {"skp_dc_import": {"definition": name, "definition_attributes": {"lenx": 1},
                                   "instance_attributes": {}}}
    return g

# --- inventory -------------------------------------------------------------------
scene = Scene()
taula = comp("Taula", 6)
scene.groups += [comp("Armari", 0, True), comp("Armari#2", 3, True), taula, copy_group(taula, QVector3D(2, 0, 0))]
entries = inventory.components_in(scene)
ok([(e.name, e.count, e.dynamic) for e in entries] == [("Armari", 2, True), ("Taula", 2, False)],
   "inventory groups by definition («Armari#2» is still Armari; copies share the mesh)")
ok(inventory.components_in(Scene()) == [], "empty scene -> no components")
other = comp("Taula", 9)                       # same name, its own definition
scene.groups.append(other)
ok(len(inventory.components_in(scene)) == 3, "same name but another definition -> its own entry")
scene.groups.remove(other)

rail = comp("Barana", 0, True)
rail.children = [comp("Lama", 0, True), comp("Lama copy 001", 1, True)]
holder = Group(Mesh(), name="Grup")
chair = comp("Cadira", 0)
holder.children = [chair, copy_group(chair)]
s2 = Scene(); s2.groups += [rail, holder, copy_group(chair, QVector3D(5, 0, 0))]
ok([(e.name, e.count) for e in inventory.components_in(s2)] == [("Barana", 1), ("Cadira", 3)],
   "inner parts of a dynamic component are hidden, nested components kept")
here, total = inventory.instances_of(s2, inventory.definition_key(chair))
ok(len(here) == 1 and total == 3, "instances: 1 selectable at the top, 3 in the model")
ok(inventory.selected_component([rail]) is rail and inventory.selected_component([rail, chair]) is None,
   "selected_component: one component, else None")

px = thumbs.render(entries[0].sample, 64)
img = px.toImage()
painted = sum(1 for x in range(64) for y in range(64) if img.pixelColor(x, y).alpha() > 0)
ok(painted > 300, f"thumbnail has content ({painted} px)")
ok(thumbs.render(Group(Mesh(), name="buit"), 64).toImage().pixelColor(32, 32).alpha() == 0, "empty component -> blank thumbnail")

# A big tree must never be merged into one mesh just to draw an icon: on a
# 3.6 M-face component world_mesh took tens of seconds (2026-11-20, the user's model).
import core.group as _cg
_real_world_mesh = _cg.world_mesh
def _forbidden(*_a, **_k):
    raise AssertionError("thumbs.render must not merge placements")
_cg.world_mesh = _forbidden
try:
    import time as _time
    t0 = _time.perf_counter()
    px = thumbs.render(entries[0].sample, 64)
    img = px.toImage()
    painted = sum(1 for x in range(64) for y in range(64) if img.pixelColor(x, y).alpha() > 0)
    ok(painted > 300, f"thumbnail drawn without world_mesh ({painted} px)")
    ok(_time.perf_counter() - t0 < 2.0, "thumbnail of a small component is fast")
finally:
    _cg.world_mesh = _real_world_mesh

# --- catalog -----------------------------------------------------------------------
cat = catalog.default_folder(); cat.mkdir(parents=True)
(cat / "porta.igz").write_bytes(b"x"); (cat / "porta.png").write_bytes(b"")
(cat / "sub").mkdir(); (cat / "sub" / "finestra.igz").write_bytes(b"x")
lib = pathlib.Path(tempfile.mkdtemp())
png = b"\x89PNG\r\n\x1a\n" + b"\0" * 20 + b"IEND\xaeB`\x82"
(lib / "Barana.skp").write_bytes(b"\xff\xfe\xff\x0eS\0k\0" + b"\1" * 140 + png + b"rest")
(lib / "notes.txt").write_text("x")
ok([i.name for i in catalog.scan()] == ["finestra", "porta"], "catalog lists .igz files, subfolders included")
ok(catalog.add_folder(lib) and not catalog.add_folder(lib), "a folder is added once")
items = catalog.scan()
ok([(i.name, i.kind) for i in items] == [("Barana", "skp"), ("finestra", "igz"), ("porta", "igz")],
   "every folder scanned; .skp included, other files left out")
ok(catalog.skp_preview(lib / "Barana.skp") == png, "the .skp's own PNG preview is found")
ok(catalog.skp_preview(cat / "porta.igz") is None, "no preview -> None")
porta = next(i for i in items if i.name == "porta")
ok(porta.preview is not None and next(i for i in items if i.name == "finestra").preview is None,
   "sidecar preview found only where it exists")
ok(not catalog.remove_folder(cat) and catalog.remove_folder(lib) and catalog.folders() == [cat],
   "the own folder stays; an added one can be removed")
catalog.add_folder(lib)

# sites and watched folders
ok(catalog.valid_url("https://example.com/models") and not catalog.valid_url("file:///c:/x")
   and not catalog.valid_url("javascript:alert(1)") and not catalog.valid_url("example.com"),
   "only http(s) addresses are sites")
catalog.set_sites([("Models", "https://www.example.com/m"), ("bad", "ftp://x"), ("", "https://other.org")])
ok(catalog.sites() == [("Models", "https://www.example.com/m"), ("https://other.org", "https://other.org")],
   "sites kept in order, bad ones dropped")
ok(catalog.site_name("https://www.example.com/m") == "example.com", "a site's name from its address")
ok(catalog.watched() == [], "no folder watched at first")
catalog.set_watched(lib, True)
ok(catalog.watched() == [lib] and catalog.is_watched(lib), "a folder can be watched")
(lib / "sub").mkdir()
ok(set(catalog.subfolders(lib)) == {lib, lib / "sub"}, "a watched folder's subfolders are watched too")
extra = pathlib.Path(tempfile.mkdtemp()); catalog.add_folder(extra); catalog.set_watched(extra, True)
catalog.remove_folder(extra)
ok(catalog.watched() == [lib], "removing a folder stops watching it")

# --- Poly Haven (no network) --------------------------------------------------------
listing = {"b_tex": {"name": "Brick Wall", "categories": ["brick", "wall"], "tags": ["red"],
                     "dimensions": [2000, 1500]},
           "a_tex": {"name": "Asphalt", "categories": ["floor"], "tags": []}}
es = polyhaven.entries(listing)
ok([e["id"] for e in es] == ["a_tex", "b_tex"], "entries sorted by name, with their id")
ok(polyhaven.matches(es[1], "red wall") and not polyhaven.matches(es[1], "floor")
   and polyhaven.matches(es[0], "", "floor") and not polyhaven.matches(es[0], "", "brick"),
   "search by words and category")
ok(polyhaven.tile_size_m(es[1]) == (2.0, 1.5) and polyhaven.tile_size_m(es[0]) == (1.0, 1.0),
   "material size in metres (1 m when unknown)")
U = "https://dl.polyhaven.org/file/ph-assets/"
files = {"hdri": {"1k": {"hdr": {"url": U + "x_1k.hdr", "md5": "a"}}, "4k": {"hdr": {"url": U + "x_4k.hdr"}}},
         "Diffuse": {"2k": {"jpg": {"url": U + "d_2k.jpg"}}},
         "nor_gl": {"1k": {"jpg": {"url": U + "n_1k.jpg"}}}, "Rough": {"1k": {"png": {"url": U + "r_1k.png"}}},
         "gltf": {"1k": {"gltf": {"url": U + "m.gltf", "include": {"m.bin": {"url": U + "m.bin"},
                                                                   "textures/d.jpg": {"url": U + "d.jpg"}}}}}}
ok(polyhaven.files_for("hdris", files, "2k")[0] == "x_1k.hdr", "missing 2K -> the nearest smaller")
mmain, mtodo, mmaps = polyhaven.files_for("materials", files, "1k")
ok(mmain == "d_2k.jpg", "only a bigger one -> that one")
ok(mmaps == {"color": "d_2k.jpg", "normal_gl": "n_1k.jpg", "roughness": "r_1k.png"} and len(mtodo) == 3,
   "a material brings every map it has, not only its colour image")
main, todo, _maps = polyhaven.files_for("models", files, "1k")
ok(main == "m.gltf" and [t[0] for t in todo] == ["m.gltf", "m.bin", "textures/d.jpg"],
   "a model brings its .gltf and every file it refers to")
root = pathlib.Path(tempfile.mkdtemp())
ok(polyhaven.safe_target(root, "textures/d.jpg") == (root / "textures" / "d.jpg").resolve(), "safe path inside")
bad = 0
for rel in ("../x.jpg", "/etc/x", "C:/x.jpg", "a/../../x", ""):
    try:
        polyhaven.safe_target(root, rel)
    except ValueError:
        bad += 1
ok(bad == 5, "paths escaping the cache folder are refused")
ok(polyhaven.allowed_url(U + "a.jpg") and polyhaven.allowed_url("https://api.polyhaven.com/files/x")
   and not polyhaven.allowed_url("http://dl.polyhaven.org/a") and not polyhaven.allowed_url("https://evil.com/polyhaven.org")
   and not polyhaven.allowed_url("https://polyhaven.org.evil.com/a"), "downloads only from Poly Haven over https")
d = polyhaven.asset_dir("models", "m", "1k"); d.mkdir(parents=True)
ok(polyhaven.cached_main("models", "m", "1k") is None, "no cache before a complete download")
(d / "m.gltf").write_text("{}"); (d / ".complete").write_text("m.gltf")
ok(polyhaven.cached_main("models", "m", "1k") == d / "m.gltf", "a complete download is reused")

# --- manifest, ambientCG (no network) -------------------------------------------------
from asset_manager import ambientcg, online
mroot = pathlib.Path(tempfile.mkdtemp())
for n in ("w_diff_1k.jpg", "w_nor_gl_1k.jpg", "w_rough_1k.jpg"):
    (mroot / n).write_bytes(b"x")
man = online.write_manifest(mroot / "w_diff_1k.jpg", {"color": mroot / "w_diff_1k.jpg", "normal_gl": mroot / "w_nor_gl_1k.jpg",
                                                      "roughness": mroot / "w_rough_1k.jpg"}, (2.0, 1.5), "polyhaven", "w")
data = online.read_manifest(mroot / "w_diff_1k.jpg")
ok(man.name == "w_diff_1k.pbr.json" and data == {"version": 1, "color": "w_diff_1k.jpg", "normal_gl": "w_nor_gl_1k.jpg",
   "roughness": "w_rough_1k.jpg", "size_m": [2.0, 1.5], "source": "polyhaven", "id": "w"},
   "the .pbr.json manifest names the maps next to the colour image")
page = {"numberOfResults": 2, "foundAssets": [
    {"assetId": "Bricks097", "displayName": "Bricks 097", "displayCategory": "Bricks", "dataType": "Material",
     "tags": ["red"], "dimensionX": 200, "dimensionY": 150, "previewImage": {"128-PNG": "https://acg-media.struffelproductions.com/t.png"}},
    {"assetId": "Wood01", "displayName": "Wood 01", "displayCategory": "Wood", "dataType": "Material"}]}
aes = ambientcg.entries([page])
ok([e["id"] for e in aes] == ["Bricks097", "Wood01"] and aes[0]["categories"] == ["Bricks"]
   and polyhaven.matches(aes[0], "red bricks"), "ambientCG entries: name, category, tags, search")
ok(ambientcg.tile_size_m(aes[0]) == (2.0, 1.5) and ambientcg.tile_size_m(aes[1]) == (1.0, 1.0),
   "ambientCG size in metres (from centimetres)")
ok(ambientcg.map_key("Bricks097_1K-JPG_NormalGL.jpg") == "normal_gl" and ambientcg.map_key("Bricks097_1K-JPG_Color.jpg") == "color"
   and ambientcg.map_key("Bricks097.png") is None, "ambientCG map names")
import zipfile
zroot = pathlib.Path(tempfile.mkdtemp()); zp = zroot / "b.zip"
with zipfile.ZipFile(zp, "w") as z:
    z.writestr("Bricks097_1K-JPG_Color.jpg", b"c"); z.writestr("Bricks097_1K-JPG_NormalGL.jpg", b"n")
    z.writestr("Bricks097_1K-JPG_Roughness.jpg", b"r"); z.writestr("Bricks097_1K-JPG.blend", b"b")
    z.writestr("../../evil_Color.jpg", b"e"); z.writestr("Bricks097.png", b"p")
out = zroot / "out"; out.mkdir()
maps = ambientcg.extract_maps(zp, out)
ok(sorted(maps) == ["color", "normal_gl", "roughness"] and sorted(p.name for p in out.iterdir())
   == ["Bricks097_1K-JPG_Color.jpg", "Bricks097_1K-JPG_NormalGL.jpg", "Bricks097_1K-JPG_Roughness.jpg"]
   and not (zroot / "evil_Color.jpg").exists(), "only the maps come out of the zip, flat, nothing outside the folder")
# ambientCG HDRIs: the full-range 360° image is taken out of the zip, nothing else
names = ["Night011_1K.usdc", "Night011_1K_HDR.exr", "Night011_1K_TONEMAPPED.jpg", "Night011_1K.blend", "Night011.png"]
ok(ambientcg.pick_hdri(names) == "Night011_1K_HDR.exr" and ambientcg.pick_hdri(["a.hdr", "b.exr"]) == "a.hdr"
   and ambientcg.pick_hdri(["a_TONEMAPPED.jpg", "x.blend"]) is None, "ambientCG HDRI: the full-range image is the one picked")
hz = zroot / "hdri.zip"
with zipfile.ZipFile(hz, "w") as z:
    for n in names: z.writestr(n, b"x" * 10)
hout = zroot / "hdri_out"; hout.mkdir()
img = ambientcg.extract_hdri(hz, hout)
ok(img.name == "Night011_1K_HDR.exr" and [p.name for p in hout.iterdir()] == ["Night011_1K_HDR.exr"], "only the 360° image is written")
hp = {"foundAssets": [{"assetId": "NightEnvironmentHDRI011", "dataType": "HDRI", "displayName": "Night Environment HDRI 011",
                       "displayCategory": "Night Environment HDRI", "tags": ["night"], "previewImage": {"128-PNG": "u"}},
                      {"assetId": "Bricks097", "dataType": "Material", "displayName": "Bricks 097"}]}
ok([e["id"] for e in ambientcg.entries([hp], "hdris")] == ["NightEnvironmentHDRI011"]
   and [e["id"] for e in ambientcg.entries([hp])] == ["Bricks097"], "listings keep only the kind asked for")
dp = {"foundAssets": [{"assetId": "ManholeCover011", "dataType": "Decal", "displayName": "Manhole Cover 011",
                       "displayCategory": "Manhole Cover", "dimensionX": 90, "dimensionY": 90},
                      {"assetId": "GraffitiSet001", "dataType": "Atlas", "displayName": "Graffiti Set 001",
                       "displayCategory": "Graffiti Set"},
                      {"assetId": "BricksSubstance008", "dataType": "Substance", "displayName": "Bricks Substance 008"},
                      {"assetId": "Bricks097", "dataType": "Material", "displayName": "Bricks 097", "displayCategory": "Bricks"}]}
des = {e["id"]: e for e in ambientcg.entries([dp])}
ok(set(des) == {"ManholeCover011", "GraffitiSet001", "Bricks097"}, "the Materials list holds decals and atlases, not substances")
ok(des["ManholeCover011"]["categories"] == ["Manhole Cover", "Decals"] and des["GraffitiSet001"]["categories"] == ["Graffiti Set", "Atlases"]
   and des["Bricks097"]["categories"] == ["Bricks"], "decals and atlases are also under a category of their own")
ok(ambientcg.tile_size_m(des["ManholeCover011"]) == (0.9, 0.9) and not ambientcg.entries([dp], "hdris"), "a decal keeps its real size; HDRIs stay apart")
ok(online.host_allowed("https://acg-download.struffelproductions.com/x.zip", ambientcg.HOSTS)
   and online.host_allowed("https://ambientcg.com/get?file=a", ambientcg.HOSTS)
   and not online.host_allowed("https://struffelproductions.com.evil.org/x", ambientcg.HOSTS)
   and not online.host_allowed("https://dl.polyhaven.org/x", ambientcg.HOSTS), "each source reaches only its own servers")

# --- material sets and zips in the catalog ---------------------------------------
from asset_manager import materials
names = {"Bricks097_1K-JPG_NormalGL.jpg": "normal_gl", "Bricks097_1K-JPG_Color.jpg": "color",
         "x_nor_gl_1k.jpg": "normal_gl", "x_diff_1k.jpg": "color", "Wood_Floor_BaseColor.png": "color",
         "wood_albedo.jpg": "color", "Wood_Normal.png": "normal_gl", "Wood_Roughness.jpg": "roughness",
         "Wood_NormalDX.png": "normal_dx", "Wood_AmbientOcclusion.jpg": "ao", "Wood_Height.png": "displacement",
         "Plate_Metallic.png": "metalness", "IMG_1234.jpg": None, "logo.png": None, "notes.txt": None}
got = {n: materials.map_key(n) for n in names}
ok(got == names, f"map names from several sites are recognised ({[n for n in names if got[n] != names[n]]})")
sets = materials.find_sets(["Wood_Floor_BaseColor.png", "Wood_Floor_Normal.png", "Wood_Floor_Roughness.jpg",
                            "IMG_1234.jpg", "logo.png", "Stone_Color.jpg", "Stone_Normal.jpg", "Lonely_Color.jpg"])
ok(sorted(tuple(sorted(s)) for s in sets) == sorted([("color", "normal_gl", "roughness"), ("color", "normal_gl")]),
   "maps are grouped by the name they share; lone photos and a colour alone are not materials")
ok(materials.set_name("Wood_Floor_BaseColor.png") == "Wood Floor" and materials.set_name("Bricks097_1K-JPG_Color.jpg") == "Bricks097",
   "a material's name from its colour image")
zlib = pathlib.Path(tempfile.mkdtemp())
skp_bytes = b"\xff\xfe\xff\x0eS\0k\0" + b"\1" * 40 + png + b"rest"
with zipfile.ZipFile(zlib / "download.zip", "w") as z:
    z.writestr("model/Cadira.skp", skp_bytes)
    z.writestr("textures/Oak_BaseColor.jpg", b"colour"); z.writestr("textures/Oak_Normal.jpg", b"normal")
    z.writestr("textures/Oak_Roughness.jpg", b"rough"); z.writestr("readme.txt", b"x")
(zlib / "Tiles_Color.png").write_bytes(b"c"); (zlib / "Tiles_Normal.png").write_bytes(b"n")
(zlib / "photo.jpg").write_bytes(b"p")
before_files = sorted(p.name for p in zlib.rglob("*"))
zitems = catalog.scan(zlib)
ok(sorted((i.name, i.kind, i.member) for i in zitems) == [("Cadira", "skp", "model/Cadira.skp"), ("Oak", "material", None),
                                                          ("Tiles", "material", None)],
   "a zip's model and material set, and a folder's material set, are listed")
cad = next(i for i in zitems if i.name == "Cadira")
ok(cad.label == f"Cadira  ·  skp (zip)  ·  {catalog.size_text(len(skp_bytes))}" and catalog.preview_bytes(cad) == png,
   "a .skp in a zip shows its own preview, and its size")
ok(cad.size == len(skp_bytes) and not cad.heavy, "its size is the member's, and it is not heavy")
oak = next(i for i in zitems if i.name == "Oak")
ok(oak.size == len(b"colour") + len(b"normal") + len(b"rough"), "a material set's size adds up its maps")
big = catalog.Item("Arbre", pathlib.Path("a.igz"), None, size=catalog.HEAVY_BYTES)
ok(big.heavy and big.label.startswith(catalog.HEAVY_MARK) and "100 MB" in big.label, "a model of 100 MB or more is marked heavy")
out = catalog.extract(cad)
ok(out.read_bytes() == skp_bytes and pathlib.Path(home) in out.parents, "the model is taken out of the zip into the extension's folder")
oak = next(i for i in zitems if i.name == "Oak")
color, mpaths = catalog.material_files(oak)
man = online.read_manifest(color)
ok(sorted(mpaths) == ["color", "normal_gl", "roughness"] and man and man["normal_gl"] == "Oak_Normal.jpg"
   and man["source"] == "catalog" and pathlib.Path(home) in color.parents and color.read_bytes() == b"colour",
   "a material's maps are copied out with their manifest")
tiles = next(i for i in zitems if i.name == "Tiles")
tcolor, _tp = catalog.material_files(tiles)
ok(online.read_manifest(tcolor)["normal_gl"] == "Tiles_Normal.png" and sorted(p.name for p in zlib.rglob("*")) == before_files,
   "a folder's material too, and the user's folder is left as it was")

# --- drag and drop placement ------------------------------------------------------
class Snap:
    def __init__(self, p): self.point = p; self.kind = "on_face"
class History:
    def __init__(self, scene): self.scene = scene; self.done = []
    def execute(self, cmd): cmd.do(self.scene); self.done.append(cmd)
    def undo(self): self.done.pop().undo(self.scene)
class Win(QWidget):
    def __init__(self):
        super().__init__(); self.tools = []; self.placed = []
    def _activate_tool(self, name): self.tools.append(name)
    def _start_place(self, group, anchor=None): self.placed.append((group, anchor))
    def _replacement_choices(self, sel): return [("Other  (1×)", scene.groups[0])]
    def replace_selection_with(self, source): self.replaced = (list(scene.selection), source); return len(scene.selection)
class VP(QWidget):
    def __init__(self, scene, win):
        super().__init__(win); self.scene = scene; self.history = History(scene); self.tool = None
    def set_active_tool(self, t): self.tool = t; t.on_activate(self)
    def _snap_at(self, x, y, mods): return Snap(QVector3D(x / 10.0, y / 10.0, 0))
    def flash_status(self, *a): pass
    def notify_scene_changed(self): pass
    def end_group_edit(self): pass
    def begin_group_edit(self, g): self.edited = g
    def update(self): pass
win = Win(); vp = VP(scene, win); win.viewport = vp
drop = place.DropOnView(win)
drop.watch_all()
ok(vp.acceptDrops() and vp.property("asset_manager_drop"), "the view accepts drops from the panel")
before = len(scene.groups)
src = scene.groups[2]
drop.begin(lambda: (lambda g: (g, place.origin_of(g)))(place.copy_of(src)))
mime = QMimeData(); mime.setData(place.MIME, b"1")
ev = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
ok(drop.eventFilter(vp, ev) and ev.isAccepted() and vp.tool is not None, "drag enter -> placement tool")
drop.eventFilter(vp, QDragMoveEvent(QPoint(30, 40), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
ev = QDropEvent(QPointF(50, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
drop.eventFilter(vp, ev)
drop.end()
ok(len(scene.groups) == before, "nothing changes inside the drop event itself")
qa.processEvents()
new = scene.groups[-1] if len(scene.groups) > before else None
ok(new is not None and new.mesh is src.mesh, "drop -> a copy sharing the definition, one undo step")
ok(new is not None and abs(new.xform.map(QVector3D()).x() - 5.0) < 1e-6
   and abs(new.xform.map(QVector3D()).y() - 2.0) < 1e-6, "placed where it was dropped (its axes at the point)")
foreign = QMimeData(); foreign.setText("hello")
ok(not drop.eventFilter(vp, QDragEnterEvent(QPoint(1, 1), Qt.CopyAction, foreign, Qt.LeftButton, Qt.NoModifier)),
   "other drags are left to the view")

# a .skp dragged from the file explorer goes through our importer
from PySide6.QtCore import QUrl
import types
skp_file = zlib / "Explorer.skp"; skp_file.write_bytes(b"x")
url_mime = QMimeData(); url_mime.setUrls([QUrl.fromLocalFile(str(skp_file))])
ok(not drop.eventFilter(vp, QDragEnterEvent(QPoint(1, 1), Qt.CopyAction, url_mime, Qt.LeftButton, Qt.NoModifier)),
   "without the .skp extension, a dragged file is left to the window")
sys.modules[place.SKP_EXT] = types.ModuleType(place.SKP_EXT)
asked = []
real_from_file = place.group_from_file
place.group_from_file = lambda v, p: (asked.append(p), place.copy_of(src))[1]
txt_mime = QMimeData(); txt_mime.setUrls([QUrl.fromLocalFile(str(zlib / "photo.jpg"))])
ok(not drop.eventFilter(vp, QDragEnterEvent(QPoint(1, 1), Qt.CopyAction, txt_mime, Qt.LeftButton, Qt.NoModifier)),
   "a dragged file that is not a .skp is left to the window")
before = len(scene.groups)
ev = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, url_mime, Qt.LeftButton, Qt.NoModifier)
ok(drop.eventFilter(vp, ev) and ev.isAccepted() and asked == [],
   "a dragged .skp is taken by our importer (read once dropped, with a progress window)")
drop.eventFilter(vp, QDragMoveEvent(QPoint(30, 40), Qt.CopyAction, url_mime, Qt.LeftButton, Qt.NoModifier))
drop.eventFilter(vp, QDropEvent(QPointF(20, 20), Qt.CopyAction, url_mime, Qt.LeftButton, Qt.NoModifier))
qa.processEvents()
ok(asked == [skp_file] and len(scene.groups) == before + 1 and drop.provider is None and not drop._explorer,
   "read by our importer and placed where it was dropped; the drag leaves nothing behind")
drop.eventFilter(vp, QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, url_mime, Qt.LeftButton, Qt.NoModifier))
from PySide6.QtGui import QDragLeaveEvent
drop.eventFilter(vp, QDragLeaveEvent())
ok(drop.provider is None and not drop._explorer and len(scene.groups) == before + 1, "leaving the view cancels it")
place.group_from_file = real_from_file
del sys.modules[place.SKP_EXT]

# --- settings (the panel itself: test_asset_manager_tabs.py) --------------------------
from asset_manager import ui_settings
dlg = ui_settings.SettingsDialog()
ok(dlg.sites.count() == 2 and dlg.folders.count() == 2
   and dlg.folders.item(1).checkState() == Qt.Checked, "settings list the sites and the folders with their watch tick")
dlg.folders.item(1).setCheckState(Qt.Unchecked)
ok(catalog.watched() == [] and dlg.changed, "unticking a folder stops watching it")
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
