"""Page 3 — Catalogue des données : tableau + fiche scientifique détaillée.

Toutes les colonnes de la section 5 du cahier des charges sont accessibles.
Les champs absents s'affichent « — » et sont comptés dans la complétude des
métadonnées : on ne complète jamais une valeur manquante par une estimation.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QSplitter,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.models import Dataset
from app.core.taxonomy import (
    ACQUISITION_CLASSES, ACQUISITION_METHODS, DATA_FORMATS, LICENSE_TYPES,
    METADATA_STATUS, label_of,
)
from app.database.repository import DatasetFilter
from app.geospatial.geometry import bbox_area_km2, human_area, human_distance
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS, CLASS_COLORS
from app.gui.widgets import (
    Badge, Card, CardLayout, DataTable, EmptyState, SectionHeader, class_badge_color,
    hline, kv_row, label, status_color,
)

#: Colonnes du tableau principal. La fiche latérale expose l'intégralité des
#: champs de la section 5 (datum, précision verticale, taille, DOI, etc.).
COLUMNS = [
    "Nom du produit", "Source", "Cl.", "Résol.", "Profondeurs", "Licence",
    "Validation", "MàJ",
]


class CataloguePage(BasePage):
    def build_content(self) -> None:
        # Barre d'outils
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un produit, un producteur…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._debounced_refresh)
        bar_layout.addWidget(self.search, 2)

        self.class_filter = QComboBox()
        self.class_filter.addItem("Toutes les classes", None)
        for key, meta in ACQUISITION_CLASSES.items():
            self.class_filter.addItem(f"{key} · {meta['label']}", key)
        self.class_filter.currentIndexChanged.connect(lambda _: self.refresh())
        bar_layout.addWidget(self.class_filter, 1)

        self.source_filter = QComboBox()
        self.source_filter.addItem("Toutes les sources", None)
        for info in self.repo.connector_infos():
            self.source_filter.addItem(info.label, info.source_id)
        self.source_filter.currentIndexChanged.connect(lambda _: self.refresh())
        bar_layout.addWidget(self.source_filter, 1)

        self.algeria_only = QPushButton("Littoral algérien")
        self.algeria_only.setCheckable(True)
        self.algeria_only.toggled.connect(lambda _: self.refresh())
        bar_layout.addWidget(self.algeria_only)

        self.gt_only = QPushButton("Vérité terrain (A)")
        self.gt_only.setCheckable(True)
        self.gt_only.toggled.connect(lambda _: self.refresh())
        bar_layout.addWidget(self.gt_only)

        refresh_btn = QPushButton("Actualiser")
        refresh_btn.setObjectName("Ghost")
        refresh_btn.clicked.connect(self.refresh)
        bar_layout.addWidget(refresh_btn)
        self.content.addWidget(bar)

        # Splitter tableau / fiche
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        self.count_label = label("", "Dim")
        ll.addWidget(self.count_label)
        self.table = DataTable(COLUMNS, stretch_column=0)
        header = self.table.horizontalHeader()
        # largeurs fixes pour les colonnes techniques, le nom absorbe le reste
        widths = {1: 152, 2: 34, 3: 62, 4: 104, 5: 84, 6: 112, 7: 84}
        header.setSectionResizeMode(QHeaderView.Fixed)
        for col, width in widths.items():
            self.table.setColumnWidth(col, width)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(self._on_selection)
        ll.addWidget(self.table, 1)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.detail_tabs = QTabWidget()
        self.detail_stack = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_stack)
        self.detail_layout.setContentsMargins(14, 12, 14, 12)
        self.detail_layout.setSpacing(3)
        self.empty_detail = EmptyState(
            "Sélectionnez un produit",
            "La fiche scientifique détaillée (métadonnées complètes, limites, usage SDB) s'affichera ici.",
        )
        self.detail_layout.addWidget(self.empty_detail)
        self.detail_layout.addStretch(1)
        self.detail_tabs.addTab(self.detail_stack, "Fiche produit")

        self.raw_view = QTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setStyleSheet(
            f"font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 11px;"
            f"background-color: {COLORS['bg_alt']};"
        )
        self.detail_tabs.addTab(self.raw_view, "Métadonnées brutes")
        rl.addWidget(self.detail_tabs)
        splitter.addWidget(right)

        splitter.setSizes([980, 480])
        self.content.addWidget(splitter, 1)

        self._refresh_timer = None
        self.refresh()

    # ------------------------------------------------------------------
    def _debounced_refresh(self) -> None:
        from PySide6.QtCore import QTimer

        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(220)

    def _current_filter(self) -> DatasetFilter:
        return DatasetFilter(
            text=self.search.text().strip(),
            classes=[self.class_filter.currentData()] if self.class_filter.currentData() else [],
            source_ids=[self.source_filter.currentData()] if self.source_filter.currentData() else [],
            only_algeria=self.algeria_only.isChecked(),
            only_ground_truth=self.gt_only.isChecked(),
            order_by="name",
        )

    def refresh(self) -> None:
        filt = self._current_filter()
        rows = self.repo.list_dataset_rows(filt)
        display, colors, data = [], [], []
        for row in rows:
            src_label = _source_label(row["source_id"])
            depths = "—"
            if row["depth_min_m"] is not None and row["depth_max_m"] is not None:
                depths = f"{row['depth_min_m']:.0f} – {row['depth_max_m']:.0f} m"
            display.append([
                row["name"],
                src_label,
                row["acquisition_class"],
                _num(row["resolution_m"], 0),
                depths,
                _short_license(row["license"]),
                METADATA_STATUS.get(row["metadata_status"], row["metadata_status"]).split(" —")[0],
                (row["update_date"] or row["publication_date"] or "—")[:10],
            ])
            colors.append(CLASS_COLORS.get(row["acquisition_class"], COLORS["text"]))
            data.append(row["uid"])
        self.table.set_rows(display, colors, data, sortable_numbers=False)
        self.count_label.setText(
            f"{len(rows)} produit(s) affiché(s) · tri par colonne · "
            "couleur du nom = classe d'acquisition · fiche complète à droite"
        )
        if rows and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _on_selection(self) -> None:
        uid = self.table.selected_data()
        if not uid:
            return
        dataset = self.repo.get_dataset(str(uid))
        if dataset is None:
            return
        self._render_detail(dataset)

    # ------------------------------------------------------------------
    def _render_detail(self, ds: Dataset) -> None:
        # vide la fiche
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        title = label(ds.name, "SectionTitle", word_wrap=True)
        self.detail_layout.addWidget(title)
        badges = QHBoxLayout()
        badges.setSpacing(5)
        badges.addWidget(Badge(f"Classe {ds.acquisition_class}", class_badge_color(ds.acquisition_class)))
        badges.addWidget(Badge(label_of(METADATA_STATUS, ds.metadata_status),
                               status_color(ds.metadata_status)))
        if ds.coastal:
            badges.addWidget(Badge("côtière", COLORS["success"]))
        if ds.in_algerian_waters:
            badges.addWidget(Badge("littoral algérien", COLORS["accent"]))
        badges.addStretch(1)
        self.detail_layout.addLayout(badges)
        self.detail_layout.addWidget(hline())

        is_seed = "jeu-de-demonstration" in ds.tags
        if is_seed:
            warn = label(
                "⚠  Fiche de démonstration : produit public réel, mais valeurs numériques à confirmer "
                "par le connecteur officiel avant tout usage scientifique.",
                "WarningBanner", word_wrap=True,
            )
            self.detail_layout.addWidget(warn)

        self.detail_layout.addWidget(label("Identité et provenance", "SectionTitle"))
        self.detail_layout.addWidget(kv_row("Producteur", ds.producer))
        from app.core.sources import SOURCES as _S

        _src = _S.get(ds.source_id)
        self.detail_layout.addWidget(kv_row("Source", _src.label if _src else ds.source_id))
        self.detail_layout.addWidget(kv_row("URL officielle", ds.official_url))
        self.detail_layout.addWidget(kv_row("DOI", ds.doi))
        self.detail_layout.addWidget(kv_row("Mode d'accès", label_of(
            {"http_direct": "HTTP direct", "api": "API", "stac": "STAC", "ogc_wcs": "OGC WCS/WMTS",
             "subset": "Sous-ensemble", "manual": "Manuel", "restricted": "Restreint"}, ds.access_mode)))
        self.detail_layout.addWidget(kv_row("Date de publication", ds.publication_date or "—"))
        self.detail_layout.addWidget(kv_row("Dernière mise à jour", ds.update_date or "—"))
        self.detail_layout.addWidget(kv_row("Version", ds.version or "—"))
        self.detail_layout.addWidget(kv_row("Première détection", ds.first_seen[:19].replace("T", " ")))
        self.detail_layout.addWidget(kv_row("Dernière vérification", (ds.last_checked or "—")))

        self.detail_layout.addWidget(hline())
        self.detail_layout.addWidget(label("Géométrie et résolution", "SectionTitle"))
        if ds.bbox:
            bb = ds.bbox
            self.detail_layout.addWidget(kv_row(
                "Emprise (WGS84)",
                f"{bb.minx:.3f}° / {bb.miny:.3f}°  →  {bb.maxx:.3f}° / {bb.maxy:.3f}°"))
            self.detail_layout.addWidget(kv_row("Surface d'emprise", human_area(bbox_area_km2(bb))))
        else:
            self.detail_layout.addWidget(kv_row("Emprise (WGS84)", "—"))
        self.detail_layout.addWidget(kv_row("Résolution nominale", _res(ds.resolution_m)))
        self.detail_layout.addWidget(kv_row("Résolution effective", _res(ds.effective_resolution_m)
                                            + ("  (non documentée)" if ds.effective_resolution_m is None else "")))
        if ds.resolution_note:
            self.detail_layout.addWidget(kv_row("Note de résolution", ds.resolution_note))
        self.detail_layout.addWidget(kv_row("Distance au littoral (réf.)", human_distance(ds.distance_to_coast_km)))

        self.detail_layout.addWidget(hline())
        self.detail_layout.addWidget(label("Bathymétrie et références verticales", "SectionTitle"))
        self.detail_layout.addWidget(kv_row("Profondeur min", _res(ds.depth_min_m)))
        self.detail_layout.addWidget(kv_row("Profondeur max", _res(ds.depth_max_m)))
        self.detail_layout.addWidget(kv_row("Fenêtre SDB 0–100 m", f"{ds.sdb_window_fraction() * 100:.0f} % de la colonne d'eau"))
        self.detail_layout.addWidget(kv_row("Référence verticale", ds.vertical_reference))
        self.detail_layout.addWidget(kv_row("Datum vertical", ds.vertical_datum))
        self.detail_layout.addWidget(kv_row("Précision verticale annoncée", _res(ds.vertical_accuracy_m)))
        self.detail_layout.addWidget(kv_row("Incertitude", ds.uncertainty_note))

        self.detail_layout.addWidget(hline())
        self.detail_layout.addWidget(label("Méthode et qualité", "SectionTitle"))
        self.detail_layout.addWidget(kv_row("Méthode d'acquisition", label_of(ACQUISITION_METHODS, ds.acquisition_method)))
        self.detail_layout.addWidget(kv_row("Classe", f"{ds.acquisition_class} — {ds.class_label()}"))
        self.detail_layout.addWidget(kv_row("Plateforme", ds.platform))
        self.detail_layout.addWidget(kv_row("Capteur", ds.sensor))
        self.detail_layout.addWidget(kv_row("Licence", label_of(LICENSE_TYPES, ds.license)))
        self.detail_layout.addWidget(kv_row("Format", label_of(DATA_FORMATS, ds.data_format)))
        self.detail_layout.addWidget(kv_row("Taille", f"{ds.file_size_mb:.1f} Mo" if ds.file_size_mb else "—"))
        self.detail_layout.addWidget(kv_row("Complétude métadonnées", f"{ds.metadata_completeness * 100:.0f} %"))
        missing = ds.missing_critical_fields()
        if missing:
            self.detail_layout.addWidget(kv_row("Champs critiques manquants", ", ".join(missing)))

        class_meta = ACQUISITION_CLASSES.get(ds.acquisition_class, {})
        if class_meta:
            self.detail_layout.addWidget(hline())
            self.detail_layout.addWidget(label("Lecture scientifique", "SectionTitle"))
            self.detail_layout.addWidget(kv_row(
                "Nature", str(class_meta.get("description", "")), mono=False))
            self.detail_layout.addWidget(kv_row(
                "Vérité terrain possible",
                "oui" if class_meta.get("ground_truth_candidate") else
                "non — ne peut pas servir de référence de validation sans contrôle indépendant"))
        if ds.notes:
            self.detail_layout.addWidget(kv_row("Notes", ds.notes))

        self.detail_layout.addStretch(1)
        raw = {
            "uid": ds.uid,
            "source_id": ds.source_id,
            "source_item_id": ds.source_item_id,
            "bbox": ds.bbox.as_tuple() if ds.bbox else None,
            "raw_metadata": ds.raw_metadata,
            "tags": ds.tags,
            "identity_key": ds.identity_key(),
            "fingerprint": ds.fingerprint(),
        }
        self.raw_view.setPlainText(json.dumps(raw, indent=2, ensure_ascii=False))


def _short_license(license_key: str) -> str:
    text = label_of(LICENSE_TYPES, license_key)
    mapping = {
        "cc_by": "CC-BY", "cc_by_sa": "CC-BY-SA", "cc_by_nc": "CC-BY-NC",
        "cc0": "CC0", "open_government": "Ouverte", "copernicus": "Copernicus",
        "research_only": "Recherche", "restricted": "Restreinte",
        "commercial": "Commerciale", "unknown": "Non précisée",
    }
    return mapping.get(license_key, text.split("(")[0].strip())


def _num(value, digits: int) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _res(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1000:
        return f"{value / 1000:.1f} km"
    return f"{value:.1f} m"


SHORT_SOURCE_LABELS = {
    "emodnet": "EMODnet",
    "gebco": "GEBCO",
    "copernicus": "Copernicus",
    "icesat2": "ICESat-2",
    "national_hydrographic": "Hydrographie nat.",
    "scientific_repositories": "Dépôts sci.",
    "sonar_surveys": "Levés sonar",
    "coastal_dtm": "MNT côtiers",
}


def _source_label(source_id: str) -> str:
    """Libellé court pour les tableaux (le libellé long reste dans la fiche)."""
    from app.core.sources import SOURCES

    if source_id in SHORT_SOURCE_LABELS:
        return SHORT_SOURCE_LABELS[source_id]
    src = SOURCES.get(source_id)
    return src.label if src else source_id
