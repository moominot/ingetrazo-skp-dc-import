# SPDX-License-Identifier: GPL-3.0-or-later
"""The user's own catalog: folders of models (.igz and .skp), each with an
optional preview next to it (same name, .png/.jpg). No database: the
folders are the catalog, so they can be synced, shared or kept in version
control. A .skp usually carries its own preview inside; it is used when
there is no image next to it."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PREVIEW_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
MODEL_SUFFIXES = (".igz", ".skp", ".gltf", ".glb")
HDRI_SUFFIXES = (".hdr", ".exr")
MANIFEST_END = ".pbr.json"
RSMAT = ".rsmat"                 # Render Studio's material file (JSON, pictures in a folder beside it)
RSMAT_FORMAT = "render-studio-material"
IGMAT = ".igmat"                 # IngeTrazo's own material file: a ZIP with material.json and textures/
_IGMAT_DOC_MAX = 8 << 20         # a material.json larger than this is not one
SKM = ".skm"                     # a SketchUp material file: a ZIP with document.xml and the pictures under ref/
_SKM_DOC_MAX = 8 << 20
_INCH = 0.0254                   # a .skm gives the tile size in inches
ZIP_LIKE = (".zip", IGMAT, SKM)  # files whose members are read from inside
#: sub-folders of the extension's own folder where saved assets go
SAVE_DIRS = {"materials": "Materials", "models": "Models", "hdris": "Backgrounds"}
_SETTINGS_KEY = "asset_manager/folders"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SKP_HEAD = 512 * 1024           # the preview sits in the first bytes


@dataclass
class Item:
    name: str
    path: Path                      # the file, or the zip that holds it
    preview: Path | None
    folder: Path | None = None
    member: str | None = None       # inside a zip: the model's path there
    maps: dict | None = None        # a material: key -> file name (or zip member)
    spec: dict | None = None        # a material kept with a manifest (.pbr.json): its content
    scene_mat: object | None = None  # a material of the open drawing (core.materials.Material)

    @property
    def is_material(self) -> bool:
        return bool(self.maps) or self.spec is not None or self.scene_mat is not None

    @property
    def type_key(self) -> str:
        """``material``, ``background`` or ``model``: what the type filter tells apart."""
        return "material" if self.is_material else "background" if self.is_hdri else "model"

    @property
    def is_hdri(self) -> bool:
        return not self.is_material and self.path.suffix.lower() in HDRI_SUFFIXES

    @property
    def kind(self) -> str:
        if self.is_material:
            return "material"
        if self.is_hdri:
            return "background"
        return Path(self.member or self.path.name).suffix.lower().lstrip(".")

    @property
    def key(self) -> str:
        """Tells items apart (several can live in one zip or folder)."""
        if self.scene_mat is not None:
            return f"drawing::{self.name}"
        if self.spec is not None:
            n = self.spec.get("index")
            return f"{self.path}::material" + (f"::{n}" if n else "")
        if self.maps:
            return f"{self.path}::{self.maps['color']}"
        return f"{self.path}::{self.member}" if self.member else str(self.path)

    @property
    def label(self) -> str:
        where = (" (zip)" if self.path.suffix.lower() == ".zip" else
                 " (drawing)" if self.scene_mat is not None else "")
        return f"{self.name}  ·  {self.kind}{where}"


def home() -> Path:
    override = os.environ.get("ASSET_MANAGER_HOME")
    if override:
        return Path(override)
    try:
        from PySide6.QtCore import QStandardPaths
        loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        base = Path(loc) if loc else Path.home() / ".ingetrazo"
    except Exception:  # noqa: BLE001
        base = Path.home() / ".ingetrazo"
    return base / "asset_manager"


def default_folder() -> Path:
    return home() / "catalog"


# --- the folders -----------------------------------------------------------
def _settings():
    from PySide6.QtCore import QSettings
    return QSettings()


def folders() -> list[Path]:
    """The catalog folders: the extension's own one first, then the ones the
    user added, in the order they were added."""
    out = [default_folder()]
    try:
        raw = _settings().value(_SETTINGS_KEY, []) or []
    except Exception:  # noqa: BLE001
        raw = []
    if isinstance(raw, str):
        raw = [raw]
    for f in raw:
        p = Path(str(f))
        if str(f) and all(p != q for q in out):
            out.append(p)
    return out


def _save(extra: list[Path]) -> None:
    _settings().setValue(_SETTINGS_KEY, [str(p) for p in extra])


def add_folder(path) -> bool:
    """Add ``path`` to the catalog; False when it is already there."""
    p = Path(path)
    current = folders()
    if any(p == q for q in current):
        return False
    _save(current[1:] + [p])
    return True


def remove_folder(path) -> bool:
    """Take ``path`` off the catalog (its files stay where they are). The
    extension's own folder cannot be removed."""
    p = Path(path)
    current = folders()
    if p == current[0] or not any(p == q for q in current):
        return False
    _save([q for q in current[1:] if q != p])
    set_watched(p, False)
    return True


