"""Page 2 — Carte interactive de la Méditerranée (version Phase 1).

Cette page est une version fonctionnelle *hors ligne* du module cartographique :
elle utilise un fond marin stylisé, un trait de côte de référence et les
emprises réelles des produits stockés en base (projection Mercator).

Ce qui est déjà opérationnel :
  * affichage des emprises, colorées par classe d'acquisition ;
  * filtrage par source, classe, pays/bassin et type (côtier / offshore) ;
  * superposition de plusieurs sources, zoom/déplacement, info-bulle ;
  * surbrillance du littoral algérien et de la fenêtre 0–100 m ;
  * export des emprises visibles en GeoJSON.

Ce qui relève de la Phase 5 (et n'est pas simulé ici) :
  * quantification des surfaces couvertes par bande de profondeur,
  * détection automatique des lacunes de couverture,
  * fonds de carte raster (WMS/XYZ) et couches bathymétriques,
  * calcul des surfaces en projection équivalente.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPolygonF, QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGraphicsItem, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.config.settings import ALGERIA_COASTAL_BBOX, MEDITERRANEAN_BBOX
from app.core.models import BBox
from app.core.sources import SOURCES
from app.core.taxonomy import ACQUISITION_CLASSES
from app.exporters import export_datasets_geojson
from app.geospatial.geometry import COASTLINE_REFERENCE
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS, CLASS_COLORS
from app.gui.widgets import Card, CardLayout, SectionHeader, label

MAP_EXTENT = BBox(-6.5, 29.5, 36.5, 46.5)   # étendue affichée (WGS84)


class EmpriseItem(QGraphicsItem):
    """Emprise rectangulaire interactive (survol, clic)."""

    def __init__(self, bbox: BBox, dataset_row: dict, color: QColor,
                 selected: bool = False) -> None:
        super().__init__()
        self.bbox = bbox
        self.row = dataset_row
        self.color = color
        self._selected = selected
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10 if selected else 5)
        tip = (
            f"<b>{dataset_row['name']}</b><br>"
            f"Source : {SOURCES[dataset_row['source_id']].label if dataset_row['source_id'] in SOURCES else dataset_row['source_id']}<br>"
            f"Classe {dataset_row['acquisition_class']} · "
            f"{'résolution ' + format(int(dataset_row['resolution_m']), ',d') + ' m' if dataset_row['resolution_m'] else 'résolution non précisée'}<br>"
            f"Profondeurs : {_depth_text(dataset_row)}"
        )
        self.setToolTip(tip)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-4, -4, 8, 8)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        # le tracé réel est géré par la vue (coordonnées scène)
        pass


class MediterraneanView(QGraphicsView):
    """Vue cartographique Mercator avec zoom molette et déplacement."""

    feature_clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(COLORS["sea_deep"])))
        self.setFrameShape(QGraphicsView.NoFrame)
        self._scale = 1.0
        self._footer_text = ""
        self.setMinimumHeight(420)

    # -- projection ---------------------------------------------------------
    @staticmethod
    def mercator(lon: float, lat: float) -> tuple[float, float]:
        """Projection de Mercator, axe Y inversé pour que le nord soit en haut."""
        import math

        lat = max(-85.0, min(85.0, lat))
        x = lon
        y = -math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
        return x, y

    @staticmethod
    def _norm_rect(bbox: "BBox") -> QRectF:
        x1, y1 = MediterraneanView.mercator(bbox.minx, bbox.maxy)
        x2, y2 = MediterraneanView.mercator(bbox.maxx, bbox.miny)
        left, top = min(x1, x2), min(y1, y2)
        return QRectF(left, top, abs(x2 - x1), abs(y2 - y1))

    def _extent_rect(self) -> QRectF:
        return self._norm_rect(MAP_EXTENT)

    def to_scene_rect(self, bbox: BBox) -> QRectF:
        return self._norm_rect(bbox)

    # -- helpers de scène ---------------------------------------------------
    def _add_rect(self, rect: QRectF, pen: QPen | Qt.PenStyle, brush: QBrush | Qt.BrushStyle,
                  z: float) -> None:
        item = self.scene_.addRect(rect, pen, brush)
        item.setZValue(z)

    def _add_line(self, x1: float, y1: float, x2: float, y2: float, pen: QPen, z: float) -> None:
        item = self.scene_.addLine(x1, y1, x2, y2, pen)
        item.setZValue(z)

    # -- rendu du fond ------------------------------------------------------
    def draw_background(self, show_graticule: bool = True, show_algeria: bool = True) -> None:
        self.scene_.clear()
        rect = self._extent_rect()
        self.scene_.setSceneRect(rect.adjusted(-1, -1, 1, 1))

        # mer : dégradé de profondeur purement indicatif
        self._add_rect(rect, QPen(Qt.NoPen), QBrush(QColor(COLORS["sea_deep"])), -10)
        bands = (
            (0.00, 0.30, "#1b3149"),   # nord (plateau)
            (0.30, 0.62, "#18304a"),
            (0.62, 1.00, "#152a41"),
        )
        for f0, f1, color in bands:
            band = QRectF(rect.left(), rect.top() + rect.height() * f0,
                          rect.width(), rect.height() * (f1 - f0))
            self._add_rect(band, QPen(Qt.NoPen), QBrush(QColor(color)), -9)

        if show_graticule:
            self._draw_graticule(rect)
        self._draw_coastline()
        if show_algeria:
            self._draw_algeria_window()

    def _draw_graticule(self, rect: QRectF) -> None:
        pen = QPen(QColor(COLORS["border"]))
        pen.setCosmetic(True)
        pen.setStyle(Qt.DotLine)
        for lon in range(-5, 40, 5):
            x, _ = self.mercator(lon, 38)
            if not (rect.left() <= x <= rect.right()):
                continue
            self._add_line(x, rect.top(), x, rect.bottom(), pen, -8)
            self._add_text(f"{lon}°E", x + 0.15, rect.bottom() - 1.35, 9, COLORS["text_dim"])
        for lat in range(30, 47, 5):
            _, y = self.mercator(10, lat)
            if not (rect.top() <= y <= rect.bottom()):
                continue
            self._add_line(rect.left(), y, rect.right(), y, pen, -8)
            self._add_text(f"{lat}°N", rect.left() + 0.35, y - 0.15, 9, COLORS["text_dim"])

    def _draw_coastline(self) -> None:
        """Trait de côte de référence (polyligne, sans remplissage).

        Le remplissage des terres n'est pas tenté en Phase 1 : le trait de côte
        embarqué est trop simplifié pour fermer correctement les continents.
        Un fond vectoriel réel (Natural Earth / GSHHG) est prévu en Phase 5.
        """
        pen = QPen(QColor("#c3dcea"))
        pen.setCosmetic(True)
        pen.setWidthF(1.6)
        poly = QPolygonF([QPointF(*self.mercator(lon, lat)) for lon, lat in COASTLINE_REFERENCE])
        coast = self.scene_.addPolygon(poly, pen)
        coast.setZValue(8)

    def _draw_algeria_window(self) -> None:
        bbox = BBox.from_any(ALGERIA_COASTAL_BBOX)
        r = self.to_scene_rect(bbox)
        pen = QPen(QColor(COLORS["warning"]))
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)
        pen.setWidthF(1.2)
        band = QColor(COLORS["warning"])
        band.setAlpha(26)
        self._add_rect(r, pen, QBrush(band), -3)
        self._add_text("Façade maritime algérienne", r.left(), r.top(), 10, COLORS["warning"])

    def _add_text(self, text: str, x: float, y: float, size: int = 9,
                  color: str = COLORS["text"]) -> None:
        """Étiquette dont la taille écran reste constante quel que soit le zoom."""
        item = self.scene_.addSimpleText(text)
        item.setBrush(QBrush(QColor(color)))
        font = QFont()
        font.setPixelSize(size)
        item.setFont(font)
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        item.setPos(x, y)
        item.setZValue(30)

    # -- emprises -----------------------------------------------------------
    def add_bbox(self, bbox: BBox, row: dict, color: str, selected: bool = False,
                 fill_alpha: int = 7, label_text: str | None = None) -> None:
        rect = self.to_scene_rect(bbox)
        c = QColor(color)
        fill = QColor(c)
        fill.setAlpha(min(40, fill_alpha + (16 if selected else 0)))
        pen = QPen(c)
        pen.setCosmetic(True)
        pen.setWidthF(1.8 if selected else 1.2)
        item = self.scene_.addRect(rect, pen, QBrush(fill))
        item.setZValue(12 if selected else 6)
        item.setToolTip(
            f"<b>{row['name']}</b><br>"
            f"Classe {row['acquisition_class']} · {_depth_text(row)}"
        )
        item.setData(0, row)
        item.setCursor(Qt.PointingHandCursor)
        if label_text:
            self._add_text(label_text, rect.left() + 0.25, rect.top() - 0.6, 8, color)

    # -- interactions -------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self._scale *= factor
        self.scale(factor, factor)

    def fit_extent(self) -> None:
        """Cadre l'étendue méditerranéenne avec une petite marge de lisibilité."""
        self.resetTransform()
        self.fitInView(self._extent_rect(), Qt.KeepAspectRatio)
        self.scale(0.955, 0.955)
        self._scale = self.transform().m11()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self.scene_.items():
            self.fit_extent()


