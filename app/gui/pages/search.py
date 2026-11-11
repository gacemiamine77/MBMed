"""Page 4 — Recherche et filtres avancés (section 9).

Construit un ``DatasetFilter`` complet (source, classe, licence, format,
profondeurs, résolution, emprise, statut de métadonnées, fenêtre SDB) et
exporte les résultats en CSV / JSON / GeoJSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.core.models import BBox
from app.core.sources import SOURCES
from app.core.taxonomy import (
    ACQUISITION_CLASSES, DATA_FORMATS, LICENSE_TYPES, METADATA_STATUS,
)
from app.database.repository import DatasetFilter
from app.exporters import export_datasets_csv, export_datasets_geojson, export_datasets_json
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS, CLASS_COLORS
from app.gui.widgets import Card, CardLayout, DataTable, SectionHeader, label

RESULT_COLUMNS = ["Produit", "Source", "Cl.", "Résol.", "Profondeurs", "Licence",
                  "Validation", "DZ", "Côtier"]


class SearchPage(BasePage):
    def build_content(self) -> None:
        grid = QHBoxLayout()
        grid.setSpacing(12)

        # ---- Critères -----------------------------------------------------
        criteria_card = Card()
        cl = CardLayout(criteria_card, spacing=8)
        cl.addWidget(SectionHeader("Critères de recherche", "Combinaison libre — tous les filtres sont cumulatifs"))

        self.text = QLineEdit()
        self.text.setPlaceholderText("Texte libre (nom, producteur, description)")
        cl.addWidget(self.text)

        form = QFormLayout()
        form.setSpacing(6)
        self.source_combo = _multi_combo([(s.label, s.source_id) for s in SOURCES.values()], "Toutes les sources")
        form.addRow("Source", self.source_combo)
        self.class_combo = _multi_combo(
            [(f"{k} · {v['label']}", k) for k, v in ACQUISITION_CLASSES.items()], "Toutes les classes")
        form.addRow("Classe A→E", self.class_combo)
        self.license_combo = _multi_combo(
            [(v, k) for k, v in LICENSE_TYPES.items()], "Toutes les licences")
        form.addRow("Licence", self.license_combo)
        self.format_combo = _multi_combo(
            [(v, k) for k, v in DATA_FORMATS.items()], "Tous les formats")
        form.addRow("Format", self.format_combo)
        self.meta_combo = _multi_combo(
            [(v, k) for k, v in METADATA_STATUS.items()], "Tous les statuts")
        form.addRow("Validation métadonnées", self.meta_combo)
        cl.addLayout(form)

        depth_row = QHBoxLayout()
        self.depth_min = QDoubleSpinBox(); self.depth_min.setRange(-1, 11000)
        self.depth_min.setSuffix(" m"); self.depth_min.setSpecialValueText("non précisée")
        self.depth_min.setValue(-1)
        self.depth_max = QDoubleSpinBox(); self.depth_max.setRange(-1, 11000)
        self.depth_max.setSuffix(" m"); self.depth_max.setSpecialValueText("non précisée")
        self.depth_max.setValue(-1)
        depth_row.addWidget(label("Profondeur entre", "Dim"))
        depth_row.addWidget(self.depth_min)
        depth_row.addWidget(label("et", "Dim"))
        depth_row.addWidget(self.depth_max)
        cl.addLayout(depth_row)

        res_row = QHBoxLayout()
        self.max_res = QDoubleSpinBox()
        self.max_res.setRange(0, 50000); self.max_res.setSuffix(" m"); self.max_res.setValue(0)
        self.max_res.setSpecialValueText("non limitée")
        res_row.addWidget(label("Résolution ≤", "Dim"))
        res_row.addWidget(self.max_res)
        cl.addLayout(res_row)

        bbox_grid = QGridLayout()
        bbox_grid.setSpacing(5)
        self.bb = {}
        for i, (key, text) in enumerate((("minx", "Lon min"), ("miny", "Lat min"),
                                         ("maxx", "Lon max"), ("maxy", "Lat max"))):
            spin = QDoubleSpinBox(); spin.setRange(-180, 180); spin.setDecimals(3)
            spin.setValue(0.0)
            self.bb[key] = spin
            bbox_grid.addWidget(label(text, "Dim"), i // 2, (i % 2) * 2)
            bbox_grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)
        cl.addWidget(label("Emprise intersectant (laisser 0 = ignorée)", "Dim"))
        cl.addLayout(bbox_grid)

        self.chk_algeria = QCheckBox("Littoral algérien uniquement")
        self.chk_coastal = QCheckBox("Emprises côtières (< 25 km)")
        self.chk_sdb = QCheckBox("Fenêtre SDB 0–100 m")
        self.chk_gt = QCheckBox("Vérité terrain possible (classe A)")
        for chk in (self.chk_algeria, self.chk_coastal, self.chk_sdb, self.chk_gt):
            cl.addWidget(chk)

        buttons = QHBoxLayout()
        run = QPushButton("Rechercher")
        run.setObjectName("Primary")
        run.clicked.connect(self.refresh)
        reset = QPushButton("Réinitialiser")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset)
        buttons.addWidget(run)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        cl.addLayout(buttons)
        cl.addStretch(1)
        criteria_card.setMinimumWidth(392)
        criteria_card.setMaximumWidth(440)
        grid.addWidget(criteria_card)

        # ---- Résultats ----------------------------------------------------
        result_card = Card()
        rl = CardLayout(result_card, spacing=8)
        head = SectionHeader("Résultats", "Tri par colonne · export CSV / JSON / GeoJSON")
        self.btn_csv = QPushButton("CSV")
        self.btn_csv.setObjectName("Ghost")
        self.btn_csv.clicked.connect(lambda: self._export("csv"))
        self.btn_json = QPushButton("JSON")
        self.btn_json.setObjectName("Ghost")
        self.btn_json.clicked.connect(lambda: self._export("json"))
        self.btn_geo = QPushButton("GeoJSON")
        self.btn_geo.setObjectName("Ghost")
        self.btn_geo.clicked.connect(lambda: self._export("geojson"))
        for b in (self.btn_csv, self.btn_json, self.btn_geo):
            head.add_action(b)
        rl.addWidget(head)
        self.summary = label("", "Dim", word_wrap=True)
        rl.addWidget(self.summary)
        self.table = DataTable(RESULT_COLUMNS, stretch_column=0)
        from PySide6.QtWidgets import QHeaderView

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        for col, width in {1: 132, 2: 36, 3: 64, 4: 100, 5: 96, 6: 120, 7: 48, 8: 54}.items():
            self.table.setColumnWidth(col, width)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setStretchLastSection(False)
        rl.addWidget(self.table, 1)
        grid.addWidget(result_card, 1)

        self.content.addLayout(grid, 1)
        self._last_rows: list[dict] = []

    # ------------------------------------------------------------------
    def _filter(self) -> DatasetFilter:
        bbox = None
        try:
            if any(self.bb[k].value() != 0.0 for k in self.bb):
                values = [self.bb["minx"].value(), self.bb["miny"].value(),
                          self.bb["maxx"].value(), self.bb["maxy"].value()]
                if values[0] < values[2] and values[1] < values[3]:
                    bbox = BBox(*values)
        except Exception:
            bbox = None
        dmin = self.depth_min.value() if self.depth_min.value() >= 0 else None
        dmax = self.depth_max.value() if self.depth_max.value() >= 0 else None
        return DatasetFilter(
            text=self.text.text().strip(),
            source_ids=_combo_values(self.source_combo),
            classes=_combo_values(self.class_combo),
            licenses=_combo_values(self.license_combo),
            formats=_combo_values(self.format_combo),
            metadata_status=_combo_values(self.meta_combo),
            depth_min=dmin,
            depth_max=dmax,
            max_resolution_m=self.max_res.value() if self.max_res.value() > 0 else None,
            bbox=bbox,
            only_algeria=self.chk_algeria.isChecked(),
            only_coastal=self.chk_coastal.isChecked(),
            only_sdb_depth=self.chk_sdb.isChecked(),
            only_ground_truth=self.chk_gt.isChecked(),
        )

    def refresh(self) -> None:
        filt = self._filter()
        rows = self.repo.list_dataset_rows(filt)
        self._last_rows = rows
        display, colors, data = [], [], []
        for row in rows:
            depth = "—"
            if row["depth_min_m"] is not None and row["depth_max_m"] is not None:
                depth = f"{row['depth_min_m']:.0f}–{row['depth_max_m']:.0f} m"
            display.append([
                row["name"],
                SOURCES[row["source_id"]].label if row["source_id"] in SOURCES else row["source_id"],
                row["acquisition_class"],
                f"{row['resolution_m']:.0f} m" if row["resolution_m"] else "—",
                depth,
                _short_license(row["license"]),
                METADATA_STATUS.get(row["metadata_status"], row["metadata_status"]).split(" —")[0],
                "oui" if row["in_algerian_waters"] else "—",
                "oui" if row["coastal"] else "—",
            ])
            colors.append(CLASS_COLORS.get(row["acquisition_class"], COLORS["text"]))
            data.append(row["uid"])
        self.table.set_rows(display, colors, data, sortable_numbers=False)
        total = self.repo.count_datasets()
        self.summary.setText(
            f"{len(rows)} produit(s) correspondent aux critères sur {total} catalogués."
            + ("" if not filt.is_empty() else " Aucun filtre actif : catalogue complet.")
        )
        self.notify(f"Recherche : {len(rows)} résultat(s)")

    def _reset(self) -> None:
        self.text.clear()
        for combo in (self.source_combo, self.class_combo, self.license_combo,
                      self.format_combo, self.meta_combo):
            combo.setCurrentIndex(0)
        self.depth_min.setValue(-1); self.depth_max.setValue(-1)
        self.max_res.setValue(0)
        for spin in self.bb.values():
            spin.setValue(0.0)
        for chk in (self.chk_algeria, self.chk_coastal, self.chk_sdb, self.chk_gt):
            chk.setChecked(False)
        self.refresh()

    def _export(self, kind: str) -> None:
        if not self._last_rows:
            self.notify("Aucun résultat à exporter")
            return
        default_dir = self.ctx.settings.report_dir()
        default_dir.mkdir(parents=True, exist_ok=True)
        labels = {"csv": "CSV (*.csv)", "json": "JSON (*.json)", "geojson": "GeoJSON (*.geojson)"}
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les résultats", str(default_dir / f"recherche_mbm.{kind}"), labels[kind])
        if not path:
            return
        try:
            target = Path(path)
            if kind == "csv":
                export_datasets_csv(self._last_rows, target)
            elif kind == "json":
                export_datasets_json(self._last_rows, target)
            else:
                export_datasets_geojson(self._last_rows, target)
            self.notify(f"Export réussi : {target}")
        except Exception as exc:  # pragma: no cover
            self.notify(f"Échec de l'export : {exc}")


SHORT_LICENSES = {
    "cc_by": "CC-BY", "cc_by_sa": "CC-BY-SA", "cc_by_nc": "CC-BY-NC", "cc0": "CC0",
    "open_government": "Ouverte", "copernicus": "Copernicus", "research_only": "Recherche",
    "restricted": "Restreinte", "commercial": "Commerciale", "unknown": "Non précisée",
}


def _short_license(key: str) -> str:
    return SHORT_LICENSES.get(key, key)


def _multi_combo(items, first_label: str) -> QComboBox:
    combo = QComboBox()
    combo.addItem(first_label, None)
    for text, value in items:
        combo.addItem(text, value)
    return combo


def _combo_values(combo: QComboBox) -> list[str]:
    value = combo.currentData()
    return [value] if value else []
