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
MODEL_SUFFIXES = (".igz", ".skp")
_SETTINGS_KEY = "asset_manager/folders"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SKP_HEAD = 512 * 1024           # the preview sits in the first bytes


#: A model or texture set of this many bytes or more is flagged as heavy.
HEAVY_BYTES = 100 * 1024 * 1024
HEAVY_MARK = "⚠ "


def size_text(n: int) -> str:
    """``n`` bytes as KB / MB / GB, for a label."""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}".replace(".0 ", " ")
        n /= 1024
    return ""


@dataclass
class Item:
    name: str
    path: Path                      # the file, or the zip that holds it
    preview: Path | None
    folder: Path | None = None
    member: str | None = None       # inside a zip: the model's path there
    maps: dict | None = None        # a material: key -> file name (or zip member)
    size: int = 0                   # bytes of the file(s) it takes; 0 = not known

    @property
    def heavy(self) -> bool:
        return self.size >= HEAVY_BYTES

    @property
    def kind(self) -> str:
        if self.maps:
            return "material"
        return Path(self.member or self.path.name).suffix.lower().lstrip(".")

    @property
    def key(self) -> str:
        """Tells items apart (several can live in one zip or folder)."""
        if self.maps:
            return f"{self.path}::{self.maps['color']}"
        return f"{self.path}::{self.member}" if self.member else str(self.path)

    @property
    def label(self) -> str:
        where = " (zip)" if self.path.suffix.lower() == ".zip" else ""
        weight = f"  ·  {size_text(self.size)}" if self.size else ""
        return f"{HEAVY_MARK if self.heavy else ''}{self.name}  ·  {self.kind}{where}{weight}"


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
            sizes = {i.filename: i.file_size for i in z.infolist() if not i.filename.endswith("/")}
            names = list(sizes)
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        return []
    if len(names) > MAX_ZIP_MEMBERS:
        return []
    names = [n for n in names if "__MACOSX" not in n]
    out = []
    for n in names:
        if n.lower().endswith(MODEL_SUFFIXES):
            stem = Path(n.replace("\\", "/").split("/")[-1]).stem
            out.append(Item(stem, p, None, root, member=n, size=sizes.get(n, 0)))
    by_dir: dict = {}
    for n in names:
        by_dir.setdefault(n.rsplit("/", 1)[0] if "/" in n else "", []).append(n)
    for _d, group in sorted(by_dir.items()):
        for maps in materials.find_sets(group):
            name = materials.set_name(maps["color"].split("/")[-1], p.stem)
            out.append(Item(name, p, None, root, maps=maps,
                            size=sum(sizes.get(m, 0) for m in maps.values())))
    return out


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def scan(folder: Path | None = None) -> list[Item]:
    """The models and material sets under ``folder`` (subfolders and zips
    included), by name; with no folder, those of every catalog folder."""
    from . import materials
    roots = [Path(folder)] if folder else folders()
    items = []
    for root in roots:
        if not root.is_dir():
            continue
        found = []
        for dirpath, _dirs, files in os.walk(root):
            d = Path(dirpath)
            for fn in files:
                p = d / fn
                suffix = p.suffix.lower()
                if suffix in MODEL_SUFFIXES:
                    prev = next((p.with_suffix(s) for s in PREVIEW_SUFFIXES
                                 if p.with_suffix(s).is_file()), None)
                    found.append(Item(p.stem, p, prev, root, size=_file_size(p)))
                elif suffix == ".zip":
                    found += _zip_items(p, root)
            images = [fn for fn in files if fn.lower().endswith(materials.IMAGE_SUFFIXES)]
            for maps in materials.find_sets(images):
                color = d / maps["color"]
                found.append(Item(materials.set_name(maps["color"], d.name), color, color,
                                  root, maps=maps,
                                  size=sum(_file_size(d / m) for m in maps.values())))
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
        if item.path.suffix.lower() == ".zip":
            return read_member(item.path, item.maps["color"], 40 * 1024 * 1024)
        try:
            return Path(item.path).read_bytes()
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
    src_tag = f"{item.path}|{item.maps['color']}|{item.path.stat().st_mtime}"
    tag = hashlib.sha1(src_tag.encode()).hexdigest()[:10]
    out_dir = home() / "materials" / f"{online.safe_name(item.name)}_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, name in item.maps.items():
        target = online.safe_target(out_dir, name.replace("\\", "/").split("/")[-1])
        if not target.is_file():
            if item.path.suffix.lower() == ".zip":
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
    online.write_manifest(color, paths, (1.0, 1.0), "catalog", item.name)
    return color, paths


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
