"""Graphiques Matplotlib intégrés aux pages Qt.

Chaque classe encapsule une figure et une méthode ``update_data`` : les pages
n'ont pas à manipuler Matplotlib directement. Les graphiques fonctionnent
entièrement hors ligne (aucune ressource externe).
"""
from __future__ import annotations

import logging
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget  # noqa: E402

from app.gui.theme import COLORS, CLASS_COLORS, SEQUENCE, chart_style  # noqa: E402

log = logging.getLogger(__name__)

matplotlib.rcParams.update(chart_style())


class BaseChart(QWidget):
    """Figure Matplotlib dans un widget Qt."""

    def __init__(self, title: str = "", parent: QWidget | None = None,
                 height: int = 210) -> None:
        super().__init__(parent)
        self.figure = Figure(figsize=(4, 2.4), dpi=100, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumHeight(height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self._title = title
        self._empty_message = "Aucune donnée"

    # -- API ---------------------------------------------------------------
    def clear(self) -> None:
        self.ax.clear()

    def redraw(self) -> None:
        try:
            self.canvas.draw_idle()
        except Exception as exc:  # pragma: no cover
            log.warning("Rendu graphique impossible: %s", exc)

    def _no_data(self, message: str = "Aucune donnée") -> None:
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.text(0.5, 0.5, message, ha="center", va="center",
                     color=COLORS["text_dim"], fontsize=9, transform=self.ax.transAxes)
        self.redraw()

    def _style_axes(self) -> None:
        self.ax.tick_params(labelsize=7.5, length=2)
        for spine in ("left", "bottom"):
            self.ax.spines[spine].set_color(COLORS["border"])
        self.ax.set_title(self._title, color=COLORS["text"], fontsize=9.5,
                          loc="left", pad=6, fontweight="bold")


class BarChart(BaseChart):
    """Histogramme horizontal ou vertical avec couleurs personnalisées."""

    def update_data(self, data: Mapping[str, float], color_map: Mapping[str, str] | None = None,
                    horizontal: bool = False, value_suffix: str = "") -> None:
        self.ax.clear()
        if not data:
            self._no_data()
            return
        labels = [str(k) for k in data.keys()]
        values = [float(v) for v in data.values()]
        colors = [color_map.get(k, SEQUENCE[i % len(SEQUENCE)]) if color_map else SEQUENCE[i % len(SEQUENCE)]
                  for i, k in enumerate(data.keys())]
        if horizontal:
            bars = self.ax.barh(labels, values, color=colors, height=0.62)
            self.ax.invert_yaxis()
            self.ax.tick_params(axis="y", labelsize=7.5)
            self.ax.set_xlim(0, max(values) * 1.22 if max(values) > 0 else 1)
            for bar, value in zip(bars, values):
                self.ax.text(bar.get_width() + max(values) * 0.015, bar.get_y() + bar.get_height() / 2,
                             f"{value:g}{value_suffix}", va="center", fontsize=7.5,
                             color=COLORS["text_muted"])
        else:
            bars = self.ax.bar(labels, values, color=colors, width=0.62)
            self.ax.tick_params(axis="x", labelsize=7.5)
            self.ax.set_ylim(0, max(values) * 1.22 if max(values) > 0 else 1)
            for bar, value in zip(bars, values):
                self.ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                             f"{value:g}{value_suffix}", ha="center", va="bottom", fontsize=7.5,
                             color=COLORS["text_muted"])
            if any(len(lbl) > 9 for lbl in labels):
                self.ax.tick_params(axis="x", labelrotation=25)
        self.ax.grid(axis="x" if horizontal else "y", alpha=0.18, linewidth=0.5)
        self.ax.set_axisbelow(True)
        self._style_axes()
        self.redraw()


class ClassDonutChart(BaseChart):
    """Répartition par classe d'acquisition A-E (anneau + légende)."""

    def update_data(self, data: Mapping[str, int], label_map: Mapping[str, str] | None = None) -> None:
        self.ax.clear()
        if not data or sum(data.values()) == 0:
            self._no_data("Aucun produit classé")
            return
        keys = list(data.keys())
        values = [data[k] for k in keys]
        colors = [CLASS_COLORS.get(k, COLORS["class_none"]) for k in keys]
        short_names = {
            "A": "Sonar direct", "B": "Altimétrie", "C": "SDB optique",
            "D": "MNT interpolé", "E": "Géophysique",
        }
        labels = []
        for k, v in zip(keys, values):
            name = short_names.get(k) or (label_map or {}).get(k, k)
            name = name.split(" — ")[0][:20]
            labels.append(f"{k} · {name} ({v})")
        wedges = self.ax.pie(values, colors=colors, startangle=90, radius=0.86,
                                wedgeprops={"width": 0.34, "edgecolor": COLORS["surface"],
                                            "linewidth": 1.4},
                                autopct=lambda p: f"{p:.0f}%" if p >= 8 else "",
                                pctdistance=0.79,
                                textprops={"color": COLORS["text"], "fontsize": 7.0})[0]
        self.ax.text(0, 0.04, str(sum(values)), ha="center", va="center",
                     color=COLORS["text"], fontsize=14, fontweight="bold")
        self.ax.legend(wedges, labels, loc="upper center", bbox_to_anchor=(0.5, 0.02),
                       ncol=1, fontsize=6.8, labelcolor=COLORS["text_muted"], frameon=False,
                       handlelength=0.9, handleheight=0.9, borderpad=0.1,
                       labelspacing=0.25, columnspacing=0.8)
        self.ax.set_aspect("equal")
        self._style_axes()
        self.ax.set_title("")
        self.redraw()


class DepthBandChart(BaseChart):
    """Répartition des produits par tranche bathymétrique."""

    BAND_COLORS = {
        "0-20 m": "#8ed0c8",
        "20-50 m": "#5fa9c0",
        "50-100 m": "#3f7fa8",
        "100-200 m": "#2c5f80",
        "> 200 m": "#1d3d55",
    }

    def update_data(self, data: Mapping[str, int]) -> None:
        self.ax.clear()
        if not data:
            self._no_data()
            return
        labels = list(data.keys())
        values = [data[k] for k in labels]
        colors = [self.BAND_COLORS.get(k, COLORS["accent"]) for k in labels]
        bars = self.ax.bar(labels, values, color=colors, width=0.66)
        self.ax.set_ylim(0, (max(values) * 1.25) if max(values) > 0 else 1)
        for bar, value in zip(bars, values):
            self.ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                         str(value), ha="center", va="bottom", fontsize=8,
                         color=COLORS["text_muted"])
        self.ax.grid(axis="y", alpha=0.18, linewidth=0.5)
        self.ax.set_axisbelow(True)
        self.ax.set_ylabel("Nombre de produits", fontsize=7.5)
        self._style_axes()
        self.redraw()


