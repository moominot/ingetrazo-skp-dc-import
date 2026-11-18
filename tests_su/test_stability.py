"""Redraw twice = once; change an option and set it back = unchanged.
argv: <ingetrazo-src> <extension repo> <skp> <dump dir>"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP, DUMPS = [os.path.abspath(a) for a in sys.argv[1:5]]
sys.path[:0] = [SRC, EXT, os.path.dirname(os.path.abspath(__file__))]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from core.scene import Scene
from skp_dc_import import builder, reader
from skp_dc_import.dc import apply as A
import dc_harness as H
IN = 1 / 2.54
def world(g, parent=None, depth=0, out=None, hidden=False):
    out = [] if out is None else out
    m = g.xform if parent is None else parent * g.xform
    h = hidden or g.hidden
    data = (g.ext or {}).get(A.KEY) or {}
    attrs = dict(data.get("definition_attributes") or {}); attrs.update(data.get("instance_attributes") or {})
    rows = A._rows_from_q(m)
    out.append((depth, attrs.get("_name") or g.name, tuple(rows[r][c] for r in range(3) for c in range(4)), h))
    for c in g.children or (): world(c, m, depth + 1, out, h)
    return out
model = reader.parse(SKP)
round_trips = {'FINESTRA SIMPLE#34': ('a_fulles', 3, 2), 'Barana': ('c_horitzontals2_num', 20, 60),
               'Escala simple#7': ('num1_graons_tram1', 5, 7), 'barana_ferro#1': ('lenx', 250*IN, None)}
for dname, (opt, v1, v0) in round_trips.items():
    scene = Scene(); builder.build(scene, model, SKP)
    root = next(g for g in scene.groups if ((g.ext or {}).get(A.KEY) or {}).get("definition") == dname)
    once, _ = A.redraw_group(root, {})
    twice, _ = A.redraw_group(once, {})
    ok1, tot1, _, _ = H.compare_tol(world(twice), world(once), only_visible=False, tol=1e-3)
    changed, _ = A.redraw_group(once, {opt: v1})
    if v0 is None:   # a size: go back to the size it had
        from skp_dc_import.dc.redraw import live_value
        v0 = live_value(A.part_tree(once), opt)
    back, _ = A.redraw_group(changed, {opt: v0})
    ok2, tot2, ex, mi = H.compare_tol(world(back), world(once), only_visible=True, tol=0.03)
    print(f"{dname:20} redraw twice = once: {ok1}/{tot1} | {opt} -> {v1:.4g} -> back: {ok2}/{tot2} (ours {len([x for x in world(back) if not x[3]])})")
