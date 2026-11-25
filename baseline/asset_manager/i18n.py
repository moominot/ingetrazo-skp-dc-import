# SPDX-License-Identifier: GPL-3.0-or-later
"""Translation of this extension into the language IngeTrazo runs in.

English is the source: ``tr("Import")`` looks the English text up in
``locales/<lang>.json`` (a flat ``{english: translation}`` map, as IngeTrazo's
own catalogues) and gives it back unchanged when there is none, so a
missing translation reads as English, never as a key. Texts IngeTrazo
already translates (Cancel, Close, Apply…) are taken from its catalogue.

Two ways in, so the code does not have to wrap every string:

* ``tr(text, **fields)`` for messages built in code;
* ``translate_tree(widget)`` for everything a panel's widgets already show
  (labels, buttons, tips, tabs, headers) — call it once the panel is built;
  ``translate_on_show(widget)`` repeats it whenever the panel is shown, to
  catch pieces built later. Combo boxes are left alone on purpose: code
  often reads their text back as a key.

This file is the same in every extension of the repository (each ships
alone); keep the copies identical. Add a language by dropping its
``locales/<code>.json`` next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "locales"
_cache: dict[str, dict[str, str]] = {}


def language() -> str:
    try:
        from core.i18n import current_language
        return current_language() or "en"
    except Exception:  # noqa: BLE001 - outside the app
        return "en"


def catalog(lang: str | None = None) -> dict[str, str]:
    lang = lang or language()
    if lang == "en":
        return {}
    if lang not in _cache:
        try:
            data = json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))
            _cache[lang] = {str(k): str(v) for k, v in data.items()}
        except (OSError, ValueError):
            _cache[lang] = {}
    return _cache[lang]


def _lookup(text: str) -> str:
    out = catalog().get(text)
    if out is not None:
        return out
    try:                                # IngeTrazo's own words (Cancel, Close…)
        from core.i18n import tr as core_tr
        return core_tr(text)
    except Exception:  # noqa: BLE001
        return text


def tr(text: str, /, **fields) -> str:
    """``text`` in the interface language; ``{fields}`` filled in after."""
    out = _lookup(text)
    if fields:
        try:
            return out.format(**fields)
        except (KeyError, IndexError, ValueError):
            return text.format(**fields)
    return out


def _has(text: str) -> bool:
    return bool(text) and _lookup(text) != text


def _fix_widget(w) -> None:
    from PySide6.QtWidgets import (
        QAbstractButton, QGroupBox, QLabel, QLineEdit, QTabWidget,
        QTableWidget, QTextEdit, QTreeWidget)
    for get, put in ((w.toolTip, w.setToolTip), (w.statusTip, w.setStatusTip)):
        t = get()
        if _has(t):
            put(tr(t))
    if isinstance(w, (QLabel, QAbstractButton)):
        if _has(w.text()):
            w.setText(tr(w.text()))
    elif isinstance(w, QGroupBox):
        if _has(w.title()):
            w.setTitle(tr(w.title()))
    elif isinstance(w, QTabWidget):
        for i in range(w.count()):
            if _has(w.tabText(i)):
                w.setTabText(i, tr(w.tabText(i)))
            if _has(w.tabToolTip(i)):
                w.setTabToolTip(i, tr(w.tabToolTip(i)))
    elif isinstance(w, (QLineEdit, QTextEdit)):
        if _has(w.placeholderText()):
            w.setPlaceholderText(tr(w.placeholderText()))
    elif isinstance(w, QTableWidget):
        for i in range(w.columnCount()):
            it = w.horizontalHeaderItem(i)
            if it is not None and _has(it.text()):
                it.setText(tr(it.text()))
    elif isinstance(w, QTreeWidget):
        head = w.headerItem()
        for i in range(w.columnCount()):
            if head is not None and _has(head.text(i)):
                head.setText(i, tr(head.text(i)))


def translate_tree(root) -> None:
    """Translate the texts ``root`` and its widgets show now."""
    if not catalog():
        return
    from PySide6.QtWidgets import QWidget
    for w in [root, *root.findChildren(QWidget)]:
        try:
            _fix_widget(w)
        except Exception:  # noqa: BLE001 - a missed text must never break a panel
            pass


def translate_on_show(root) -> None:
    """``translate_tree(root)`` now and each time ``root`` is shown."""
    if not catalog():
        return
    from PySide6.QtCore import QEvent, QObject

    class _OnShow(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Show:
                translate_tree(obj)
            return False

    flt = _OnShow(root)
    root.installEventFilter(flt)
    translate_tree(root)


def localized_text(name: str) -> str | None:
    """The contents of ``locales/<name>.<lang>.html`` (a long text, such as a
    help page, translated as a whole), or None in English / when the file
    does not exist."""
    lang = language()
    if lang == "en":
        return None
    try:
        return (_DIR / f"{name}.{lang}.html").read_text(encoding="utf-8")
    except OSError:
        return None
