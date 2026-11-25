# SPDX-License-Identifier: GPL-3.0-or-later
"""ambientCG (ambientcg.com): free CC0 PBR materials, through its public
API. A material is downloaded as the site's zip of maps; its images are
taken out (nothing else from the zip is kept) and a ``.pbr.json`` manifest
is written next to the colour image."""
from __future__ import annotations

import json
import logging
import time
import zipfile
from pathlib import Path, PurePosixPath

from . import online

_log = logging.getLogger(__name__)

KEY = "ambientcg"
LABEL = "ambientCG"
API = "https://ambientcg.com/api/v2/full_json"
SITE = "https://ambientcg.com/a/{id}"
ZIP = "https://ambientcg.com/get?file={id}_{res}-JPG.zip"
HDRI_ZIP = "https://ambientcg.com/get?file={id}_{res}.zip"
CREDIT = 'Free CC0 assets from <a href="https://ambientcg.com">ambientcg.com</a>.'
HOSTS = ("ambientcg.com", "struffelproductions.com")
KINDS = (("HDRIs (360° backgrounds)", "hdris"), ("Materials", "materials"))
#: The API's asset types of each kind. The Materials tab also lists the
#: site's decals and atlases: they come as the same zip of maps (with an
#: opacity map), and show up as categories of their own.
API_TYPE = {"hdris": ("HDRI",), "materials": ("Material", "Decal", "Atlas")}
#: The extra category an asset type is listed under, besides its own.
TYPE_CATEGORY = {"Decal": "Decals", "Atlas": "Atlases"}
RESOLUTIONS = ("1k", "2k", "4k")
PAGE = 500
LISTING_MAX_AGE = 24 * 3600
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")
#: the zip's map names (file name ending) -> the manifest's keys
MAPS = (("_Color", "color"), ("_NormalGL", "normal_gl"), ("_NormalDX", "normal_dx"),
        ("_Roughness", "roughness"), ("_AmbientOcclusion", "ao"),
        ("_Displacement", "displacement"), ("_Metalness", "metalness"), ("_Opacity", "opacity"))
MAX_UNZIPPED = 1_500_000_000        # bytes: a 4K set is ~300 MB; past this it is not a material
MAX_MEMBERS = 64


def cache_root() -> Path:
    from .catalog import home
    return home() / KEY


def entry(a: dict) -> dict:
    """One asset of the API as ``{id, name, categories, tags, size_m, thumb}``."""
    aid = str(a.get("assetId") or "")
    cat = str(a.get("displayCategory") or "").strip()
    extra = TYPE_CATEGORY.get(a.get("dataType"))
    thumbs = a.get("previewImage") or {}
    return {
        "id": aid,
        "name": str(a.get("displayName") or aid),
        "categories": [c for c in (cat, extra) if c],
        "tags": [str(t) for t in (a.get("tags") or [])],
        "dimensions_cm": [a.get("dimensionX"), a.get("dimensionY")],
        "thumb": thumbs.get("128-PNG") or thumbs.get("256-PNG") or "",
    }


def entries(pages: list[dict], kind: str = "materials") -> list[dict]:
    want = API_TYPE.get(kind, API_TYPE["materials"])
    out, seen = [], set()
    for page in pages:
        for a in page.get("foundAssets") or []:
            if not isinstance(a, dict) or a.get("dataType") not in (None, *want):
                continue
            e = entry(a)
            if e["id"] and e["id"] not in seen:
                seen.add(e["id"])
                out.append(e)
    return sorted(out, key=lambda e: e["name"].lower())


def tile_size_m(e: dict) -> tuple[float, float]:
    """The material's real size in metres (the API gives centimetres)."""
    try:
        w, h = (float(v) / 100.0 for v in e["dimensions_cm"])
        if w > 0 and h > 0:
            return w, h
    except (KeyError, TypeError, ValueError):
        pass
    return 1.0, 1.0


def map_key(name: str):
    """The manifest key of a file in the zip (by its name's ending), or None."""
    stem = PurePosixPath(name).stem
    for ending, key in MAPS:
        if stem.endswith(ending):
            return key
    return None


def extract_maps(zip_path: Path, root: Path) -> dict:
    """Take the material's images out of the zip into ``root`` (flat, by
    their own file name; nothing else is written). Returns manifest key ->
    path."""
    maps = {}
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNZIPPED:
            raise ValueError("the zip is not a material set")
        for info in infos:
            name = PurePosixPath(info.filename.replace("\\", "/")).name
            if info.is_dir() or not name.lower().endswith(IMAGE_SUFFIXES):
                continue
            key = map_key(name)
            if key is None or key in maps:
                continue
            target = online.safe_target(root, name)
            with z.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            maps[key] = target
    if "color" not in maps:
        raise ValueError("no colour image in the material")
    return maps


#: The 360° image inside an HDRI's zip: the full-range one, never the
#: tone-mapped preview, the Blender file or the USD.
HDRI_FILES = ("_HDR.exr", ".hdr", ".exr")


