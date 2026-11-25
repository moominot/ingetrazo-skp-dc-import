# SPDX-License-Identifier: GPL-3.0-or-later
"""GC Tune — keeps big models from freezing IngeTrazo for seconds.

Why: IngeTrazo keeps every face, edge and vertex as a Python object. A model
of ~600 000 faces is ~12 million objects, and one *full* garbage collection
over them takes ~8.5 s of a window that does not answer (measured
2026-11-20: ``gc.collect(2)`` 8511 ms; picking itself is < 1 ms). The
collector decides by itself when to run one, so selecting or deleting a
component freezes the app "at random".

What it does:

* After a big document loads (once per document, never because the heap
  merely grew: that is garbage, and freezing it keeps it for good — if it
  grows past 1.5x it warns instead), ``gc.freeze()`` moves every live object into
  the permanent generation, so later collections skip them (8.5 s -> ~1 ms).
  The young-generation threshold is raised like the core does in
  ``settle_heap`` (fewer passes while drawing).
* A stall log: every time the main thread is blocked for more than 300 ms it
  writes how long, whether a garbage collection ran meanwhile, and the last
  command executed (e.g. ``DeleteGroupCommand``). File:
  ``%LOCALAPPDATA%\\IngeTrazo\\gc_tune.log``.
* Extensions menu: **GC Tune: free memory now** (full collection, then
  freeze again) and **GC Tune: status**.

Trade-off: frozen objects are never collected, so reference cycles that die
after the freeze (a deleted component's meshes) are not given back until you
run *free memory now* (or close the tab). Do it from time to time, e.g. before
saving and leaving.
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

__version__ = "0.2.0"

#: Young-generation threshold (the core's own value, see settle_heap).
YOUNG_THRESHOLD = 50_000
#: Do not bother below this many allocated blocks (small models are fine).
MIN_BLOCKS = 2_000_000
#: Freeze again only when the heap grew by this much since the last freeze
#: (a document load), never on ordinary edits.
REFREEZE_GROWTH = 1_000_000
#: A main-thread block longer than this is logged.
STALL_MS = 300
TICK_MS = 50

_S = {
    "frozen_blocks": 0,      # allocated blocks at the last freeze
    "scene_id": None,        # the scene that was in front at that freeze
    "warned": False,
    "app": None,
    "last_tick": None,
    "gen2": 0,
    "last_cmd": ("", 0.0, 0.0),   # (name, ms, wall time)
    "timers": [],
}


def _log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "IngeTrazo" / "gc_tune.log"


def _log(text: str) -> None:
    try:
        p = _log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(time.strftime("%H:%M:%S ") + text + "\n")
    except OSError:
        pass


def _gen2() -> int:
    return gc.get_stats()[2]["collections"]


def freeze_now(reason: str) -> None:
    """Collect the young generations (cheap) and freeze what is left."""
    t0 = time.perf_counter()
    gc.collect(1)
    gc.freeze()
    _S["frozen_blocks"] = sys.getallocatedblocks()
    _S["scene_id"] = _scene_id()
    _S["warned"] = False
    _log(f"freeze ({reason}): {gc.get_freeze_count()} objects frozen, "
         f"{_S['frozen_blocks']:,} blocks, {(time.perf_counter()-t0)*1000:.0f} ms")


#: Heap growth (against the last freeze) that is NOT a document load: a
#: second copy of the model, a huge temporary. Freezing it would freeze the
#: garbage too and it would never come back (2026-11-20: two 3.6 M-face
#: merges left +14 GB until IngeTrazo was closed).
SUSPICIOUS_GROWTH = 1.5


def _scene_id():
    app = _S.get("app")
    try:
        return id(app.scene) if app is not None else None
    except Exception:
        return None


def maybe_freeze(reason: str = "document loaded") -> None:
    """Freeze once per document: the first time, and when another scene is
    in front (New, Open, another tab). Never because the heap merely grew —
    that is what garbage looks like; warn instead."""
    blocks = sys.getallocatedblocks()
    if blocks < MIN_BLOCKS:
        return
    sid = _scene_id()
    if _S["frozen_blocks"] == 0 or sid != _S["scene_id"]:
        _S["scene_id"] = sid
        _S["warned"] = False
        freeze_now(reason)
        return
    grown = blocks - _S["frozen_blocks"]
    if (grown >= REFREEZE_GROWTH
            and blocks > SUSPICIOUS_GROWTH * _S["frozen_blocks"]
            and not _S["warned"]):
        _S["warned"] = True
        msg = (f"heap grew {grown:,} blocks since the freeze "
               f"({_S['frozen_blocks']:,} -> {blocks:,}): not freezing it. "
               "Extensions > GC Tune: free memory now gives it back.")
        _log("WARNING " + msg)
        app = _S.get("app")
        try:
            app.window.viewport.flash_status("GC Tune: " + msg, 10000)
        except Exception:
            pass


def free_memory_now() -> float:
    """Full collection over everything (frozen objects included), then
    freeze again. Returns seconds taken."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.setOverrideCursor(Qt.WaitCursor)
    t0 = time.perf_counter()
    try:
        gc.unfreeze()
        gc.collect()
        try:
            from core import malloc_arenas
            malloc_arenas.trim()
        except Exception:
            pass
        _S["frozen_blocks"] = 0
        freeze_now("free memory")
    finally:
        QApplication.restoreOverrideCursor()
    dt = time.perf_counter() - t0
    _log(f"free memory: full collection took {dt:.1f} s")
    return dt


