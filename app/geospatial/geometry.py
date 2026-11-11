"""Outils géospatiaux de la Phase 1.

Objectif : calculs fiables d'emprise, de surface, de distance à la côte et de
filtrage spatial, sans dépendre d'un service en ligne.

Choix méthodologiques :
  * les emprises d'origine restent en WGS84 (EPSG:4326) et ne sont jamais
    reprojetées dans la base ;
  * les SURFACES sont calculées en projection équivalente (LAEA Méditerranée)
    pour éviter les biais de la projection géographique ;
  * la distance à la côte est estimée sur un trait de côte de référence
    embarqué (simplifié, résolution ~0,25°) : c'est une indication de contexte,
    pas une mesure hydrographique. Ce point est documenté dans l'interface.

GeoPandas/Shapely/pyproj sont utilisés s'ils sont installés ; un repli
mathématique pur (haversine + aire sphérique) garantit le fonctionnement sans
GDAL.
"""
from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from typing import Any, Iterable, Sequence

from app.config.settings import (
    ALGERIA_BBOX,
    ALGERIA_COASTAL_BBOX,
    DEFAULT_AREA_CRS,
    MEDITERRANEAN_BBOX,
)
from app.core.models import BBox

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088

# -- dépendances optionnelles ------------------------------------------------
try:  # pragma: no cover - dépend de l'environnement
    from pyproj import Geod, Transformer
    _HAS_PYPROJ = True
except Exception:  # pragma: no cover
    _HAS_PYPROJ = False

try:  # pragma: no cover
    from shapely.geometry import box as shapely_box, shape as shapely_shape
    from shapely.ops import transform as _shapely_ops_transform
    _HAS_SHAPELY = True

    def shapely_transform(func, geom):
        """Projection via shapely.transform si disponible (API non dépréciée)."""
        try:
            from shapely import transform as _transform  # shapely >= 2.0

            return _transform(geom, func, interleaved=False)
        except Exception:
            return _shapely_ops_transform(func, geom)
except Exception:  # pragma: no cover
    _HAS_SHAPELY = False


GEOSPATIAL_CAPABILITIES = {
    "pyproj": _HAS_PYPROJ,
    "shapely": _HAS_SHAPELY,
    "area_crs": DEFAULT_AREA_CRS,
    "coastline": "trait de côte de référence embarqué (simplifié)",
}


# ---------------------------------------------------------------------------
# Conversions et surfaces
# ---------------------------------------------------------------------------
def bbox_area_km2(bbox: BBox) -> float:
    """Surface géodésique exacte d'une emprise (ellipsoïde WGS84)."""
    if _HAS_PYPROJ:
        geod = Geod(ellps="WGS84")
        lons = [bbox.minx, bbox.maxx, bbox.maxx, bbox.minx, bbox.minx]
        lats = [bbox.miny, bbox.miny, bbox.maxy, bbox.maxy, bbox.miny]
        area, _ = geod.polygon_area_perimeter(lons, lats)
        return abs(area) / 1e6
    return _spherical_bbox_area_km2(bbox)


def _spherical_bbox_area_km2(bbox: BBox) -> float:
    phi1, phi2 = math.radians(bbox.miny), math.radians(bbox.maxy)
    dlam = math.radians(bbox.maxx - bbox.minx)
    return abs(EARTH_RADIUS_KM ** 2 * dlam * (math.sin(phi2) - math.sin(phi1)))


def bbox_area_km2_projected(bbox: BBox, crs: str = DEFAULT_AREA_CRS) -> float | None:
    """Surface en projection équivalente (comparable entre produits)."""
    if not (_HAS_PYPROJ and _HAS_SHAPELY):
        return None
    try:  # pragma: no cover
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        geom = shapely_transform(transformer.transform, shapely_box(*bbox.as_tuple()))
        return abs(geom.area) / 1e6
    except Exception as exc:  # pragma: no cover
        log.debug("Projection impossible: %s", exc)
        return None


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bbox_distance_km(a: BBox, b: BBox) -> float:
    """Distance minimale entre deux emprises (0 si elles se touchent)."""
    dx = max(0.0, b.minx - a.maxx, a.minx - b.maxx)
    dy = max(0.0, b.miny - a.maxy, a.miny - b.maxy)
    if dx == 0.0 and dy == 0.0:
        return 0.0
    cx = (a.minx + a.maxx) / 2.0
    cy = (a.miny + a.maxy) / 2.0
    return haversine_km(cx, cy, cx + dx, cy + dy) if dx else abs(dy) * 111.32


def bbox_intersection(a: BBox, b: BBox) -> BBox | None:
    minx, miny = max(a.minx, b.minx), max(a.miny, b.miny)
    maxx, maxy = min(a.maxx, b.maxx), min(a.maxy, b.maxy)
    if minx >= maxx or miny >= maxy:
        return None
    return BBox(minx, miny, maxx, maxy)


