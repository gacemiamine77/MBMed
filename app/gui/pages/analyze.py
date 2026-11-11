"""Page 5 — Analyse et comparaison des produits (section 7 du cahier des charges).

La comparaison porte sur les huit critères exigés, mais affiche les VALEURS
DOCUMENTÉES, pas un score agrégé : le score multi-critères et la fiche
scientifique automatique relèvent de la Phase 6.

Rappels scientifiques affichés dans la page :
  * le pas de grille n'est pas la résolution effective ;
  * un produit régional interpolé (classe D) n'est jamais une vérité terrain.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from app.core.models import Dataset
from app.core.taxonomy import ACQUISITION_CLASSES, ACQUISITION_METHODS, LICENSE_TYPES, label_of
from app.gui.charts import BarChart
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS, CLASS_COLORS
from app.gui.widgets import Card, CardLayout, SectionHeader, label

CRITERIA = [
    ("Classe", lambda d: d.acquisition_class),
    ("Nature", lambda d: d.class_label()),
    ("Résolution nominale", lambda d: _m(d.resolution_m)),
    ("Résolution effective", lambda d: _m(d.effective_resolution_m) if d.effective_resolution_m else "non documentée"),
    ("Précision verticale", lambda d: _m(d.vertical_accuracy_m) if d.vertical_accuracy_m else "non documentée"),
    ("Couverture bathymétrique", lambda d: _range(d.depth_min_m, d.depth_max_m)),
    ("Fenêtre 0–100 m", lambda d: f"{d.sdb_window_fraction() * 100:.0f} %"),
    ("Proximité temporelle", lambda d: _temporal(d)),
    ("Complétude métadonnées", lambda d: f"{d.metadata_completeness * 100:.0f} %"),
    ("Méthode d'acquisition", lambda d: label_of(ACQUISITION_METHODS, d.acquisition_method)),
    ("Données brutes", lambda d: _raw_availability(d)),
    ("Validation indépendante", lambda d: "possible (mesure directe)" if d.acquisition_class == "A"
        else "indispensable (produit dérivé)"),
    ("Référence verticale", lambda d: d.vertical_reference or "non documentée"),
    ("Licence", lambda d: label_of(LICENSE_TYPES, d.license)),
    ("Accès", lambda d: d.access_mode),
]


class AnalyzePage(BasePage):
    def build_content(self) -> None:
        top = QHBoxLayout()
        top.setSpacing(12)

        # --- sélection -------------------------------------------------------
        sel_card = Card()
        sl = CardLayout(sel_card, spacing=8)
        sl.addWidget(SectionHeader("Produits à comparer",
                                  "Sélection multiple (Ctrl+clic)"))
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.MultiSelection)
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setMinimumWidth(300)
        self.list.itemSelectionChanged.connect(self._compare)
        sl.addWidget(self.list, 1)
        btns = QHBoxLayout()
        b_all = QPushButton("Tout sélectionner")
        b_all.setObjectName("Ghost")
        b_all.clicked.connect(self.list.selectAll)
        b_none = QPushButton("Effacer")
        b_none.setObjectName("Ghost")
        b_none.clicked.connect(self.list.clearSelection)
        b_gt = QPushButton("Classe A seulement")
        b_gt.setObjectName("Ghost")
        b_gt.clicked.connect(self._select_class)
        for b in (b_all, b_gt, b_none):
            btns.addWidget(b)
        sl.addLayout(btns)
        compare = QPushButton("Comparer la sélection")
        compare.setObjectName("Primary")
        compare.clicked.connect(self._compare)
        sl.addWidget(compare)
        sel_card.setMaximumWidth(400)
        top.addWidget(sel_card)

        # --- résultats -------------------------------------------------------
        res_card = Card()
        rl = CardLayout(res_card, spacing=8)
        self.tabs = QTabWidget()

        self.table = QTableWidget(0, 1)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.tabs.addTab(self.table, "Tableau comparatif")

        self.chart_widget = QWidget()
        chl = QVBoxLayout(self.chart_widget)
        chl.setContentsMargins(8, 8, 8, 8)
        chl.setSpacing(8)
        self.res_chart = BarChart("Résolution nominale (m, échelle log)", height=180)
        self.meta_chart = BarChart("Complétude des métadonnées (%)", height=180)
        chl.addWidget(self.res_chart)
        chl.addWidget(self.meta_chart)
        self.tabs.addTab(self.chart_widget, "Graphiques")

        self.class_browser = QTextBrowser()
        self.class_browser.setOpenExternalLinks(False)
        self.class_browser.setHtml(_classes_html())
        self.tabs.addTab(self.class_browser, "Classes A→E")

        self.rules = QTextBrowser()
        self.rules.setHtml(_rules_html())
        self.tabs.addTab(self.rules, "Règles d'évaluation")

        rl.addWidget(self.tabs, 1)
        top.addWidget(res_card, 1)
        self.content.addLayout(top, 1)

        self._datasets: list[Dataset] = []

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        previous = {i.data(Qt.UserRole) for i in self.list.selectedItems()}
        self.list.blockSignals(True)
        self.list.clear()
        self._datasets = self.repo.list_datasets()
        for ds in sorted(self._datasets, key=lambda d: (d.acquisition_class, d.name)):
            item = QListWidgetItem(f"[{ds.acquisition_class}] {ds.name}")
            item.setData(Qt.UserRole, ds.uid)
            item.setToolTip(ds.name)
            from PySide6.QtGui import QColor

            item.setForeground(QColor(CLASS_COLORS.get(ds.acquisition_class, COLORS["text"])))
            self.list.addItem(item)
        self.list.blockSignals(False)
        if previous:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) in previous:
                    self.list.item(i).setSelected(True)
        else:
            self._preselect_demo()
        self._compare()

    def _preselect_demo(self) -> None:
        """Présélectionne un jeu comparatif pertinent (mesure directe vs MNT)."""
        wanted = []
        seen_classes = set()
        for i in range(self.list.count()):
            item = self.list.item(i)
            uid = item.data(Qt.UserRole)
            ds = next((d for d in self._datasets if d.uid == uid), None)
            if ds is None:
                continue
            if ds.acquisition_class in ("A", "D") and ds.acquisition_class not in seen_classes:
                item.setSelected(True)
                seen_classes.add(ds.acquisition_class)
                wanted.append(uid)
            if len(wanted) >= 3:
                break

    def _select_class(self) -> None:
        self.list.clearSelection()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.text().startswith("[A]"):
                item.setSelected(True)

    def _selected(self) -> list[Dataset]:
        by_uid = {d.uid: d for d in self._datasets}
        chosen = []
        for item in self.list.selectedItems():
            uid = item.data(Qt.UserRole)
            if uid in by_uid:
                chosen.append(by_uid[uid])
        return chosen[:4]  # lisibilité

    def _compare(self) -> None:
        chosen = self._selected()
        if not chosen:
            self.table.setRowCount(0)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["Sélectionnez au moins un produit"])
            return
        self.table.setColumnCount(len(chosen) + 1)
        self.table.setRowCount(len(CRITERIA))
        headers = ["Critère"] + [d.name[:34] + ("…" if len(d.name) > 34 else "") for d in chosen]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnWidth(0, 176)
        for col, ds in enumerate(chosen, start=1):
            self.table.horizontalHeaderItem(col).setToolTip(ds.name)
        for row, (label_text, getter) in enumerate(CRITERIA):
            head = QTableWidgetItem(label_text)
            head.setForeground(Qt.gray)
            self.table.setItem(row, 0, head)
            for col, ds in enumerate(chosen, start=1):
                value = getter(ds)
                cell = QTableWidgetItem(str(value))
                if row == 0:
                    from PySide6.QtGui import QColor

                    cell.setForeground(QColor(CLASS_COLORS.get(ds.acquisition_class, COLORS["text"])))
                self.table.setItem(row, col, cell)

        res_data = {}
        meta_data = {}
        for ds in chosen:
            short = ds.name[:28] + ("…" if len(ds.name) > 28 else "")
            if ds.resolution_m:
                res_data[short] = ds.resolution_m
            meta_data[short] = round(ds.metadata_completeness * 100, 1)
        self._log_chart(res_data)
        self.meta_chart.update_data(meta_data, horizontal=True)

    def _log_chart(self, data: dict[str, float]) -> None:
        chart = self.res_chart
        chart.ax.clear()
        if not data:
            chart._no_data("Résolution non documentée")
            return
        names = list(data.keys())
        values = [data[k] for k in names]
        bars = chart.ax.barh(names, values, color=COLORS["accent"], height=0.55)
        chart.ax.set_xscale("log")
        chart.ax.invert_yaxis()
        chart.ax.set_xlim(min(values) / 2, max(values) * 3)
        for bar, value in zip(bars, values):
            tid = f"{value:.0f} m" if value >= 10 else f"{value:.1f} m"
            chart.ax.text(bar.get_width() * 1.12, bar.get_y() + bar.get_height() / 2,
                          tid, va="center", fontsize=7.5, color=COLORS["text_muted"])
        chart.ax.grid(axis="x", alpha=0.18, linewidth=0.5)
        chart.ax.set_axisbelow(True)
        chart._style_axes()
        chart.redraw()


def _m(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0f} m" if value >= 10 else f"{value:.1f} m"


def _range(dmin: float | None, dmax: float | None) -> str:
    if dmin is None or dmax is None:
        return "non documentée"
    return f"{dmin:.0f} – {dmax:.0f} m"


def _temporal(ds: Dataset) -> str:
    date = ds.update_date or ds.publication_date
    if not date:
        return "non documentée"
    return f"réf. {date[:10]} (à confronter aux dates d'images)"


def _raw_availability(ds: Dataset) -> str:
    if ds.acquisition_class == "A":
        return "mesures brutes possibles (sondes/photons)"
    if ds.data_format in ("netcdf", "geotiff", "cog"):
        return "grille dérivée (pas de mesures brutes)"
    return "non documenté"


def _classes_html() -> str:
    rows = []
    for key, meta in ACQUISITION_CLASSES.items():
        color = CLASS_COLORS[key]
        gt = "oui" if meta["ground_truth_candidate"] else "non"
        rows.append(
            f"<tr><td style='color:{color};font-weight:700;padding:6px'>{key}</td>"
            f"<td style='padding:6px'><b>{meta['label']}</b><br>"
            f"<span style='color:#93a4bb'>{meta['description']}</span></td>"
            f"<td style='padding:6px;text-align:center'>{gt}</td></tr>"
        )
    return (
        "<html><body style='font-family:Segoe UI,sans-serif;font-size:11px;color:#e6edf6'>"
        "<h3>Classification A → E</h3>"
        "<table width='100%' cellspacing='0'>"
        "<tr style='color:#93a4bb'><th align='left'>Classe</th><th align='left'>Nature</th>"
        "<th>Vérité terrain</th></tr>" + "".join(rows) + "</table>"
        "<p style='color:#e8b64c'>Un modèle régional interpolé (classe D) n'est jamais une vérité terrain.</p>"
        "</body></html>"
    )


def _rules_html() -> str:
    return (
        "<html><body style='font-family:Segoe UI,sans-serif;font-size:11px;color:#e6edf6'>"
        "<h3>Règles d'évaluation retenues</h3>"
        "<ol>"
        "<li><b>Pas de grille ≠ résolution effective.</b> Une grille EMODnet à 115 m ou GEBCO à 450 m "
        "interpole des levés dont la densité réelle varie de quelques mètres à plusieurs kilomètres.</li>"
        "<li><b>Aucune vérité terrain automatique.</b> Seules les mesures directes (classe A) peuvent "
        "prétendre à ce rôle, et après contrôle de la référence verticale et de l'incertitude.</li>"
        "<li><b>Huit critères évalués séparément</b> : résolution, précision verticale, couverture "
        "bathymétrique, proximité temporelle, qualité des métadonnées, méthode d'acquisition, "
        "disponibilité des données brutes, possibilité de validation indépendante.</li>"
        "<li><b>Information manquante = « non documentée »</b>, jamais une estimation inventée.</li>"
        "<li><b>Score agrégé et fiche scientifique</b> : module d'évaluation de la Phase 6, "
        "avec pondérations explicites et traçabilité.</li>"
        "</ol>"
        "<p style='color:#93a4bb'>Cette page affiche donc les valeurs documentées, critère par critère, "
        "sans produire de note globale prématurée.</p>"
        "</body></html>"
    )