def _wrap_history() -> None:
    """Remember the last command and how long it took (the command itself,
    not the redraw that follows — the stall watchdog sees that)."""
    from core.history import History
    if getattr(History.execute, "_gc_tune", False):
        return
    orig = History.execute

    def execute(self, cmd):
        t0 = time.perf_counter()
        try:
            return orig(self, cmd)
        finally:
            ms = (time.perf_counter() - t0) * 1000
            _S["last_cmd"] = (type(cmd).__name__, ms, time.time())
            if ms >= 100:
                _log(f"command {type(cmd).__name__}: {ms:.0f} ms")

    execute._gc_tune = True
    execute._orig = orig
    History.execute = execute


def _unwrap_history() -> None:
    from core.history import History
    orig = getattr(History.execute, "_orig", None)
    if orig is not None:
        History.execute = orig


#: (module, class, method): the calls whose cost the log should show.
_TIMED = (
    ("views.viewport", "Viewport", "begin_group_edit"),
    ("views.viewport", "Viewport", "end_group_edit"),
    ("core.scene", "Scene", "begin_group_edit"),
    ("core.scene", "Scene", "end_group_edit"),
    ("core.scene", "Scene", "share_back"),
)


def _wrap_timed() -> None:
    """Log entering/leaving a group or component (it copies the whole
    definition into new Python objects) with its time and heap growth."""
    import importlib
    for modname, clsname, meth in _TIMED:
        try:
            cls = getattr(importlib.import_module(modname), clsname)
            cur = cls.__dict__[meth]
        except (ImportError, AttributeError, KeyError):
            continue
        fn = getattr(cur, "__func__", cur)
        orig = getattr(fn, "_orig", fn)

        def make(orig=orig, label=f"{clsname}.{meth}"):
            def timed(*a, **k):
                b0 = sys.getallocatedblocks()
                t0 = time.perf_counter()
                try:
                    return orig(*a, **k)
                finally:
                    ms = (time.perf_counter() - t0) * 1000
                    if ms >= 100:
                        db = sys.getallocatedblocks() - b0
                        _log(f"{label}: {ms:.0f} ms, heap {db:+,} blocks")
            timed._orig = orig
            timed._gc_tune = True
            return timed

        wrapped = make()
        if isinstance(cur, staticmethod):
            wrapped = staticmethod(wrapped)
        setattr(cls, meth, wrapped)


SAMPLE_AFTER_S = 1.0    # start sampling once the main thread is this late
SAMPLE_EVERY_S = 0.05


