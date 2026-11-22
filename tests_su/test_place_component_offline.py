"""Offscreen: a model file's group (Poly Haven glTF) is placed as a COMPONENT, and Replace
Component puts the new one where the old sat. argv: <ingetrazo-src> <extension repo> <a .gltf>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, GLTF = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QMatrix4x4, QVector3D
qa = QApplication.instance() or QApplication([])
from core.scene import Scene
from core.group import Group, world_mesh
from core.history import ReplaceComponentCommand
from asset_manager import place

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

dst = Scene()
temp = Scene()
from formats import glb
glb.load_glb(temp, GLTF)
print("top groups:", len(temp.groups), [(g.name, g.xform is not None) for g in temp.groups][:3], "loose faces:", len(temp.mesh.faces))
g = place._from_scene(dst, temp, "chair")
ok(g is not None and g.xform is not None and g.is_component(), "the model is a component instance, not a classic group")

# a target placed at (5, 2, 0), turned 90 degrees about Z: Replace Component must put the new one there
target = place.copy_of(g)
m = QMatrix4x4(); m.translate(5, 2, 0); m.rotate(90, 0, 0, 1)
target.xform = m
src = place.copy_of(g)
dst.groups.extend([target, src])
before = target.xform.map(QVector3D(0, 0, 0))
other = place._from_scene(dst, _t := Scene(), "x") if False else None
cmd = ReplaceComponentCommand([target], src)
ok(bool(cmd.targets) is False, "(same definition: nothing to replace, as in IngeTrazo)")
# a different definition: the chair stands in for a copy of itself made unique
alt = place.copy_of(g); alt.make_unique(); alt.xform = QMatrix4x4()
cmd = ReplaceComponentCommand([target], alt); cmd.do(dst)
after = target.xform.map(QVector3D(0, 0, 0))
ok((after - before).length() < 1e-6, "Replace keeps the target's origin (%s -> %s)" % (before, after))
print("FAILS:", fails); sys.exit(1 if fails else 0)
