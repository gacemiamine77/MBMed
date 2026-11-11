"""Tests du schéma, du dépôt et de la détection des changements."""
from __future__ import annotations

import pytest

from app.core.models import BBox, ChangeLogEntry, Dataset, DatasetVersion
from app.database.repository import DatasetFilter

REQUIRED_TABLES = {
    "datasets", "dataset_versions", "source_registry", "source_status",
    "watch_runs", "watch_run_sources", "change_log", "footprints",
    "downloads", "evaluations", "publications", "coverage_gaps", "audit_log",
    "tags", "dataset_tags", "schema_meta",
}

REQUIRED_VIEWS = {
    "v_dataset_summary", "v_depth_bands", "v_class_distribution",
    "v_source_health", "v_algeria_coverage", "v_recent_changes",
}


def _dataset(**kwargs) -> Dataset:
    base = dict(
        source_id="emodnet", source_item_id="dtm", name="DTM test",
        producer="EMODnet", official_url="https://example.org",
        bbox=BBox(-2.0, 35.0, 9.0, 37.0), resolution_m=115.0,
        depth_min_m=0.0, depth_max_m=120.0, license="cc_by",
        acquisition_method="interpolation", publication_date="2024-01-01",
        vertical_reference="MSL",
    )
    base.update(kwargs)
    return Dataset(**base)


class TestSchema:
    def test_tables_and_views_exist(self, database):
        names = set(database.table_names())
        assert REQUIRED_TABLES <= names
        assert REQUIRED_VIEWS <= names

    def test_schema_version(self, database):
        assert database.schema_version() == "1.0.0"

    def test_initialize_is_idempotent(self, database):
        database.initialize()
        database.initialize()
        assert database.schema_version() == "1.0.0"

    def test_foreign_keys_enforced(self, database):
        with pytest.raises(Exception):
            with database.transaction() as conn:
                conn.execute(
                    "INSERT INTO datasets(uid, source_id, name, first_seen) "
                    "VALUES ('x','source_inexistante','n','2024-01-01')"
                )


class TestSources:
    def test_all_sources_synchronised(self, repo):
        health = repo.source_health()
        assert len(health) == 8
        ids = {h["source_id"] for h in health}
        assert {"emodnet", "gebco", "copernicus", "icesat2"} <= ids

    def test_no_connector_claimed_operational_in_phase1(self, repo):
        health = repo.source_health()
        assert all(h["implemented"] == 0 for h in health)
        assert all(h["last_status"] == "not_run" for h in health)

    def test_enable_disable(self, repo):
        repo.set_source_enabled("gebco", False)
        assert repo.source_enabled("gebco") is False
        assert "gebco" not in repo.enabled_source_ids()
        repo.set_source_enabled("gebco", True)
        assert repo.source_enabled("gebco") is True

    def test_connector_infos_have_limits(self, repo):
        infos = {i.source_id: i for i in repo.connector_infos()}
        assert infos["emodnet"].implemented_phase == 2
        assert infos["copernicus"].requires_credentials is True
        assert infos["emodnet"].enabled is True


class TestDatasetCrud:
    def test_insert_then_unchanged(self, repo):
        ds = _dataset()
        assert repo.upsert_dataset(ds) == "new"
        assert repo.count_datasets() == 1
        assert repo.upsert_dataset(_dataset()) == "unchanged"

    def test_update_detects_changed_fields(self, repo):
        repo.upsert_dataset(_dataset())
        updated = _dataset(resolution_m=100.0, version="v2")
        assert repo.upsert_dataset(updated) == "updated"
        stored = repo.get_dataset(updated.uid)
        assert stored is not None
        assert stored.resolution_m == 100.0
        history = repo.version_history(updated.uid)
        assert len(history) == 2
        import json

        fields = json.loads(history[0]["changed_fields"])
        assert "resolution_m" in fields and "version" in fields

    def test_version_history_deduplicates(self, repo):
        ds = _dataset()
        repo.upsert_dataset(ds)
        repo.add_version(DatasetVersion(dataset_uid=ds.uid, fingerprint=ds.fingerprint(),
                                        changed_fields=["x"]))
        assert len(repo.version_history(ds.uid)) == 1

    def test_bbox_columns_are_denormalised(self, repo):
        ds = _dataset()
        repo.upsert_dataset(ds)
        row = repo.db.query("SELECT bbox_minx, bbox_maxy FROM datasets WHERE uid=?", (ds.uid,))[0]
        assert row["bbox_minx"] == -2.0
        assert row["bbox_maxy"] == 37.0

    def test_unknown_dataset_returns_none(self, repo):
        assert repo.get_dataset("inconnu") is None