class MapPage(BasePage):
    def build_content(self) -> None:
        # --- barre de contrôle ---------------------------------------------
        ctrl = Card()
        cl = CardLayout(ctrl, spacing=8, margins=(12, 10, 12, 10))
        row = QHBoxLayout()
        row.setSpacing(8)

        self.src_combo = QComboBox()
        self.src_combo.addItem("Toutes les sources", None)
        for src in SOURCES.values():
            self.src_combo.addItem(src.label, src.source_id)
        self.src_combo.currentIndexChanged.connect(lambda _: self._render())
        row.addWidget(label("Source", "Dim"))
        row.addWidget(self.src_combo)

        self.class_combo = QComboBox()
        self.class_combo.addItem("Toutes les classes", None)
        for k, meta in ACQUISITION_CLASSES.items():
            self.class_combo.addItem(f"{k} · {meta['label']}", k)
        self.class_combo.currentIndexChanged.connect(lambda _: self._render())
        row.addWidget(label("Classe", "Dim"))
        row.addWidget(self.class_combo)

        self.chk_coastal = QCheckBox("Côtier")
        self.chk_coastal.stateChanged.connect(lambda _: self._render())
        self.chk_offshore = QCheckBox("Large")
        self.chk_offshore.setChecked(True)
        self.chk_offshore.stateChanged.connect(lambda _: self._render())
        self.chk_algeria = QCheckBox("Littoral algérien")
        self.chk_algeria.stateChanged.connect(lambda _: self._render())
        self.chk_graticule = QCheckBox("Graticule")
        self.chk_graticule.setChecked(True)
        self.chk_graticule.stateChanged.connect(lambda _: self._render())
        for chk in (self.chk_coastal, self.chk_offshore, self.chk_algeria, self.chk_graticule):
            row.addWidget(chk)

        row.addStretch(1)
        fit_btn = QPushButton("Vue d'ensemble")
        fit_btn.setObjectName("Ghost")
        fit_btn.clicked.connect(lambda: self.view.fit_extent())
        row.addWidget(fit_btn)
        export_btn = QPushButton("Exporter emprises (GeoJSON)")
        export_btn.setObjectName("Ghost")
        export_btn.clicked.connect(self._export)
        row.addWidget(export_btn)
        cl.addLayout(row)
        self.content.addWidget(ctrl)

        # --- carte + légende -----------------------------------------------
        body = QHBoxLayout()
        body.setSpacing(12)
        self.view = MediterraneanView()
        body.addWidget(self.view, 1)

        legend_card = Card()
        ll = CardLayout(legend_card, spacing=6, margins=(12, 10, 12, 10))
        ll.addWidget(SectionHeader("Légende — classes A→E"))
        self.legend_layout = QVBoxLayout()
        self.legend_layout.setSpacing(4)
        ll.addLayout(self.legend_layout)
        ll.addWidget(label("Repères", "SectionTitle"))
        self.rep1 = label("▭  emprise d'un produit", "Dim")
        self.rep2 = label("┄  façade maritime algérienne", "Dim")
        ll.addWidget(self.rep1)
        ll.addWidget(self.rep2)
        ll.addSpacing(8)
        ll.addWidget(SectionHeader("Filtres actifs"))
        self.filter_summary = label("", "Dim", word_wrap=True)
        ll.addWidget(self.filter_summary)
        ll.addStretch(1)
        note = label(
            "Fond de carte schématique hors ligne. Les surfaces et lacunes de couverture "
            "seront calculées en Phase 5 (projection équivalente).",
            "Dim", word_wrap=True,
        )
        ll.addWidget(note)
        legend_card.setFixedWidth(272)
        body.addWidget(legend_card)
        self.content.addLayout(body, 1)

        # ---- légende : une entrée par classe présente ---------------------
        for key, meta in ACQUISITION_CLASSES.items():
            line = QWidget()
            lay = QHBoxLayout(line)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background-color: {CLASS_COLORS[key]}; border-radius: 2px;")
            lay.addWidget(swatch)
            lay.addWidget(label(f"{key} — {meta['label']}", "Dim", word_wrap=True), 1)
            self.legend_layout.addWidget(line)

        self._render()

    # ------------------------------------------------------------------
    def _rows(self) -> list[dict]:
        from app.database.repository import DatasetFilter

        class_key = self.class_combo.currentData()
        source_key = self.src_combo.currentData()
        rows = self.repo.list_dataset_rows(DatasetFilter(
            source_ids=[source_key] if source_key else [],
            classes=[class_key] if class_key else [],
        ))
        filtered = []
        for row in rows:
            if row["coastal"] and not self.chk_coastal.isChecked():
                # un produit côtier reste visible s'il couvre aussi le large
                if row["distance_to_coast_km"] is not None and row["distance_to_coast_km"] > 25:
                    filtered.append(row)
                continue
            if not row["coastal"] and not self.chk_offshore.isChecked():
                continue
            if self.chk_algeria.isChecked() and not row["in_algerian_waters"]:
                continue
            filtered.append(row)
        return filtered

    def _render(self) -> None:
        if not hasattr(self, "view"):
            return
        self.view.draw_background(
            show_graticule=self.chk_graticule.isChecked(),
            show_algeria=True,
        )
        rows = self._rows()
        for row in rows:
            bbox_raw = row.get("bbox")
            if not bbox_raw:
                continue
            try:
                bbox = BBox.from_any(json.loads(bbox_raw) if isinstance(bbox_raw, str) else bbox_raw)
            except Exception:
                continue
            color = CLASS_COLORS.get(row["acquisition_class"], COLORS["class_none"])
            self.view.add_bbox(bbox, row, color, selected=row["in_algerian_waters"])
        self.view.fit_extent()

        active = []
        if self.src_combo.currentData():
            active.append(f"source = {self.src_combo.currentText()}")
        if self.class_combo.currentData():
            active.append(f"classe = {self.class_combo.currentData()}")
        if self.chk_coastal.isChecked():
            active.append("côtier inclus")
        if self.chk_algeria.isChecked():
            active.append("littoral algérien seulement")
        self.filter_summary.setText(
            f"{len(rows)} emprise(s) affichée(s)" +
            (" · " + " · ".join(active) if active else " · aucun filtre")
        )
        self.notify(f"Carte : {len(rows)} emprise(s)")

    def _export(self) -> None:
        rows = self._rows()
        if not rows:
            self.notify("Aucune emprise à exporter")
            return
        target_dir = self.ctx.settings.report_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les emprises", str(target_dir / "emprises_mediterranee.geojson"),
            "GeoJSON (*.geojson)")
        if not path:
            return
        try:
            export_datasets_geojson(rows, Path(path))
            self.notify(f"Emprises exportées : {path}")
        except Exception as exc:  # pragma: no cover
            self.notify(f"Échec de l'export : {exc}")


def _depth_text(row: dict) -> str:
    dmin, dmax = row.get("depth_min_m"), row.get("depth_max_m")
    if dmin is None or dmax is None:
        return "non précisées"
    return f"{dmin:.0f} – {dmax:.0f} m"