# --- folders watched in real time ----------------------------------------------
_WATCH_KEY = "asset_manager/watched"


def _str_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw else []
    return [str(x) for x in raw if str(x)]


def watched() -> list[Path]:
    """The catalog folders watched in real time (the others are read again
    with Update)."""
    try:
        raw = _str_list(_settings().value(_WATCH_KEY, []))
    except Exception:  # noqa: BLE001
        raw = []
    known = folders()
    return [q for q in known if any(Path(r) == q for r in raw)]


def is_watched(path) -> bool:
    return any(Path(path) == q for q in watched())


def set_watched(path, on: bool) -> None:
    p = Path(path)
    current = [q for q in watched() if q != p]
    if on:
        current.append(p)
    _settings().setValue(_WATCH_KEY, [str(q) for q in current])


# --- model sites -------------------------------------------------------------------
_SITES_KEY = "asset_manager/sites"
_PROXY_KEY = "asset_manager/as_proxy"


def as_proxy() -> bool:
    """Whether models from the catalog and online go in as proxies."""
    try:
        v = _settings().value(_PROXY_KEY, False)
    except Exception:  # noqa: BLE001
        return False
    return v is True or str(v).lower() in ("true", "1")


def set_as_proxy(on: bool) -> None:
    _settings().setValue(_PROXY_KEY, bool(on))


def valid_url(url: str) -> bool:
    from urllib.parse import urlsplit
    u = urlsplit(str(url).strip())
    return u.scheme in ("http", "https") and bool(u.hostname)


def sites() -> list[tuple[str, str]]:
    """The model sites the user added: ``[(name, url), …]``, in order."""
    import json
    try:
        raw = _settings().value(_SITES_KEY, "") or ""
        data = json.loads(raw) if isinstance(raw, str) and raw else []
    except Exception:  # noqa: BLE001
        data = []
    out = []
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, (list, tuple)) and len(entry) == 2 and valid_url(entry[1]):
            out.append((str(entry[0]).strip() or str(entry[1]), str(entry[1]).strip()))
    return out


def set_sites(entries) -> None:
    import json
    clean = [(str(n).strip() or str(u).strip(), str(u).strip())
             for n, u in entries if valid_url(u)]
    _settings().setValue(_SITES_KEY, json.dumps(clean))


def site_name(url: str) -> str:
    """A name for a site from its address («www.example.com/x» → «example.com»)."""
    from urllib.parse import urlsplit
    host = (urlsplit(str(url).strip()).hostname or str(url)).lower()
    return host[4:] if host.startswith("www.") else host


def subfolders(root, limit: int = 400) -> list[Path]:
    """``root`` and the folders under it (at most ``limit``), for watching."""
    root = Path(root)
    out = [root] if root.is_dir() else []
    for dirpath, dirs, _files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for d in dirs:
            out.append(Path(dirpath) / d)
            if len(out) >= limit:
                return out
    return out


# --- the models ------------------------------------------------------------
MAX_ZIP_MEMBERS = 2000


