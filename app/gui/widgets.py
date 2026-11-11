"""Composants d'interface réutilisables (cartes, badges, tuiles, tableaux, listes).

Ces widgets ne contiennent aucune logique métier : ils affichent ce que les
pages leur donnent. Cela garde l'interface testable et réutilisable.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QBrush,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget,
    QAbstractItemView, QListWidget, QListWidgetItem,
)

from app.gui.theme import COLORS, CLASS_COLORS, STATUS_COLORS


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def label(text: str, object_name: str = "", word_wrap: bool = False,
          tooltip: str | None = None) -> QLabel:
    lbl = QLabel(text)
    if object_name:
        lbl.setObjectName(object_name)
    lbl.setWordWrap(word_wrap)
    if tooltip:
        lbl.setToolTip(tooltip)
    return lbl


class Card(QFrame):
    """Conteneur arrondi avec ombre légère."""

    def __init__(self, parent: QWidget | None = None, alt: bool = False,
                 shadow: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("CardAlt" if alt else "Card")
        if shadow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(18)
            effect.setOffset(0, 2)
            effect.setColor(QColor(0, 0, 0, 70))
            self.setGraphicsEffect(effect)


class CardLayout(QVBoxLayout):
    """Layout avec marges cohérentes à l'intérieur d'une carte."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8,
                 margins: tuple[int, int, int, int] = (14, 12, 14, 12)) -> None:
        super().__init__(parent)
        self.setSpacing(spacing)
        self.setContentsMargins(*margins)


class Badge(QLabel):
    """Petite étiquette colorée (statut, classe, licence…)."""

    def __init__(self, text: str, color: str = COLORS["accent"], parent: QWidget | None = None,
                 filled: bool = True) -> None:
        super().__init__(text, parent)
        self._color = color
        self._filled = filled
        self.setAlignment(Qt.AlignCenter)
        self.set_size_policy_fixed()

    def set_size_policy_fixed(self) -> None:
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set_color(self, color: str) -> None:
        self._color = color
        self._restyle()

    def _restyle(self) -> None:
        c = QColor(self._color)
        if self._filled:
            bg = QColor(c)
            bg.setAlpha(48)
            self.setStyleSheet(
                f"background-color: rgba({bg.red()},{bg.green()},{bg.blue()},{bg.alpha()});"
                f"color: {self._color}; border: 1px solid {self._color};"
                "border-radius: 4px; padding: 1px 7px; font-size: 10px; font-weight: 600;"
            )
        else:
            self.setStyleSheet(
                f"color: {self._color}; font-size: 10px; font-weight: 600;"
            )

    def showEvent(self, event) -> None:  # noqa: N802 (API Qt)
        super().showEvent(event)
        self._restyle()


class StatusDot(QWidget):
    """Pastille de statut avec halo."""

    def __init__(self, color: str = COLORS["text_dim"], size: int = 9,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._size = size
        self.setFixedSize(size + 6, size + 6)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        halo = QColor(self._color)
        halo.setAlpha(60)
        painter.setBrush(QBrush(halo))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self._size + 6, self._size + 6)
        painter.setBrush(QBrush(self._color))
        offset = 3
        painter.drawEllipse(offset, offset, self._size, self._size)
        painter.end()


