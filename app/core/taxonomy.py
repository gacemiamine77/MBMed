"""Taxonomie scientifique du projet MBM.

Ce module fixe les vocabulaires contrôlés partagés par la base de données,
les connecteurs, l'évaluation et l'interface :

* les classes d'acquisition A→E (règle : un modèle régional interpolé n'est
  jamais une vérité terrain) ;
* les types de méthode d'acquisition (sonar multifaisceaux, lidar, SDB…)
* les types de licence et de format ;
* les statuts de validation des métadonnées ;
* les utilitaires de classes de profondeur et de distance à la côte.

Aucune dépendance à Qt ni au réseau : ce module est testable isolément.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.config.settings import DEPTH_CLASSES, SDB_DEPTH_WINDOW


class AcquisitionClass(str, Enum):
    """Classification A→E de la nature d'un produit bathymétrique."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"

    @property
    def label(self) -> str:
        return ACQUISITION_CLASSES[self.value]["label"]

    @property
    def is_ground_truth_candidate(self) -> bool:
        return ACQUISITION_CLASSES[self.value]["ground_truth_candidate"]


ACQUISITION_CLASSES: dict[str, dict[str, object]] = {
    "A": {
        "label": "Mesures sonar directes",
        "description": (
            "Bathymétrie issue de sondeurs multifaisceaux (MBES), monofaisceaux "
            "(SBES), sonar latéral ou lidar bathymétrique. Mesure directe de la "
            "profondeur, généralement la référence la plus fiable pour la "
            "validation d'un modèle SDB."
        ),
        "ground_truth_candidate": True,
        "weight_prior": 1.00,
        "color": "#2f9e6e",
    },
    "B": {
        "label": "Bathymétrie issue de l'altimétrie satellitaire",
        "description": (
            "Profondeur prédite à partir de l'anomalie de gravité marine "
            "(altimétrie radar). Résolution effective de plusieurs centaines de "
            "mètres à quelques kilomètres, adaptée aux grands fonds, non valide "
            "en zone littorale peu profonde."
        ),
        "ground_truth_candidate": False,
        "weight_prior": 0.35,
        "color": "#3d7ebe",
    },
    "C": {
        "label": "Bathymétrie dérivée de données optiques",
        "description": (
            "Satellite-Derived Bathymetry (SDB) : inversion du signal optique "
            "multispectral ou hyperspectral. Pertinente en eaux claires de 0 à "
            "~20-30 m ; dépend fortement de la turbidité, du substrat et de "
            "l'atmosphère. Ne se valide jamais par elle-même."
        ),
        "ground_truth_candidate": False,
        "weight_prior": 0.55,
        "color": "#c8912a",
    },
    "D": {
        "label": "Modèles bathymétriques régionaux interpolés",
        "description": (
            "Grilles régionales issues de la compilation et de l'interpolation "
            "de sources hétérogènes (EMODnet, GEBCO, SRTM+, cartes marines "
            "numérisées). Le pas de grille n'est pas la résolution effective ; "
            "ce type de produit ne doit JAMAIS être utilisé comme vérité terrain "
            "sans contrôle indépendant."
        ),
        "ground_truth_candidate": False,
        "weight_prior": 0.45,
        "color": "#8a6dbf",
    },
    "E": {
        "label": "Estimations géophysiques ou gravimétriques",
        "description": (
            "Profondeur déduite de modèles gravimétriques, sismiques ou de "
            "modélisation géophysique. Utile pour la structure régionale du "
            "fond, inadaptée à la validation SDB côtière."
        ),
        "ground_truth_candidate": False,
        "weight_prior": 0.25,
        "color": "#b2564f",
    },
}

ACQUISITION_METHODS: dict[str, str] = {
    "mbes": "Sonar multifaisceaux (MBES)",
    "sbes": "Sonar monofaisceau (SBES)",
    "sidescan": "Sonar latéral",
    "lidar_bathy": "Lidar bathymétrique (ALB)",
    "lidar_icesat2": "Altimétrie laser spatiale (ICESat-2 ATL03/ATL24)",
    "satellite_altimetry": "Altimétrie radar satellitaire",
    "sdb_optical": "SDB optique (multispectral/hyperspectral)",
    "sdb_sar": "SDB radar (SAR, approche indirecte)",
    "interpolation": "Interpolation/compilation de sources",
    "nautical_chart": "Cartes marines numérisées (ENC/données historiques)",
    "gravity_inversion": "Inversion gravimétrique",
    "seismic": "Sismique/estimation géophysique",
    "crowdsourced": "Bathymétrie participative (crowdsourced)",
    "unknown": "Méthode non documentée",
}