def _zip_items(p: Path, root: Path) -> list[Item]:
    """The models and the material sets a downloaded zip holds."""
    import zipfile

    from . import materials
    try:
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        return []
    if len(names) > MAX_ZIP_MEMBERS:
        return []
    names = [n for n in names if "__MACOSX" not in n]
    out = []
    for n in names:
        if n.lower().endswith(MODEL_SUFFIXES):
            stem = Path(n.replace("\\", "/").split("/")[-1]).stem
            out.append(Item(stem, p, None, root, member=n))
    by_dir: dict = {}
    for n in names:
        by_dir.setdefault(n.rsplit("/", 1)[0] if "/" in n else "", []).append(n)
    for _d, group in sorted(by_dir.items()):
        for maps in materials.find_sets(group):
            name = materials.set_name(maps["color"].split("/")[-1], p.stem)
            out.append(Item(name, p, None, root, maps=maps))
    return out


def read_spec(path: Path) -> dict | None:
    """The content of a material manifest, or None when it is not one."""
    import json
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not (data.get("color") or data.get("rgb")):
        return None
    return data


def read_rsmat(path: Path) -> dict | None:
    """A Render Studio ``.rsmat`` as a material spec (colour, picture,
    size, translucency, finish), or None when it is not one. The picture's
    path is relative to the file's folder."""
    import json
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != RSMAT_FORMAT:
        return None
    tex = data.get("texture") if isinstance(data.get("texture"), dict) else {}
    spec = {"name": data.get("name") or Path(path).stem, "source": "rsmat"}
    if isinstance(data.get("color"), (list, tuple)) and len(data["color"]) >= 3:
        spec["rgb"] = [float(c) for c in data["color"][:3]]
    if tex.get("path"):
        spec["color"] = str(tex["path"]).replace("\\", "/")
        spec["size_m"] = [float(tex.get("sw") or 1.0), float(tex.get("sh") or 1.0)]
    if data.get("opacity") is not None:
        spec["opacity"] = float(data["opacity"])
    if data.get("finish"):
        spec["finish"] = str(data["finish"])
    return spec if (spec.get("color") or spec.get("rgb")) else None


def read_igmat(path: Path) -> list[dict]:
    """The materials of an IngeTrazo ``.igmat`` as specs (colour, picture, size, translucency, finish): the file is a ZIP with
    ``material.json`` and the pictures under ``textures/``, so a spec's ``color`` is the picture's member inside the file. One
    file can hold several (each spec has its ``index``). ``[]`` when it is not one. Render Studio's settings, which its own
    files carry beside, are not read here: its **Load material…** brings them."""
    import json
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("material.json")
            if info.file_size > _IGMAT_DOC_MAX:
                return []
            data = json.loads(z.read(info).decode("utf-8"))
            members = set(z.namelist())
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, RuntimeError):
        return []
    raw = data.get("materials") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not isinstance(data.get("format"), int) or data["format"] > 1:
        return []
    out = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict) or not str(r.get("name") or "").strip():
            continue
        spec = {"name": str(r["name"]).strip(), "source": "igmat", "index": i}
        try:
            if isinstance(r.get("color"), (list, tuple)) and len(r["color"]) >= 3:
                spec["rgb"] = [float(c) for c in r["color"][:3]]
            tex = r.get("texture") if isinstance(r.get("texture"), dict) else {}
            if isinstance(tex.get("embed"), str) and tex["embed"] in members:
                spec["color"] = tex["embed"]
                spec["size_m"] = [float(tex.get("sw") or 1.0), float(tex.get("sh") or 1.0)]
            if r.get("opacity") is not None:
                spec["opacity"] = float(r["opacity"])
        except (TypeError, ValueError):
            continue
        if r.get("finish"):
            spec["finish"] = str(r["finish"])
        if spec.get("color") or spec.get("rgb"):
            out.append(spec)
    return out


