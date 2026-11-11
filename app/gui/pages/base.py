"""Classe de base des pages de l'application."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from app.core.context import AppContext
from app.gui.widgets import PageHeader


class BasePage(QWidget):
    """Page standard : en-tête + zone de contenu.

    Les sous-classes implémentent ``build_content`` et ``refresh``.
    ``status`` permet de signaler un message dans la barre d'état.
    """

    status = Signal(str)
    navigate = Signal(str, object)   # (nom de page, payload)

    def __init__(self, ctx: AppContext, title: str, subtitle: str = "",
                 scrollable: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.page_title = title
        self.header = PageHeader(title, subtitle)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(22, 18, 22, 14)
        self._outer.setSpacing(14)
        self._outer.addWidget(self.header)

        self._scroll: QScrollArea | None = None
        if scrollable:
            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setFrameShape(QScrollArea.NoFrame)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            container = QWidget()
            self.content = QVBoxLayout(container)
            self.content.setContentsMargins(0, 0, 8, 0)
            self.content.setSpacing(14)
            self._scroll.setWidget(container)
            self._outer.addWidget(self._scroll, 1)
        else:
            self.content = self._outer

        self.build_content()
        self.refresh()

    # -- API à implémenter --------------------------------------------------
    def build_content(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        """Recharge les données affichées."""

    # -- utilitaires --------------------------------------------------------
    def notify(self, message: str) -> None:
        self.status.emit(message)

    @property
    def repo(self):
        return self.ctx.repo

    def activate(self) -> None:
        """Appelée quand la page devient visible."""