class StatTile(Card):
    """Tuile d'indicateur du tableau de bord."""

    clicked = Signal()

    def __init__(self, title: str, value: str = "—", hint: str = "",
                 accent: str = COLORS["accent"], icon_text: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent = accent
        layout = CardLayout(self, spacing=4, margins=(14, 12, 14, 12))

        top = QHBoxLayout()
        top.setSpacing(6)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedSize(26, 26)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(
            f"background-color: rgba(0,0,0,0); color: {accent}; font-size: 14px; font-weight: 700;"
        )
        top.addWidget(self.icon_label)
        self.title_label = label(title.upper(), "StatLabel")
        self.title_label.setWordWrap(True)
        top.addWidget(self.title_label, 1)
        layout.addLayout(top)

        self.value_label = label(value, "StatValue")
        f = self.value_label.font()
        f.setPixelSize(26)
        f.setWeight(QFont.Bold)
        self.value_label.setFont(f)
        layout.addWidget(self.value_label)

        self.hint_label = label(hint, "StatHint", word_wrap=True)
        layout.addWidget(self.hint_label)
        layout.addStretch(1)

        self.setMinimumHeight(104)
        self.setCursor(Qt.PointingHandCursor)

        # Liseré coloré à gauche
        self.setStyleSheet(
            f"#Card {{ background-color: {COLORS['surface']}; border: 1px solid {COLORS['border']};"
            f" border-left: 3px solid {accent}; border-radius: 10px; }}"
        )

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SectionHeader(QWidget):
    """Titre de section avec sous-titre optionnel et widgets d'action."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        block = QVBoxLayout()
        block.setSpacing(1)
        block.addWidget(label(title, "SectionTitle"))
        if subtitle:
            block.addWidget(label(subtitle, "SectionHint", word_wrap=True))
        layout.addLayout(block)
        layout.addStretch(1)
        self._layout = layout

    def add_action(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


class PageHeader(QWidget):
    """En-tête standard d'une page (titre, sous-titre, actions à droite)."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        block = QVBoxLayout()
        block.setSpacing(2)
        block.addWidget(label(title, "PageTitle"))
        if subtitle:
            block.addWidget(label(subtitle, "PageSubtitle", word_wrap=True))
        layout.addLayout(block)
        layout.addStretch(1)
        self._layout = layout

    def add_action(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


def separator(horizontal: bool = True) -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    line.setStyleSheet(f"color: {COLORS['border_soft']}; background-color: {COLORS['border_soft']};")
    line.setFixedHeight(1 if horizontal else 0)
    return line


def hline() -> QFrame:
    return separator(True)


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------
class DataTable(QTableWidget):
    """Tableau en lecture seule, tri par colonne, lignes alternées."""

    def __init__(self, headers: Sequence[str], parent: QWidget | None = None,
                 stretch_column: int | None = None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(list(headers))
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        if stretch_column is not None:
            self.horizontalHeader().setSectionResizeMode(stretch_column, QHeaderView.Stretch)
        self.setShowGrid(False)
        self._rows_data: list[Any] = []

    def set_rows(self, rows: Iterable[Sequence[Any]], colors: Iterable[str | None] | None = None,
                 data: Iterable[Any] | None = None, sortable_numbers: bool = True) -> None:
        rows = list(rows)
        colors = list(colors) if colors is not None else [None] * len(rows)
        data = list(data) if data is not None else [None] * len(rows)
        self.setSortingEnabled(False)
        self.setRowCount(0)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem()
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    item.setData(Qt.DisplayRole, value)
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setData(Qt.DisplayRole, "" if value is None else str(value))
                    if value is not None and len(str(value)) > 12:
                        item.setToolTip(str(value))
                if colors[r]:
                    item.setForeground(QColor(colors[r]))
                self.setItem(r, c, item)
            if data[r] is not None:
                self.item(r, 0).setData(Qt.UserRole, data[r])
        self._rows_data = data
        if sortable_numbers:
            self.setSortingEnabled(True)

    def selected_data(self) -> Any:
        row = self.currentRow()
        if row < 0 or row >= len(self._rows_data):
            return None
        item = self.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def selected_row_index(self) -> int:
        return self.currentRow()


class BadgeList(QWidget):
    """Liste de badges empilables horizontalement."""

    def __init__(self, badges: Sequence[tuple[str, str]] = (), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        self._layout.addStretch(1)
        for text, color in badges:
            self.add_badge(text, color)

    def add_badge(self, text: str, color: str) -> None:
        self._layout.insertWidget(self._layout.count() - 1, Badge(text, color))

    def clear(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


# ---------------------------------------------------------------------------
# Dessins / pictogrammes vectoriels (aucune dépendance externe)
# ---------------------------------------------------------------------------
def make_icon(glyph: str, color: str = COLORS["accent"], size: int = 18) -> QIcon:
    """Pictogramme texte simple dans une pastille transparente."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor(color))
    font = QFont()
    font.setPixelSize(int(size * 0.78))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)


def class_badge_color(acquisition_class: str | None) -> str:
    return CLASS_COLORS.get(acquisition_class or "", COLORS["class_none"])


def status_color(status: str | None) -> str:
    return STATUS_COLORS.get(status or "", COLORS["text_muted"])


def draw_coast_preview(bbox, width: int = 260, height: int = 120) -> QPixmap:
    """Miniature schématique de l'emprise (fallback sans fond de carte)."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(COLORS["bg_alt"]))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(COLORS["border"]), 1))
    painter.setBrush(QBrush(QColor(COLORS["surface_alt"])))
    painter.drawRoundedRect(4, 4, width - 8, height - 8, 6, 6)
    if bbox is not None:
        painter.setBrush(QBrush(QColor(COLORS["accent"])))
        painter.setPen(QPen(QColor(COLORS["accent"]), 1))
        painter.drawRect(20, 20, width - 40, height - 40)
    painter.setPen(QColor(COLORS["text_dim"]))
    painter.drawText(pixmap.rect(), Qt.AlignCenter,
                     "—" if bbox is None else f"{bbox.minx:.1f},{bbox.miny:.1f}\n{bbox.maxx:.1f},{bbox.maxy:.1f}")
    painter.end()
    return pixmap


def clear_layout(layout) -> None:
    """Supprime récursivement tous les widgets d'un layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            child = item.layout()
            if child is not None:
                clear_layout(child)


def kv_row(key: str, value: str, mono: bool = False,
           value_color: str | None = None) -> QWidget:
    """Ligne « clé : valeur » pour les fiches détaillées."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 1, 0, 1)
    lay.setSpacing(8)
    k = label(key, "Dim")
    k.setFixedWidth(180)
    k.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    v = QLabel(value if value not in ("", None) else "—")
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    style = "font-size: 11px;"
    if mono:
        style += "font-family: " + "Consolas, DejaVu Sans Mono, monospace;"
    if value_color:
        style += f"color: {value_color};"
    elif value in ("", None, "—"):
        style += f"color: {COLORS['text_dim']};"
    v.setStyleSheet(style)
    lay.addWidget(k)
    lay.addWidget(v, 1)
    return w


class EmptyState(QWidget):
    """Message affiché lorsqu'une liste ou un tableau est vide."""

    def __init__(self, title: str, message: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        t = label(title, "SectionTitle")
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)
        if message:
            m = label(message, "SectionHint", word_wrap=True)
            m.setAlignment(Qt.AlignCenter)
            m.setMaximumWidth(420)
            layout.addWidget(m, 0, Qt.AlignHCenter)


def tooltip_card(title: str, lines: Sequence[str]) -> str:
    body = "<br>".join(lines)
    return f"<b>{title}</b><br>{body}"
