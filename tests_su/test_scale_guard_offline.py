"""dc_tools.scale_guard: ScaleTool hides handles; scaling a dynamic component
redraws it (one undo step), the same as typing LenX in Component Options.
argv: <ingetrazo-src> <extension repo> <skp with a dynamic component>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
qa = QApplication.instance() or QApplication([])
from PySide6.QtGui import QVector3D
from core.scene import Scene
from core.history import History, ScaleGroupCommand
from core.group import iter_placements
from skp_dc_import import reader, builder
from dc_tools import scale_guard as SG
from dc_tools.dc import apply as A

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

# --- the mask ---------------------------------------------------------------------
class G:
    def __init__(self, v, where="definition_attributes"):
        self.ext = {"skp_dc_import": {where: {"scaletool": v}}}
ok(SG.scale_mask(G("120")) == 120 and SG.scale_mask(G(126.0)) == 126 and SG.scale_mask(G(None)) == 0
   and SG.scale_mask(G("7", "instance_attributes")) == 7, "ScaleTool read as an int (text, number, instance)")
ok(SG.handle_allowed(0, (0,)) and not SG.handle_allowed(1, (0,)) and SG.handle_allowed(1, (1,))
   and not SG.handle_allowed(8, (0, 1)) and not SG.handle_allowed(64, (0, 1, 2)) and SG.handle_allowed(63, (0, 1, 2)),
   "bits: 1 X, 2 Y, 4 Z, 8 XY, 16 XZ, 32 YZ, 64 uniform")

# --- the Scale tool's handles --------------------------------------------------------
ok(SG.patch_scale_tool() and SG.patch_scale_tool(), "Scale tool wrapped (once)")
from tools.scale import ScaleTool

model = reader.parse(SKP)
scene = Scene(); builder.build(scene, model, SKP)
roots = [g for g in scene.groups if A.is_dynamic_root(g) and g.children]
ok(bool(roots), f"the file has a dynamic component with parts ({len(roots)})")
root = roots[0]

class VP:
    def __init__(self, scene):
        self.scene = scene; self.history = History(scene)
    def update(self): pass
    def notify_scene_changed(self): self.scene.version += 1
vp = VP(scene)
scene.selection.clear(); scene.selection.add(root)

def grips_with(mask):
    data = root.ext["skp_dc_import"]
    inst = data.setdefault("instance_attributes", {})
    old = inst.get("scaletool")
    inst["scaletool"] = mask
    t = ScaleTool(); t._box_version = -1; scene.version += 1
    t._refresh_box(vp)
    if old is None: inst.pop("scaletool")
    else: inst["scaletool"] = old
    return sorted(tuple(g.mask) for g in t._grips)

every = grips_with(0)
ok(len(every) == 26, f"no mask: every handle ({len(every)})")
only_x = grips_with(126)
ok(only_x and all(m == (0,) for m in only_x), f"ScaleTool 126: only the red (X) handles {only_x}")
no_uniform = grips_with(64)
ok(len(no_uniform) == 18 and all(len(m) < 3 for m in no_uniform), "ScaleTool 64: no corner (uniform) handles")
ok(grips_with(127) == [], "ScaleTool 127: no handle at all")

# --- redraw after a scale, one undo step -------------------------------------------------
def snapshot(g):
    pts = []
    for pg, m in iter_placements(g):
        if pg.hidden:
            continue
        for v in pg.mesh.vertices:
            p = m.map(v.position) if m is not None else v.position
            pts.append((round(p.x(), 4), round(p.y(), 4), round(p.z(), 4)))
    return sorted(set(pts))

class App:
    def __init__(self, vp): self.viewport = vp
watcher = SG.RedrawOnScale(App(vp))
watcher.check()                                      # first look: remembers the scales
before_root, before_snap = root, snapshot(root)
before_scale_x = SG._scale_of(root)[0]
n_before = len(vp.history.undo_stack)
lo = min(p[0] for p in before_snap); hi = max(p[0] for p in before_snap)
centre = QVector3D(lo, 0, 0)
vp.history.execute(ScaleGroupCommand(root, centre, (1.5, 1.0, 1.0), None))
ok(root in scene.groups and abs(SG._scale_of(root)[0] / before_scale_x - 1.5) < 1e-6, "scaled by the Scale tool's command")
watcher.check()
new = next((g for g in scene.groups if A.is_dynamic_root(g) and g is not root and g.name == root.name), None)
ok(new is not None and root not in scene.groups, "the scaled component was redrawn (a new tree in its place)")
ok(len(vp.history.undo_stack) == n_before + 1, "scale + redraw are ONE undo step")
ok(new is not None and all(abs(s - 1.0) < 1e-6 for s in SG._scale_of(new)), "the redrawn component is at scale 1")
after = snapshot(new) if new else []
ok(after and abs((max(p[0] for p in after) - min(p[0] for p in after)) - 1.5 * (hi - lo)) < 0.01,
   "and it is 1.5× as wide")

# the same as typing LenX in Component Options (the path checked against SketchUp)
scene2 = Scene(); builder.build(scene2, model, SKP)
root2 = next(g for g in scene2.groups if A.is_dynamic_root(g) and g.children and g.name == root.name)
from dc_tools.dc.redraw import live_value
part2, _f = A.part_in_context(scene2, root2)
lenx = live_value(part2, "lenx")
ref, _ev = A.redraw_group(root2, {"lenx": lenx * 1.5}, scene2)
ok(abs(len(snapshot(ref)) - len(after)) == 0 and snapshot(ref) == after or
   max(abs(a - b) for pa, pb in zip(snapshot(ref), after) for a, b in zip(pa, pb)) < 0.002,
   "identical to LenX ×1.5 typed in Component Options")

vp.history.undo()
ok(root in scene.groups and new not in scene.groups and snapshot(root) == before_snap,
   "undo puts the original back, unscaled")
watcher.check()
ok(len(vp.history.undo_stack) == n_before and root in scene.groups, "and the undo is not taken for a new scale")
vp.history.redo()
ok(new in scene.groups and root not in scene.groups, "redo brings the redrawn one back")
watcher.check()
ok(new in scene.groups, "redo is not redrawn again")
print("FAILED" if fails else "ALL OK"); sys.exit(1 if fails else 0)
