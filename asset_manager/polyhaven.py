# SPDX-License-Identifier: GPL-3.0-or-later
"""Poly Haven (polyhaven.com): free CC0 HDRIs, materials and 3-D models,
through its public API. A material comes with all its maps (colour, normal,
roughness, AO, displacement, metal) and a ``.pbr.json`` manifest."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path, PurePosixPath

from . import online
from .online import safe_target  # noqa: F401 - part of this module's API

_log = logging.getLogger(__name__)

KEY = "polyhaven"
LABEL = "Poly Haven"
API = "https://api.polyhaven.com"
THUMB = "https://cdn.polyhaven.com/asset_img/thumbs/{id}.png?width=128&height=128"
SITE = "https://polyhaven.com/a/{id}"
CREDIT = 'Free CC0 assets from <a href="https://polyhaven.com">polyhaven.com</a>.'
HOSTS = ("polyhaven.com", "polyhaven.org")
KINDS = (("HDRIs (360° backgrounds)", "hdris"), ("Materials", "materials"), ("3-D models", "models"))
TYPES = {"hdris": "hdris", "materials": "textures", "models": "models"}
RESOLUTIONS = ("1k", "2k", "4k")
LISTING_MAX_AGE = 24 * 3600
#: Poly Haven's map names -> the manifest's keys
MATERIAL_MAPS = (("Diffuse", "color"), ("nor_gl", "normal_gl"), ("Rough", "roughness"),
                 ("AO", "ao"), ("Displacement", "displacement"), ("Metal", "metalness"),
                 ("arm", "arm"))


def cache_root() -> Path:
    from .catalog import home
    return home() / KEY


def allowed_url(url: str) -> bool:
    return online.host_allowed(url, HOSTS)


# --- listings -------------------------------------------------------------------
def entries(listing: dict) -> list[dict]:
    """The API's ``{id: info}`` as a list of ``{id, name, categories, …}``,
    by name."""
    out = []
    for aid, info in (listing or {}).items():
        if not isinstance(info, dict):
            continue
        e = dict(info)
        e["id"] = aid
        e["name"] = str(info.get("name") or aid)
        e["categories"] = [str(c) for c in (info.get("categories") or [])]
        e["thumb"] = THUMB.format(id=aid)
        out.append(e)
    return sorted(out, key=lambda e: e["name"].lower())


def categories(items: list[dict], top: int = 40) -> list[str]:
    """The most used categories, most common first."""
    count: dict[str, int] = {}
    for e in items:
        for c in e["categories"]:
            count[c] = count.get(c, 0) + 1
    return [c for c, _n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]


def matches(e: dict, text: str = "", category: str = "") -> bool:
    if category and category not in e["categories"]:
        return False
    text = text.strip().lower()
    if not text:
        return True
    hay = " ".join([e["id"], e["name"], *e["categories"], *(e.get("tags") or [])]).lower()
    return all(word in hay for word in text.split())


def tile_size_m(e: dict) -> tuple[float, float]:
    """A material's real size in metres (the API gives millimetres); 1 m
    when it does not say."""
    dims = e.get("dimensions") or []
    try:
        w, h = float(dims[0]) / 1000.0, float(dims[1]) / 1000.0
        if w > 0 and h > 0:
            return w, h
    except (IndexError, TypeError, ValueError):
        pass
    return 1.0, 1.0


# --- what to download -------------------------------------------------------
def _pick_res(block: dict, res: str) -> dict | None:
    """The block of ``res``, else the nearest smaller one, else any."""
    if not isinstance(block, dict):
        return None
    if res in block:
        return block[res]
    order = [r for r in ("8k", "4k", "2k", "1k") if r in block]
    smaller = [r for r in order if int(r[:-1]) <= int(res[:-1])]
    pick = smaller[0] if smaller else (order[-1] if order else None)
    return block.get(pick) if pick else None


def files_for(kind: str, files: dict, res: str):
    """(the main file's relative path, [(relative path, url, md5), …], maps)
    of what ``kind`` needs at ``res`` — an HDRI's .hdr; a material's colour
    image and its other maps (``maps``: manifest key -> relative path); a
    model's .gltf with every file it refers to."""
    if kind == "hdris":
        blk = _pick_res(files.get("hdri"), res) or {}
        f = blk.get("hdr") or blk.get("exr")
        if not f:
            raise ValueError("no HDRI file")
        name = PurePosixPath(f["url"]).name
        return name, [(name, f["url"], f.get("md5", ""))], {}
    if kind == "materials":
        todo, maps = [], {}
        for api_key, key in MATERIAL_MAPS:
            blk = _pick_res(files.get(api_key), res) or {}
            f = blk.get("jpg") or blk.get("png")
            if not f:
                continue
            name = PurePosixPath(f["url"]).name
            todo.append((name, f["url"], f.get("md5", "")))
            maps[key] = name
        if "color" not in maps:
            raise ValueError("no colour image")
        return maps["color"], todo, maps
    if kind == "models":
        blk = (_pick_res(files.get("gltf"), res) or {}).get("gltf")
        if not blk:
            raise ValueError("no glTF file")
        main = PurePosixPath(blk["url"]).name
        out = [(main, blk["url"], blk.get("md5", ""))]
        for rel, f in (blk.get("include") or {}).items():
            out.append((rel, f["url"], f.get("md5", "")))
        return main, out, {}
    raise ValueError(kind)


def asset_dir(kind: str, aid: str, res: str) -> Path:
    return cache_root() / kind / online.safe_name(aid) / res


def cached_main(kind: str, aid: str, res: str) -> Path | None:
    """The asset's main file when a complete download is in the cache."""
    return online.cached_main(asset_dir(kind, aid, res))


# --- the source ------------------------------------------------------------------
class Source:
    key, label, credit, kinds, resolutions = KEY, LABEL, CREDIT, KINDS, RESOLUTIONS

    def __init__(self, parent=None):
        self.client = online.Client(HOSTS, parent)

    def site(self, e) -> str:
        return SITE.format(id=e["id"])

    def tile_size_m(self, e):
        return tile_size_m(e)

    def cached(self, kind, e, res):
        return cached_main(kind, e["id"], res)

    def listing(self, kind: str, done, refresh: bool = False):
        """``done(list of entries, error)``; cached on disk for a day."""
        api_type = TYPES[kind]
        path = cache_root() / f"assets_{api_type}.json"
        fresh = path.is_file() and time.time() - path.stat().st_mtime < LISTING_MAX_AGE

        def from_disk():
            return entries(json.loads(path.read_text(encoding="utf-8")))

        if fresh and not refresh:
            try:
                done(from_disk(), "")
                return
            except (OSError, ValueError):
                pass

        def got(data, err):
            if data is None:
                try:
                    done(from_disk(), "")          # offline: the old listing will do
                except (OSError, ValueError):
                    done([], err)
                return
            try:
                parsed = json.loads(data.decode("utf-8"))
            except ValueError as exc:
                done([], f"unreadable listing: {exc}")
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(parsed), encoding="utf-8")
            done(entries(parsed), "")

        self.client.get(f"{API}/assets?t={api_type}", got)

    def thumbnail(self, e, done):
        path = cache_root() / "thumbs" / f"{online.safe_name(e['id'])}.png"
        self.client.thumbnail(KEY + e["id"], e.get("thumb") or THUMB.format(id=e["id"]), path, done)

    def forget_thumbs(self):
        self.client.forget_thumbs()

    def download(self, kind: str, e: dict, res: str, done, progress=None):
        """Fetch what ``kind`` needs of ``e`` at ``res`` into the cache;
        ``done(main file path or None, error)``. Files already there (same
        checksum) are not fetched again."""
        aid = e["id"]
        hit = cached_main(kind, aid, res)
        if hit is not None:
            done(hit, "")
            return

        def got_files(data, err):
            if data is None:
                done(None, err)
                return
            try:
                main, todo, maps = files_for(kind, json.loads(data.decode("utf-8")), res)
                bad = [url for _r, url, _m in todo if not allowed_url(url)]
                if bad:
                    raise ValueError(f"a file outside Poly Haven: {bad[0]}")
                root = asset_dir(kind, aid, res)
                root.mkdir(parents=True, exist_ok=True)
                plan = [(online.safe_target(root, rel), url, md5, 0) for rel, url, md5 in todo]
            except Exception as exc:  # noqa: BLE001
                done(None, str(exc))
                return

            def fetched(failed):
                if failed:
                    done(None, failed)
                    return
                main_path = online.safe_target(root, main)
                if kind == "materials":
                    online.write_manifest(main_path, {k: root / v for k, v in maps.items()},
                                          tile_size_m(e), KEY, aid)
                online.mark_complete(root, main_path)
                done(main_path, "")

            self.client.fetch_all(plan, fetched, progress)

        self.client.get(f"{API}/files/{aid}", got_files)