class TimelineChart(BaseChart):
    """Évolution mensuelle (publications et détections)."""

    def update_data(self, rows: Sequence[dict]) -> None:
        self.ax.clear()
        if not rows:
            self._no_data()
            return
        months = [r["ref_month"] for r in rows]
        published = [r.get("published", 0) for r in rows]
        seen = [r.get("seen", 0) for r in rows]
        x = range(len(months))
        self.ax.plot(x, published, marker="o", markersize=3, linewidth=1.6,
                     color=COLORS["accent"], label="Publiés")
        self.ax.fill_between(x, published, color=COLORS["accent"], alpha=0.16)
        self.ax.plot(x, seen, marker="s", markersize=3, linewidth=1.4,
                     color=COLORS["warning"], label="Détectés")
        step = max(1, len(months) // 6)
        self.ax.set_xticks(list(x)[::step])
        self.ax.set_xticklabels(months[::step], rotation=42, ha="right", fontsize=6.8)
        self.ax.legend(fontsize=6.8, labelcolor=COLORS["text_muted"], loc="upper left",
                       frameon=False, handlelength=1.2, borderpad=0.2)
        self.ax.grid(axis="y", alpha=0.18, linewidth=0.5)
        self.ax.set_axisbelow(True)
        self._style_axes()
        self.redraw()


class HBarQualityChart(BaseChart):
    """Barres horizontales de qualité des métadonnées par source (0-100 %)."""

    def update_data(self, data: Mapping[str, float], color_map: Mapping[str, str] | None = None) -> None:
        self.ax.clear()
        if not data:
            self._no_data()
            return
        labels = list(data.keys())
        values = [round(v * 100, 1) for v in data.values()]
        colors = [SEQUENCE[i % len(SEQUENCE)] for i in range(len(labels))]
        bars = self.ax.barh(labels, values, color=colors, height=0.58)
        self.ax.invert_yaxis()
        self.ax.set_xlim(0, 108)
        for bar, value in zip(bars, values):
            self.ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                         f"{value:.0f} %", va="center", fontsize=7.5, color=COLORS["text_muted"])
        self.ax.grid(axis="x", alpha=0.18, linewidth=0.5)
        self.ax.set_axisbelow(True)
        self._style_axes()
        self.redraw()
