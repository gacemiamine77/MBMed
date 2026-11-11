"""Dépôt de données MBM : unique point d'accès SQL pour le catalogue, la veille,
les versions, les sources, les téléchargements et les statistiques du dashboard.

Les requêtes sont écrites en SQL portable (SQLite/PostgreSQL) : les agrégats
spécifiques (JSON, regex) sont évités ou calculés en Python.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from app.core.models import (
    BBox,
    ChangeLogEntry,
    ConnectorInfo,
    Dataset,
    DatasetVersion,
    DownloadRecord,
    WatchRun,
    utcnow,
)
from app.core.sources import SOURCES
from app.database.connection import Database

log = logging.getLogger(__name__)

DATASET_COLUMNS = (
    "uid", "source_id", "source_item_id", "name", "producer", "description",
    "official_url", "download_url", "access_mode", "doi", "citation",
    "publication_date", "update_date", "version", "first_seen", "last_checked", "status",
    "bbox", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy",
    "footprint_geojson", "region", "countries",
    "resolution_m", "effective_resolution_m", "resolution_note",
    "depth_min_m", "depth_max_m", "vertical_reference", "vertical_datum",
    "vertical_accuracy_m", "uncertainty_note",
    "acquisition_method", "acquisition_class", "platform", "sensor",
    "license", "license_url", "data_format", "file_size_mb", "crs", "download_method",
    "metadata_status", "metadata_completeness", "raw_metadata", "tags", "notes",
    "coastal", "distance_to_coast_km", "in_algerian_waters",
    "fingerprint", "identity_key", "data_origin", "created_at", "updated_at",
)


@dataclass(slots=True)
class DatasetFilter:
    """Filtres du catalogue / de la recherche avancée (section 9, page 4)."""

    text: str = ""
    source_ids: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    licenses: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    metadata_status: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    depth_min: float | None = None
    depth_max: float | None = None
    max_resolution_m: float | None = None
    bbox: BBox | None = None
    only_algeria: bool = False
    only_coastal: bool = False
    only_sdb_depth: bool = False
    only_ground_truth: bool = False
    since: str | None = None
    order_by: str = "name"
    descending: bool = False
    limit: int | None = None
    offset: int = 0

    def is_empty(self) -> bool:
        return not any([
            self.text, self.source_ids, self.classes, self.licenses, self.formats,
            self.methods, self.metadata_status, self.statuses, self.depth_min,
            self.depth_max, self.max_resolution_m, self.bbox, self.only_algeria,
            self.only_coastal, self.only_sdb_depth, self.only_ground_truth, self.since,
        ])


_ORDERABLE = {
    "name": "name", "source": "source_id", "class": "acquisition_class",
    "resolution": "resolution_m", "depth_min": "depth_min_m", "depth_max": "depth_max_m",
    "publication": "publication_date", "update": "update_date", "checked": "last_checked",
    "status": "status", "completeness": "metadata_completeness",
}


class Repository:
    """Accès données de haut niveau."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ==================================================================
    # Initialisation / sources
    # ==================================================================
    def sync_sources(self) -> None:
        """Aligne la table source_registry sur le registre Python (idempotent)."""
        now = utcnow()
        with self.db.transaction() as conn:
            for sid, src in SOURCES.items():
                conn.execute(
                    """
                    INSERT INTO source_registry (
                        source_id, label, category, description, institutions, homepage,
                        documentation, access_types, products, expected_classes, licenses,
                        known_limits, requires_credentials, implemented_phase, implemented,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        label=excluded.label, category=excluded.category,
                        description=excluded.description, institutions=excluded.institutions,
                        homepage=excluded.homepage, documentation=excluded.documentation,
                        access_types=excluded.access_types, products=excluded.products,
                        expected_classes=excluded.expected_classes, licenses=excluded.licenses,
                        known_limits=excluded.known_limits,
                        requires_credentials=excluded.requires_credentials,
                        implemented_phase=excluded.implemented_phase,
                        implemented=excluded.implemented, updated_at=excluded.updated_at
                    """,
                    (
                        sid, src.label, src.category, src.description, src.institutions,
                        src.homepage, src.documentation,
                        json.dumps(list(src.access_types)), json.dumps(list(src.products)),
                        json.dumps(list(src.expected_classes)), json.dumps(list(src.licenses)),
                        json.dumps(list(src.known_limits)),
                        int(src.requires_credentials), src.implemented_phase, int(src.implemented),
                        now, now,
                    ),
                )
                conn.execute(
                    "INSERT INTO source_status(source_id, last_status) VALUES (?, 'not_run') "
                    "ON CONFLICT(source_id) DO NOTHING",
                    (sid,),
                )

    def source_health(self) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM v_source_health ORDER BY source_id")

    def set_source_enabled(self, source_id: str, enabled: bool) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE source_registry SET enabled=? WHERE source_id=?",
                         (int(enabled), source_id))

    def source_enabled(self, source_id: str) -> bool:
        val = self.db.scalar("SELECT enabled FROM source_registry WHERE source_id=?", (source_id,))
        return bool(val) if val is not None else True

    def enabled_source_ids(self) -> list[str]:
        rows = self.db.query("SELECT source_id FROM source_registry WHERE enabled=1 ORDER BY source_id")
        return [r["source_id"] for r in rows]

    def update_source_status(
        self, source_id: str, status: str, message: str = "", items_seen: int = 0,
        duration_s: float | None = None,
    ) -> None:
        now = utcnow()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO source_status(source_id, last_run, last_status, last_message,
                                          items_seen, last_duration_s, consecutive_failures, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_run=excluded.last_run, last_status=excluded.last_status,
                    last_message=excluded.last_message, items_seen=excluded.items_seen,
                    last_duration_s=excluded.last_duration_s,
                    consecutive_failures = CASE WHEN excluded.last_status = 'ok' THEN 0
                                                ELSE source_status.consecutive_failures + 1 END,
                    updated_at=excluded.updated_at
                """,
                (source_id, now, status, message, items_seen, duration_s,
                 0 if status == "ok" else 1, now),
            )

    def connector_infos(self) -> list[ConnectorInfo]:
        """Fusionne définitions statiques + état persisté."""
        statuses = {r["source_id"]: r for r in self.source_health()}
        infos: list[ConnectorInfo] = []
        for sid, src in SOURCES.items():
            row = statuses.get(sid, {})
            info = src.to_info(enabled=bool(row.get("enabled", 1)))
            info.last_run = row.get("last_run")
            info.last_status = row.get("last_status") or "not_run"
            info.last_message = row.get("last_message") or ""
            info.items_seen = int(row.get("items_seen") or 0)
            info.last_duration_s = row.get("last_duration_s")
            infos.append(info)
        return infos

    # ==================================================================
    # Datasets — écriture
    # ==================================================================
    def upsert_dataset(self, ds: Dataset, origin: str = "connector") -> str:
        """Insère ou met à jour un jeu de données. Retourne 'new' | 'updated' | 'unchanged'."""
        ds.refresh_metadata_status()
        fingerprint = ds.fingerprint()
        existing = self.get_dataset(ds.uid)
        now = utcnow()
        if existing is None:
            self._insert_dataset(ds, fingerprint, origin, now)
            self.add_version(DatasetVersion(
                dataset_uid=ds.uid, version=ds.version, update_date=ds.update_date,
                fingerprint=fingerprint, changed_fields=[], comment="version initiale",
                source_snapshot=ds.raw_metadata,
            ))
            return "new"

        changed = self._changed_fields(existing, ds)
        if not changed:
            with self.db.transaction() as conn:
                conn.execute("UPDATE datasets SET last_checked=? WHERE uid=?", (now, ds.uid))
            return "unchanged"

        self._update_dataset(ds, fingerprint, now)
        self.add_version(DatasetVersion(
            dataset_uid=ds.uid, version=ds.version, update_date=ds.update_date,
            fingerprint=fingerprint, changed_fields=changed,
            comment="mise à jour détectée", source_snapshot=ds.raw_metadata,
        ))
        return "updated"

    def _insert_dataset(self, ds: Dataset, fingerprint: str, origin: str, now: str) -> None:
        row = ds.to_row()
        row.update({
            "fingerprint": fingerprint,
            "identity_key": ds.identity_key(),
            "data_origin": origin,
            "created_at": now,
            "updated_at": now,
        })
        if ds.bbox:
            row["bbox_minx"], row["bbox_miny"], row["bbox_maxx"], row["bbox_maxy"] = ds.bbox.as_tuple()
        else:
            row["bbox_minx"] = row["bbox_miny"] = row["bbox_maxx"] = row["bbox_maxy"] = None
        row["coastal"] = int(ds.coastal)
        row["in_algerian_waters"] = int(ds.in_algerian_waters)
        cols = [c for c in DATASET_COLUMNS if c in row]
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT INTO datasets ({','.join(cols)}) VALUES ({placeholders})"
        with self.db.transaction() as conn:
            conn.execute(sql, tuple(_sql_value(row[c]) for c in cols))

    def _update_dataset(self, ds: Dataset, fingerprint: str, now: str) -> None:
        row = ds.to_row()
        row.update({
            "fingerprint": fingerprint,
            "identity_key": ds.identity_key(),
            "updated_at": now,
            "last_checked": ds.last_checked or now,
        })
        if ds.bbox:
            row["bbox_minx"], row["bbox_miny"], row["bbox_maxx"], row["bbox_maxy"] = ds.bbox.as_tuple()
        row["coastal"] = int(ds.coastal)
        row["in_algerian_waters"] = int(ds.in_algerian_waters)
        update_cols = [c for c in DATASET_COLUMNS if c in row and c not in ("uid", "created_at", "data_origin")]
        assignments = ",".join(f"{c}=?" for c in update_cols)
        with self.db.transaction() as conn:
            conn.execute(f"UPDATE datasets SET {assignments} WHERE uid=?",
                         tuple(_sql_value(row[c]) for c in update_cols) + (ds.uid,))

    @staticmethod
    def _changed_fields(old: Dataset, new: Dataset) -> list[str]:
        fields = (
            "name", "producer", "version", "update_date", "publication_date",
            "resolution_m", "effective_resolution_m", "depth_min_m", "depth_max_m",
            "license", "data_format", "file_size_mb", "official_url", "download_url",
            "acquisition_method", "acquisition_class", "vertical_reference",
            "vertical_accuracy_m", "metadata_status", "description",
        )
        changed: list[str] = []
        for f in fields:
            if getattr(old, f) != getattr(new, f):
                changed.append(f)
        old_bbox = old.bbox.as_tuple() if old.bbox else None
        new_bbox = new.bbox.as_tuple() if new.bbox else None
        if old_bbox != new_bbox:
            changed.append("bbox")
        return changed

    def update_dataset_fields(self, uid: str, **fields: Any) -> bool:
        """Mise à jour ciblée (ex. revue manuelle des métadonnées)."""
        if not fields:
            return False
        fields["updated_at"] = utcnow()
        assignments = ",".join(f"{k}=?" for k in fields)
        with self.db.transaction() as conn:
            cur = conn.execute(f"UPDATE datasets SET {assignments} WHERE uid=?",
                               tuple(fields.values()) + (uid,))
            return cur.rowcount > 0

    def delete_dataset(self, uid: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM datasets WHERE uid=?", (uid,))

    def count_datasets(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM datasets") or 0)

    def clear_all_datasets(self) -> int:
        """Supprime tous les jeux de données (utilisé par scripts/tests)."""
        n = self.count_datasets()
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM datasets")
        return n

    # ==================================================================
    # Datasets — lecture
    # ==================================================================
    def get_dataset(self, uid: str) -> Dataset | None:
        rows = self.db.query("SELECT * FROM datasets WHERE uid=?", (uid,))
        return Dataset.from_row(rows[0]) if rows else None

    def list_datasets(self, filt: DatasetFilter | None = None) -> list[Dataset]:
        sql, params = self._build_query(filt, count=False)
        rows = self.db.query(sql, params)
        return [Dataset.from_row(r) for r in rows]

    def list_dataset_rows(self, filt: DatasetFilter | None = None) -> list[dict[str, Any]]:
        """Variante légère pour les tableaux de l'interface (pas d'objets métier)."""
        sql, params = self._build_query(filt, count=False)
        return self.db.query(sql, params)

    def count_filtered(self, filt: DatasetFilter | None = None) -> int:
        sql, params = self._build_query(filt, count=True)
        return int(self.db.scalar(sql, params) or 0)

    def _build_query(self, filt: DatasetFilter | None, count: bool) -> tuple[str, list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        f = filt or DatasetFilter()

        if f.text:
            where.append("(LOWER(name) LIKE ? OR LOWER(producer) LIKE ? OR LOWER(description) LIKE ?)")
            like = f"%{f.text.lower().strip()}%"
            params += [like, like, like]
        for column, values in (
            ("source_id", f.source_ids), ("acquisition_class", f.classes),
            ("license", f.licenses), ("data_format", f.formats),
            ("acquisition_method", f.methods), ("metadata_status", f.metadata_status),
            ("status", f.statuses),
        ):
            if values:
                where.append(f"{column} IN ({','.join('?' for _ in values)})")
                params += list(values)
        if f.depth_min is not None:
            where.append("depth_max_m IS NOT NULL AND depth_max_m >= ?")
            params.append(f.depth_min)
        if f.depth_max is not None:
            where.append("depth_min_m IS NOT NULL AND depth_min_m <= ?")
            params.append(f.depth_max)
        if f.max_resolution_m is not None:
            where.append("resolution_m IS NOT NULL AND resolution_m <= ?")
            params.append(f.max_resolution_m)
        if f.only_algeria:
            where.append("in_algerian_waters = 1")
        if f.only_coastal:
            where.append("coastal = 1")
        if f.only_sdb_depth:
            where.append("depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL "
                         "AND depth_min_m < 100 AND depth_max_m > 0")
        if f.only_ground_truth:
            where.append("acquisition_class = 'A'")
        if f.since:
            where.append("(update_date >= ? OR publication_date >= ? OR first_seen >= ?)")
            params += [f.since, f.since, f.since]
        if f.bbox is not None:
            bb = f.bbox
            where.append("bbox_minx IS NOT NULL AND bbox_minx <= ? AND bbox_maxx >= ? "
                         "AND bbox_miny <= ? AND bbox_maxy >= ?")
            params += [bb.maxx, bb.minx, bb.maxy, bb.miny]

        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        if count:
            return f"SELECT COUNT(*) FROM datasets{where_sql}", params

        order_col = _ORDERABLE.get(f.order_by, "name")
        direction = "DESC" if f.descending else "ASC"
        nulls = "NULLS LAST" if self.db.backend != "sqlite" else ""
        if self.db.backend == "sqlite":
            order_sql = f" ORDER BY {order_col} IS NULL, {order_col} {direction}, name ASC"
        else:  # pragma: no cover
            order_sql = f" ORDER BY {order_col} {direction} {nulls}, name ASC"
        limit_sql = ""
        if f.limit is not None:
            limit_sql = f" LIMIT {int(f.limit)} OFFSET {int(f.offset or 0)}"
        return f"SELECT * FROM datasets{where_sql}{order_sql}{limit_sql}", params

    # ==================================================================
    # Versions et journal
    # ==================================================================
    def add_version(self, version: DatasetVersion) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO dataset_versions(dataset_uid, version, update_date, fingerprint,
                                             changed_fields, detected_at, source_snapshot, comment)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(dataset_uid, fingerprint) DO NOTHING
                """,
                (version.dataset_uid, version.version, version.update_date, version.fingerprint,
                 json.dumps(version.changed_fields, ensure_ascii=False), version.detected_at,
                 json.dumps(version.source_snapshot, ensure_ascii=False, default=str),
                 version.comment),
            )

    def version_history(self, uid: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM dataset_versions WHERE dataset_uid=? ORDER BY detected_at DESC",
            (uid,),
        )

    def add_change(self, entry: ChangeLogEntry) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO change_log(dataset_uid, run_id, change_type, field_name,
                                       old_value, new_value, detected_at, source_id, details)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (entry.dataset_uid, entry.run_id, entry.change_type, entry.field_name,
                 str(entry.old_value)[:500], str(entry.new_value)[:500], entry.detected_at,
                 entry.source_id, json.dumps(entry.details, ensure_ascii=False, default=str)),
            )

    def recent_changes(self, limit: int = 200, change_types: Sequence[str] | None = None,
                       since: str | None = None) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if change_types:
            where.append(f"c.change_type IN ({','.join('?' for _ in change_types)})")
            params += list(change_types)
        if since:
            where.append("c.detected_at >= ?")
            params.append(since)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        return self.db.query(
            f"""
            SELECT c.*, d.name AS dataset_name, d.source_id AS ds_source
            FROM change_log c LEFT JOIN datasets d ON d.uid = c.dataset_uid
            {where_sql}
            ORDER BY c.detected_at DESC LIMIT ?
            """,
            tuple(params) + (limit,),
        )

    # ==================================================================
    # Exécutions de veille
    # ==================================================================
    def start_watch_run(self, run: WatchRun) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO watch_runs(run_id, started_at, trigger, status, sources_total)
                VALUES (?,?,?,?,?)
                """,
                (run.run_id, run.started_at, run.trigger, run.status, run.sources_total),
            )

    def finish_watch_run(self, run: WatchRun) -> None:
        run.finished_at = run.finished_at or utcnow()
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE watch_runs SET finished_at=?, status=?, sources_total=?, sources_ok=?,
                    sources_failed=?, items_seen=?, new_count=?, updated_count=?,
                    removed_count=?, duplicate_count=?, message=?, details=?
                WHERE run_id=?
                """,
                (run.finished_at, run.status, run.sources_total, run.sources_ok,
                 run.sources_failed, run.items_seen, run.new_count, run.updated_count,
                 run.removed_count, run.duplicate_count, run.message,
                 json.dumps(run.details, ensure_ascii=False, default=str), run.run_id),
            )

    def add_run_source(self, run_id: str, source_id: str, status: str, items: int,
                       new_count: int, updated_count: int, errors: int,
                       duration_s: float | None, message: str = "") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO watch_run_sources(run_id, source_id, status, items, new_count,
                                              updated_count, errors, duration_s, message)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id, source_id) DO UPDATE SET
                    status=excluded.status, items=excluded.items, new_count=excluded.new_count,
                    updated_count=excluded.updated_count, errors=excluded.errors,
                    duration_s=excluded.duration_s, message=excluded.message
                """,
                (run_id, source_id, status, items, new_count, updated_count, errors,
                 duration_s, message),
            )

    def watch_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM watch_runs ORDER BY started_at DESC LIMIT ?", (limit,))

    def last_watch_run(self) -> dict[str, Any] | None:
        rows = self.watch_runs(limit=1)
        return rows[0] if rows else None

    def run_sources(self, run_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM watch_run_sources WHERE run_id=? ORDER BY source_id", (run_id,)
        )

    # ==================================================================
    # Statistiques du tableau de bord (section 9)
    # ==================================================================
    def dashboard_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        stats["total"] = self.count_datasets()
        stats["by_status"] = {r["status"]: r["n"] for r in self.db.query(
            "SELECT status, COUNT(*) AS n FROM datasets GROUP BY status")}
        stats["by_class"] = {r["acquisition_class"]: r["n"] for r in self.db.query(
            "SELECT acquisition_class, COUNT(*) AS n FROM datasets GROUP BY acquisition_class")}
        stats["by_source"] = {r["source_id"]: r["n"] for r in self.db.query(
            "SELECT source_id, COUNT(*) AS n FROM datasets GROUP BY source_id")}
        stats["by_license"] = {r["license"]: r["n"] for r in self.db.query(
            "SELECT license, COUNT(*) AS n FROM datasets GROUP BY license ORDER BY n DESC")}
        stats["by_depth_band"] = {r["band"]: r["n"] for r in self.db.query(
            "SELECT * FROM v_depth_bands")}
        stats["by_method"] = {r["acquisition_method"]: r["n"] for r in self.db.query(
            "SELECT acquisition_method, COUNT(*) AS n FROM datasets GROUP BY acquisition_method")}
        stats["by_metadata_status"] = {r["metadata_status"]: r["n"] for r in self.db.query(
            "SELECT metadata_status, COUNT(*) AS n FROM datasets GROUP BY metadata_status")}

        stats["algeria_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE in_algerian_waters=1") or 0)
        stats["algeria_sdb"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE in_algerian_waters=1 "
            "AND depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL "
            "AND depth_min_m < 100 AND depth_max_m > 0") or 0)
        stats["algeria_coastal"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE in_algerian_waters=1 AND coastal=1") or 0)
        # « noyau algérien » : produits dont l'emprise recouvre réellement la
        # fenêtre côtière algérienne (et non seulement le pays) en 0-100 m.
        stats["algeria_core"] = self._algeria_core_count()
        stats["algeria_ground_truth"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE in_algerian_waters=1 AND acquisition_class='A'") or 0)
        stats["coastal_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE coastal=1") or 0)
        stats["ground_truth_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE acquisition_class='A'") or 0)
        stats["sdb_depth_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL "
            "AND depth_min_m < 100 AND depth_max_m > 0") or 0)
        stats["avg_completeness"] = round(float(self.db.scalar(
            "SELECT AVG(metadata_completeness) FROM datasets") or 0.0), 3)

        # Sources
        health = self.source_health()
        stats["sources_total"] = len(health)
        stats["sources_implemented"] = sum(1 for r in health if r["implemented"])
        stats["sources_operational"] = sum(
            1 for r in health if r["implemented"] and r["last_status"] == "ok" and r["enabled"])
        stats["sources_failing"] = sum(
            1 for r in health if r["implemented"] and r["last_status"] == "error" and r["enabled"])
        stats["sources_enabled"] = sum(1 for r in health if r["enabled"])
        stats["sources_never_run"] = sum(
            1 for r in health if r["implemented"] and r["last_status"] == "not_run")

        # Veille
        last_run = self.last_watch_run()
        stats["last_run"] = last_run
        stats["new_count"] = int(last_run["new_count"]) if last_run else 0
        stats["updated_count"] = int(last_run["updated_count"]) if last_run else 0
        stats["removed_count"] = int(last_run["removed_count"]) if last_run else 0
        stats["duplicate_count"] = int(last_run["duplicate_count"]) if last_run else 0
        stats["new_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE status='new'") or 0)
        stats["updated_total"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE status='updated'") or 0)
        stats["changes_7d"] = {}
        stats["recent_changes"] = self.recent_changes(limit=12)
        stats["manual_datasets"] = int(self.db.scalar(
            "SELECT COUNT(*) FROM datasets WHERE data_origin='manual'") or 0)
        return stats

    def _algeria_core_count(self) -> int:
        """Produits couvrant la façade maritime algérienne en zone 0-100 m.

        Calcul Python (portable) : recouvrement de l'emprise du produit avec
        ALGERIA_COASTAL_BBOX supérieur à 5 % ET intersection avec la tranche
        bathymétrique 0-100 m.
        """
        from app.geospatial.geometry import algeria_coastal_overlap_fraction

        rows = self.db.query(
            "SELECT uid, bbox, depth_min_m, depth_max_m, coastal FROM datasets "
            "WHERE in_algerian_waters = 1 AND bbox_minx IS NOT NULL"
        )
        count = 0
        for row in rows:
            bbox = _safe_bbox(row.get("bbox"))
            if bbox is None:
                continue
            overlap = algeria_coastal_overlap_fraction(bbox)
            in_sdb = (
                row.get("depth_min_m") is not None and row.get("depth_max_m") is not None
                and row["depth_min_m"] < 100 and row["depth_max_m"] > 0
            )
            if overlap >= 0.05 and in_sdb:
                count += 1
        return count

    def algeria_coastal_zone(self):
        """Fenêtre côtière algérienne de référence (BBox) pour l'affichage."""
        from app.config.settings import ALGERIA_COASTAL_BBOX
        from app.core.models import BBox as _B

        return _B.from_any(ALGERIA_COASTAL_BBOX)

    def timeseries_datasets(self) -> list[dict[str, Any]]:
        """Nombre de jeux de données par mois (publication + première détection)."""
        rows = self.db.query(
            """
            SELECT ref_month, SUM(pub) AS published, SUM(seen) AS seen FROM (
                SELECT substr(publication_date,1,7) AS ref_month, 1 AS pub, 0 AS seen
                FROM datasets WHERE publication_date IS NOT NULL AND length(publication_date) >= 7
                UNION ALL
                SELECT substr(first_seen,1,7) AS ref_month, 0 AS pub, 1 AS seen
                FROM datasets WHERE first_seen IS NOT NULL AND length(first_seen) >= 7
            ) GROUP BY ref_month ORDER BY ref_month
            """
        )
        return _fill_missing_months(rows)

    # ==================================================================
    # Téléchargements / publications (structures prêtes)
    # ==================================================================
    def add_download(self, rec: DownloadRecord) -> int:
        row = rec.to_row()
        with self.db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO downloads(dataset_uid, url, local_path, status, bytes_total,
                                      checksum, checksum_algorithm, started_at, finished_at,
                                      message, subset_bbox)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(dataset_uid, url, local_path) DO UPDATE SET
                    status=excluded.status, bytes_total=excluded.bytes_total,
                    checksum=excluded.checksum, message=excluded.message
                """,
                (row["dataset_uid"], row["url"], row["local_path"], row["status"],
                 row["bytes_total"], row["checksum"], row["checksum_algorithm"],
                 row["started_at"], row["finished_at"], row["message"],
                 json.dumps(row["subset_bbox"]) if row["subset_bbox"] else None),
            )
            return int(cur.lastrowid or 0)

    def list_downloads(self) -> list[dict[str, Any]]:
        return self.db.query(
            """
            SELECT dl.*, d.name AS dataset_name, d.source_id
            FROM downloads dl LEFT JOIN datasets d ON d.uid = dl.dataset_uid
            ORDER BY dl.created_at DESC
            """
        )

    def downloads_summary(self) -> dict[str, int]:
        rows = self.db.query("SELECT status, COUNT(*) AS n FROM downloads GROUP BY status")
        summary = {r["status"]: int(r["n"]) for r in rows}
        summary["total"] = sum(summary.values())
        return summary

    def add_publication(self, pub: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO publications(doi, title, authors, journal, publication_date, url,
                                         abstract, source_id, related_dataset_uid, relevance_score,
                                         detected_at, verified, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(doi) DO UPDATE SET
                    title=excluded.title, url=excluded.url, abstract=excluded.abstract,
                    relevance_score=excluded.relevance_score, verified=excluded.verified
                """,
                (pub.get("doi"), pub.get("title", ""), pub.get("authors", ""),
                 pub.get("journal", ""), pub.get("publication_date"), pub.get("url", ""),
                 pub.get("abstract", ""), pub.get("source_id", ""),
                 pub.get("related_dataset_uid"), pub.get("relevance_score"),
                 pub.get("detected_at") or utcnow(), int(pub.get("verified", 0)),
                 pub.get("notes", "")),
            )

    def list_publications(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM publications ORDER BY publication_date DESC, detected_at DESC LIMIT ?",
            (limit,),
        )

    def audit(self, action: str, entity: str = "", entity_id: str = "",
              details: dict[str, Any] | None = None, actor: str = "system") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO audit_log(ts, actor, action, entity, entity_id, details) VALUES (?,?,?,?,?,?)",
                (utcnow(), actor, action, entity, entity_id,
                 json.dumps(details or {}, ensure_ascii=False, default=str)),
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sql_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, BBox):
        return json.dumps(list(value.as_tuple()))
    return value


def _safe_bbox(raw: Any) -> BBox | None:
    if not raw:
        return None
    try:
        return BBox.from_any(json.loads(raw) if isinstance(raw, str) else raw)
    except Exception:
        return None


def _fill_missing_months(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Complète les mois manquants à zéro entre le premier et le dernier point."""
    data = list(rows)
    if not data:
        return []
    months = sorted(r["ref_month"] for r in data if r.get("ref_month"))
    if not months:
        return []
    first, last = months[0], months[-1]
    y0, m0 = int(first[:4]), int(first[5:7])
    y1, m1 = int(last[:4]), int(last[5:7])
    index = {r["ref_month"]: r for r in data}
    out: list[dict[str, Any]] = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        key = f"{y:04d}-{m:02d}"
        row = index.get(key)
        out.append({
            "ref_month": key,
            "published": int(row["published"]) if row else 0,
            "seen": int(row["seen"]) if row else 0,
        })
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out
