"""Offscreen: the paints of a glTF model are named after it. argv: <ingetrazo-src> <extension repo> <models dir>"""
import os, sys, glob, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, DIR = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
qa = QApplication.instance() or QApplication([])
from core.scene import Scene
from asset_manager import place, gltf_names as N

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

ok(N.model_title("x/ArmChair_01_1k.gltf") == "ArmChair_01" and N.model_title("a/Chair.glb") == "Chair", "title drops the size")
files = sorted(glob.glob(os.path.join(DIR, "*", "*", "*.gltf")))
multi = [f for f in files if len(json.load(open(f))["materials"]) > 1]
print(len(files), "models,", len(multi), "with several materials")
dst = Scene()
for path in ([f for f in files if "ArmChair_01" in f][:1] + multi[:2]):
    temp = place.read_file(type("V", (), {})(), path) if False else None
    from formats import glb
    temp = Scene(); glb.load_glb(temp, path)
    names = N.name_materials(temp, path)
    title = N.model_title(path)
    ok(names and all(n.startswith(title) for n in names), "%s -> %s" % (os.path.basename(path), names))
    faces = [f for g in temp.groups for f in g.mesh.faces] + list(temp.mesh.faces)
    painted = [f for f in faces if f.attrs and (f.attrs.get("texture") or f.attrs.get("color"))]
    ok(painted and all(f.attrs.get("mat") in temp.materials for f in painted), "every painted face names a registered material")
    g = place._from_scene(dst, temp, title)
    ok(all(n in dst.materials for n in names), "the names reach the drawing's materials")
print("FAILS:", fails); sys.exit(1 if fails else 0)