#: Méthodes compatibles avec chaque classe d'acquisition
METHODS_BY_CLASS: dict[str, tuple[str, ...]] = {
    "A": ("mbes", "sbes", "sidescan", "lidar_bathy", "nautical_chart", "crowdsourced", "lidar_icesat2"),
    "B": ("satellite_altimetry", "gravity_inversion"),
    "C": ("sdb_optical", "sdb_sar"),
    "D": ("interpolation",),
    "E": ("gravity_inversion", "seismic"),
}

LICENSE_TYPES: dict[str, str] = {
    "cc_by": "Creative Commons Attribution (CC-BY)",
    "cc_by_sa": "Creative Commons Attribution – Partage identique (CC-BY-SA)",
    "cc_by_nc": "Creative Commons Attribution – Pas d'utilisation commerciale (CC-BY-NC)",
    "cc0": "Domaine public (CC0)",
    "open_government": "Licence ouverte gouvernementale",
    "copernicus": "Licence Copernicus Marine / données Sentinel",
    "research_only": "Usage recherche uniquement",
    "restricted": "Accès restreint ou sur demande",
    "commercial": "Licence commerciale",
    "unknown": "Licence non précisée",
}

DATA_FORMATS: dict[str, str] = {
    "netcdf": "NetCDF / CF",
    "geotiff": "GeoTIFF",
    "cog": "Cloud Optimized GeoTIFF",
    "xyz": "ASCII XYZ",
    "csv": "CSV",
    "las": "LAS/LAZ (nuage de points)",
    "shapefile": "Shapefile",
    "geopackage": "GeoPackage",
    "bathy_att": "Attributs bathymétriques d'ENC (S-57/S-101)",
    "stac": "Catalogue STAC (items JSON)",
    "wms_wcs": "Service OGC (WMS/WCS/WMTS)",
    "other": "Autre",
}

METADATA_STATUS: dict[str, str] = {
    "validated": "Validé (revue humaine)",
    "auto_complete": "Complet automatiquement",
    "partial": "Partiel — champs critiques manquants",
    "unverified": "Non vérifié",
    "conflict": "Conflit entre sources",
}

DATASET_STATUS: dict[str, str] = {
    "new": "Nouveau",
    "updated": "Mis à jour",
    "unchanged": "Inchangé",
    "removed": "Retiré du catalogue source",
    "archived": "Archivé",
}

ACCESS_MODES: dict[str, str] = {
    "http_direct": "Téléchargement HTTP direct",
    "api": "API documentée",
    "stac": "Catalogue STAC",
    "ogc_wcs": "Service OGC WCS/WMTS",
    "subset": "Sous-ensemble par emprise (subset)",
    "manual": "Téléchargement manuel / sur demande",
    "restricted": "Accès restreint",
}

VALIDATION_CHECK_STATUS = ("ok", "partial", "missing", "conflict", "na")


@dataclass(frozen=True, slots=True)
class DepthClass:
    label: str
    min_m: float
    max_m: float

    def contains(self, dmin: float | None, dmax: float | None) -> bool:
        if dmin is None or dmax is None:
            return False
        return dmin < self.max_m and dmax > self.min_m

    def overlap_m(self, dmin: float | None, dmax: float | None) -> float:
        if dmin is None or dmax is None:
            return 0.0
        return max(0.0, min(dmax, self.max_m) - max(dmin, self.min_m))


def depth_classes() -> list[DepthClass]:
    return [DepthClass(label, lo, hi) for label, lo, hi in DEPTH_CLASSES]


def depth_coverage_windows(dmin: float | None, dmax: float | None) -> dict[str, float]:
    """Recouvrement (en mètres de colonne d'eau) avec chaque classe de profondeur."""
    bands = depth_classes()
    total = sum(b.overlap_m(dmin, dmax) for b in bands) or 1.0
    return {
        b.label: round(b.overlap_m(dmin, dmax) / total, 4) for b in bands
    }


def sdb_relevance_window(dmin: float | None, dmax: float | None) -> float:
    """Fraction de la colonne d'eau couverte dans la fenêtre SDB (0–100 m)."""
    if dmin is None or dmax is None or dmax <= dmin:
        return 0.0
    lo, hi = SDB_DEPTH_WINDOW
    overlap = max(0.0, min(dmax, hi) - max(dmin, lo))
    return round(min(1.0, overlap / (dmax - dmin)), 4)


def classify_method(method: str) -> str:
    """Déduit la classe A→E d'une méthode d'acquisition."""
    if not method:
        return "D"
    for cls, methods in METHODS_BY_CLASS.items():
        if method in methods:
            return cls
    return "D"


def coastal_class(distance_to_coast_km: float | None) -> str:
    """Classe côtière / plateau / large à partir de la distance à la côte."""
    if distance_to_coast_km is None:
        return "inconnue"
    if distance_to_coast_km <= 20.0:
        return "côtière"
    if distance_to_coast_km <= 100.0:
        return "plateau"
    return "large"


def label_of(mapping: dict[str, str], key: str | None, default: str = "—") -> str:
    if not key:
        return default
    return mapping.get(key, key)
