"""Fenêtre principale : barre latérale de navigation + pile de pages + barre d'état."""
from __future__ import annotations

import logging

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QSizePolicy,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from app.config.settings import APP_SHORT, APP_VERSION, PHASE
from app.core.context import AppContext
from app.gui.pages.analyze import AnalyzePage
from app.gui.pages.catalogue import CataloguePage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.downloads import DownloadsPage
from app.gui.pages.history import HistoryPage
from app.gui.pages.map import MapPage
from app.gui.pages.reports import ReportsPage
from app.gui.pages.search import SearchPage
from app.gui.pages.settings import SettingsPage
from app.gui.theme import COLORS, stylesheet
from app.gui.widgets import StatusDot, label

log = logging.getLogger(__name__)

PAGES = [
    ("dashboard", "Tableau de bord", "◱"),
    ("carte", "Carte interactive", "◈"),
    ("catalogue", "Catalogue", "▤"),
    ("recherche", "Recherche avancée", "⌕"),
    ("analyse", "Analyse & comparaison", "⚖"),
    ("telechargements", "Téléchargements", "⇩"),
    ("historique", "Historique des mises à jour", "↻"),
    ("rapports", "Rapports scientifiques", "▦"),
    ("parametres", "Paramètres", "⚙"),
]


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_SHORT} — Mediterranean Bathymetry Monitor")
        self.setMinimumSize(QSize(1280, 800))
        self.resize(1560, 940)
        self.setStyleSheet(stylesheet())

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._build_status_bar()
        self._build_pages()
        self.nav_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(248)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 10)
        layout.setSpacing(4)

        # Marque
        brand = QWidget()
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(16, 0, 16, 10)
        bl.setSpacing(9)
        logo = QLabel()
        logo.setPixmap(_logo_pixmap(34))
        bl.addWidget(logo)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(label("Bathymetry", "BrandTitle"))
        texts.addWidget(label("Mediterranean Monitor", "BrandTitle"))
        texts.addWidget(label(f"v{APP_VERSION} · phase 1/8", "BrandSubtitle"))
        bl.addLayout(texts)
        bl.addStretch(1)
        layout.addWidget(brand)

        layout.addWidget(label("  NAVIGATION", "BrandSubtitle"))
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setIconSize(QSize(16, 16))
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        for key, text, glyph in PAGES:
            item = QListWidgetItem(f"  {glyph}   {text}")
            item.setData(Qt.UserRole, key)
            item.setSizeHint(QSize(220, 34))
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self._on_nav)
        layout.addWidget(self.nav_list, 1)

        # Pied de la barre latérale : état de la base
        footer = QWidget()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(16, 6, 16, 4)
        fl.setSpacing(3)
        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        self.db_dot = StatusDot(COLORS["success"])
        status_row.addWidget(self.db_dot)
        status_row.addWidget(label("Base connectée", "SidebarFooter"), 1)
        fl.addLayout(status_row)
        self.db_label = label(self.ctx.db_info(), "SidebarFooter")
        self.db_label.setWordWrap(True)
        fl.addWidget(self.db_label)
        fl.addWidget(label(PHASE, "SidebarFooter"))
        layout.addWidget(footer)
        return sidebar

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.status_label = QLabel("Prêt")
        bar.addWidget(self.status_label, 1)
        self.phase_label = QLabel("Connecteurs réseau : aucun actif (phase 1)")
        self.phase_label.setStyleSheet(f"color: {COLORS['warning']};")
        bar.addPermanentWidget(self.phase_label)
        self.count_label = QLabel("0 produit")
        bar.addPermanentWidget(self.count_label)
        try:
            count = self.ctx.repo.count_datasets()
            self.count_label.setText(f"{count} produit(s) catalogué(s)")
        except Exception:  # pragma: no cover
            pass

    def _build_pages(self) -> None:
        self.pages: dict[str, object] = {}
        order = {
            "dashboard": lambda: DashboardPage(self.ctx, "Tableau de bord",
                                               "Veille des données bathymétriques ouvertes de Méditerranée",
                                               scrollable=True),
            "carte": lambda: MapPage(self.ctx, "Carte interactive",
                                     "Emprises des produits — littoral algérien et Méditerranée"),
            "catalogue": lambda: CataloguePage(self.ctx, "Catalogue des données",
                                               "Fiches produits complètes et statut de validation des métadonnées"),
            "recherche": lambda: SearchPage(self.ctx, "Recherche et filtres avancés",
                                            "Combinaison de critères spatiaux, techniques et licences"),
            "analyse": lambda: AnalyzePage(self.ctx, "Analyse et comparaison des produits",
                                           "Huit critères d'évaluation SDB — valeurs documentées, sans score prématuré"),
            "telechargements": lambda: DownloadsPage(self.ctx, "Gestion des téléchargements",
                                                     "Accessibilité, organisation locale et vérification d'intégrité"),
            "historique": lambda: HistoryPage(self.ctx, "Historique des mises à jour",
                                              "Exécutions de veille, journal des changements et versions"),
            "rapports": lambda: ReportsPage(self.ctx, "Rapports scientifiques",
                                            "Inventaire du catalogue et préparation du rapport hebdomadaire"),
            "parametres": lambda: SettingsPage(self.ctx, "Paramètres",
                                               "Sources, planification, stockage et informations"),
        }
        for key, text, _glyph in PAGES:
            page = order[key]()
            page.status.connect(self._set_status)
            if hasattr(page, "navigate"):
                page.navigate.connect(self._navigate)
            self.pages[key] = page
            self.stack.addWidget(page)

    # ------------------------------------------------------------------
    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        page = self.stack.widget(row)
        self.stack.setCurrentIndex(row)
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception as exc:  # pragma: no cover
                log.exception("Rafraîchissement de page impossible")
                self._set_status(f"Erreur d'affichage : {exc}")

    def _navigate(self, key: str, payload: object = None) -> None:
        keys = [k for k, _, _ in PAGES]
        if key not in keys:
            return
        index = keys.index(key)
        if payload and isinstance(payload, dict) and key == "historique":
            page = self.pages.get("historique")
            combo = getattr(page, "filter_combo", None)
            wanted = payload.get("filter")
            if combo is not None and wanted:
                idx = combo.findData(wanted)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        self.nav_list.setCurrentRow(index)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        QTimer.singleShot(6000, lambda: self.status_label.setText("Prêt"))


def _logo_pixmap(size: int) -> QPixmap:
    """Logo dessiné (vague + sonde) — aucune ressource externe requise."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setBrush(QColor(COLORS["accent_dark"]))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 9, 9)

    from PySide6.QtGui import QPainterPath, QPen

    path = QPainterPath()
    path.moveTo(4, size * 0.62)
    path.cubicTo(size * 0.28, size * 0.38, size * 0.44, size * 0.80, size * 0.66, size * 0.55)
    path.cubicTo(size * 0.80, size * 0.38, size * 0.88, size * 0.50, size - 4, size * 0.42)
    pen = QPen(QColor("#eaf6ff"))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)

    # sonde verticale
    pen2 = QPen(QColor(COLORS["success"]))
    pen2.setWidthF(1.6)
    painter.setPen(pen2)
    painter.drawLine(int(size * 0.34), int(size * 0.18), int(size * 0.34), int(size * 0.78))
    painter.setBrush(QColor(COLORS["success"]))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(int(size * 0.34) - 2, int(size * 0.78) - 2, 5, 5)
    painter.end()
    return pixmap