def coverage_fraction(container: BBox, area: BBox) -> float:
    """Part de ``container`` couverte par ``area`` (ex. emprise / fenêtre côtière)."""
    total = container.area_deg2()
    if total <= 0:
        return 0.0
    inter = bbox_intersection(container, area)
    return round(inter.area_deg2() / total, 4) if inter else 0.0


def intersection_fraction(area: BBox, container: BBox) -> float:
    total = area.area_deg2()
    if total <= 0:
        return 0.0
    inter = bbox_intersection(area, container)
    return round(inter.area_deg2() / total, 4) if inter else 0.0


def bbox_to_geojson(bbox: BBox, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    feature = {"type": "Feature", "geometry": bbox.to_geojson(), "properties": properties or {}}
    return feature


def bbox_to_wkt(bbox: BBox) -> str:
    return ("POLYGON((" +
            f"{bbox.minx} {bbox.miny}, {bbox.maxx} {bbox.miny}, "
            f"{bbox.maxx} {bbox.maxy}, {bbox.minx} {bbox.maxy}, "
            f"{bbox.minx} {bbox.miny}))")


# ---------------------------------------------------------------------------
# Trait de côte de référence (simplifié, usage contextuel)
# ---------------------------------------------------------------------------
#: Polyligne du littoral méditerranéen, ~0,25° de résolution. Suffisant pour
#: classer un produit « côtier / plateau / large », pas pour une analyse
#: hydrographique. Une version haute résolution (GSHHG/EMODnet) est prévue
#: en Phase 5.
COASTLINE_REFERENCE: tuple[tuple[float, float], ...] = (
    (-5.60, 36.01), (-5.35, 36.14), (-4.42, 36.72), (-2.46, 36.83), (-2.20, 36.72),
    (-1.90, 36.75), (-1.30, 37.55), (-0.98, 37.60), (-0.70, 37.63), (-0.48, 38.35),
    (0.15, 38.75), (0.23, 39.45), (0.87, 40.05), (0.87, 40.72), (1.25, 41.10),
    (2.17, 41.38), (3.20, 41.88), (3.32, 42.32), (3.60, 43.00), (4.00, 43.40),
    (4.65, 43.35), (5.35, 43.30), (6.15, 43.10), (6.90, 43.55), (7.60, 43.80),
    (8.45, 44.30), (8.93, 44.40), (9.85, 44.10), (10.30, 43.55), (10.55, 42.95),
    (11.10, 42.40), (12.05, 41.75), (12.60, 41.40), (13.60, 41.25), (14.25, 40.85),
    (14.75, 40.65), (15.30, 40.00), (15.65, 39.90), (16.05, 39.35), (16.55, 38.90),
    (17.10, 39.05), (17.12, 40.45), (17.95, 40.65), (18.35, 40.15), (18.48, 40.14),
    (18.95, 40.65), (19.45, 41.30), (19.40, 41.85), (18.95, 42.35), (18.55, 42.45),
    (17.75, 43.05), (16.45, 43.50), (15.20, 44.20), (14.45, 45.30), (13.75, 45.65),
    (13.60, 45.78), (13.05, 45.65), (12.35, 45.42), (12.32, 45.15), (12.42, 44.60),
    (12.55, 44.20), (13.10, 43.60), (13.52, 43.62), (14.00, 43.00), (14.75, 42.45),
    (15.90, 41.95), (16.18, 41.90), (16.87, 41.13), (17.95, 40.63), (18.35, 40.15),
    (18.00, 40.05), (17.25, 40.45), (16.55, 39.75), (17.15, 39.08), (16.90, 38.55),
    (16.25, 38.00), (15.65, 37.95), (15.10, 38.20), (15.25, 37.70), (15.10, 37.30),
    (15.29, 37.07), (15.09, 36.68), (14.40, 36.75), (13.60, 37.10), (12.60, 37.65),
    (12.43, 37.80), (11.85, 37.90), (11.10, 37.10), (10.60, 36.85), (10.18, 37.00),
    (10.20, 36.80), (9.85, 36.60), (9.20, 36.95), (8.75, 36.95), (8.25, 37.00),
    (7.75, 36.90), (7.00, 36.90), (6.60, 37.10), (5.80, 36.85), (5.10, 36.75),
    (4.50, 36.90), (3.90, 36.92), (3.30, 36.80), (2.60, 36.60), (2.20, 36.60),
    (1.30, 36.50), (0.25, 36.35), (-0.15, 35.95), (-0.60, 35.75), (-1.30, 35.45),
    (-1.95, 35.10), (-2.95, 35.15), (-3.90, 35.20), (-4.90, 35.20), (-5.30, 35.90),
    (-5.60, 36.01),
)


@lru_cache(maxsize=1)
def _coast_geod():
    return Geod(ellps="WGS84") if _HAS_PYPROJ else None


def distance_to_coast_km(lon: float, lat: float) -> float:
    """Distance approximative au trait de côte de référence (km)."""
    geod = _coast_geod()
    best = float("inf")
    for (lon2, lat2) in COASTLINE_REFERENCE:
        if geod is not None:  # pragma: no cover - dépend de l'environnement
            _, _, d = geod.inv(lon, lat, lon2, lat2)
            dist = abs(d) / 1000.0
        else:
            dist = haversine_km(lon, lat, lon2, lat2)
        if dist < best:
            best = dist
    return round(best, 2)


def bbox_distance_to_coast_km(bbox: BBox) -> float:
    """Distance du point le plus proche de l'emprise au littoral de référence."""
    cx, cy = bbox.centroid()
    return distance_to_coast_km(cx, cy)


#: Seuil de qualification « côtier » (distance centre d'emprise / trait de côte).
#: 50 km correspond à une emprise régionale touchant le plateau côtier ; la
#: classification fine par masque de distance sera faite en Phase 5.
COASTAL_THRESHOLD_KM = 50.0


def is_coastal(bbox: BBox | None, threshold_km: float = COASTAL_THRESHOLD_KM) -> bool:
    if bbox is None:
        return False
    return bbox_distance_to_coast_km(bbox) <= threshold_km


def touches_algeria(bbox: BBox | None) -> bool:
    if bbox is None:
        return False
    return bbox.intersects(BBox.from_any(ALGERIA_BBOX))


def algeria_overlap_fraction(bbox: BBox | None) -> float:
    if bbox is None:
        return 0.0
    return intersection_fraction(bbox, BBox.from_any(ALGERIA_BBOX))


def algeria_coastal_overlap_fraction(bbox: BBox | None) -> float:
    """Part de la fenêtre côtière algérienne couverte par le produit (0-1)."""
    if bbox is None:
        return 0.0
    return coverage_fraction(BBox.from_any(ALGERIA_COASTAL_BBOX), bbox)


def mediterranean_overlap_fraction(bbox: BBox | None) -> float:
    if bbox is None:
        return 0.0
    return intersection_fraction(bbox, BBox.from_any(MEDITERRANEAN_BBOX))


# ---------------------------------------------------------------------------
# Enrichissement d'un Dataset
# ---------------------------------------------------------------------------
def enrich_geometry(dataset: Any, coastal_threshold_km: float = COASTAL_THRESHOLD_KM) -> Any:
    """Renseigne coastal / distance_to_coast_km / in_algerian_waters.

    ``coastal_threshold_km`` : distance maximale entre le centre de l'emprise et
    le trait de côte de référence pour qualifier un produit de « côtier ».
    """
    bbox = getattr(dataset, "bbox", None)
    if bbox is None:
        dataset.coastal = False
        dataset.distance_to_coast_km = None
        dataset.in_algerian_waters = False
        return dataset
    dataset.distance_to_coast_km = bbox_distance_to_coast_km(bbox)
    dataset.coastal = bool(is_coastal(bbox, threshold_km=coastal_threshold_km))
    dataset.in_algerian_waters = bool(touches_algeria(bbox))
    if not dataset.footprint_geojson:
        dataset.footprint_geojson = bbox.to_geojson()
    return dataset


# ---------------------------------------------------------------------------
# Reprojection pour affichage / analyse (Phase 5)
# ---------------------------------------------------------------------------
def to_crs_points(points: Iterable[tuple[float, float]], dst_crs: str) -> list[tuple[float, float]]:
    """Reprojette une liste (lon, lat) vers un CRS cible."""
    pts = list(points)
    if not _HAS_PYPROJ or not pts or dst_crs.upper() in ("EPSG:4326", "4326"):
        return pts
    try:  # pragma: no cover
        tr = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
        return [tr.transform(lon, lat) for lon, lat in pts]
    except Exception as exc:  # pragma: no cover
        log.warning("Reprojection échouée (%s): %s", dst_crs, exc)
        return pts


def footprint_geojson_for_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Construit une FeatureCollection des emprises (utilisée par la carte)."""
    features: list[dict[str, Any]] = []
    for row in rows:
        bbox_raw = row.get("bbox")
        if not bbox_raw:
            continue
        try:
            bbox = BBox.from_any(json.loads(bbox_raw) if isinstance(bbox_raw, str) else bbox_raw)
        except Exception:
            continue
        features.append(bbox_to_geojson(bbox, {
            "uid": row.get("uid"),
            "name": row.get("name"),
            "source_id": row.get("source_id"),
            "acquisition_class": row.get("acquisition_class"),
        }))
    return {"type": "FeatureCollection", "features": features}


def human_area(area_km2: float | None) -> str:
    if area_km2 is None:
        return "—"
    if area_km2 >= 1_000_000:
        return f"{area_km2 / 1_000_000:.2f} M km²"
    if area_km2 >= 1000:
        return f"{area_km2:,.0f} km²".replace(",", " ")
    return f"{area_km2:.0f} km²"


def human_distance(km: float | None) -> str:
    if km is None:
        return "—"
    return f"{km:.0f} km" if km >= 10 else f"{km:.1f} km"