def read_skm(path: Path) -> dict | None:
    """A SketchUp ``.skm`` material file as a spec (colour, picture, tile size, translucency, and the roughness, occlusion and metal
    maps), or None when it is not one. The file is a ZIP: ``document.xml`` describes the material and the pictures are under
    ``ref/``, so a spec's ``color`` and ``maps`` are members of the file. Read with the standard library, which refuses a file that
    declares a DTD. Its normal map is left out: the file says which way its green channel points only as a number
    (``normalMapStyle``) that could not be checked against a render, and a map read the wrong way gives the relief upside down."""
    import zipfile
    from xml.etree import ElementTree as ET
    try:
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("document.xml")
            if info.file_size > _SKM_DOC_MAX:
                return None
            raw = z.read(info)
            members = [n for n in z.namelist() if not n.endswith("/")]
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError):
        return None
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    nodes: dict = {}
    for el in root.iter():
        nodes.setdefault(el.tag.rsplit("}", 1)[-1], el)       # names are matched without their namespace
    mat = nodes.get("material")
    if mat is None:
        return None

    def number(v, default=None):
        try:
            n = float(v)
            return n if n == n else default
        except (TypeError, ValueError):
            return default

    def member_of(file_name):
        """The member of the ZIP a ``path`` / file name of the XML points to (under ``ref/``, else anywhere by its name)."""
        base = str(file_name or "").replace("\\", "/").rsplit("/", 1)[-1]
        if not base:
            return None
        for n in members:
            if n == "ref/" + base:
                return n
        return next((n for n in members if n.rsplit("/", 1)[-1] == base), None)

    spec = {"name": (mat.get("name") or "").strip() or Path(path).stem, "source": "skm"}
    rgb = [number(mat.get(k)) for k in ("colorRed", "colorGreen", "colorBlue")]
    if all(c is not None for c in rgb):
        rgb = [max(0.0, min(1.0, c / 255.0)) for c in rgb]
    else:
        rgb = None
    if number(mat.get("useTrans"), 0) == 1 and number(mat.get("trans")) is not None:
        spec["opacity"] = max(0.0, min(1.0, 1.0 - number(mat.get("trans"))))
    tex = nodes.get("texture")
    color = None
    if tex is not None:
        image = next((e for e in tex.iter() if e.tag.rsplit("}", 1)[-1] == "image"), None)
        color = member_of(image.get("path") if image is not None else None) or member_of(tex.get("textureFilename"))
        if color is None:
            refs = [n for n in members if n.startswith("ref/")]
            color = refs[0] if len(refs) == 1 else None
    if color is not None:
        spec["color"] = color
        sx, sy = number(tex.get("xScale")), number(tex.get("yScale"))
        spec["size_m"] = [sx * _INCH if sx and sx > 0 else 1.0, sy * _INCH if sy and sy > 0 else 1.0]
        maps = {}
        for tag, key, switch in (("roughness_texture", "roughness", "enable_roughness"),
                                 ("occlusion_texture", "ao", "enable_occlusion"),
                                 ("metallic_texture", "metalness", "enable_metalness")):
            el, on = nodes.get(tag), nodes.get(switch)
            if el is None or (on is not None and (on.text or "").strip() == "0"):
                continue
            m = member_of(el.get("path"))
            if m is not None:
                maps[key] = m
        if maps:
            spec["maps"] = maps
    elif rgb is not None:
        spec["rgb"] = rgb
    return spec if (spec.get("color") or spec.get("rgb")) else None


def _manifest_items(d: Path, files, root: Path) -> tuple[list[Item], set]:
    """The materials the ``.pbr.json`` manifests of folder ``d`` describe,
    and the image names they use (so the loose-image reader skips them)."""
    from .online import MAP_KEYS
    items, used = [], set()
    for fn in files:
        low = fn.lower()
        if low.endswith(IGMAT):
            for spec in read_igmat(d / fn):
                maps = {"color": spec["color"]} if spec.get("color") else None
                items.append(Item(spec["name"], d / fn, None, root, maps=maps, spec=spec))
            continue
        if low.endswith(SKM):
            spec = read_skm(d / fn)
            if spec is not None:
                maps = ({"color": spec["color"], **spec.get("maps", {})} if spec.get("color") else None)
                items.append(Item(spec["name"], d / fn, None, root, maps=maps, spec=spec))
            continue
        if low.endswith(RSMAT):
            spec = read_rsmat(d / fn)
        elif low.endswith(MANIFEST_END):
            spec = read_spec(d / fn)
        else:
            continue
        if spec is None:
            continue
        maps = {}
        if spec.get("color"):
            maps["color"] = str(spec["color"])
            for key in MAP_KEYS[1:]:
                if isinstance(spec.get(key), str):
                    maps[key] = spec[key]
            if not (d / maps["color"]).is_file():
                continue
        used |= {m.replace("\\", "/") for m in maps.values()}
        name = str(spec.get("name") or "").strip() or fn.rsplit(".", 1)[0]
        color = d / maps["color"] if maps else None
        if color is None and isinstance(spec.get("preview"), str) and (d / spec["preview"]).is_file():
            color = d / spec["preview"]          # a plain colour: the picture saved with it
            used.add(spec["preview"])
        items.append(Item(name, d / fn, color, root, maps=maps or None, spec=spec))
    return items, used


