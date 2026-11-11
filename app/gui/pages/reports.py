"""Page 8 — Rapports scientifiques (section 11).

En Phase 1, cette page produit un rapport d'INVENTAIRE du catalogue au format
HTML et Excel (les deux formats sont opérationnels) et prépare l'emplacement du
rapport hebdomadaire de veille en français, qui sera généré automatiquement en
Phase 7 (PDF compris).

La génération est réelle : le fichier est écrit sur disque et peut être ouvert.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from app.exporters import EXPORT_COLUMNS, export_excel
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS
from app.gui.widgets import Card, CardLayout, SectionHeader, label
from app.reports.inventory import build_inventory_report, render_inventory_html

SCOPES = {
    "catalogue": "Inventaire complet du catalogue",
    "algeria": "Produits couvrant le littoral algérien",
    "class_a": "Mesures directes (classe A) — candidats vérité terrain",
    "sdb": "Produits couvrant la fenêtre SDB 0–100 m",
    "gaps": "Produits aux métadonnées incomplètes",
}


class ReportsPage(BasePage):
    def build_content(self) -> None:
        ctrl = Card()
        cl = CardLayout(ctrl, spacing=8)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("Périmètre", "Dim"))
        self.scope = QComboBox()
        for key, text in SCOPES.items():
            self.scope.addItem(text, key)
        self.scope.currentIndexChanged.connect(lambda _: self._preview())
        row.addWidget(self.scope, 1)
        preview_btn = QPushButton("Aperçu")
        preview_btn.setObjectName("Ghost")
        preview_btn.clicked.connect(self._preview)
        row.addWidget(preview_btn)
        html_btn = QPushButton("Exporter HTML")
        html_btn.setObjectName("Primary")
        html_btn.clicked.connect(lambda: self._export("html"))
        row.addWidget(html_btn)
        xlsx_btn = QPushButton("Exporter Excel")
        xlsx_btn.setObjectName("Ghost")
        xlsx_btn.clicked.connect(lambda: self._export("xlsx"))
        row.addWidget(xlsx_btn)
        open_btn = QPushButton("Ouvrir le dossier")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.ctx.settings.report_dir()))))
        row.addWidget(open_btn)
        cl.addLayout(row)

        self.note = label(
            "ⓘ  Rapport d'inventaire : décrit l'état du catalogue à l'instant T. "
            "Le rapport hebdomadaire de veille (nouveautés, publications, limites scientifiques, "
            "PDF) est produit automatiquement en Phase 7 à partir des mêmes données.",
            "Banner", word_wrap=True,
        )
        cl.addWidget(self.note)
        self.content.addWidget(ctrl)

        card = Card()
        vl = CardLayout(card, spacing=8)
        vl.addWidget(SectionHeader("Aperçu du rapport", "Rendu HTML identique au fichier exporté"))
        self.browser = QTextBrowser()
        self.browser.setStyleSheet(f"background-color: {COLORS['surface']}; border-radius: 6px;")
        vl.addWidget(self.browser, 1)
        self.content.addWidget(card, 1)

        self._preview()

    # ------------------------------------------------------------------
    def _rows(self) -> list[dict]:
        scope = self.scope.currentData()
        from app.database.repository import DatasetFilter

        filt = DatasetFilter()
        if scope == "algeria":
            filt.only_algeria = True
        elif scope == "class_a":
            filt.only_ground_truth = True
        elif scope == "sdb":
            filt.only_sdb_depth = True
        rows = self.repo.list_dataset_rows(filt)
        if scope == "gaps":
            rows = [r for r in rows if (r.get("metadata_completeness") or 0) < 0.75]
        return rows

    def _preview(self) -> None:
        rows = self._rows()
        stats = self.repo.dashboard_stats()
        report = build_inventory_report(rows, stats, SCOPES.get(self.scope.currentData(), ""))
        self.browser.setHtml(render_inventory_html(report))

    def _export(self, kind: str) -> None:
        rows = self._rows()
        stats = self.repo.dashboard_stats()
        scope_key = self.scope.currentData()
        report = build_inventory_report(rows, stats, SCOPES.get(scope_key, ""))
        out_dir = self.ctx.settings.report_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        default = out_dir / f"mbm_inventaire_{scope_key}_{stamp}.{kind if kind != 'xlsx' else 'xlsx'}"
        filters = {"html": "HTML (*.html)", "xlsx": "Excel (*.xlsx)"}
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", str(default), filters[kind])
        if not path:
            return
        target = Path(path)
        try:
            if kind == "html":
                target.write_text(render_inventory_html(report, standalone=True), encoding="utf-8")
            else:
                export_excel({
                    "Synthèse": (
                        [("indicateur", "Indicateur"), ("valeur", "Valeur")],
                        [{"indicateur": k, "valeur": v} for k, v in report["summary"].items()],
                    ),
                    "Catalogue": (EXPORT_COLUMNS, rows),
                }, target, title=report["title"])
            self.notify(f"Rapport exporté : {target}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))
        except Exception as exc:  # pragma: no cover
            self.notify(f"Échec de l'export : {exc}")
