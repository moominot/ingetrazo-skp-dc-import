# SPDX-License-Identifier: GPL-3.0-or-later
"""Material sets downloaded by hand from any site: a folder or a zip with a
colour image and its other maps (normal, roughness, AO…), told apart by the
words the sites put in the file names. Pure Python: no Qt."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".webp", ".bmp", ".tga")

#: manifest key -> words that name that map (checked as whole words of the
#: file name, last word first: «Wood_Floor_Normal_GL» is a normal map).
WORDS = {
    "color": ("color", "colour", "col", "albedo", "basecolor", "base", "diffuse", "diff", "diffusemap"),
    "normal_gl": ("normalgl", "nor_gl", "normal_gl", "norgl"),
    "normal_dx": ("normaldx", "nor_dx", "normal_dx", "nordx"),
    "normal": ("normal", "nor", "nrm", "norm", "normals", "normalmap"),
    "roughness": ("roughness", "rough", "rgh"),
    "ao": ("ao", "ambientocclusion", "occlusion", "ambient_occlusion", "occ"),
    "displacement": ("displacement", "disp", "height", "bump", "heightmap"),
    "metalness": ("metalness", "metallic", "metal", "met"),
    "opacity": ("opacity", "alpha", "mask", "transparency"),
    "arm": ("arm",),
}
_SPLIT = re.compile(r"[^a-z0-9]+")
_RES = re.compile(r"^\d+k$|^\d{3,5}$|^(jpg|png|exr)$")


def _words(name: str) -> list[str]:
    stem = PurePosixPath(name).stem.lower()
    return [w for w in _SPLIT.split(stem.replace("-", "_")) if w and not _RES.match(w)]


def map_key(name: str):
    """The map a file name names (a manifest key, with a plain «normal»
    read as the OpenGL one), or None."""
    if not str(name).lower().endswith(IMAGE_SUFFIXES):
        return None
    words = _words(name)
    joined = "_".join(words)
    for key in ("normal_gl", "normal_dx"):           # two-word names first
        if any(joined.endswith(w) or ("_" + w + "_") in ("_" + joined + "_") for w in WORDS[key]):
            return key
    for w in reversed(words):
        for key, names in WORDS.items():
            if w in names:
                return "normal_gl" if key == "normal" else key
    return None


_ALL_MAP_WORDS = {w for names in WORDS.values() for w in names} | {"gl", "dx"}


def base_of(name: str) -> str:
    """What the maps of one material share in their names: the words that
    are not a map word or a resolution («Bricks097_1K-JPG_NormalGL» →
    «bricks097»)."""
    return "_".join(w for w in _words(name) if w not in _ALL_MAP_WORDS)


def find_sets(names) -> list[dict]:
    """Every material among ``names`` (maps grouped by the name they share)."""
    groups: dict = {}
    for n in names:
        if map_key(n):
            groups.setdefault(base_of(n), []).append(n)
    return [s for s in (find_set(g) for _b, g in sorted(groups.items())) if s]


def find_set(names) -> dict:
    """``{key: name}`` for a group of file names that make one material: a
    colour image and at least one other map. ``{}`` when they do not."""
    maps: dict = {}
    for n in sorted(names, key=lambda s: (len(s), s)):
        key = map_key(n)
        if key and key not in maps:
            maps[key] = n
    if "color" not in maps or len(maps) < 2:
        return {}
    return maps


def set_name(color_name: str, folder_name: str = "") -> str:
    """A readable name for the material: the colour image's name without the
    map word and the resolution, else the folder's."""
    words = _words(color_name)
    keep = [w for w in words if w not in WORDS["color"]]
    name = " ".join(keep).strip()
    return name.title() if name else (folder_name or PurePosixPath(color_name).stem)