def scan(folder: Path | None = None) -> list[Item]:
    """The models, backgrounds and material sets under ``folder``
    (subfolders and zips included), by name; with no folder, those of every
    catalog folder."""
    from . import materials
    roots = [Path(folder)] if folder else folders()
    items = []
    for root in roots:
        if not root.is_dir():
            continue
        found = []
        model_dirs: set = set()
        for dirpath, _dirs, files in os.walk(root):
            d = Path(dirpath)
            if any(fn.lower().endswith((".gltf", ".glb")) for fn in files):
                model_dirs.add(d)
            # a model's textures (in its folder or below) are not materials
            has_model = d in model_dirs or any(q in model_dirs for q in d.parents)
            saved, used = _manifest_items(d, files, root)
            found += saved
            images = [fn for fn in files if fn.lower().endswith(materials.IMAGE_SUFFIXES)
                      and fn not in used]
            loose = [] if has_model else materials.find_sets(images)
            in_sets = {n for m in loose for n in m.values()}
            for fn in files:
                p = d / fn
                suffix = p.suffix.lower()
                if suffix in MODEL_SUFFIXES or suffix in HDRI_SUFFIXES:
                    if suffix in HDRI_SUFFIXES and (fn in used or fn in in_sets or has_model):
                        continue
                    prev = next((p.with_suffix(s) for s in PREVIEW_SUFFIXES
                                 if p.with_suffix(s).is_file()), None)
                    found.append(Item(p.stem, p, prev, root))
                elif suffix == ".zip":
                    found += _zip_items(p, root)
            for maps in loose:
                color = d / maps["color"]
                found.append(Item(materials.set_name(maps["color"], d.name), color, color,
                                  root, maps=maps))
        items += found
    return sorted(items, key=lambda i: (i.name.lower(), i.key.lower()))


def read_member(path, member: str, limit: int | None = None) -> bytes | None:
    """The bytes of ``member`` inside the zip ``path`` (at most ``limit``)."""
    import zipfile
    try:
        with zipfile.ZipFile(path) as z, z.open(member) as fh:
            return fh.read(limit) if limit else fh.read()
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError):
        return None


def preview_bytes(item: Item) -> bytes | None:
    """An image for the item's icon: the .skp's own preview, or a
    material's colour image (from the zip when it is in one)."""
    if item.maps:
        if item.path.suffix.lower() in ZIP_LIKE:
            return read_member(item.path, item.maps["color"], 40 * 1024 * 1024)
        try:
            return (Path(item.path).parent / item.maps["color"]).read_bytes()
        except OSError:
            return None
    if item.kind == "skp":
        if item.member:
            return _png_in(read_member(item.path, item.member, _SKP_HEAD) or b"")
        return skp_preview(item.path)
    return None


def extract(item: Item) -> Path:
    """The model inside a zip, taken out to the extension's folder (once),
    for the importer. Only that one file is written."""
    import hashlib

    from .online import safe_name
    tag = hashlib.sha1(f"{item.path}|{item.path.stat().st_mtime}".encode()).hexdigest()[:10]
    out_dir = home() / "extracted" / f"{safe_name(item.path.stem)}_{tag}"
    out = out_dir / Path(item.member.replace("\\", "/").split("/")[-1]).name
    if not out.is_file():
        data = read_member(item.path, item.member)
        if data is None:
            raise OSError(f"cannot read {item.member} in {item.path.name}")
        out_dir.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return out


