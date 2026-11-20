"""Offscreen: builder._mesh_from builds the same mesh through the bulk path
(Mesh.bulk_weld + add_faces_welded) as through the per-face path, falls back to
it for degenerate polygons, and fixes a numeric face layer.
argv: <ingetrazo-src> <extension repo>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT = [os.path.abspath(a) for a in sys.argv[1:3]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from skp_dc_import import builder as B

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c: fails.append(w)

N = 24
faces = []
for i in range(N):
    for j in range(N):
        z = 0.1 * ((i * 7 + j * 3) % 5)
        quad = [(i, j, z), (i + 1, j, z), (i + 1, j + 1, z), (i, j + 1, z)]
        attrs = {"mat": "m%d" % ((i + j) % 4)} if (i + j) % 3 else None
        if (i + j) % 11 == 0 and attrs is not None:
            attrs["layer"] = 170280742            # a number, not a name
        if (i + j) % 7 == 0:
            attrs = dict(attrs or {}, layer="Mobles")
        if i % 13 == 5 and j % 13 == 5:
            hole = [(i + .25, j + .25, z), (i + .75, j + .25, z),
                    (i + .75, j + .75, z), (i + .25, j + .75, z)]
            faces.append((quad, [hole], attrs))
        elif (i + j) % 5 == 0:
            faces.append((quad[:3], [], attrs))
            faces.append(([quad[0], quad[2], quad[3]], [], attrs))
        else:
            faces.append((quad, [], attrs))

def pos(v):
    p = v.position
    return (round(p.x(), 5), round(p.y(), 5), round(p.z(), 5))

def sig(m):
    fs = [(tuple(pos(v) for v in f.loop),
           tuple(tuple(pos(v) for v in h) for h in f.hole_loops),
           tuple(sorted(f.attrs.items()))) for f in m.faces]
    es = sorted((tuple(sorted((pos(e.v0), pos(e.v1)))), len(e.faces)) for e in m.edges)
    return len(m.vertices), len(m.edges), len(m.faces), fs, es

old, new = B._faces_slow(faces), B._faces_bulk(faces)
ok(new is not None, "the bulk path takes clean polygons")
a, b = sig(old), sig(new)
ok(a[:3] == b[:3], f"same vertices / edges / faces {a[:3]}")
ok(a[3] == b[3], "same faces: order, loops, holes and attrs")
ok(a[4] == b[4], "same edges and how many faces each carries")
ok(all(isinstance(f.attrs.get("layer", ""), str) for f in new.faces), "a numeric layer is dropped")

# a degenerate polygon is built exactly as the per-face path builds it
bad = faces[:40] + [([(0, 0, 0), (0, 0, 0), (1, 0, 0)], [], None),
                    ([(2, 2, 0), (3, 2, 0)], [], None)]
nb, sl = B._faces_bulk(bad), B._faces_slow(bad)
ok(nb is not None and len(nb.faces) == len(sl.faces) == 42,
   f"a zero-length side or two corners: kept, as before ({len(nb.faces) if nb else None} / {len(sl.faces)})")
ok(sig(nb)[1:] == sig(sl)[1:] and sig(nb)[0] == sig(sl)[0],
   "…with the same vertices, edges and faces")
ok(len(B._mesh_from(faces[:5], [], []).faces) == 5, "a handful of faces still works")

# soft edges: marked on existing edges only, the same ones as the per-face path
def seg(e):
    return (pos(e.v0), pos(e.v1))
all_edges = [seg(e) for e in old.edges]
soft = [(a, b) for k, (a, b) in enumerate(all_edges) if k % 3 == 0]
def soft_set(m):
    return sorted(tuple(sorted(seg(e))) for e in m.edges if e.soft)
ref = B._faces_slow(faces)
for a, b in soft:
    va, vb = ref.vertex_at(B._q(a)), ref.vertex_at(B._q(b))
    ed = ref.find_edge(va, vb) if va is not None and vb is not None and va is not vb else None
    if ed is not None:
        ed.soft = True
got = B._faces_bulk(faces, soft)
ok(got is not None and soft_set(got) == soft_set(ref) and len(soft_set(ref)) > 100,
   f"soft edges marked as in the per-face path ({len(soft_set(ref))})")
off = soft + [((50, 50, 0), (51, 50, 0))]
ok(B._faces_bulk(faces, off) is None, "a soft edge outside every face sends the mesh to the exact path")
m = B._mesh_from(faces, off, [((60, 60, 0), (61, 60, 0))])
ok(soft_set(m) == soft_set(ref) and len(m.edges) == len(old.edges) + 1,
   "…which ignores it, and loose lines are added after")

print("FAILED" if fails else "ALL PASSED", len(fails))
sys.exit(1 if fails else 0)
