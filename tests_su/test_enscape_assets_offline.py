"""Offscreen: Enscape's library objects come in as stand-ins (translucent, left out
of the render), and asset_manager.stand_in sets / clears the property, undoably.
argv: <ingetrazo-src> <extension repo> [<a .skp with Enscape.Asset components>]"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
SKP = sys.argv[3] if len(sys.argv) > 3 else None
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from skp_dc_import import enscape_assets as A, builder, reader
from asset_manager import stand_in as S
from core.scene import Scene
from core.history import History

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

class _E:
    def __init__(self, d): self.attribute_dictionaries = d
a = A.asset_of(_E({"Enscape.Asset": {"Id": "abc", "Source": "REMOTE"}}))
ok(a == {"id": "abc", "source": "REMOTE"}, "asset_of reads Id and Source")
ok(A.asset_of(_E({"x": {}})) is None and A.asset_of(None) is None, "no Enscape.Asset: not a stand-in")
ext = A.with_stand_in({"keep": 1}, a, {"color": (1, 0, 0)})
ok(ext["keep"] == 1 and ext["enscape_asset"]["id"] == "abc" and ext["render_studio"]["hide_in_render"], "ext marks")

class G:  # a group stand-in for the pure functions
    def __init__(self, ext=None, material=None): self.ext, self.material, self.children = ext, material, []
g = G(None, {"color": (1, 0, 0)})
e2, m2 = S.stand_in_state(g, True)
ok(e2["render_studio"]["hide_in_render"] and m2 == S.PAINT, "on: hidden in render + translucent paint")
g.ext, g.material = e2, m2
ok(S.is_stand_in(g), "is_stand_in")
e3, m3 = S.stand_in_state(g, False)
ok(e3 is None and m3 == {"color": (1, 0, 0)}, "off: the old paint and a clean ext come back")
g2 = G({"render_studio": {"lights": [1], "hide_in_render": True}}, None)   # a light's symbol
e4, m4 = S.stand_in_state(g2, False)
ok(e4 == {"render_studio": {"lights": [1]}} and m4 is None, "off keeps the lights")

if SKP:
    scene = Scene(); rep = builder.build(scene, reader.parse(SKP), SKP)
    found = []
    def walk(gs):
        for x in gs:
            if (x.ext or {}).get("enscape_asset"): found.append(x)
            walk(x.children or [])
    walk(scene.groups)
    ok(len(found) > 0 and rep["stand_ins"] == len(found), "built: %d stand-ins (report %s)" % (len(found), rep["stand_ins"]))
    x = found[0]
    ok(S.is_stand_in(x) and x.material == S.PAINT, "placement is a stand-in with the translucent paint")
    paints = [f for f in x.mesh.faces if any(k in f.attrs for k in ("color", "mat", "texture", "opacity"))]
    ok(x.mesh.faces and not paints, "envelope faces carry no paint of their own")
    class VP:
        history = History(scene); scene_ = scene
        def __init__(s): s.scene = scene
        def update(s): pass
    vp = VP()
    n = S.set_stand_in(vp, [x], False)
    ok(n == 1 and not S.is_stand_in(x) and x.material is None, "cleared: renders again")
    vp.history.undo()
    ok(S.is_stand_in(x) and x.material == S.PAINT, "undo puts the stand-in back")
print("FAILS:", fails)
sys.exit(1 if fails else 0)
