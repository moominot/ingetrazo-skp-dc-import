"""asset_manager 0.5: what goes into the catalog (materials of the drawing,
online downloads, .rsmat files) and how it reads back. Pure Python, no Qt,
no network. argv: <extension repo>"""
import json, os, sys, tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp())
os.environ["ASSET_MANAGER_HOME"] = str(tmp / "home")
sys.path.insert(0, os.path.abspath(sys.argv[1]))
from asset_manager import catalog, online

fails = []
def ok(c, w):
    print(("PASS " if c else "FAIL ") + w)
    if not c: fails.append(w)

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6c6d70000000049454e44ae426082")
def scan(): return {i.name: i for i in catalog.scan()}

# an online material (Poly Haven's layout: colour image + maps + manifest)
src = tmp / "cache" / "bricks"; src.mkdir(parents=True)
maps = {"color": src / "Bricks_Diffuse_1k.jpg", "normal_gl": src / "Bricks_nor_gl_1k.jpg", "roughness": src / "Bricks_Rough_1k.jpg"}
for p in maps.values(): p.write_bytes(PNG)
online.write_manifest(maps["color"], maps, (2.0, 1.0), "polyhaven", "bricks")
path, new = catalog.save_online("materials", "Bricks", maps["color"], (2, 1), "polyhaven", "bricks")
ok(new and path.name == "Bricks.pbr.json", "an online material is kept with its manifest")
ok(catalog.save_online("materials", "Bricks", maps["color"])[1] is False, "kept twice: already there")
b = scan()["Bricks"]
ok(b.is_material and b.type_key == "material" and sorted(b.maps) == ["color", "normal_gl", "roughness"], "it reads back with its maps")
ok(catalog.material_size(b) == (2.0, 1.0), "and its real size")
ok(sum(i.is_material for i in catalog.scan()) == 1, "its images are not listed again as a loose set")

# a plain-colour material of the drawing: a generated picture is kept
class Plain: name = "Rojo"; color = (0.8, 0.1, 0.1); texture = None; opacity = 0.5; finish = "glass"
_p, new = catalog.save_scene_material(Plain, lambda c, o, f: PNG)
r = scan()["Rojo"]
ok(new and r.is_material and not r.maps and r.spec["rgb"] == [0.8, 0.1, 0.1], "a plain colour is kept")
ok(r.spec["opacity"] == 0.5 and r.spec["finish"] == "glass", "with its translucency and finish")
ok(r.preview is not None and r.preview.name == "Rojo.png", "and the simple picture beside it")

# a textured material of the drawing: its image and maps are copied
class Tex: name = "Ladrillo"; color = None; texture = {"path": str(maps["color"]), "sw": 2.0, "sh": 1.0}; opacity = None; finish = None
catalog.save_scene_material(Tex)
t = scan()["Ladrillo"]
ok(sorted(t.maps) == ["color", "normal_gl", "roughness"] and catalog.material_size(t) == (2.0, 1.0), "a textured material keeps its image, maps and size")

# a background and a model with its textures
h = tmp / "cache" / "sky"; h.mkdir(); (h / "sky_1k.hdr").write_bytes(b"x"); (tmp / "t.png").write_bytes(PNG)
catalog.save_online("hdris", "Sky", h / "sky_1k.hdr", preview=tmp / "t.png")
m = tmp / "cache" / "chair"; (m / "textures").mkdir(parents=True)
(m / "chair_1k.gltf").write_text("{}"); (m / ".complete").write_text("x")
for n in ("chair_diff_1k.jpg", "chair_nor_gl_1k.jpg"): (m / "textures" / n).write_bytes(PNG)
catalog.save_online("models", "Chair", m / "chair_1k.gltf", preview=tmp / "t.png")
s = scan()
ok(s["sky_1k"].type_key == "background" and s["sky_1k"].preview is not None, "a background is listed with its picture")
ok(s["chair_1k"].type_key == "model" and "Chair" not in s, "a model is listed, and its textures are not taken for a material")
ok(not (catalog.default_folder() / "Models" / "Chair" / ".complete").exists(), "the download's marker is not copied")

# Render Studio's .rsmat files are read
rs = catalog.default_folder() / "rs"; (rs / "Laca").mkdir(parents=True)
(rs / "Laca" / "picture.png").write_bytes(PNG)
(rs / "Laca.rsmat").write_text(json.dumps({"format": "render-studio-material", "version": 1, "name": "Laca",
    "color": [.1, .3, .6], "texture": {"path": "Laca/picture.png", "sw": 2, "sh": 3}, "opacity": .8, "finish": "gloss"}))
(rs / "Plano.rsmat").write_text(json.dumps({"format": "render-studio-material", "version": 1, "name": "Plano", "color": [.1, .3, .6]}))
(rs / "Otro.rsmat").write_text(json.dumps({"format": "something-else"}))
s = scan()
ok(catalog.material_size(s["Laca"]) == (2.0, 3.0) and s["Laca"].spec["finish"] == "gloss", ".rsmat with a picture: size and finish")
ok("Plano" in s and not s["Plano"].maps, ".rsmat with a plain colour")
ok("Otro" not in s, "another JSON is not a material")
f, paths = catalog.material_files(s["Laca"])
ok(f.is_file() and f.name == "picture.png", "its picture goes to the extension's folder to paint with")

print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
