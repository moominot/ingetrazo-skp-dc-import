import json, sys, math, collections
sys.path.insert(0, sys.argv[1])
from dc_tools.dc import model as M
from dc_tools.dc.evaluate import Evaluator, _num
nodes = json.load(open(sys.argv[2], encoding="utf-8"))
vis = json.load(open(sys.argv[3], encoding="utf-8"))
for n, v in zip(nodes, vis): n["vmin"], n["vmax"] = v["vmin"], v["vmax"]
def trees(nodes):
    roots, stack = [], []
    for n in nodes:
        n = dict(n, kids=[])
        while stack and stack[-1]["depth"] >= n["depth"]: stack.pop()
        (stack[-1]["kids"] if stack else roots).append(n); stack.append(n)
    return roots
def merged(n):
    m = dict(n["defdict"]); m.update(n["inst"])
    t = n["xform"]; sc = [math.sqrt(sum(c*c for c in t[k*4:k*4+3])) for k in range(3)]
    live = {"x": t[12], "y": t[13], "z": t[14]}
    lo, hi = n["vmin"], n["vmax"]
    for i, a in enumerate(("lenx", "leny", "lenz")):
        nom = _num(m.get(f"_{a}_nominal"))
        base = nom if isinstance(nom, float) else ((hi[i] - lo[i]) if lo else 0.0)
        live[a] = base * sc[i]
    m["__live__"] = live
    return m
class LiveEval(Evaluator):
    def stored(self, part, attr):
        live = part.attrs.get("__live__", {})
        if attr in live and part.formula(attr) is None:
            return live[attr]
        return super().stored(part, attr)
stats = collections.Counter(); bad = collections.defaultdict(list)
for r in trees(nodes):
    root = M.build(r, merged, lambda n: n["name"] or n["defn"], lambda n: n["kids"])
    ev = LiveEval(root, use_stored=True)
    for part in root.walk():
        for k in list(part.attrs):
            if not k.endswith("_formula") or not str(part.attrs[k] or "").strip(): continue
            attr = k[1:-8]
            if k.startswith("_inst__"): continue
            if part.formula(attr) != str(part.attrs[k]): continue
            got = ev.value(part, attr)
            # compare with what the geometry actually shows for geometric attrs, else stored
            want = part.attrs["__live__"][attr] if attr in part.attrs["__live__"] else part.stored(attr)
            g, w = _num(got), _num(want)
            ok = abs(g - w) <= 1e-3 * max(1.0, abs(w)) if isinstance(g, float) and isinstance(w, float) else str(got) == str(want)
            kind = attr if attr in M.PREDEFINED else "custom"
            stats[(kind, ok)] += 1
            if not ok: bad[kind].append((root.name, part.name, attr, str(part.attrs[k])[:60], round(w,3) if isinstance(w,float) else w, round(g,3) if isinstance(g,float) else g))
tot_ok = sum(v for (k, ok), v in stats.items() if ok); tot = sum(stats.values())
print(f"formulas matching SketchUp: {tot_ok}/{tot}")
for k in sorted({k for k, _ in stats}): print(f"  {k:10} ok={stats[(k, True)]:4} bad={stats[(k, False)]:4}")
for k in bad:
    for b in bad[k][:6]: print("  BAD", k, b)
