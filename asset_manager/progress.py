# SPDX-License-Identifier: GPL-3.0-or-later
"""A modal progress window for a long import, like IngeTrazo's own («Preparing
the drawing…»): it appears only when the work takes longer than a moment,
keeps the window painted, and blocks clicks on the drawing meanwhile.

``with window(parent, title) as cb:`` — ``cb(fraction, text)``; a fraction
of ``None`` shows a moving bar (work with no measure). ``in_thread(fn, cb,
text)`` runs ``fn()`` off the UI thread (reading a file, which touches no
scene) while the window keeps moving. ``current()`` is the callback of the
window that is up, so code deep below can report without being handed it.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

SHOW_AFTER = 0.3           # seconds: quicker work never flashes a window
_current = None


def current():
    """The callback of the progress window that is up, or None."""
    return _current


def scaled(cb, start: float, end: float, text: str | None = None):
    """``cb`` for one stage that fills ``start``…``end`` of the bar; its
    ``text``, when given, is what the window says (whatever the work reports)."""
    if cb is None:
        return None

    def stage(frac, label=None):
        cb(None if frac is None else start + (end - start) * max(0.0, min(1.0, frac)),
           text if text is not None else label)
    return stage


@contextmanager
def stage(start: float, end: float):
    """Inside it, whoever reports to :func:`current` fills only
    ``start``…``end`` of the bar (what follows gets the rest)."""
    global _current
    previous = _current
    _current = scaled(previous, start, end) if previous is not None else None
    try:
        yield
    finally:
        _current = previous


@contextmanager
def window(parent, title: str):
    global _current
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QProgressDialog

    dlg = QProgressDialog(title, "", 0, 100, parent)
    dlg.setWindowTitle("IngeTrazo")
    dlg.setCancelButton(None)
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(10 ** 9)          # shown by hand, below
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setMinimumWidth(320)
    t0 = time.monotonic()
    state = {"last": 0.0, "busy": False}

    def cb(frac, text=None):
        now = time.monotonic()
        if text:
            dlg.setLabelText(text)
        if frac is None:
            if not state["busy"]:
                dlg.setRange(0, 0)
                state["busy"] = True
        else:
            if state["busy"]:
                dlg.setRange(0, 100)
                state["busy"] = False
            dlg.setValue(int(round(frac * 100)))
        if not dlg.isVisible() and now - t0 >= SHOW_AFTER:
            dlg.show()
        if now - state["last"] >= 0.05 or frac in (0, 1):
            state["last"] = now
            QApplication.processEvents()

    previous, _current = _current, cb
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        yield cb
    finally:
        _current = previous
        QApplication.restoreOverrideCursor()
        dlg.close()
        dlg.deleteLater()


def in_thread(fn, cb, text: str):
    """``fn()`` run off the UI thread, ``cb`` ticking with the seconds it
    takes; returns its result or raises what it raised."""
    if cb is None:
        return fn()
    from PySide6.QtCore import QEventLoop, QTimer
    out: dict = {}

    def work():
        try:
            out["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - handed back to the caller
            out["error"] = exc

    th = threading.Thread(target=work, name="ingetrazo-import-read", daemon=True)
    t0 = time.monotonic()
    th.start()
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(80)

    def tick():
        if th.is_alive():
            secs = time.monotonic() - t0
            cb(None, f"{text} ({secs:.0f} s)" if secs >= 2 else text)
        else:
            timer.stop()
            loop.quit()

    timer.timeout.connect(tick)
    cb(None, text)
    timer.start()
    if th.is_alive():
        loop.exec()
    timer.stop()
    th.join()
    if "error" in out:
        raise out["error"]
    return out.get("value")
