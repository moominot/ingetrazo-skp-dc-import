# SPDX-License-Identifier: GPL-3.0-or-later
"""«Components manager settings»: the model sites «Open a model site» offers,
and the catalog folders, each one watched in real time or read again with
Update."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

from . import catalog
from .i18n import tr, translate_on_show

WATCH_QUESTION = ("Watch this folder in real time?\n\n"
                  "Yes: a model saved or downloaded into it shows in the catalog at once "
                  "(handy for the browser's Downloads folder).\n"
                  "No: the catalog reads it again when you press Update.")


def ask_watch(parent, folder) -> bool:
    return QMessageBox.question(
        parent, tr("Catalog folder"), f"{folder}\n\n{tr(WATCH_QUESTION)}",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


def downloads_folder() -> str:
    from PySide6.QtCore import QStandardPaths
    return QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or ""


def choose_and_add_folder(parent):
    """Ask for a folder and whether to watch it; add it. Returns the folder
    added, or None."""
    path = QFileDialog.getExistingDirectory(parent, tr("Folder with your models (.igz, .skp)"),
                                            downloads_folder())
    if not path:
        return None
    if not catalog.add_folder(path):
        QMessageBox.information(parent, tr("Catalog folder"), tr("That folder is already in the catalog."))
        return None
    catalog.set_watched(path, ask_watch(parent, path))
    return Path(path)


class SiteDialog(QDialog):
    def __init__(self, parent=None, name="", url=""):
        super().__init__(parent)
        self.setWindowTitle(tr("Model site"))
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.url = QLineEdit(url)
        self.url.setPlaceholderText("https://…")
        self.name = QLineEdit(name)
        self.name.setPlaceholderText(tr("(the site's address if left empty)"))
        form.addRow("Address", self.url)
        form.addRow("Name", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        translate_on_show(self)

    def _ok(self):
        url = self.url.text().strip()
        if url and "://" not in url:
            url = "https://" + url
            self.url.setText(url)
        if not catalog.valid_url(url):
            QMessageBox.warning(self, self.windowTitle(), tr("Write a web address (https://…)."))
            return
        self.accept()

    def value(self):
        url = self.url.text().strip()
        return (self.name.text().strip() or catalog.site_name(url), url)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Components manager settings"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        box = QGroupBox("Model sites")
        v = QVBoxLayout(box)
        hint = QLabel("«Open a model site» opens these in your browser. Download the models "
                      "into a catalog folder that is watched (your Downloads folder, for "
                      "instance) and they show in the catalog at once.")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.sites = QListWidget()
        self.sites.itemDoubleClicked.connect(lambda _i: self._edit_site())
        v.addWidget(self.sites)
        row = QHBoxLayout()
        for text, fn in (("Add…", self._add_site), ("Edit…", self._edit_site),
                         ("Remove", self._remove_site), ("Open", self._open_site)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        lay.addWidget(box)

        box2 = QGroupBox("Catalog folders")
        v2 = QVBoxLayout(box2)
        hint2 = QLabel("Ticked: watched in real time. Unticked: read again with Update.")
        hint2.setWordWrap(True)
        v2.addWidget(hint2)
        self.folders = QListWidget()
        self.folders.itemChanged.connect(self._folder_ticked)
        v2.addWidget(self.folders)
        row2 = QHBoxLayout()
        for text, fn in (("Add…", self._add_folder), ("Remove", self._remove_folder)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row2.addWidget(b)
        row2.addStretch(1)
        v2.addLayout(row2)
        lay.addWidget(box2)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.accept)
        close.accepted.connect(self.accept)
        lay.addWidget(close)
        self.changed = False
        self._fill()
        translate_on_show(self)

    # -- sites --
    def _fill(self):
        self.sites.clear()
        for name, url in catalog.sites():
            it = QListWidgetItem(f"{name} — {url}")
            it.setData(Qt.UserRole, (name, url))
            self.sites.addItem(it)
        self.folders.blockSignals(True)
        self.folders.clear()
        watched = catalog.watched()
        for i, f in enumerate(catalog.folders()):
            it = QListWidgetItem((tr("Extension's own folder — ") if i == 0 else "") + str(f))
            it.setData(Qt.UserRole, str(f))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if any(f == w for w in watched) else Qt.Unchecked)
            self.folders.addItem(it)
        self.folders.blockSignals(False)

    def _site_values(self):
        return [self.sites.item(i).data(Qt.UserRole) for i in range(self.sites.count())]

    def _add_site(self):
        d = SiteDialog(self)
        if d.exec():
            catalog.set_sites(self._site_values() + [d.value()])
            self._fill()

    def _edit_site(self):
        row = self.sites.currentRow()
        if row < 0:
            return
        values = self._site_values()
        d = SiteDialog(self, *values[row])
        if d.exec():
            values[row] = d.value()
            catalog.set_sites(values)
            self._fill()
            self.sites.setCurrentRow(row)

    def _remove_site(self):
        row = self.sites.currentRow()
        if row >= 0:
            values = self._site_values()
            del values[row]
            catalog.set_sites(values)
            self._fill()

    def _open_site(self):
        it = self.sites.currentItem()
        if it is not None:
            QDesktopServices.openUrl(QUrl(it.data(Qt.UserRole)[1]))

    # -- folders --
    def _folder_ticked(self, it):
        catalog.set_watched(it.data(Qt.UserRole), it.checkState() == Qt.Checked)
        self.changed = True

    def _add_folder(self):
        if choose_and_add_folder(self) is not None:
            self.changed = True
            self._fill()

    def _remove_folder(self):
        it = self.folders.currentItem()
        if it is None:
            return
        if not catalog.remove_folder(it.data(Qt.UserRole)):
            QMessageBox.information(self, self.windowTitle(),
                                    tr("The extension's own folder stays in the catalog."))
            return
        self.changed = True
        self._fill()
