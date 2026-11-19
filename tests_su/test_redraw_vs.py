"""Our redraw of the START state (with overrides) vs SketchUp's state AFTER its own redraw.
argv: ext_repo start_tag expected_tag [overrides json: {"<root defn>": {"attr": value_in_stored_units}}]"""
import sys, json
sys.path[:0] = [sys.argv[1], '.']
from dc_tools.dc import model as M
from dc_tools.dc.redraw import redraw
import dc_harness as H
start = H.load(f'su_{sys.argv[2]}_geo.json', f'su_{sys.argv[2]}_vis.json')
want = {r['defn']: r for r in H.load(f'su_{sys.argv[3]}_geo.json', f'su_{sys.argv[3]}_vis.json')}
ovr = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
total = [0, 0]
for r in start:
    root = H.to_parts(r, M)
    overrides = {(root, a): v for a, v in (ovr.get(r['defn']) or {}).items()}
    placed, ev = redraw(root, overrides)
    got = H.flatten_placed(placed); exp = H.flatten_su(want[r['defn']])
    ok, tot, extra, missing = H.compare(got, exp)
    total[0] += ok; total[1] += tot
    print(f"{r['defn']:22} visible placements = SketchUp: {ok}/{tot}  (ours {sum(1 for x in got if not x[3])} visible) formula errors={len(ev.errors)}")
    for x in list(missing)[:3]: print('    missing', x[:2], x[2])
    for x in list(extra)[:3]: print('    extra  ', x[:2], x[2])
print('TOTAL', total)
