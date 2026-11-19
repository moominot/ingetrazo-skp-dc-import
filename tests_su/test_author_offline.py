"""Author a cabinet from plain IngeTrazo groups (Make dynamic + attributes),
redraw, resize and change an option, and compare every part with the same
component made with SketchUp's own Dynamic Components (su_author_probe.json,
dumped by the Ruby probe). argv: <ingetrazo-src> <extension repo> <dump dir>"""
import os, sys, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, DUMPS = [os.path.abspath(a) for a in sys.argv[1:4]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from PySide6.QtGui import QVector3D, QMatrix4x4
from core.group import Group
from core.mesh import Mesh
from dc_tools.dc import apply as A, author as AU

CM = 0.01

def box(x, y, z, w, d, h):
    """A plain group: a box drawn at (x, y, z), its mesh in world metres."""
    m = Mesh()
    P = lambda a, b, c: QVector3D((x + a) * CM, (y + b) * CM, (z + c) * CM)
    for quad in ([P(0,0,0), P(0,d,0), P(w,d,0), P(w,0,0)], [P(0,0,h), P(w,0,h), P(w,d,h), P(0,d,h)],
                 [P(0,0,0), P(w,0,0), P(w,0,h), P(0,0,h)], [P(0,d,0), P(0,d,h), P(w,d,h), P(w,d,0)],
                 [P(0,0,0), P(0,0,h), P(0,d,h), P(0,d,0)], [P(w,0,0), P(w,d,0), P(w,d,h), P(w,0,h)]):
        m.add_face(quad)
    return m

def part(name, x, y, z, w, d, h):
    """A sub-part as IngeTrazo nests it: its own frame at its corner."""
    g = Group(box(0, 0, 0, w, d, h), name=name)
    t = QMatrix4x4(); t.translate(QVector3D(x * CM, y * CM, z * CM))
    g.xform = t
    return g

# What a user has drawn: a group holding three boards.
root = Group(Mesh(), name="armari")
root.adopt([part("lateral", 0, 0, 0, 1.8, 40, 100), part("lateral2", 78.2, 0, 0, 1.8, 40, 100),
            part("prestatge", 1.8, 0, 50, 76.4, 40, 1.8)])
root.xform = None          # a plain (classic) group
root = A.make_dynamic_tree(root, "armari")
L, R, S = root.children
edits = {
    id(root): AU.set_changes("n", value="3"),
    id(L): {"_name": "lateral"},
    id(R): {"_name": "lateral2", **AU.set_changes("x", formula="parent!lenx-lenx")},
    id(S): {"_name": "prestatge",
            **AU.set_changes("x", formula="1.8"), **AU.set_changes("lenx", formula="parent!lenx-3.6"),
            **AU.set_changes("copies", formula="parent!n-1"),
            **AU.set_changes("z", formula="(copy+1)*parent!lenz/parent!n")},
}
step1, ev1 = A.redraw_group(root, {}, None, edits)
step2, ev2 = A.redraw_group(step1, {"lenx": 100 / 2.54, "n": "4"})

def world(g, parent=None, out=None, path=""):
    out = [] if out is None else out
    m = g.xform if parent is None else (parent * g.xform if g.xform is not None else parent)
    a = AU.merged(g)
    p = path + "/" + str(a.get("_name") or g.name)
    out.append((p, float(a.get("copy") or 0), A._rows_from_q(m)))
    for c in g.children or ():
        world(c, m, out, p)
    return out

def rel(rows_list):
    """Placements relative to the root (SketchUp's probe sits elsewhere)."""
    import numpy as np
    r0 = np.array(rows_list[0][2])
    inv = np.linalg.inv(r0)
    return sorted((p, c, [round(v, 3) + 0.0 for v in (inv @ np.array(m))[:3].ravel()]) for p, c, m in rows_list)

su = json.load(open(os.path.join(DUMPS, "su_author_probe.json"), encoding="utf-8"))
def su_rows(entries):
    out = []
    for e in entries:
        t = e["m"]
        out.append((e["path"], e["copy"], [[t[c * 4 + r] for c in range(4)] for r in range(4)]))
    return out

for label, ours, want in (("step1: authored, n=3", step1, su["step1"]), ("step2: LenX 100 cm, n=4", step2, su["step2"])):
    a, b = rel(world(ours)), rel(su_rows(want))
    same = len(a) == len(b) and all(x[0].split("/")[-1] == y[0].split("/")[-1] and
                                   all(abs(p - q) <= 0.01 for p, q in zip(x[2], y[2])) for x, y in zip(a, b))
    print(("OK " if same else "BAD"), label, f"ours {len(a)} parts, SketchUp {len(b)}")
    if not same:
        for x, y in zip(a, b):
            print("   ours", x[0][-22:], x[1], x[2][:4], x[2][8:12])
            print("   SU  ", y[0][-22:], y[1], y[2][:4], y[2][8:12])
print("formula errors:", ev1.errors, ev2.errors)
print("root attributes now:", {k: v for k, v in AU.merged(step2).items() if not k.startswith("_")})
