# SPDX-License-Identifier: GPL-3.0-or-later
"""Names for the materials of an imported glTF model.

IngeTrazo's glTF reader paints each face with its colour or texture but gives
the paint no NAME: the Materials panel then lists nothing, or anonymous
entries. Here every distinct paint the model wears is registered in the
scene's material registry under a name that points back at the model:

    «ArmChair_01»                  one material, named like the model
    «ArmChair_01 · Fabric»         several: the model, then the glTF's own name
    «ArmChair_01 · 2»              a paint the file does not name

and the faces that wear it get ``attrs["mat"]``. The face's own texture
mapping is left as it is (it is what draws it); the registry entry only
says what the paint is called.

No Qt here; the glTF's JSON is read for names and image names only.
"""
from __future__ import annotations

import json
import logging
import re
import struct
from pathlib import Path, PurePosixPath

_log = logging.getLogger(__name__)

#: «ArmChair_01_1k» -> «ArmChair_01» (Poly Haven adds the size to the file).
_SIZE_SUFFIX = re.compile(r"[_-]\d+k$", re.I)
SEP = " · "


def model_title(path) -> str:
    """The model's name, from its file."""
    return _SIZE_SUFFIX.sub("", Path(path).stem) or Path(path).stem


def read_json(path) -> dict | None:
    """The JSON part of a .gltf or .glb; None when it cannot be read."""
    path = Path(path)
    try:
        if path.suffix.lower() == ".gltf":
            return json.loads(path.read_text(encoding="utf-8"))
        data = path.read_bytes()
        if data[:4] != b"glTF":
            return None
        length, kind = struct.unpack_from("<II", data, 12)
        if kind != 0x4E4F534A:                  # "JSON"
            return None
        return json.loads(data[20:20 + length].decode("utf-8"))
    except (OSError, ValueError, struct.error):
        _log.debug("could not read the glTF's JSON", exc_info=True)
        return None


def _image_name(js, tex_info) -> str:
    """How the reader's copy of the image a texture points at is called:
    ``img_<index>`` (the reader extracts every image under that name), or, for
    a file it left where it was, the file's own lower-case name."""
    if not isinstance(tex_info, dict):
        return ""
    textures = js.get("textures") or []
    i = tex_info.get("index")
    if not isinstance(i, int) or not (0 <= i < len(textures)):
        return ""
    src = textures[i].get("source")
    images = js.get("images") or []
    if not isinstance(src, int) or not (0 <= src < len(images)):
        return ""
    return f"img_{src}"


def materials_of(js) -> list:
    """``[{"name", "image", "color"}]`` for each glTF material: its own name,
    its colour map's file name and its base colour (0..1)."""
    out = []
    for m in (js or {}).get("materials") or []:
        pbr = m.get("pbrMetallicRoughness") or {}
        sg = (m.get("extensions") or {}).get("KHR_materials_pbrSpecularGlossiness") or {}
        image = _image_name(js, pbr.get("baseColorTexture") or sg.get("diffuseTexture"))
        factor = pbr.get("baseColorFactor") or sg.get("diffuseFactor") or (1.0, 1.0, 1.0, 1.0)
        out.append({"name": str(m.get("name") or "").strip(), "image": image,
                    "color": tuple(float(c) for c in factor[:3])})
    return out


def _signature(attrs):
    """What a face's paint is, for grouping: its texture file or its colour."""
    if not attrs:
        return None
    tex = attrs.get("texture")
    if isinstance(tex, dict) and tex.get("path"):
        return ("tex", PurePosixPath(str(tex["path"]).replace("\\", "/")).name.lower())
    color = attrs.get("color")
    if color is not None:
        return ("col", tuple(round(float(c), 3) for c in color[:3]),
                round(float(attrs.get("opacity", 1.0)), 3))
    return None


def _label(title, own, index, only) -> str:
    if own:
        return title if own.lower() == title.lower() else f"{title}{SEP}{own}"
    return title if only else f"{title}{SEP}{index}"


def name_materials(scene, path, title=None) -> list:
    """Register the model's paints in ``scene.materials`` under names that
    refer to the model and stamp them on the faces. Returns the names."""
    from core.group import iter_placements
    from core.materials import Material, register

    title = title or model_title(path)
    js = read_json(path) or {}
    gltf_mats = materials_of(js)

    meshes, seen = [], set()
    for top in list(getattr(scene, "groups", ()) or ()):
        for g, _m in iter_placements(top):
            if id(g.mesh) not in seen:
                seen.add(id(g.mesh))
                meshes.append(g.mesh)
    if getattr(scene, "mesh", None) is not None and id(scene.mesh) not in seen:
        meshes.append(scene.mesh)

    # The distinct paints, in the order the faces show them.
    sigs: dict = {}
    for mesh in meshes:
        for f in mesh.faces:
            sig = _signature(f.attrs)
            if sig is not None and sig not in sigs:
                sigs[sig] = f.attrs
    if not sigs:
        return []

    def own_name(sig):
        for gm in gltf_mats:
            if sig[0] == "tex" and gm["image"] and gm["image"] == PurePosixPath(sig[1]).stem:
                return gm["name"]
        if sig[0] == "col":
            for gm in gltf_mats:
                if not gm["image"] and all(abs(a - b) < 0.002 for a, b in zip(gm["color"], sig[1])):
                    return gm["name"]
        return ""

    if getattr(scene, "materials", None) is None:
        scene.materials = {}
    names: dict = {}
    for i, (sig, attrs) in enumerate(sigs.items(), 1):
        label = _label(title, own_name(sig), i, only=len(sigs) == 1)
        tex = attrs.get("texture")
        mat = Material(label,
                       color=tuple(attrs["color"]) if attrs.get("color") is not None else None,
                       texture=({k: v for k, v in tex.items() if k in ("path", "sw", "sh")}
                                if isinstance(tex, dict) else None),
                       opacity=attrs.get("opacity"))
        names[sig] = register(scene.materials, mat)
    for mesh in meshes:
        for f in mesh.faces:
            sig = _signature(f.attrs)
            if sig is not None and f.attrs is not None:
                f.attrs["mat"] = names[sig]
    return list(dict.fromkeys(names.values()))
