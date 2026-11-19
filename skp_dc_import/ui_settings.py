# SPDX-License-Identifier: GPL-3.0-or-later
"""«SketchUp .skp settings»: credits, and the blank .skp the exporter needs."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QVBoxLayout)

from . import template

_log = logging.getLogger(__name__)

WHY = (
    "<p>Writing a .skp starts from SketchUp's own empty document "
    "(<code>blank_v17.skp</code>, 5.8 KB, made with Trimble's SDK). This "
    "extension does <b>not</b> include it, so that only free pieces are "
    "distributed. Get it once; importing .skp files works without it.</p>"
    "<p>Either download it from the OpenSKP project (a fixed commit, checked "
    "against its SHA-256), or choose a copy you already have. Only that exact "
    "file works: the writer depends on its bytes, so a blank file saved from "
    "SketchUp (including SketchUp for Web) will be rejected.</p>")

CREDITS = (
    "<p><b>Credits.</b> Formula interpreter: d1rty-pixel, "
    "<i>Dynamic Components for IngeTrazo</i> (GPL-3.0). .skp writer: IngeTrazo's "
    "<code>formats/skp_out.py</code> (GPL-3.0, Marco Sumari Tellez and "
    "contributors), adapted. OpenSKP: © Ahsan Mehmood (MIT), vendored with "
    "definition dictionaries added. This extension: GPL-3.0-or-later.</p>")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SketchUp .skp settings")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        for html in (WHY, CREDITS):
            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.RichText)
            lay.addWidget(lbl)
        self.state = QLabel()
        self.state.setWordWrap(True)
        lay.addWidget(self.state)
        row = QHBoxLayout()
        self.btn_dl = QPushButton("Download from OpenSKP")
        self.btn_dl.setToolTip(template.URL)
        self.btn_dl.clicked.connect(self._download)
        btn_file = QPushButton("Choose file…")
        btn_file.clicked.connect(self._choose)
        row.addWidget(self.btn_dl)
        row.addWidget(btn_file)
        row.addStretch(1)
        lay.addLayout(row)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)
        self.refresh()

    def refresh(self):
        state, msg = template.status()
        mark = {"ok": "✔", "missing": "✖", "bad": "⚠"}[state]
        self.state.setText(f"<b>{mark} Export template:</b> {msg}")

    def _download(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            template.download()
        except Exception as exc:  # noqa: BLE001 - say it, never crash the app
            _log.exception("template download failed")
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, self.windowTitle(),
                                f"Could not get the file:\n{exc}\n\n"
                                f"You can download it yourself from\n{template.URL}\n"
                                f"and use «Choose file…».")
        else:
            QApplication.restoreOverrideCursor()
        self.refresh()

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Blank .skp (blank_v17.skp)", "", "SketchUp (*.skp)")
        if not path:
            return
        try:
            template.install_from_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh()


def ensure_template(parent) -> bool:
    """True when export can proceed; otherwise opens the dialog."""
    if template.apply():
        return True
    SettingsDialog(parent).exec()
    return template.apply()
