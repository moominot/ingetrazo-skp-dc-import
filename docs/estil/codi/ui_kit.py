# SPDX-License-Identifier: GPL-3.0-or-later
"""The panel's building blocks, taken from Render Studio's widgets.py (see the style guide): Card, CentredButton, split_button
and the flat style of the buttons. Needs ``icons.py`` beside it, and a ``tr`` (here: the text as it is)."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QSizePolicy, QStyle, QStyleOptionToolButton, QStylePainter, QToolButton,
                               QVBoxLayout, QWidget)


def tr(text: str) -> str:
    return text


QWIDGETSIZE_MAX = (1 << 24) - 1                  # Qt's «no maximum»


class Card(QGroupBox):
    """A group of the panel: a card whose header, in a colour of its own, has the group's icon and name and folds it away
    with a click; whether it is open is remembered under ``key``. Fill ``form`` (``kind`` "form") or ``body_layout``
    ("column"): both are in the card's body, so what the code shows or hides row by row is not disturbed by folding."""

    def __init__(self, title: str, key: str = "", parent=None, icon: str = "", kind: str = "form"):
        super().__init__(title, parent)
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QFormLayout
        self._key = "render_studio/fold_" + key if key else ""
        self.icon_key = icon
        self._forced = False
        self._lay = QVBoxLayout(self)
        self.body = QWidget(self)
        self._lay.addWidget(self.body)
        if kind == "form":
            self.form = QFormLayout(self.body)
            self.form.setContentsMargins(0, 0, 0, 0)
            self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        else:
            self.body_layout = QVBoxLayout(self.body)
            self.body_layout.setContentsMargins(0, 0, 0, 0)
        opened = True
        if self._key:
            try:
                opened = str(QSettings().value(self._key, "true")).lower() != "false"
            except Exception:  # noqa: BLE001
                pass
        self._open = opened
        self.body.setVisible(opened)
        self._fit()
        self.setToolTip(tr("Click the title to fold or unfold this group"))
        self.body.setToolTip(" ")                     # (what is inside does not wear the header's tip)
        self.body.setToolTipDuration(1)

    def _title_height(self) -> int:
        return max(28, self.fontMetrics().height() + 12)

    def minimumSizeHint(self) -> QSize:         # noqa: N802 (Qt)
        """As narrow as what is inside: Qt would keep room for the whole title, which is cut short when it does not fit."""
        return QSize(self._lay.totalMinimumSize().width(), super().minimumSizeHint().height())

    def _fit(self) -> None:
        """The body below the header (Qt keeps some room of its own for a group box's title: only the rest is added)."""
        own = self.contentsMargins().top()
        shown = self._open or self._forced
        margins = (8, max(0, self._title_height() - own) + (6 if shown else 0), 8, 8 if shown else 0)
        if self._lay.getContentsMargins() != margins:
            self._lay.setContentsMargins(*margins)
        # folded, it is exactly as tall as its header (Qt would give a group box a little more)
        self.setMaximumHeight(QWIDGETSIZE_MAX if shown else self._title_height())

    def changeEvent(self, ev) -> None:          # noqa: N802 (Qt: another font or style, other margins)
        super().changeEvent(ev)
        if hasattr(self, "_lay"):
            self._fit()

    def showEvent(self, ev) -> None:            # noqa: N802 (Qt)
        self._fit()
        super().showEvent(ev)

    def is_open(self) -> bool:
        return self._open

    def set_open(self, on: bool) -> None:
        on = bool(on)
        if on == self._open:
            return
        self._open = on
        self.body.setVisible(on or self._forced)
        self._fit()
        if self._key:
            try:
                from PySide6.QtCore import QSettings
                QSettings().setValue(self._key, "true" if on else "false")
            except Exception:  # noqa: BLE001
                pass
        self.update()

    def force_open(self, on: bool) -> None:
        """Open while ``on`` whatever was chosen (a search shows what it finds); the choice is kept."""
        self._forced = bool(on)
        self.body.setVisible(self._open or self._forced)
        self._fit()
        self.update()

    def mousePressEvent(self, ev) -> None:      # noqa: N802 (Qt)
        if ev.button() == Qt.LeftButton and ev.position().y() <= self._title_height():
            self.set_open(not self._open)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def paintEvent(self, ev) -> None:           # noqa: N802 (Qt)
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QPainter, QPainterPath, QPen
        from . import icons
        palette, accent = self.palette(), icons._accent()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        whole = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        head = float(self._title_height())
        card = QPainterPath()
        card.addRoundedRect(whole, 6, 6)
        p.fillPath(card, palette.color(QPalette.Base))
        p.save()                                                    # the header: the accent, faint, over the card
        p.setClipPath(card)
        tint = QColor(accent)
        tint.setAlpha(46)
        p.fillRect(QRectF(0, 0, self.width(), head), tint)
        p.restore()
        edge = palette.color(QPalette.WindowText)
        edge.setAlpha(40)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(card)
        x = 8
        if self.icon_key:
            icons.icon(self.icon_key).paint(p, QRect(x, int((head - 18) / 2), 18, 18))
            x += 24
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        ink = palette.color(QPalette.WindowText)
        p.setPen(ink)
        title = p.fontMetrics().elidedText(self.title(), Qt.ElideRight, max(10, self.width() - x - 28))
        p.drawText(QRectF(x, 0, self.width() - x - 24, head), Qt.AlignVCenter | Qt.AlignLeft, title)
        ink.setAlpha(170)
        pen = QPen(ink, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cx, cy = self.width() - 14.0, head / 2.0
        if self._open or self._forced:
            p.drawPolyline([QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2)])
        else:
            p.drawPolyline([QPointF(cx - 2, cy - 4), QPointF(cx + 2, cy), QPointF(cx - 2, cy + 4)])
        p.end()


