"""Modèles métier (dataclasses) partagés par la base, l'interface et les rapports.

Ces structures sont volontairement indépendantes de SQLAlchemy (pas de
dépendance ORM imposée) : le dépôt SQL ``app/database/repository.py`` mappe
ces objets vers les tables SQLite/PostGIS.

Règles de conception :
  * les profondeurs sont exprimées en MÈTRES POSITIFS (profondeur = -z) ;
  * les emprises sont en WGS84 (EPSG:4326) ;
  * un champ inconnu vaut ``None`` et n'est JAMAIS remplacé par une valeur
    inventée (exigence scientifique du projet, section 10) ;
  * chaque jeu de données porte la provenance de ses métadonnées.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from app.core.taxonomy import (
    ACQUISITION_CLASSES,
    METADATA_STATUS,
    classify_method,
    depth_coverage_windows,
    sdb_relevance_window,
)


def utcnow() -> str:
    """Horodatage ISO-8601 UTC (seconde près), utilisé partout en base."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.lower().split())
    return value


# ---------------------------------------------------------------------------
# Emprise géographique
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class BBox:
    """Rectangle géographique en WGS84 (minx, miny, maxx, maxy)."""

    minx: float
    miny: float
    maxx: float
    maxy: float

    def __post_init__(self) -> None:
        if self.minx > self.maxx or self.miny > self.maxy:
            raise ValueError(f"Emprise invalide: {self.as_tuple()}")

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.minx, self.miny, self.maxx, self.maxy)

    @classmethod
    def from_any(cls, value: "BBox | tuple | list | dict | None") -> "BBox | None":
        if value is None:
            return None
        if isinstance(value, BBox):
            return value
        if isinstance(value, dict):
            return cls(float(value["minx"]), float(value["miny"]),
                       float(value["maxx"]), float(value["maxy"]))
        seq = list(value)
        if len(seq) != 4:
            raise ValueError("Une emprise doit comporter 4 valeurs")
        return cls(*(float(v) for v in seq))  # type: ignore[arg-type]

    def to_geojson(self) -> dict[str, Any]:
        return {
            "type": "Polygon",
            "coordinates": [[
                [self.minx, self.miny], [self.maxx, self.miny],
                [self.maxx, self.maxy], [self.minx, self.maxy],
                [self.minx, self.miny],
            ]],
        }

    def intersects(self, other: "BBox") -> bool:
        return not (
            self.maxx < other.minx or self.minx > other.maxx
            or self.maxy < other.miny or self.miny > other.maxy
        )

    def area_deg2(self) -> float:
        return max(0.0, self.maxx - self.minx) * max(0.0, self.maxy - self.miny)

    def centroid(self) -> tuple[float, float]:
        return ((self.minx + self.maxx) / 2.0, (self.miny + self.maxy) / 2.0)


