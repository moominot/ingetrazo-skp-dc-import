"""End to end, offline: import the test model into an IngeTrazo Scene (from
IngeTrazo's source), redraw each component with the same options as the
SketchUp cases, and compare every visible part's WORLD transform with
SketchUp's.

argv: <ingetrazo-src> <extension repo> <skp> <dump dir>
"""
import os, sys, collections
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP, DUMPS = [os.path.abspath(a) for a in sys.argv[1:5]]
sys.path[:0] = [SRC, EXT, os.path.dirname(os.path.abspath(__file__))]
os.chdir(DUMPS)
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from core.scene import Scene
from skp_dc_import import builder, reader
from dc_tools.dc import apply as A
import dc_harness as H

IN = 1 / 2.54
CASES = {
  'FINESTRA SIMPLE#34': [('c2_FINESTRASIMPLE_0', {}), ('c2_FINESTRASIMPLE_1', {'a_fulles': 3}), ('c2_FINESTRASIMPLE_2', {'b_tipus': 0}),
                         ('c3_FINESTRASIMPLE_3', {'lenx': 150*IN}), ('c2_FINESTRASIMPLE_4', {'g_obert': 1, 'p_obertura': 0.5}),
                         ('c3_FINESTRASIMPLE_5', {'lenz': 120*IN, 'm_alt_inf': 10*IN})],
  'Barana': [('c2_Barana_0', {}), ('c3_Barana_1', {'lenx': 150*IN}), ('c3_Barana_2', {'lenz': 100*IN}), ('c2_Barana_3', {'c_horitzontals2_num': 20}),
             ('c2_Barana_4', {'b_horitzontals1_num': 3, 'c_horitzontals2_gir': 30}), ('c2_Barana_5', {'e_verticals2_num': 3})],
  'Escala simple#7': [('c2_Escalasimple_0', {}), ('c2_Escalasimple_1', {'a_alcada_total': 280*IN}), ('c2_Escalasimple_2', {'g_x1_tipus_estructura': 1}),
                      ('c2_Escalasimple_3', {'num1_graons_tram1': 5, 'num3_graons_tram2': 4}), ('c2_Escalasimple_4', {'g_amplada': 100*IN}), ('c2_Escalasimple_5', {'r1_vist': 1})],
  'barana_ferro#1': [('c2_baranaferro_0', {}), ('c3_baranaferro_1', {'lenx': 250*IN}), ('c2_baranaferro_2', {'p1_repart_punt': 0}),
                     ('c2_baranaferro_3', {'t13_plet_inf': 1}), ('c2_baranaferro_4', {'t1_angletravessers': 0}), ('c3_baranaferro_5', {'lenz': 100*IN})],
}

model = reader.parse(SKP)

def world_groups(g, parent, depth, out, hidden):
    m = g.xform if parent is None else parent * g.xform
    h = hidden or g.hidden
    data = (g.ext or {}).get(A.KEY) or {}
    attrs = dict(data.get("definition_attributes") or {}); attrs.update(data.get("instance_attributes") or {})
    name = attrs.get("_name") or g.name
    rows = A._rows_from_q(m)
    out.append((depth, name, tuple(round(rows[r][c], 2) + 0.0 for r in range(3) for c in range(4)), h))
    for c in g.children or ():
        world_groups(c, m, depth + 1, out, h)
    return out

ok_cases = 0; total = 0; vis = [0, 0]
for dname, cases in CASES.items():
    for tag, opts in cases:
        scene = Scene()
        builder.build(scene, model, SKP)
        root = next(g for g in scene.groups if ((g.ext or {}).get(A.KEY) or {}).get("definition") == dname)
        new, ev = A.redraw_group(root, opts)
        got = world_groups(new, None, 0, [], False)
        want = {r['defn']: r for r in H.load(f'su_{tag}_geo.json', f'su_{tag}_vis.json')}[dname]
        exp = H.flatten_su(want)
        ok, tot, extra, missing = H.compare_tol(got, exp)
        ours = sum(1 for x in got if not x[3])
        good = ok == tot == ours
        ok_cases += good; total += 1; vis[0] += ok; vis[1] += tot
        print(("OK " if good else "BAD"), f"{dname:20} {opts}: {ok}/{tot} (ours {ours})")
print(f"cases identical to SketchUp inside IngeTrazo groups: {ok_cases}/{total}; visible parts {vis[0]}/{vis[1]}")
