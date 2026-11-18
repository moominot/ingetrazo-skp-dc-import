"""Root resized the dialog's way: the root's transform is scaled, then redraw."""
import sys
sys.path[:0] = [sys.argv[1], '.']
from skp_dc_import.dc import model as M
from skp_dc_import.dc.redraw import redraw, live_value
import dc_harness as H
IN = 1 / 2.54
cases = [('FINESTRA SIMPLE#34', 'lenx', 150*IN, 'FINESTRASIMPLE_3', {}), ('FINESTRA SIMPLE#34', 'lenz', 120*IN, 'FINESTRASIMPLE_5', {'m_alt_inf': 10*IN}),
         ('Barana', 'lenx', 150*IN, 'Barana_1', {}), ('Barana', 'lenz', 100*IN, 'Barana_2', {}),
         ('barana_ferro#1', 'lenx', 250*IN, 'baranaferro_1', {}), ('barana_ferro#1', 'lenz', 100*IN, 'baranaferro_5', {})]
start = {r['defn']: r for r in H.load('su_file_geo.json', 'su_file_vis.json')}
detail = len(sys.argv) > 2
for dname, axis, value, tag, extra in cases:
    want = {r['defn']: r for r in H.load(f'su_c3_{tag}_geo.json', f'su_c3_{tag}_vis.json')}[dname]
    root = H.to_parts(start[dname], M)
    f = value / live_value(root, axis); i = 'xyz'.index(axis[-1])
    root.xform = [[root.xform[r][c] * (f if c == i else 1.0) for c in range(4)] for r in range(4)]
    placed, ev = redraw(root, {(root, k): str(v) for k, v in extra.items()})
    got = H.flatten_placed(placed); exp = H.flatten_su(want)
    ok, tot, ex, mi = H.compare(got, exp); ours = sum(1 for x in got if not x[3])
    print(('OK ' if ok == tot == ours else 'BAD'), f"{dname:20} {axis}={value/IN:.0f}cm {extra}: {ok}/{tot} (ours {ours})")
    if detail and not ok == tot == ours:
        for x in sorted(mi)[:4]: print('     SU  ', x[:2], x[2])
        for x in sorted(ex)[:4]: print('     ours', x[:2], x[2])