def material_files(item: Item) -> tuple[Path, dict]:
    """A copy of the material's maps in the extension's folder, with its
    ``.pbr.json`` manifest (the user's folder is left as it is). Returns
    (the colour image, key -> path)."""
    import hashlib

    from . import online
    if not item.maps:
        raise ValueError("a plain colour has no files")
    src_tag = f"{item.path}|{item.maps['color']}|{item.path.stat().st_mtime}"
    tag = hashlib.sha1(src_tag.encode()).hexdigest()[:10]
    out_dir = home() / "materials" / f"{online.safe_name(item.name)}_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, name in item.maps.items():
        target = online.safe_target(out_dir, name.replace("\\", "/").split("/")[-1])
        if not target.is_file():
            if item.path.suffix.lower() in ZIP_LIKE:
                data = read_member(item.path, name)
            else:
                try:
                    data = (Path(item.path).parent / name).read_bytes()
                except OSError:
                    data = None
            if data is None:
                continue
            target.write_bytes(data)
        paths[key] = target
    color = paths["color"]
    online.write_manifest(color, paths, material_size(item), "catalog", item.name)
    return color, paths


def material_size(item: Item) -> tuple[float, float]:
    """The real size in metres a catalog material was saved with (1 × 1 m
    when it does not say)."""
    try:
        w, h = (float(v) for v in (item.spec or {}).get("size_m") or ())
        if w > 0 and h > 0:
            return w, h
    except (TypeError, ValueError):
        pass
    return 1.0, 1.0


def _png_in(head: bytes) -> bytes | None:
    i = head.find(_PNG_MAGIC)
    if i < 0:
        return None
    j = head.find(b"IEND", i)
    return head[i:j + 8] if j >= 0 else None


