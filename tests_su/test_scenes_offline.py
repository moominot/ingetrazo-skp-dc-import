"""Offline, no Qt: a .skp's saved scenes as plain records (inches -> metres).
argv: <extension repo>"""
import os
import sys
from types import SimpleNamespace as NS

sys.path[:0] = [os.path.abspath(sys.argv[1])]
from skp_dc_import import builder as B

fails = []


def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c:
        fails.append(w)


pages = [
    NS(name="Planta", eye=(0, 0, 3937.0079), target=(0, 0, 0), up=(0, 1, 0), fov=35.0,
       parallel=True, ortho_height=393.7008, hidden_layers=["Mobles"]),
    NS(name="", eye=(100, 0, 50), target=(0, 0, 0), up=None, fov=45.0,
       parallel=False, ortho_height=0.0, hidden_layers=None),
    NS(name="Sense camera", eye=None, target=None),
]
recs = B.scene_records(NS(pages=pages))
ok(len(recs) == 2, "a scene without a camera is skipped")
ok(recs[0]["name"] == "Planta" and abs(recs[0]["eye"][2] - 100.0) < 1e-3, "eye: inches -> metres")
ok(recs[0]["parallel"] and abs(recs[0]["ortho_height"] - 10.0) < 1e-3, "parallel view and its height")
ok(recs[0]["hidden_layers"] == ["Mobles"], "hidden layers kept")
ok(recs[1]["name"] == "Scene 2" and recs[1]["up"] == [0.0, 0.0, 1.0] and recs[1]["hidden_layers"] == [],
   "unnamed scene, default up, no hidden layers")
ok(B.scene_records(NS()) == [] and B.scene_records(NS(pages=None)) == [], "no scenes, no records")

print("FAILS:", fails)
sys.exit(1 if fails else 0)
