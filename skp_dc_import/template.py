# SPDX-License-Identifier: GPL-3.0-or-later
"""The blank .skp that the exporter needs, and why it is not shipped.

OpenSKP builds every .skp by splicing geometry into SketchUp's own empty
document (``blank_v17.skp``, bytes from Trimble's SDK). This extension does
not distribute it. The user gets it once, either from OpenSKP (pinned commit,
checked against its SHA-256) or by choosing a copy they already have. Only
that exact file works: the writer's offsets are specific to its bytes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

_log = logging.getLogger(__name__)

SHA256 = "809a1ab73a20a192ab13aaff197afb1c67d0e9352f6a353a9cd8030919f8a6c3"
FILE_NAME = "blank_v17.skp"
# Pinned to a commit, never a branch: what is checked must not change.
UPSTREAM_COMMIT = "1636ba2bb095bb9e3ba7efd886cc457aff03fcd8"
UPSTREAM_REPO = "https://github.com/iamahsanmehmood/openskp"
URL = (f"https://raw.githubusercontent.com/iamahsanmehmood/openskp/"
       f"{UPSTREAM_COMMIT}/packages/python/src/openskp/_scaffold/{FILE_NAME}")

OK, MISSING, BAD = "ok", "missing", "bad"


def data_dir() -> Path:
    """Per-user folder of this extension (created on demand)."""
    override = os.environ.get("SKP_DC_IMPORT_HOME")
    if override:
        base = Path(override)
    else:
        try:
            from PySide6.QtCore import QStandardPaths
            loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            base = Path(loc) if loc else Path.home() / ".ingetrazo"
        except Exception:  # noqa: BLE001 - no Qt: tests, scripts
            base = Path.home() / ".ingetrazo"
    return base / "skp_dc_import"


def _config_file() -> Path:
    return data_dir() / "config.json"


def _read_config() -> dict:
    try:
        return json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def default_path() -> Path:
    return data_dir() / FILE_NAME


def configured_path() -> Path:
    cfg = _read_config().get("template")
    return Path(cfg) if cfg else default_path()


def sha256_of(path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def check(path=None) -> tuple[str, str]:
    """(state, message). state is OK, MISSING or BAD."""
    p = Path(path) if path else configured_path()
    digest = sha256_of(p)
    if digest is None:
        return MISSING, f"No blank .skp at {p}"
    if digest != SHA256:
        return BAD, (f"{p.name} is not the expected file (SHA-256 {digest[:12]}…, "
                     f"expected {SHA256[:12]}…). Only the exact original works.")
    return OK, f"Ready: {p}"


def bundled_path() -> Path:
    """Where a build that ships the template carries it (the vendored
    OpenSKP loads it from here by itself)."""
    return Path(__file__).parent / "_vendor" / "openskp" / "_scaffold" / FILE_NAME


def status() -> tuple[str, str]:
    bundled = bundled_path()
    if bundled.is_file():
        state, msg = check(bundled)
        if state == OK:
            return OK, f"Included with this build: {bundled}"
    return check()


def apply() -> bool:
    """Tell the vendored OpenSKP where the template is. True when usable."""
    state, _ = status()
    if state != OK:
        return False
    if bundled_path().is_file() and check(bundled_path())[0] == OK:
        return True   # the vendored OpenSKP finds it by itself
    import importlib
    # not `from … import create`: the package re-exports a function by that name
    mod = importlib.import_module("._vendor.openskp.create", __package__)
    mod.set_scaffold_path(str(configured_path()))
    return True


def _store(src: Path) -> Path:
    dest = default_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    cfg = _read_config()
    cfg["template"] = str(dest)
    _config_file().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return dest


def install_from_file(path) -> Path:
    """Verify ``path`` and keep a copy. Raises ValueError if it is not the
    exact template."""
    state, msg = check(path)
    if state != OK:
        raise ValueError(msg)
    dest = _store(Path(path))
    apply()
    return dest


def download(url: str = URL, timeout: float = 60.0) -> Path:
    """Fetch the template from OpenSKP and install it if its hash matches.
    Raises ValueError (wrong content) or OSError (network)."""
    req = urllib.request.Request(url, headers={"User-Agent": "skp-dc-import"})
    fd, tmp = tempfile.mkstemp(suffix=".skp")
    os.close(fd)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        return install_from_file(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