def skp_preview(path) -> bytes | None:
    """The PNG preview a .skp file keeps near its start, or None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(_SKP_HEAD)
    except OSError:
        return None
    i = head.find(_PNG_MAGIC)
    if i < 0:
        return None
    j = head.find(b"IEND", i)
    if j < 0:
        return None
    return head[i:j + 8]          # IEND + its CRC


# --- saving into the catalog ---------------------------------------------------
def _target_dir(kind: str, name: str) -> Path:
    from .online import safe_name
    return default_folder() / SAVE_DIRS[kind] / safe_name(name)


def _copy_into(src: Path, dst_dir: Path, rel: str | None = None) -> Path:
    import shutil
    dst = dst_dir / (rel or src.name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _copy_preview(preview, dst_dir: Path, stem: str) -> None:
    """A preview image next to the saved file (same name, .png/.jpg)."""
    if preview and Path(preview).is_file():
        suffix = Path(preview).suffix.lower()
        if suffix in PREVIEW_SUFFIXES:
            _copy_into(Path(preview), dst_dir, stem + suffix)


def save_material(name: str, color_path=None, maps=None, size_m=(1.0, 1.0), rgb=None,
                  opacity=None, finish=None, source: str = "drawing", aid: str = "",
                  preview_png: bytes | None = None):
    """Keep a material in the catalog: a folder of its own with the images
    (``color_path`` and the other ``maps`` {key: path}) and a ``.pbr.json``
    manifest that also holds a plain colour (``rgb``), translucency and
    finish. Returns ``(manifest path, True)``, or ``(path, False)`` when a
    material of that name is already there."""
    import json

    from .online import MAP_KEYS, safe_name
    if not color_path and rgb is None:
        raise ValueError("the material has neither a colour nor an image")
    out_dir = _target_dir("materials", name)
    manifest = out_dir / (safe_name(name) + MANIFEST_END)
    if manifest.is_file():
        return manifest, False
    out_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {"version": 1, "name": name}
    if color_path:
        data["color"] = _copy_into(Path(color_path), out_dir).name
        for key in MAP_KEYS[1:]:
            p = (maps or {}).get(key)
            if p and Path(p).is_file():
                data[key] = _copy_into(Path(p), out_dir).name
    if rgb is not None:
        data["rgb"] = [float(c) for c in rgb[:3]]
    if not color_path and preview_png:           # a plain colour: a simple picture of it
        (out_dir / (safe_name(name) + ".png")).write_bytes(preview_png)
        data["preview"] = safe_name(name) + ".png"
    if opacity is not None:
        data["opacity"] = float(opacity)
    if finish:
        data["finish"] = finish
    data["size_m"] = [float(size_m[0]), float(size_m[1])]
    data["source"] = source
    data["id"] = aid or name
    manifest.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return manifest, True


def _save_scene_material_igmat(mat):
    """The material of the drawing as one ``.igmat`` — IngeTrazo's own file: its picture inside (with the tile size, rotation and
    tint), its colour, translucency and finish; IngeTrazo's own **Import…** takes it too. Only for a material with no maps beside
    its picture (normal, roughness…: the ``.pbr.json`` folder keeps those) and in an IngeTrazo that has the format (0.6.3); else
    None. Returns ``(file, newly saved)``."""
    try:
        from core.materials import Material
        from formats import igmat
    except ImportError:
        return None
    from . import online
    tex = dict(getattr(mat, "texture", None) or {})
    if tex.get("path") and Path(tex["path"]).is_file():
        man = online.read_manifest(Path(tex["path"])) or {}
        if any(isinstance(man.get(k), str) for k in online.MAP_KEYS[1:]):
            return None                          # a set with maps: the manifest folder keeps them
    else:
        tex = {}
    color = getattr(mat, "color", None)
    if not tex and color is None:
        raise ValueError("the material has neither a colour nor an image")
    out_dir = _target_dir("materials", mat.name)
    path = out_dir / (online.safe_name(mat.name) + IGMAT)
    if path.is_file() or (out_dir / (online.safe_name(mat.name) + MANIFEST_END)).is_file():
        return path, False
    out_dir.mkdir(parents=True, exist_ok=True)
    igmat.save_materials(path, [Material(mat.name, color=tuple(color) if color is not None else None,
                                         texture=tex or None, opacity=getattr(mat, "opacity", None),
                                         finish=getattr(mat, "finish", None))])
    return path, True


def save_scene_material(mat, make_preview=None):
    """A material of the drawing (``core.materials.Material``) into the
    catalog: one ``.igmat`` when IngeTrazo has that format and the material
    has no maps beside its picture, else a folder with a ``.pbr.json``
    manifest (a plain colour then gets the picture ``make_preview(color,
    opacity, finish)`` returns, as PNG bytes). Returns ``(file, newly saved)``."""
    from . import online
    saved = _save_scene_material_igmat(mat)
    if saved is not None:
        return saved
    tex = getattr(mat, "texture", None) or {}
    path = tex.get("path")
    color_path = Path(path) if path and Path(path).is_file() else None
    maps = {}
    if color_path is not None:
        man = online.read_manifest(color_path) or {}
        for key in online.MAP_KEYS[1:]:
            if isinstance(man.get(key), str):
                maps[key] = color_path.parent / man[key]
    size = (float(tex.get("sw") or 1.0), float(tex.get("sh") or 1.0))
    rgb, opacity, finish = (getattr(mat, "color", None), getattr(mat, "opacity", None),
                            getattr(mat, "finish", None))
    png = None
    if color_path is None and make_preview is not None:
        try:
            png = make_preview(rgb, opacity, finish)
        except Exception:  # noqa: BLE001 - a preview is a nicety
            png = None
    return save_material(mat.name, color_path, maps, size, rgb=rgb, opacity=opacity,
                         finish=finish, preview_png=png)


def save_online(kind: str, name: str, main, size_m=(1.0, 1.0), source: str = "", aid: str = "",
                preview=None):
    """What was downloaded from an online library (``main``: the colour image
    of a material, the model's .gltf, the background's image) into the
    catalog. Returns ``(path of the saved item, newly saved)``."""
    import shutil

    from . import online
    main = Path(main)
    if kind == "materials":
        man = online.read_manifest(main) or {}
        maps = {k: main.parent / v for k, v in man.items()
                if k in online.MAP_KEYS and isinstance(v, str)}
        return save_material(name, main, maps, man.get("size_m") or size_m,
                             source=source or "online", aid=aid)
    out_dir = _target_dir(kind, name)
    target = out_dir / main.name
    if target.is_file():
        return target, False
    if kind == "models":                # the .gltf with the files it refers to
        shutil.copytree(main.parent, out_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".complete"))
    else:
        _copy_into(main, out_dir)
    _copy_preview(preview, out_dir, main.stem)
    return target, True