# ---------------------------------------------------------------------------
# Jeu de données
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Dataset:
    """Fiche d'un produit bathymétrique catalogué (section 5 du cahier des charges)."""

    # Identité
    uid: str = ""                       # clé stable calculée (source + identifiant)
    source_id: str = ""                 # identifiant du connecteur (emodnet, gebco…)
    source_item_id: str = ""            # identifiant du produit chez la source
    name: str = ""
    producer: str = ""                  # organisme producteur
    description: str = ""

    # Accès
    official_url: str = ""
    access_mode: str = "http_direct"
    download_url: str = ""
    doi: str = ""
    citation: str = ""

    # Dates et versions
    publication_date: str | None = None
    update_date: str | None = None
    version: str = ""
    first_seen: str = ""
    last_checked: str | None = None
    status: str = "new"

    # Emprise et résolution
    bbox: BBox | None = None
    footprint_geojson: dict[str, Any] | None = None
    region: str = ""
    countries: list[str] = field(default_factory=list)
    resolution_m: float | None = None            # résolution horizontale nominale
    effective_resolution_m: float | None = None  # résolution effective connue
    resolution_note: str = ""

    # Profondeur, vertical
    depth_min_m: float | None = None
    depth_max_m: float | None = None
    vertical_reference: str = ""      # ex. "MSL", "LAT", "ellipsoïde WGS84"
    vertical_datum: str = ""
    vertical_accuracy_m: float | None = None
    uncertainty_note: str = ""

    # Méthode et classe
    acquisition_method: str = "unknown"
    acquisition_class: str = ""        # A-E, déduite si vide
    platform: str = ""                 # navire, satellite, aéronef…
    sensor: str = ""

    # Technique
    license: str = "unknown"
    license_url: str = ""
    data_format: str = ""
    file_size_mb: float | None = None
    crs: str = "EPSG:4326"
    download_method: str = ""

    # Qualité
    metadata_status: str = "unverified"
    metadata_completeness: float = 0.0
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    # Dérivés (calculés)
    coastal: bool = False
    distance_to_coast_km: float | None = None
    in_algerian_waters: bool = False

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = build_uid(self.source_id, self.source_item_id or self.name)
        if not self.acquisition_class:
            self.acquisition_class = classify_method(self.acquisition_method)
        if not self.first_seen:
            self.first_seen = utcnow()
        self.metadata_completeness = self.compute_completeness()

    # -- calculs ------------------------------------------------------------
    CRITICAL_FIELDS = (
        "name", "producer", "official_url", "bbox", "resolution_m",
        "depth_min_m", "depth_max_m", "license", "acquisition_method",
        "publication_date", "vertical_reference",
    )

    def compute_completeness(self) -> float:
        filled = 0
        for f in self.CRITICAL_FIELDS:
            value = getattr(self, f)
            if value not in (None, "", [], {}):
                filled += 1
        return round(filled / len(self.CRITICAL_FIELDS), 3)

    def refresh_metadata_status(self) -> None:
        """Statut de validation automatique (jamais « validated » sans revue humaine)."""
        if self.metadata_status == "validated":
            return
        if self.metadata_completeness >= 0.995:
            self.metadata_status = "auto_complete"
        elif self.metadata_completeness >= 0.6:
            self.metadata_status = "partial"
        else:
            self.metadata_status = "unverified"

    def depth_windows(self) -> dict[str, float]:
        return depth_coverage_windows(self.depth_min_m, self.depth_max_m)

    def sdb_window_fraction(self) -> float:
        return sdb_relevance_window(self.depth_min_m, self.depth_max_m)

    def class_label(self) -> str:
        return str(ACQUISITION_CLASSES.get(self.acquisition_class, {}).get("label", "Non classé"))

    def metadata_label(self) -> str:
        return METADATA_STATUS.get(self.metadata_status, self.metadata_status)

    def missing_critical_fields(self) -> list[str]:
        return [f for f in self.CRITICAL_FIELDS if getattr(self, f) in (None, "", [], {})]

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["bbox"] = list(self.bbox.as_tuple()) if self.bbox else None
        row["countries"] = json.dumps(self.countries, ensure_ascii=False)
        row["tags"] = json.dumps(self.tags, ensure_ascii=False)
        row["raw_metadata"] = json.dumps(self.raw_metadata, ensure_ascii=False, default=str)
        row["footprint_geojson"] = (
            json.dumps(self.footprint_geojson, ensure_ascii=False) if self.footprint_geojson else None
        )
        return row

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Dataset":
        data = dict(row)
        if data.get("bbox"):
            data["bbox"] = BBox.from_any(json.loads(data["bbox"]) if isinstance(data["bbox"], str) else data["bbox"])
        for key in ("countries", "tags"):
            if isinstance(data.get(key), str):
                data[key] = json.loads(data[key] or "[]")
        if isinstance(data.get("raw_metadata"), str):
            data["raw_metadata"] = json.loads(data["raw_metadata"] or "{}")
        if isinstance(data.get("footprint_geojson"), str):
            data["footprint_geojson"] = json.loads(data["footprint_geojson"] or "null")
        data.pop("id", None)
        known = {f for f in cls.__slots__}  # type: ignore[attr-defined]
        data = {k: v for k, v in data.items() if k in known}
        return cls(**data)

    def fingerprint(self) -> str:
        """Empreinte des métadonnées : sert à détecter une mise à jour réelle."""
        payload = {
            "name": _norm(self.name),
            "version": _norm(self.version),
            "update_date": self.update_date,
            "resolution_m": self.resolution_m,
            "depth_min_m": self.depth_min_m,
            "depth_max_m": self.depth_max_m,
            "bbox": [round(v, 4) for v in self.bbox.as_tuple()] if self.bbox else None,
            "license": self.license,
            "file_size_mb": self.file_size_mb,
            "official_url": self.official_url,
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def identity_key(self) -> str:
        """Clé de déduplication tolérante (nom + producteur normalisés)."""
        blob = f"{_norm(self.name)}|{_norm(self.producer)}|{_norm(self.version)}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_uid(source_id: str, item: str) -> str:
    blob = f"{_norm(source_id)}::{_norm(item)}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Versions et empreintes d'emprise
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class DatasetVersion:
    """Historique des versions et des modifications d'un jeu de données (section 5)."""

    dataset_uid: str
    version: str = ""
    update_date: str | None = None
    fingerprint: str = ""
    changed_fields: list[str] = field(default_factory=list)
    detected_at: str = ""
    source_snapshot: dict[str, Any] = field(default_factory=dict)
    comment: str = ""

    def __post_init__(self) -> None:
        if not self.detected_at:
            self.detected_at = utcnow()

    def changed_summary(self) -> str:
        return ", ".join(self.changed_fields) if self.changed_fields else "version initiale"


@dataclass(slots=True)
class Footprint:
    """Emprise spatiale d'un jeu de données (optionnellement multi-parties)."""

    dataset_uid: str
    bbox: BBox | None = None
    geom_geojson: dict[str, Any] | None = None
    area_km2: float | None = None
    coastal_share: float | None = None
    distance_to_coast_km: float | None = None
    crs_original: str = "EPSG:4326"
    computed_at: str = ""

    def __post_init__(self) -> None:
        if not self.computed_at:
            self.computed_at = utcnow()


# ---------------------------------------------------------------------------
# Connecteurs et exécutions de veille
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ConnectorInfo:
    """État d'un connecteur de source (statique + dernier état d'exécution)."""

    source_id: str
    label: str
    category: str
    description: str
    homepage: str = ""
    documentation: str = ""
    access_types: list[str] = field(default_factory=list)
    requires_credentials: bool = False
    implemented_phase: int = 1
    implemented: bool = False
    enabled: bool = True
    last_run: str | None = None
    last_status: str = "not_run"     # ok | partial | error | not_run | disabled
    last_message: str = ""
    items_seen: int = 0
    last_duration_s: float | None = None


@dataclass(slots=True)
class WatchRun:
    """Trace d'une exécution du moteur de veille (rapport même sans nouveauté)."""

    run_id: str = ""
    started_at: str = ""
    finished_at: str | None = None
    trigger: str = "manual"           # manual | scheduler | startup
    status: str = "running"           # running | success | partial | failed
    sources_total: int = 0
    sources_ok: int = 0
    sources_failed: int = 0
    items_seen: int = 0
    new_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    duplicate_count: int = 0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        if not self.started_at:
            self.started_at = utcnow()


@dataclass(slots=True)
class ChangeLogEntry:
    """Journal des changements détectés (nouveau, mise à jour, retrait, doublon)."""

    dataset_uid: str
    run_id: str
    change_type: str                 # new | updated | removed | duplicate | error | note
    field_name: str = ""
    old_value: str = ""
    new_value: str = ""
    detected_at: str = ""
    source_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.detected_at:
            self.detected_at = utcnow()


# ---------------------------------------------------------------------------
# Téléchargements (structure posée en phase 1, exploitée en phase 7)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class DownloadRecord:
    dataset_uid: str
    url: str = ""
    local_path: str = ""
    status: str = "pending"          # pending | running | done | failed | manual_required | skipped
    bytes_total: int | None = None
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""
    subset_bbox: BBox | None = None

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["subset_bbox"] = list(self.subset_bbox.as_tuple()) if self.subset_bbox else None
        return row


@dataclass(slots=True)
class EvaluationScore:
    """Score SDB multi-critères (module d'évaluation, phase 6)."""

    dataset_uid: str
    resolution: float = 0.0
    vertical_accuracy: float = 0.0
    depth_coverage: float = 0.0
    temporal_proximity: float = 0.0
    metadata_quality: float = 0.0
    acquisition_method: float = 0.0
    raw_data_availability: float = 0.0
    independent_validation: float = 0.0
    total: float = 0.0
    grade: str = ""
    computed_at: str = ""
    rationale: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.computed_at:
            self.computed_at = utcnow()
