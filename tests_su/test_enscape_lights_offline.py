"""Offline, no Qt: Enscape's LightData XML becomes Render Studio lights.
argv: <extension repo> [<a .skp with Enscape lights>]"""
import math
import os
import re
import sys
import zipfile

EXT = os.path.abspath(sys.argv[1])
sys.path[:0] = [EXT]
from skp_dc_import import enscape_lights as E

fails = []


def ok(c, w):
    print(("PASS " if c else "FAIL ") + w, flush=True)
    if not c:
        fails.append(w)


def xml(kind, body):
    return ('<?xml version="1.0"?>\n<SketchupLight xmlns:xsi="http://www.w3.org/2001/'
            'XMLSchema-instance" xsi:type="Sketchup%sLight">%s</SketchupLight>' % (kind, body))


p = E.parse(xml("Point", "<Luminosity>1000</Luminosity><LightSourceRadius>0.5</LightSourceRadius>"))
ok(p and p["type"] == "point" and p["power"] == 1000 and p["unit"] == "lm", "point: lumens")
ok(p["radius"] == 0.5, "point: radius is already metres")
ok(p["dir"] == [0, 0, 1] and p["pos"] == [0, 0, 0] and p["kelvin"] is None, "own axes, white")

s = E.parse(xml("Spot", "<Luminosity>2000</Luminosity><BeamAngle>1.0471975511965976</BeamAngle>"))
ok(s["type"] == "spot" and abs(s["spot_angle"] - 60) < 1e-9, "spot: beam angle radians -> degrees")

d = E.parse(xml("Disk", "<Luminosity>1000</Luminosity><LightSourceRadius>19.68503937007874</LightSourceRadius>"))
ok(d["shape"] == "disk" and abs(d["size"] - 1.0) < 1e-9, "disk: 19.685 in radius -> 1 m across")

r = E.parse(xml("Rectangular", "<Luminosity>1</Luminosity><Width>39.76377952755906</Width>"
                               "<Length>39.37007874015748</Length>"))
ok(abs(r["size"] - 1.01) < 1e-9 and abs(r["size_y"] - 1.0) < 1e-9, "rectangle: inches -> metres")

li = E.parse(xml("Linear", "<Luminosity>1</Luminosity><Length>39.37007874015748</Length>"))
ok(li["type"] == "area" and abs(li["size_y"] - 1.0) < 1e-9 and li["size"] < 0.05, "linear: a thin strip along Y")

class _E:
    def __init__(self, text):
        self.attribute_dictionaries = {E.DICT: {E.KEY: text}}


tube = E.lights_of(None, _E(xml("Linear", "<Luminosity>1000</Luminosity><Length>39.37007874015748</Length>")))
ok(len(tube) == 4 and all("_tube" not in t for t in tube), "linear: a tube is four lights")
ok(abs(sum(t["power"] for t in tube) - 1000) < 1e-9, "linear: the four share the lumens")
ok(sorted(tuple(t["dir"]) for t in tube) == [(-1, 0, 0), (0, 0, -1), (0, 0, 1), (1, 0, 0)],
   "linear: facing +Z, -Z, +X, -X (all round)")
ok(all(abs(max(t["size"], t["size_y"]) - 1.0) < 1e-9 for t in tube), "linear: each as long as the tube")
ok(all(t["size_y"] > 0.5 for t in tube if abs(t["dir"][2]) == 1) and
   all(t["size"] > 0.5 for t in tube if abs(t["dir"][0]) == 1), "linear: length along Y whichever way it faces")
ok(len({t["id"] for t in tube}) == 4, "linear: four distinct ids")
ok(E.parse(xml("Sun", "<Luminosity>1</Luminosity>")) is None, "unknown kind -> None")
ok(E.parse("<nope/>") is None and E.parse(None) is None, "not a light -> None")
ok(E.parse(xml("Point", "<Luminosity>nan</Luminosity>"))["power"] == 1000.0, "garbage number -> default")


class Ent:
    def __init__(self, text):
        self.attribute_dictionaries = {E.DICT: {E.KEY: text}} if text else {}


inst, defn = Ent(None), Ent(xml("Point", "<Luminosity>5</Luminosity>"))
ok(E.lights_of(defn, inst)[0]["power"] == 5, "falls back to the definition's data")
ok(E.lights_of(Ent(None), Ent(None)) == [], "no data, no light")
ext = E.with_lights({"skp_dc_import": {"x": 1}}, E.lights_of(defn, inst))
ok(ext["skp_dc_import"] == {"x": 1} and len(ext["render_studio"]["lights"]) == 1, "keeps the other data")
ok(ext["render_studio"]["hide_in_render"] is True, "the symbol is flagged to stay out of the render")

if len(sys.argv) > 2:
    z = zipfile.ZipFile(sys.argv[2]).read("model.dat")
    texts = [m.group(0).decode("utf-8", "replace")
             for m in re.finditer(rb'<\?xml version="1.0"\?>\s*<SketchupLight.*?</SketchupLight>', z, re.S)]
    got = [E.parse(t) for t in texts]
    print([(g["type"], g.get("shape"), round(g["power"])) for g in got])
    ok(len(got) >= 5 and all(got), "the real file: its lights are read")

print("FAILS:", fails)
sys.exit(1 if fails else 0)
