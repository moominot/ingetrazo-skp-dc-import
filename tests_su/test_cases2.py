import sys, json
sys.path[:0] = [sys.argv[1], '.']
from skp_dc_import.dc import model as M
from skp_dc_import.dc.redraw import redraw
import dc_harness as H
IN = 1 / 2.54
cases = {
  'FINESTRA SIMPLE#34': ('FINESTRASIMPLE', [{}, {'a_fulles': 3}, {'b_tipus': 0}, {'lenx': 150*IN}, {'g_obert': 1, 'p_obertura': 0.5}, {'lenz': 120*IN, 'm_alt_inf': 10*IN}]),
  'Barana': ('Barana', [{}, {'lenx': 150*IN}, {'lenz': 100*IN}, {'c_horitzontals2_num': 20}, {'b_horitzontals1_num': 3, 'c_horitzontals2_gir': 30}, {'e_verticals2_num': 3}]),
  'Escala simple#7': ('Escalasimple', [{}, {'a_alcada_total': 280*IN}, {'g_x1_tipus_estructura': 1}, {'num1_graons_tram1': 5, 'num3_graons_tram2': 4}, {'g_amplada': 100*IN}, {'r1_vist': 1}]),
  'barana_ferro#1': ('baranaferro', [{}, {'lenx': 250*IN}, {'p1_repart_punt': 0}, {'t13_plet_inf': 1}, {'t1_angletravessers': 0}, {'lenz': 100*IN}]),
}
only = sys.argv[3] if len(sys.argv) > 3 else None
start = {r['defn']: r for r in H.load('su_file_geo.json', 'su_file_vis.json')}
grand = [0, 0, 0]; detail = len(sys.argv) > 2 and sys.argv[2] == 'detail'
for dname, (tagname, lst) in cases.items():
    if only and only not in dname: continue
    for i, attrs in enumerate(lst):
        want = {r['defn']: r for r in H.load(f'su_c2_{tagname}_{i}_geo.json', f'su_c2_{tagname}_{i}_vis.json')}[dname]
        root = H.to_parts(start[dname], M)
        placed, ev = redraw(root, {(root, k): str(v) for k, v in attrs.items()})
        got = H.flatten_placed(placed); exp = H.flatten_su(want)
        ok, tot, extra, missing = H.compare(got, exp)
        ours = sum(1 for x in got if not x[3])
        grand[0] += ok; grand[1] += tot; grand[2] += (ok == tot == ours)
        mark = 'OK ' if ok == tot == ours else 'BAD'
        print(f"{mark} {dname:20} {attrs}: {ok}/{tot} (ours {ours})")
        if mark == 'BAD' and detail:
            for x in list(missing)[:4]: print('      SU  ', x[:2], x[2])
            for x in list(extra)[:4]: print('      ours', x[:2], x[2])
print('TOTAL visible placements equal to SketchUp:', grand[:2], 'cases fully equal:', grand[2], 'of', sum(len(l) for _, l in cases.values()))