SPLIT_STYLE = """
QToolButton { border: none; border-radius: 5px; padding: 4px 22px 4px 10px; background: rgba(128,128,128,38);
              color: palette(button-text); }
QToolButton:hover { background: rgba(128,128,128,70); }
QToolButton:pressed { background: rgba(128,128,128,100); }
QToolButton:disabled { color: palette(mid); background: rgba(128,128,128,20); }
QToolButton::menu-button { border: none; border-left: 1px solid rgba(128,128,128,90); width: 20px;
                           border-top-right-radius: 5px; border-bottom-right-radius: 5px; }
QToolButton::menu-button:hover { background: rgba(128,128,128,70); }
QToolButton::menu-arrow { width: 8px; height: 8px; }
"""


#: Every button of the panel's pages and foot (not the tab bar's arrows, which a style sheet would leave blank): flat, no frame; a faint ground, stronger under the pointer, the accent when it is the one chosen.
FLAT_STYLE = """
QPushButton, QToolButton {{ border: none; border-radius: 5px; padding: 4px 8px; background: rgba(128,128,128,38);
                           color: palette(button-text); }}
QPushButton:hover, QToolButton:hover {{ background: rgba(128,128,128,70); }}
QPushButton:pressed, QToolButton:pressed {{ background: rgba(128,128,128,100); }}
QPushButton:checked, QToolButton:checked {{ background: rgba({r},{g},{b},80); }}
QPushButton:disabled, QToolButton:disabled {{ color: palette(mid); background: rgba(128,128,128,20); }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}
"""


#: The two buttons of the tray's header: as low as its one line of text.
SMALL_BUTTON = """
QToolButton { padding: 2px 6px; font-size: 11px; }
"""


def flat_style() -> str:
    from . import icons
    c = icons._accent()
    return FLAT_STYLE.format(r=c.red(), g=c.green(), b=c.blue())


class CentredButton(QToolButton):
    """A tool button with its icon and its words together in the middle of it (Qt puts them at its left edge). The middle is
    the whole button's, arrow or no arrow, so buttons one above another line up."""

    GAP = 6
    ARROW = 24                                  # what the menu's arrow takes at the right

    def paintEvent(self, _ev) -> None:  # noqa: N802 (Qt)
        painter = QStylePainter(self)
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        text, icon = option.text, QIcon(option.icon)      # (a copy: PySide hands out the option's own, emptied below)
        option.text, option.icon = "", QIcon()
        painter.drawComplexControl(QStyle.CC_ToolButton, option)        # the button itself, empty
        size = self.iconSize() if not icon.isNull() else QSize(0, 0)
        gap = self.GAP if size.width() and text else 0
        words = painter.fontMetrics().horizontalAdvance(text)
        content = size.width() + gap + words
        x = (self.width() - content) // 2
        if self.popupMode() == QToolButton.MenuButtonPopup:           # never over the arrow (a half-width button has no room
            x = min(x, self.width() - self.ARROW - content)           # to spare: it moves left)
        x = max(4, x)
        if size.width():
            icon.paint(painter, QRect(x, (self.height() - size.height()) // 2, size.width(), size.height()), Qt.AlignCenter,
                       QIcon.Normal if self.isEnabled() else QIcon.Disabled)
        group = QPalette.Active if self.isEnabled() else QPalette.Disabled
        painter.setPen(self.palette().color(group, QPalette.ButtonText))
        painter.drawText(QRect(x + size.width() + gap, 0, words + 2, self.height()), Qt.AlignVCenter | Qt.AlignLeft, text)


def split_button(text: str, main_slot, tip: str, actions):
    """A button whose arrow opens a menu of ``actions`` (QActions): the button itself does ``main_slot``."""
    from PySide6.QtWidgets import QMenu, QSizePolicy
    b = CentredButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setPopupMode(QToolButton.MenuButtonPopup)
    b.setToolButtonStyle(Qt.ToolButtonTextOnly)
    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    b.setMinimumHeight(28)
    # one rounded rectangle, with a plain divider before the arrow: no rounding where the two parts meet
    b.setStyleSheet(SPLIT_STYLE)
    menu = QMenu(b)
    for a in actions:
        menu.addAction(a)
    b.setMenu(menu)
    b.clicked.connect(lambda _c=False: main_slot())
    return b
