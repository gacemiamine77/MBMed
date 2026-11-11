"""Page 1 — Tableau de bord général (section 9 du cahier des charges).

Présente : total catalogué, nouveautés, mises à jour, sources opérationnelles,
couverture côtière algérienne, répartition par profondeur et par type
d'acquisition. Toutes les valeurs proviennent de la base ; les compteurs non
calculables restent explicitement à zéro plutôt que simulés.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from app.core.taxonomy import ACQUISITION_CLASSES, ACQUISITION_METHODS
from app.gui.charts import BarChart, ClassDonutChart, DepthBandChart, TimelineChart
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS
from app.gui.widgets import (
    Badge, Card, CardLayout, DataTable, EmptyState, SectionHeader, StatTile, hline, label,
    status_color,
)


class DashboardPage(BasePage):
    def build_content(self) -> None:
        # --- Bandeau d'information sur l'état des sources -------------------
        self.banner = QLabel()
        self.banner.setObjectName("Banner")
        self.banner.setWordWrap(True)
        self.content.addWidget(self.banner)

        # --- Tuiles d'indicateurs -------------------------------------------
        tiles = QGridLayout()
        tiles.setSpacing(12)
        self.tile_total = StatTile("Jeux catalogués", "0", "catalogue complet", COLORS["accent"], "▦")
        self.tile_new = StatTile("Nouvelles données", "0", "détectées lors de la dernière veille",
                                 COLORS["success"], "✦")
        self.tile_updated = StatTile("Produits mis à jour", "0", "versions modifiées",
                                     COLORS["warning"], "↻")
        self.tile_sources = StatTile("Sources opérationnelles", "0 / 0", "connecteurs actifs",
                                     COLORS["info"], "◉")
        for i, tile in enumerate((self.tile_total, self.tile_new, self.tile_updated, self.tile_sources)):
            tiles.addWidget(tile, 0, i)
        self.tile_total.clicked.connect(lambda: self.navigate.emit("catalogue", None))
        self.tile_new.clicked.connect(lambda: self.navigate.emit("historique", {"filter": "new"}))
        self.tile_updated.clicked.connect(lambda: self.navigate.emit("historique", {"filter": "updated"}))
        self.tile_sources.clicked.connect(lambda: self.navigate.emit("parametres", None))
        self.content.addLayout(tiles)

        # --- Couverture algérienne + graphiques ------------------------------
        row = QHBoxLayout()
        row.setSpacing(12)

        self.algeria_card = Card()
        al = CardLayout(self.algeria_card, spacing=8)
        al.addWidget(SectionHeader(
            "Couverture du littoral algérien",
            "Fenêtre côtière de référence : 2,5° O – 9,5° E / 35,0° N – 37,6° N",
        ))
        al.addWidget(hline())
        self.algeria_stats = QGridLayout()
        self.algeria_stats.setSpacing(10)
        self.algeria_values: dict[str, QLabel] = {}
        metrics = [
            ("Produits couvrant la zone", "core"),
            ("dont 0–100 m (fenêtre SDB)", "sdb"),
            ("dont classe A (vérité terrain)", "gt"),
            ("Emprises côtières (< 25 km)", "coastal"),
        ]
        for i, (text, key) in enumerate(metrics):
            cell = QWidget()
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            value = label("0", "StatValue")
            f = value.font(); f.setPixelSize(20); f.setWeight(QFont.Bold)
            value.setFont(f)
            self.algeria_values[key] = value
            lay.addWidget(value)
            lay.addWidget(label(text, "StatHint", word_wrap=True))
            self.algeria_stats.addWidget(cell, i // 2, i % 2)
        al.addLayout(self.algeria_stats)
        self.algeria_hint = label("", "Dim", word_wrap=True)
        al.addWidget(self.algeria_hint)
        al.addStretch(1)
        self.algeria_card.setMinimumWidth(392)
        row.addWidget(self.algeria_card, 0)

        depth_card = Card()
        dl = CardLayout(depth_card, spacing=6)
        dl.addWidget(SectionHeader("Répartition par profondeur",
                                   "Un produit peut couvrir plusieurs tranches"))
        self.depth_chart = DepthBandChart(height=186)
        dl.addWidget(self.depth_chart, 1)
        row.addWidget(depth_card, 1)

        class_card = Card()
        cl = CardLayout(class_card, spacing=6)
        cl.addWidget(SectionHeader("Répartition par type d'acquisition",
                                   "Classes A→E — un MNT interpolé n'est jamais une vérité terrain"))
        self.class_chart = ClassDonutChart(height=186)
        cl.addWidget(self.class_chart, 1)
        row.addWidget(class_card, 1)

        self.content.addLayout(row)

        # --- Deuxième ligne : sources + activité -----------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        src_card = Card()
        sl = CardLayout(src_card, spacing=6)
        self.sources_header = SectionHeader("État des sources", "8 familles de sources surveillées")
        sl.addWidget(self.sources_header)
        self.sources_table = DataTable(["Source", "Statut", "Connecteur", "Produits", "Dernière vérif."],
                                       stretch_column=0)
        self.sources_table.setMinimumHeight(196)
        sl.addWidget(self.sources_table)
        row2.addWidget(src_card, 3)

        timeline_card = Card()
        tl = CardLayout(timeline_card, spacing=6)
        tl.addWidget(SectionHeader("Activité du catalogue", "Publications et détections par mois"))
        self.timeline = TimelineChart(height=190)
        tl.addWidget(self.timeline, 1)
        row2.addWidget(timeline_card, 2)
        self.content.addLayout(row2)

        # --- Méthodes d'acquisition + derniers changements -------------------
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        method_card = Card()
        ml = CardLayout(method_card, spacing=6)
        ml.addWidget(SectionHeader("Méthodes d'acquisition", "Nature technique des produits"))
        self.method_chart = BarChart("", height=190)
        ml.addWidget(self.method_chart, 1)
        row3.addWidget(method_card, 1)

        changes_card = Card()
        chl = CardLayout(changes_card, spacing=6)
        head = SectionHeader("Derniers changements détectés", "Journal de veille")
        open_btn = QPushButton("Historique complet")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(lambda: self.navigate.emit("historique", None))
        head.add_action(open_btn)
        chl.addWidget(head)
        self.changes_table = DataTable(["Date", "Produit", "Type"], stretch_column=1)
        self.changes_table.setMinimumHeight(190)
        chl.addWidget(self.changes_table)
        row3.addWidget(changes_card, 1)
        self.content.addLayout(row3)

        self.content.addStretch(1)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        stats = self.repo.dashboard_stats()
        self.tile_total.set_value(f"{stats['total']}", "produits catalogués")
        self.tile_new.set_value(f"{stats['new_count']}", self._last_run_hint(stats, "nouveaux"))
        self.tile_updated.set_value(f"{stats['updated_count']}", self._last_run_hint(stats, "mis à jour"))
        self.tile_sources.set_value(
            f"{stats['sources_operational']} / {stats['sources_implemented']}",
            f"{stats['sources_total']} familles · {stats['sources_never_run']} jamais exécutée(s)",
        )

        impl = stats["sources_implemented"]
        if impl == 0:
            self.banner.setText(
                "ⓘ  Phase 1 — architecture, base de données et interface opérationnelles. "
                "Aucun connecteur réseau n'est encore actif (Phases 2 à 4) : « nouvelles données » "
                "et « mises à jour » restent à zéro ; les fiches affichées sont des jeux de "
                "démonstration à confirmer par les sources officielles."
            )
        else:
            self.banner.setText(
                f"ⓘ  {impl} famille(s) de sources disposent d'un connecteur. "
                "Les valeurs non vérifiées sont signalées dans les fiches produit."
            )

        # Couverture algérienne
        self.algeria_values["core"].setText(str(stats["algeria_core"]))
        self.algeria_values["sdb"].setText(str(stats["algeria_sdb"]))
        self.algeria_values["gt"].setText(str(stats["algeria_ground_truth"]))
        self.algeria_values["coastal"].setText(str(stats["algeria_coastal"]))
        total = max(1, stats["total"])
        self.algeria_hint.setText(
            f"{stats['algeria_core']} produit(s) / {stats['total']} recouvrent la façade "
            f"algérienne en 0–100 m ({stats['algeria_core'] / total * 100:.0f} %). "
            "Couverture surfacique quantifiée en Phase 5."
        )

        # Graphiques
        self.depth_chart.update_data(stats["by_depth_band"] or {})
        labels = {k: v["label"] for k, v in ACQUISITION_CLASSES.items()}
        self.class_chart.update_data(stats["by_class"] or {}, labels)
        methods = {ACQUISITION_METHODS.get(k, k): v for k, v in sorted(
            stats["by_method"].items(), key=lambda kv: -kv[1])}
        self.method_chart.update_data(methods, horizontal=True)

        self.timeline.update_data(self.repo.timeseries_datasets())

        # Tableau des sources
        health = {h["source_id"]: h for h in self.repo.source_health()}
        infos = {i.source_id: i for i in self.repo.connector_infos()}
        rows, colors = [], []
        for sid, info in infos.items():
            h = health.get(sid, {})
            state = "planifiée" if not info.implemented else _status_fr(info.last_status)
            impl_txt = f"Phase {info.implemented_phase}" if not info.implemented else "actif"
            rows.append([
                info.label, state, impl_txt, int(h.get("dataset_count") or 0),
                (info.last_run or "—")[:16].replace("T", " "),
            ])
            colors.append(status_color(info.last_status if info.implemented else "disabled"))
        self.sources_table.set_rows(rows, colors)
        self.sources_header = self.sources_header  # noqa: PLW0127 (lisibilité)

        # Changements récents
        changes = stats["recent_changes"]
        if changes:
            crowd, ccolors = [], []
            for c in changes:
                crowd.append([c["detected_at"][:16].replace("T", " "),
                              c.get("dataset_name") or c["dataset_uid"][:12],
                              c["change_type"]])
                ccolors.append(status_color(c["change_type"]))
            self.changes_table.set_rows(crowd, ccolors)
        else:
            self.changes_table.set_rows([["—", "Aucun changement enregistré", "—"]])

    @staticmethod
    def _last_run_hint(stats: dict, word: str) -> str:
        last = stats.get("last_run")
        if not last:
            return f"aucune veille exécutée (0 {word} cumulés)" if word == "nouveaux" else "aucune veille exécutée"
        return f"dernière veille : {(last.get('finished_at') or last.get('started_at') or '')[:16].replace('T', ' ')}"


def _status_fr(status: str) -> str:
    return {"ok": "OK", "partial": "partiel", "error": "erreur",
            "not_run": "jamais exécuté", "disabled": "désactivé"}.get(status, status)