def pick_hdri(names) -> str | None:
    """The zip member to use as the 360° background, or None."""
    names = [str(n) for n in names]
    for ending in HDRI_FILES:
        for n in names:
            if n.lower().endswith(ending.lower()) and "tonemapped" not in n.lower():
                return n
    return None


def extract_hdri(zip_path: Path, root: Path) -> Path:
    """Take the 360° image out of an HDRI's zip into ``root`` (just that file)."""
    with zipfile.ZipFile(zip_path) as z:
        infos = {i.filename: i for i in z.infolist() if not i.is_dir()}
        if len(infos) > MAX_MEMBERS:
            raise ValueError("the zip is not an HDRI")
        member = pick_hdri(infos)
        if member is None:
            raise ValueError("no 360° image in the zip")
        if infos[member].file_size > MAX_UNZIPPED:
            raise ValueError("the image is too big")
        target = online.safe_target(root, PurePosixPath(member.replace("\\", "/")).name)
        with z.open(infos[member]) as src, open(target, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)
    return target


def asset_dir(aid: str, res: str, kind: str = "materials") -> Path:
    return cache_root() / kind / online.safe_name(aid) / res


class Source:
    key, label, credit, kinds, resolutions = KEY, LABEL, CREDIT, KINDS, RESOLUTIONS

    def __init__(self, parent=None):
        self.client = online.Client(HOSTS, parent)

    def site(self, e) -> str:
        return SITE.format(id=e["id"])

    def tile_size_m(self, e):
        return tile_size_m(e)

    def cached(self, kind, e, res):
        return online.cached_main(asset_dir(e["id"], res, kind))

    def listing(self, kind: str, done, refresh: bool = False):
        """Every asset of ``kind`` (the API pages 500 at a time); cached for a day."""
        # "-2": the Materials list now holds decals and atlases too, so a
        # list cached before that is not reused.
        path = cache_root() / f"{kind}-2.json"
        fresh = path.is_file() and time.time() - path.stat().st_mtime < LISTING_MAX_AGE

        def from_disk():
            return json.loads(path.read_text(encoding="utf-8"))

        if fresh and not refresh:
            try:
                done(from_disk(), "")
                return
            except (OSError, ValueError):
                pass
        pages: list = []
        include = "previewData,displayData,tagData,dimensionsData"

        def fetch(offset):
            self.client.get(f"{API}?type={','.join(API_TYPE[kind])}&sort=Popular&limit={PAGE}&offset={offset}"
                            f"&include={include}", lambda d, err: got(offset, d, err))

        def got(offset, data, err):
            if data is None:
                try:
                    done(from_disk(), "")
                except (OSError, ValueError):
                    done(entries(pages, kind), err)
                return
            try:
                page = json.loads(data.decode("utf-8"))
            except ValueError as exc:
                done(entries(pages, kind), f"unreadable listing: {exc}")
                return
            pages.append(page)
            total = int(page.get("numberOfResults") or 0)
            got_n = len(page.get("foundAssets") or [])
            if got_n and offset + PAGE < total:
                fetch(offset + PAGE)
                return
            items = entries(pages, kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(items), encoding="utf-8")
            done(items, "")

        fetch(0)

    def thumb_path(self, e):
        return cache_root() / "thumbs" / f"{online.safe_name(e['id'])}.png"

    def thumbnail(self, e, done):
        path = cache_root() / "thumbs" / f"{online.safe_name(e['id'])}.png"
        self.client.thumbnail(KEY + e["id"], e.get("thumb", ""), path, done)

    def forget_thumbs(self):
        self.client.forget_thumbs()

    def download(self, kind: str, e: dict, res: str, done, progress=None, confirm=None):
        aid = e["id"]
        root = asset_dir(aid, res, kind)
        hit = online.cached_main(root)
        if hit is not None:
            done(hit, "")
            return
        root.mkdir(parents=True, exist_ok=True)
        zip_path = root / f"{online.safe_name(aid)}_{res.upper()}.zip"

        def fetched(failed):
            if failed:
                done(None, failed)
                return
            if kind == "hdris":
                try:
                    image = extract_hdri(zip_path, root)
                    online.mark_complete(root, image)
                except Exception as exc:  # noqa: BLE001
                    done(None, f"could not read the HDRI: {exc}")
                    return
                finally:
                    try:
                        zip_path.unlink()
                    except OSError:
                        pass
                done(image, "")
                return
            try:
                maps = extract_maps(zip_path, root)
                online.write_manifest(maps["color"], maps, tile_size_m(e), KEY, aid)
                online.mark_complete(root, maps["color"])
            except Exception as exc:  # noqa: BLE001
                done(None, f"could not read the material: {exc}")
                return
            finally:
                try:
                    zip_path.unlink()                 # the zip this download just wrote
                except OSError:
                    pass
            done(maps["color"], "")

        url = (HDRI_ZIP if kind == "hdris" else ZIP).format(id=aid, res=res.upper())
        self.client.fetch_all([(zip_path, url, "", 0)], fetched, progress)
