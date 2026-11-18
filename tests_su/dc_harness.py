"""Shared helpers: SketchUp dump → Part tree, Placed tree → comparable
placements, comparison of two placement sets."""
import json, sys, math, collections

def load(geo_path, vis_path):
    nodes = json.load(open(geo_path, encoding="utf-8"))
    vis = json.load(open(vis_path, encoding="utf-8"))
    for n, v in zip(nodes, vis):
        assert n["path"] == v["path"]
        n["vmin"], n["vmax"] = v["vmin"], v["vmax"]
    roots, stack = [], []
    for n in nodes:
        n = dict(n, kids=[])
        while stack and stack[-1]["depth"] >= n["depth"]:
            stack.pop()
        (stack[-1]["kids"] if stack else roots).append(n)
        stack.append(n)
    return roots

def rowmajor(colmajor16):
    t = colmajor16
    return [[t[c * 4 + r] for c in range(4)] for r in range(4)]

def to_parts(root_node, M):
    def attrs(n):
        a = dict(n["defdict"]); a.update(n["inst"]); a["__hidden__"] = n["hidden"]; return a
    def mk(n, parent):
        a = attrs(n)
        p = M.Part(M.part_name(a, n["name"] or n["defn"]), a, parent, [], n)
        p.xform = rowmajor(n["xform"])
        lo, hi = (n["bmin"], n["bmax"]) if not n["kids"] else (n["vmin"] or n["bmin"], n["vmax"] or n["bmax"])
        p.base = tuple(hi[i] - lo[i] for i in range(3))
        p.definition = n["defn"]
        p.children = [mk(c, p) for c in n["kids"]]
        return p
    return mk(root_node, None)

def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

def flatten_placed(node, parent=None, out=None, hidden=False, depth=0):
    """(depth, definition, world 3x4 rounded, effective hidden)"""
    out = [] if out is None else out
    world = node.xform if parent is None else mul(parent, node.xform)
    h = hidden or node.hidden
    out.append((depth, node.source.name, tuple(round(world[r][c], 2) + 0.0 for r in range(3) for c in range(4)), h))
    for c in node.children:
        flatten_placed(c, world, out, h, depth + 1)
    return out

def flatten_su(node, parent=None, out=None, hidden=False, depth=0):
    out = [] if out is None else out
    local = rowmajor(node["xform"])
    world = local if parent is None else mul(parent, local)
    h = hidden or node["hidden"]
    out.append((depth, (node["defdict"].get("_name") or node["inst"].get("_name") or node["name"] or node["defn"]), tuple(round(world[r][c], 2) + 0.0 for r in range(3) for c in range(4)), h))
    for c in node["kids"]:
        flatten_su(c, world, out, h, depth + 1)
    return out

def compare(a, b, only_visible=True):
    A = collections.Counter(x for x in a if not (only_visible and x[3]))
    B = collections.Counter(x for x in b if not (only_visible and x[3]))
    return sum((A & B).values()), sum(B.values()), A - B, B - A

def compare_tol(a, b, only_visible=True, tol=0.03):
    """Like compare, but two placements match when every matrix entry is
    within ``tol`` (inches for the translation, plain for the 3x3)."""
    A = [x for x in a if not (only_visible and x[3])]
    B = [x for x in b if not (only_visible and x[3])]
    buckets = collections.defaultdict(list)
    for x in B:
        buckets[(x[0], x[1], x[3])].append(x)
    matched = 0
    extra = []
    for x in A:
        cands = buckets.get((x[0], x[1], x[3]), [])
        hit = next((i for i, y in enumerate(cands)
                    if all(abs(p - q) <= tol for p, q in zip(x[2], y[2]))), None)
        if hit is None:
            extra.append(x)
        else:
            cands.pop(hit)
            matched += 1
    missing = [y for v in buckets.values() for y in v]
    return matched, len(B), extra, missing