class TestFiltering:
    @pytest.fixture(autouse=True)
    def _populate(self, repo):
        repo.upsert_dataset(_dataset(source_item_id="a", name="Produit A", acquisition_method="mbes",
                                     depth_max_m=20.0, resolution_m=5.0))
        repo.upsert_dataset(_dataset(source_item_id="b", name="Produit B", license="restricted",
                                     depth_min_m=150.0, depth_max_m=3000.0, resolution_m=450.0))
        repo.upsert_dataset(_dataset(source_item_id="c", name="Produit C", source_id="gebco"))
        self.repo = repo

    def test_text_search(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(text="produit b"))
        assert len(rows) == 1 and rows[0]["name"] == "Produit B"

    def test_class_filter(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(classes=["A"]))
        assert [r["name"] for r in rows] == ["Produit A"]

    def test_depth_filter(self):
        # intersection de tranche : produits dont la plage recoupe 10–50 m
        rows = self.repo.list_dataset_rows(DatasetFilter(depth_min=10, depth_max=50))
        assert {r["name"] for r in rows} == {"Produit A", "Produit C"}
        # aucun recoupement avec 4000–5000 m
        assert self.repo.list_dataset_rows(DatasetFilter(depth_min=4000, depth_max=5000)) == []

    def test_sdb_depth_filter(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(only_sdb_depth=True))
        names = {r["name"] for r in rows}
        assert "Produit A" in names and "Produit B" not in names

    def test_resolution_filter(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(max_resolution_m=10))
        assert [r["name"] for r in rows] == ["Produit A"]

    def test_source_filter(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(source_ids=["gebco"]))
        assert [r["name"] for r in rows] == ["Produit C"]

    def test_bbox_filter(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(bbox=BBox(0, 36, 20, 40)))
        assert len(rows) == 3
        rows = self.repo.list_dataset_rows(DatasetFilter(bbox=BBox(50, 10, 60, 20)))
        assert rows == []

    def test_order_and_limit(self):
        rows = self.repo.list_dataset_rows(DatasetFilter(order_by="name", descending=True, limit=2))
        assert [r["name"] for r in rows] == ["Produit C", "Produit B"]

    def test_count_filtered(self):
        assert self.repo.count_filtered(DatasetFilter(text="produit")) == 3


class TestStats:
    def test_dashboard_stats_structure(self, repo):
        repo.upsert_dataset(_dataset())
        stats = repo.dashboard_stats()
        for key in ("total", "by_class", "by_depth_band", "by_method", "by_source",
                    "sources_total", "sources_implemented", "algeria_core",
                    "algeria_sdb", "avg_completeness", "new_count", "updated_count"):
            assert key in stats
        assert stats["total"] == 1
        assert stats["sources_total"] == 8
        assert stats["sources_implemented"] == 0
        assert stats["new_count"] == 0  # aucune veille exécutée : zéro, pas de valeur inventée

    def test_depth_band_view(self, repo):
        repo.upsert_dataset(_dataset(depth_min_m=0, depth_max_m=30))
        band = {r["band"]: r["n"] for r in repo.db.query("SELECT * FROM v_depth_bands")}
        assert band["0-20 m"] == 1 and band["20-50 m"] == 1
        assert band["50-100 m"] == 0

    def test_algeria_core_metric(self, repo):
        from app.geospatial.geometry import enrich_geometry

        ds = enrich_geometry(_dataset(bbox=BBox(0.0, 36.0, 5.0, 37.5), depth_max_m=60.0))
        repo.upsert_dataset(ds)
        assert repo.dashboard_stats()["algeria_core"] == 1
        far = enrich_geometry(_dataset(source_item_id="far", bbox=BBox(20.0, 35.0, 30.0, 40.0)))
        repo.upsert_dataset(far)
        assert repo.dashboard_stats()["algeria_core"] == 1


class TestChangeLog:
    def test_add_and_read_changes(self, repo):
        ds = _dataset()
        repo.upsert_dataset(ds)
        repo.add_change(ChangeLogEntry(dataset_uid=ds.uid, run_id="run-1",
                                       change_type="new", source_id="emodnet"))
        changes = repo.recent_changes()
        assert len(changes) == 1
        assert changes[0]["change_type"] == "new"
        assert changes[0]["dataset_name"] == "DTM test"

    def test_filter_by_type(self, repo):
        ds = _dataset()
        repo.upsert_dataset(ds)
        repo.add_change(ChangeLogEntry(dataset_uid=ds.uid, run_id="r", change_type="updated"))
        repo.add_change(ChangeLogEntry(dataset_uid=ds.uid, run_id="r", change_type="duplicate"))
        assert len(repo.recent_changes(change_types=["updated"])) == 1


class TestWatchRuns:
    def test_run_cycle(self, repo):
        from app.core.models import WatchRun

        run = WatchRun(trigger="manual", sources_total=8)
        repo.start_watch_run(run)
        run.status = "success"
        run.sources_ok = 2
        run.new_count = 3
        repo.finish_watch_run(run)
        repo.add_run_source(run.run_id, "emodnet", "ok", 10, 2, 1, 0, 1.5, "")

        last = repo.last_watch_run()
        assert last is not None
        assert last["status"] == "success"
        assert last["new_count"] == 3
        assert repo.run_sources(run.run_id)[0]["source_id"] == "emodnet"
        assert repo.dashboard_stats()["new_count"] == 3


class TestDownloadsAndPublications:
    def test_download_records(self, repo):
        ds = _dataset()
        repo.upsert_dataset(ds)
        from app.core.models import DownloadRecord

        repo.add_download(DownloadRecord(dataset_uid=ds.uid, url="https://x/y.nc",
                                         status="pending"))
        rows = repo.list_downloads()
        assert len(rows) == 1
        assert rows[0]["dataset_name"] == "DTM test"
        assert repo.downloads_summary()["pending"] == 1

    def test_publications(self, repo):
        repo.add_publication({"doi": "10.1/abc", "title": "SDB en Méditerranée",
                              "verified": 0})
        pubs = repo.list_publications()
        assert len(pubs) == 1
        assert pubs[0]["verified"] == 0
