"""asset_manager 0.5: what goes into the catalog (materials of the drawing,
online downloads, .rsmat and .igmat files) and how it reads back. Pure Python, no Qt,
no network. argv: <extension repo> [<IngeTrazo source>: also tries saving as .igmat]"""
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

# IngeTrazo's .igmat files are read (a ZIP: material.json and textures/)
import zipfile
def igmat(path, materials, members=None, fmt=1):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("material.json", json.dumps({"format": fmt, "materials": materials}))
        for name, data in (members or {}).items():
            z.writestr(name, data)
ig = catalog.default_folder() / "ig"; ig.mkdir()
igmat(ig / "Madera.igmat", [{"name": "Madera", "texture": {"embed": "textures/abc-wood.png", "sw": 1.5, "sh": 0.75},
                              "opacity": 0.9, "finish": "satin",
                              "render_studio": {"type": "generic", "roughness": 0.3, "maps": {"glow": {"source": "file", "path": "rs-maps/map-1.png"}}}}],
      {"textures/abc-wood.png": PNG, "rs-maps/map-1.png": PNG})
igmat(ig / "Pinturas.igmat", [{"name": "Azul", "color": [0.1, 0.2, 0.9]}, {"name": "Verde", "color": [0.1, 0.8, 0.2], "opacity": 0.5},
                               {"name": "  "}, {"color": [1, 1, 1]}])
igmat(ig / "Nueva.igmat", [{"name": "Futura", "color": [1, 0, 0]}], fmt=2)
(ig / "Rota.igmat").write_bytes(b"not a zip")
with zipfile.ZipFile(ig / "SinDoc.igmat", "w") as z:
    z.writestr("other.json", "{}")
s = scan()
w = s["Madera"]
ok(w.is_material and w.type_key == "material" and w.maps == {"color": "textures/abc-wood.png"}, ".igmat with a picture: a material, the picture is its member")
ok(catalog.material_size(w) == (1.5, 0.75) and w.spec["finish"] == "satin" and w.spec["opacity"] == 0.9, "...its tile size, translucency and finish")
ok(catalog.preview_bytes(w) == PNG, "...its icon is read from inside the file")
ok(sorted(w.maps) == ["color"], "...Render Studio's settings and map pictures in the same file are left to Render Studio (its own Load brings them)")
ok(s["Azul"].is_material and not s["Azul"].maps and s["Azul"].spec["rgb"] == [0.1, 0.2, 0.9], "a plain colour in an .igmat")
ok(s["Verde"].spec["opacity"] == 0.5 and s["Azul"].key != s["Verde"].key, "several materials in one file: each its own, with its own key")
ok(len([i for i in catalog.scan() if i.path.name == "Pinturas.igmat"]) == 2, "(a nameless one is left out)")
ok("Futura" not in s, "a newer format is left alone")
ok(not any(i.path.name in ("Rota.igmat", "SinDoc.igmat") for i in catalog.scan()), "a file that is not an .igmat lists nothing")
f, paths = catalog.material_files(w)
ok(f.is_file() and f.read_bytes() == PNG and f.name == "abc-wood.png", "its picture goes to the extension's folder to paint with")
ok(catalog.material_files(w)[0] == f, "...once")

# an IngeTrazo that has the format: a drawing's material is kept as one .igmat
if len(sys.argv) > 2:
    sys.path.insert(0, os.path.abspath(sys.argv[2]))
    from core.materials import Material
    from formats import igmat as igm
    pic = tmp / "cache" / "wood.png"; pic.write_bytes(PNG)
    class Madera2: name = "Roble"; color = None; texture = {"path": str(pic), "sw": 1.2, "sh": 0.6}; opacity = 0.8; finish = "satin"
    p, new = catalog.save_scene_material(Madera2)
    ok(new and p.suffix == ".igmat" and p.is_file(), f"a material of the drawing is kept as an .igmat ({p.name})")
    back = igm.load_materials(p)
    ok(len(back) == 1 and back[0].name == "Roble" and back[0].texture["sw"] == 1.2 and back[0].finish == "satin", "...IngeTrazo reads it")
    r = scan()["Roble"]
    ok(r.is_material and catalog.material_size(r) == (1.2, 0.6) and catalog.preview_bytes(r) == PNG, "...and so does the Library")
    ok(catalog.save_scene_material(Madera2)[1] is False, "kept twice: already there")
    class Pintura: name = "Coral"; color = (0.9, 0.4, 0.3); texture = None; opacity = None; finish = None
    p, new = catalog.save_scene_material(Pintura, lambda c, o, f: PNG)
    ok(new and p.suffix == ".igmat" and scan()["Coral"].spec["rgb"] == [0.9, 0.4, 0.3], "a plain colour too (no picture needed: the icon is drawn)")
    # a set with maps beside its picture keeps the manifest folder: the .igmat has no place for them
    class Ladrillo2: name = "Ladrillo2"; color = None; texture = {"path": str(maps["color"]), "sw": 2.0, "sh": 1.0}; opacity = None; finish = None
    p, new = catalog.save_scene_material(Ladrillo2)
    ok(new and p.name.endswith(".pbr.json") and sorted(scan()["Ladrillo2"].maps) == ["color", "normal_gl", "roughness"],
       "a set with maps keeps the .pbr.json folder, with its maps")
    class Nada: name = "Nada"; color = None; texture = None; opacity = None; finish = None
    try:
        catalog.save_scene_material(Nada)
        ok(False, "a material with nothing to keep is refused")
    except ValueError:
        ok(True, "a material with nothing to keep is refused")

print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
