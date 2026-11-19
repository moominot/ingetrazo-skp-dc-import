"""Import a .skp, export it with skp_export, read the export back and
compare: placements, dynamic attributes (definition + instance, merged per
placement) and hidden flags. argv: <ingetrazo-src> <extension repo> <skp> <out.skp>"""
import os, sys, collections
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SRC, EXT, SKP, OUT = [os.path.abspath(a) for a in sys.argv[1:5]]
sys.path[:0] = [SRC, EXT]
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from core.scene import Scene
from skp_dc_import import builder, reader, skp_export

def summary(model):
    """Per top-level instance: (#placements, #hidden, merged DC values)."""
    defs = model.definitions
    out = {}
    def walk(inst, acc, depth):
        d = defs.get(inst.ref_idx)
        if d is None or depth > 12:
            return
        m = dict(reader.dynamic_attributes(d)); m.update(reader.dynamic_attributes(inst))
        acc["n"] += 1
        acc["hidden"] += bool(getattr(inst, "hidden", False))
        acc["values"].update((k, repr(round(v, 4)) if isinstance(v, float) else repr(v)) for k, v in m.items())
        for c in d.instances:
            walk(c, acc, depth + 1)
    for inst in model.root.instances:
        d = defs.get(inst.ref_idx)
        name = reader.dynamic_attributes(d).get("_name") or reader.dynamic_attributes(inst).get("_name") or d.name
        acc = {"n": 0, "hidden": 0, "values": collections.Counter()}
        walk(inst, acc, 0)
        out[str(name)] = acc
    return out

src = reader.parse(SKP)
scene = Scene(); builder.build(scene, src, SKP)
skp_export.save_skp(scene, OUT)
back = reader.parse(OUT)
a, b = summary(src), summary(back)
print("exported", os.path.getsize(OUT), "bytes; version", back.version)
for name in a:
    x, y = a[name], b.get(name)
    if y is None:
        print("MISSING", name); continue
    lost = x["values"] - y["values"]; extra = y["values"] - x["values"]
    print(f"{name:18} placements {x['n']}->{y['n']} hidden {x['hidden']}->{y['hidden']} "
          f"| attribute values {sum(x['values'].values())}->{sum(y['values'].values())} lost {sum(lost.values())} extra {sum(extra.values())}")
    for k in list(lost)[:3]: print("     lost ", k)
    for k in list(extra)[:3]: print("     extra", k)