class _Sampler:
    """A thread that looks at what the main thread is doing while it is
    blocked for more than a second, and writes the busiest functions when
    it answers again. Python-level frames only: a long call into native
    code shows as the Python line that made it."""

    def __init__(self, main_id: int) -> None:
        import threading
        self.main_id = main_id
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name="gc_tune_sampler")
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    @staticmethod
    def _name(f) -> str:
        fn = f.filename.replace("\\", "/")
        for marker in ("/_internal/", "/site-packages/"):
            if marker in fn:
                fn = fn.split(marker, 1)[1]
                break
        return f"{fn.rsplit('/', 2)[-2] + '/' if fn.count('/') else ''}" \
               f"{fn.rsplit('/', 1)[-1]}:{f.lineno}:{f.name}"

    def _run(self) -> None:
        import traceback
        from collections import Counter
        leaf, incl, n = Counter(), Counter(), 0
        while not self._stop.wait(SAMPLE_EVERY_S):
            tick = _S["last_tick"]
            late = (time.perf_counter() - tick) if tick is not None else 0.0
            if late >= SAMPLE_AFTER_S:
                frame = sys._current_frames().get(self.main_id)
                if frame is not None:
                    stack = traceback.extract_stack(frame)
                    if stack:
                        n += 1
                        leaf[self._name(stack[-1])] += 1
                        for key in {f"{f.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}:{f.name}"
                                    for f in stack}:
                            incl[key] += 1
            elif n:
                top = ", ".join(f"{k} x{c}" for k, c in leaf.most_common(4))
                inc = ", ".join(f"{k} x{c}" for k, c in incl.most_common(12))
                _log(f"  sampled {n} times while blocked; where: {top}")
                _log(f"  inside: {inc}")
                leaf.clear(); incl.clear(); n = 0


def _start_sampler():
    import threading
    return _Sampler(threading.get_ident())


def _tick() -> None:
    now = time.perf_counter()
    last = _S["last_tick"]
    _S["last_tick"] = now
    if last is None:
        return
    late = (now - last) * 1000 - TICK_MS
    g2 = _gen2()
    if late >= STALL_MS:
        name, ms, wall = _S["last_cmd"]
        recent = f", after {name} ({ms:.0f} ms)" if time.time() - wall < 10 else ""
        _log(f"STALL {late:.0f} ms; full GC ran: {'yes' if g2 != _S['gen2'] else 'no'}"
             f"{recent}; {sys.getallocatedblocks():,} blocks")
    _S["gen2"] = g2


def status_text() -> str:
    return (f"GC Tune {__version__}: {gc.get_freeze_count():,} objects frozen, "
            f"{sys.getallocatedblocks():,} blocks, threshold {gc.get_threshold()}. "
            f"Log: {_log_path()}")


def setup(app) -> None:
    from PySide6.QtCore import QTimer
    win = app.window
    _S["app"] = app
    gc.set_threshold(YOUNG_THRESHOLD, *gc.get_threshold()[1:])
    _S["gen2"] = _gen2()
    _S["last_tick"] = None
    # Hot reload: stop what an earlier load left running (kept on the window,
    # because this module's own globals are new each time).
    old = win.__dict__.get("_gc_tune_handles", [])
    for t in old:
        try:
            t.stop()
        except Exception:
            pass
    win.__dict__["_gc_tune_handles"] = _S["timers"]
    _S["timers"].clear()
    _S["timers"].append(_start_sampler())

    try:
        _wrap_history()
        _wrap_timed()
    except Exception as exc:         # never break the app for a log
        _log(f"could not wrap History.execute: {exc!r}")

    watchdog = QTimer(win)
    watchdog.setInterval(TICK_MS)
    watchdog.timeout.connect(_tick)
    watchdog.start()

    debounce = QTimer(win)
    debounce.setSingleShot(True)
    debounce.setInterval(2000)
    debounce.timeout.connect(maybe_freeze)
    _S["timers"] += [watchdog, debounce]

    app.on_document_changed(debounce.start)
    if hasattr(app, "on_document_closed"):
        # The core collects when a tab closes; frozen objects would not be
        # given back, so let the next load freeze again from scratch.
        def _closed(_scene):
            gc.unfreeze()
            _S["frozen_blocks"] = 0
        app.on_document_closed(_closed)

    app.add_menu_action(
        "GC Tune: free memory now",
        lambda: win.viewport.flash_status(
            f"Memory freed in {free_memory_now():.1f} s", 4000),
        tip="Full garbage collection, then freeze again (takes seconds on a "
            "big model)")
    app.add_menu_action(
        "GC Tune: status",
        lambda: win.viewport.flash_status(status_text(), 8000),
        tip="Frozen objects, heap size and where the stall log is")
    QTimer.singleShot(0, maybe_freeze)
    _log(f"loaded {__version__}")
