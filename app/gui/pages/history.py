"""Page 7 — Historique des mises à jour (sections 4 et 5).

Affiche les exécutions de veille, le journal des changements et l'historique
des versions d'un produit sélectionné. En Phase 1, le journal contient les
écritures du jeu de référence ; il s'alimentera à partir de la Phase 2 avec les
connecteurs, sans changement d'interface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QSplitter, QVBoxLayout, QWidget,
)

from app.core.taxonomy import label_of
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS
from app.gui.widgets import (
    Card, CardLayout, DataTable, EmptyState, SectionHeader, hline, kv_row, label,
    status_color,
)

RUN_COLUMNS = ["Début", "Déclencheur", "Statut", "Sources OK", "Échecs", "Vus", "Nouveaux", "MàJ", "Durée"]
CHANGE_COLUMNS = ["Date", "Produit", "Type", "Champ", "Ancienne valeur", "Nouvelle valeur", "Source"]
VERSION_COLUMNS = ["Détectée le", "Version", "Mise à jour", "Champs modifiés", "Commentaire"]

CHANGE_TYPES = {
    "new": "Nouveau produit",
    "updated": "Mise à jour",
    "removed": "Retrait",
    "duplicate": "Doublon",
    "error": "Erreur",
    "note": "Note",
}


class HistoryPage(BasePage):
    def __init__(self, *args, initial_filter: str | None = None, **kwargs) -> None:
        self._initial_filter = initial_filter
        super().__init__(*args, **kwargs)

    def build_content(self) -> None:
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # ---- exécutions de veille ------------------------------------------
        runs_card = Card()
        rl = CardLayout(runs_card, spacing=8)
        head = SectionHeader("Exécutions de veille",
                             "Chaque exécution produit un rapport, même sans nouveauté")
        rl.addWidget(head)
        self.runs_table = DataTable(RUN_COLUMNS, stretch_column=0)
        self.runs_table.setMinimumHeight(104)
        self.runs_table.setMaximumHeight(190)
        _fix_widths(self.runs_table, {1: 100, 2: 100, 3: 84, 4: 70, 5: 60, 6: 86, 7: 60, 8: 76})
        rl.addWidget(self.runs_table)
        self.runs_hint = label("", "Dim", word_wrap=True)
        rl.addWidget(self.runs_hint)
        splitter.addWidget(runs_card)

        # ---- journal des changements ---------------------------------------
        changes_card = Card()
        cl = CardLayout(changes_card, spacing=8)
        head2 = SectionHeader("Journal des changements", "Détection des nouveautés, mises à jour et doublons")
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Tous les types", None)
        for key, text in CHANGE_TYPES.items():
            self.filter_combo.addItem(text, key)
        if self._initial_filter:
            index = self.filter_combo.findData(self._initial_filter)
            self.filter_combo.setCurrentIndex(max(0, index))
        self.filter_combo.currentIndexChanged.connect(lambda _: self._load_changes())
        head2.add_action(self.filter_combo)
        cl.addWidget(head2)
        self.changes_table = DataTable(CHANGE_COLUMNS, stretch_column=1)
        _fix_widths(self.changes_table, {0: 150, 2: 126, 3: 140, 4: 140, 5: 140, 6: 150}, stretch=1)
        cl.addWidget(self.changes_table, 1)
        splitter.addWidget(changes_card)

        # ---- versions d'un produit -----------------------------------------
        versions_card = Card()
        vl = CardLayout(versions_card, spacing=8)
        head3 = SectionHeader("Historique des versions",
                              "Sélectionnez un produit dans le journal pour voir ses versions")
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(320)
        self.product_combo.currentIndexChanged.connect(lambda _: self._load_versions())
        head3.add_action(self.product_combo)
        vl.addWidget(head3)
        self.versions_table = DataTable(VERSION_COLUMNS, stretch_column=4)
        _fix_widths(self.versions_table, {0: 160, 1: 120, 2: 110, 3: 260}, stretch=4)
        vl.addWidget(self.versions_table, 1)
        splitter.addWidget(versions_card)
        splitter.setSizes([190, 400, 250])

        self.content.addWidget(splitter, 1)
        self._populate_products()
        self._load_changes()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._load_runs()
        self._load_changes()
        self._populate_products()
        self._load_versions()

    def _load_runs(self) -> None:
        runs = self.repo.watch_runs(limit=40)
        if not runs:
            self.runs_table.set_rows([["—", "—", "aucune exécution enregistrée", "—", "—", "—", "—", "—", "—"]])
            self.runs_hint.setText(
                "Aucun moteur de veille n'est encore branché (Phase 2 à 7). "
                "Les exécutions s'enregistreront ici avec leur rapport, y compris lorsque "
                "aucune nouveauté n'est détectée (exigence de la section 4)."
            )
            return
        rows, colors = [], []
        for run in runs:
            duration = ""
            if run.get("started_at") and run.get("finished_at"):
                try:
                    from datetime import datetime

                    start = datetime.fromisoformat(run["started_at"])
                    end = datetime.fromisoformat(run["finished_at"])
                    duration = f"{(end - start).total_seconds():.1f} s"
                except Exception:
                    duration = "—"
            rows.append([
                (run["started_at"] or "")[:19].replace("T", " "),
                run["trigger"], run["status"], run["sources_ok"], run["sources_failed"],
                run["items_seen"], run["new_count"], run["updated_count"], duration,
            ])
            colors.append(status_color("success" if run["status"] == "success" else run["status"]))
        self.runs_table.set_rows(rows, colors, sortable_numbers=False)
        self.runs_hint.setText(f"{len(runs)} exécution(s) enregistrée(s).")

    def _load_changes(self) -> None:
        change_type = self.filter_combo.currentData() if hasattr(self, "filter_combo") else None
        changes = self.repo.recent_changes(
            limit=500, change_types=[change_type] if change_type else None)
        rows, colors, data = [], [], []
        for c in changes:
            rows.append([
                (c["detected_at"] or "")[:19].replace("T", " "),
                c.get("dataset_name") or c["dataset_uid"][:14],
                CHANGE_TYPES.get(c["change_type"], c["change_type"]),
                c["field_name"] or "—",
                c["old_value"] or "—",
                c["new_value"] or "—",
                c.get("ds_source") or c["source_id"] or "—",
            ])
            colors.append(status_color(c["change_type"]))
            data.append(c["dataset_uid"])
        if not rows:
            self.changes_table.set_rows([["—", "Aucun changement enregistré pour ce filtre", "—", "—", "—", "—", "—"]])
        else:
            self.changes_table.set_rows(rows, colors, data, sortable_numbers=False)

    def _populate_products(self) -> None:
        current = self.product_combo.currentData() if self.product_combo.count() else None
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        for ds in sorted(self.repo.list_datasets(), key=lambda d: d.name):
            self.product_combo.addItem(f"[{ds.acquisition_class}] {ds.name}", ds.uid)
        if current:
            idx = self.product_combo.findData(current)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)
        self.product_combo.blockSignals(False)

    def _load_versions(self) -> None:
        uid = self.product_combo.currentData()
        if not uid:
            self.versions_table.set_rows([])
            return
        versions = self.repo.version_history(str(uid))
        rows = []
        for v in versions:
            import json

            fields = json.loads(v["changed_fields"] or "[]")
            rows.append([
                (v["detected_at"] or "")[:19].replace("T", " "),
                v["version"] or "—",
                (v["update_date"] or "—")[:10],
                ", ".join(fields) if fields else "—",
                v["comment"] or "—",
            ])
        if not rows:
            rows = [["—", "—", "—", "aucune version enregistrée", "—"]]
        self.versions_table.set_rows(rows)


def _fix_widths(table, widths: dict[int, int], stretch: int = 0) -> None:
    """Largeurs fixes pour les colonnes techniques, colonne texte extensible."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Fixed)
    for col, width in widths.items():
        table.setColumnWidth(col, width)
    header.setSectionResizeMode(stretch, QHeaderView.Stretch)
    header.setStretchLastSection(False)
