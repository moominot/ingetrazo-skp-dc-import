# SPDX-License-Identifier: GPL-3.0-or-later
"""What the online sources (Poly Haven, ambientCG) share: requests that only
reach the source's own servers (redirects followed by hand and checked),
thumbnails and downloads kept in a cache folder, and the ``.pbr.json``
manifest written next to a material's colour image so a renderer can find
its other maps.

The networking runs on QNetworkAccessManager: nothing blocks the window."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

_log = logging.getLogger(__name__)

MAX_REDIRECTS = 5
#: manifest keys (version 1), in the order a renderer reads them
MAP_KEYS = ("color", "normal_gl", "normal_dx", "roughness", "ao", "displacement",
            "metalness", "opacity", "arm")


def user_agent() -> str:
    from . import __version__
    return f"IngeTrazo-asset-manager/{__version__}"


def host_allowed(url: str, hosts) -> bool:
    """https only, and the host is one of ``hosts`` or below one of them."""
    u = urlsplit(str(url))
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts)


def safe_target(root: Path, rel: str) -> Path:
    """``root/rel``, refusing any path that would land outside ``root``
    (absolute, a drive, «..»)."""
    p = PurePosixPath(str(rel).replace("\\", "/"))
    if p.is_absolute() or not p.parts or any(part in ("..", "") or ":" in part for part in p.parts):
        raise ValueError(f"unsafe path in the asset: {rel!r}")
    target = (root / Path(*p.parts)).resolve()
    if root.resolve() not in target.parents:
        raise ValueError(f"unsafe path in the asset: {rel!r}")
    return target


def safe_name(text: str) -> str:
    return "".join(ch for ch in str(text) if ch.isalnum() or ch in "_-") or "asset"


def file_ok(path: Path, md5: str = "", size: int = 0) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if size and path.stat().st_size != int(size):
        return False
    if md5:
        h = hashlib.md5()                                   # noqa: S324 - a checksum, not security
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest() == md5
    return True


def write_manifest(color: Path, maps: dict, size_m, source: str, aid: str) -> Path:
    """``<colour stem>.pbr.json`` next to the colour image: the material's
    other maps (relative to that folder), its real size and where it came
    from."""
    data = {"version": 1, "color": color.name}
    for key in MAP_KEYS[1:]:
        p = maps.get(key)
        if p:
            data[key] = Path(p).resolve().relative_to(color.parent.resolve()).as_posix()
    data["size_m"] = [float(size_m[0]), float(size_m[1])]
    data["source"] = source
    data["id"] = aid
    out = color.with_name(color.stem + ".pbr.json")
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return out


def read_manifest(color: Path) -> dict | None:
    p = Path(color).with_name(Path(color).stem + ".pbr.json")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def mark_complete(root: Path, main: Path) -> None:
    rel = Path(main).resolve().relative_to(Path(root).resolve()).as_posix()
    (root / ".complete").write_text(rel, encoding="utf-8")


def cached_main(root: Path) -> Path | None:
    done = root / ".complete"
    if done.is_file():
        main = root / done.read_text(encoding="utf-8").strip()
        if main.is_file():
            return main
    return None


class Client:
    """Requests restricted to ``hosts``; callbacks run in the GUI thread."""

    MAX_THUMBS = 6

    def __init__(self, hosts, parent=None):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtNetwork import QNetworkAccessManager
        self.hosts = tuple(h.lower() for h in hosts)
        self.net = QNetworkAccessManager(parent)
        self._thumb_queue: list = []
        self._thumb_busy = 0
        self._thumb_wanted: set = set()
        self._live: set = set()               # replies still running
        self._closing = False
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.abort_all)

    def abort_all(self):
        """Stop every request still running (the app is closing: a reply
        left open kept it from exiting)."""
        self._closing = True
        self._thumb_queue.clear()
        for reply in list(self._live):
            try:
                reply.abort()
            except RuntimeError:
                pass
        self._live.clear()

    def get(self, url: str, done, _hops: int = 0):
        """GET ``url``; ``done(bytes or None, error str)``. Redirects are
        followed only to the allowed hosts."""
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
        if not host_allowed(url, self.hosts):
            done(None, f"not an allowed address: {url}")
            return None
        if self._closing:
            done(None, "closing")
            return None
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", user_agent().encode())
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.ManualRedirectPolicy)
        reply = self.net.get(req)
        self._live.add(reply)

        def finished():
            self._live.discard(reply)
            if self._closing:
                reply.deleteLater()
                return
            try:
                status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
                target = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
                if status in (301, 302, 303, 307, 308) and target is not None:
                    if _hops >= MAX_REDIRECTS:
                        done(None, "too many redirects")
                    else:
                        nxt = urljoin(url, target.toString())
                        self.get(nxt, done, _hops + 1)
                elif reply.error() == QNetworkReply.NoError:
                    done(bytes(reply.readAll()), "")
                else:
                    done(None, reply.errorString())
            except Exception:  # noqa: BLE001 - a callback must not kill the loop
                _log.exception("network callback failed")
            finally:
                reply.deleteLater()

        reply.finished.connect(finished)
        return reply

    # -- thumbnails --
    def thumbnail(self, key: str, url: str, path: Path, done):
        """``done(path)`` once the thumbnail is on disk (at once if cached)."""
        if path.is_file():
            done(path)
            return
        if key in self._thumb_wanted or not url:
            return
        self._thumb_wanted.add(key)
        self._thumb_queue.append((key, url, path, done))
        self._pump()

    def forget_thumbs(self):
        for key, *_rest in self._thumb_queue:
            self._thumb_wanted.discard(key)
        self._thumb_queue.clear()

    def _pump(self):
        while self._thumb_queue and self._thumb_busy < self.MAX_THUMBS:
            key, url, path, done = self._thumb_queue.pop(0)
            self._thumb_busy += 1

            def got(data, _err, key=key, path=path, done=done):
                self._thumb_busy -= 1
                self._thumb_wanted.discard(key)
                if data:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    done(path)
                self._pump()

            self.get(url, got)

    # -- files --
    def fetch_all(self, plan, done, progress=None):
        """Download ``plan`` = [(target path, url, md5, size), …], skipping
        files already there; ``done(error str)`` ('' when all went well)."""
        todo = [(t, u, m, s) for t, u, m, s in plan if not file_ok(t, m, s)]
        total = len(todo)
        if not todo:
            done("")
            return
        state = {"left": total, "failed": ""}

        def one(target, url, md5, size):
            def got(data, err):
                if data is None:
                    state["failed"] = state["failed"] or f"{target.name}: {err}"
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    if not file_ok(target, md5, size):
                        state["failed"] = state["failed"] or f"{target.name}: checksum differs"
                state["left"] -= 1
                if progress:
                    progress(total - state["left"], total)
                if state["left"] == 0:
                    done(state["failed"])
            self.get(url, got)

        for target, url, md5, size in todo:
            one(target, url, md5, size)
