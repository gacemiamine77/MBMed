"""Tests du jeu de référence (étiquetage honnête) et des exports."""
from __future__ import annotations

import json

from app.database.seed import SEED_DATASETS, SEED_TAG, load_seed_data, seed_is_loaded
from app.exporters import (
    EXPORT_COLUMNS,
    export_datasets_csv,
    export_datasets_geojson,
    export_datasets_json,
)


class TestSeed:
    def test_seed_datasets_are_flagged(self):
        for ds in SEED_DATASETS:
            assert SEED_TAG in ds.tags, ds.name
            assert ds.metadata_status == "unverified", ds.name
            assert "démonstration" in ds.notes.lower() or "Phase 1" in ds.notes

    def test_seed_covers_expected_sources(self):
        sources = {d.source_id for d in SEED_DATASETS}
        assert {"emodnet", "gebco", "copernicus", "icesat2"} <= sources

    def test_all_seed_sources_exist_in_registry(self):
        from app.core.sources import SOURCES

        for ds in SEED_DATASETS:
            assert ds.source_id in SOURCES

    def test_seed_load_is_idempotent(self, repo):
        first = load_seed_data(repo)
        assert first["inserted"] == len(SEED_DATASETS)
        assert seed_is_loaded(repo)
        second = load_seed_data(repo)
        assert second["inserted"] == 0
        assert repo.count_datasets() == len(SEED_DATASETS)

    def test_seed_rows_are_marked_seed_origin(self, repo):
        load_seed_data(repo)
        rows = repo.db.query("SELECT data_origin, COUNT(*) AS n FROM datasets GROUP BY data_origin")
        assert rows == [{"data_origin": "seed", "n": len(SEED_DATASETS)}]

    def test_seed_geometry_enriched(self, repo):
        load_seed_data(repo)
        rows = repo.list_dataset_rows()
        assert any(r["in_algerian_waters"] for r in rows)
        assert all(r["bbox_minx"] is not None for r in rows)


class TestExports:
    def _populate(self, repo):
        load_seed_data(repo)
        return repo.list_dataset_rows()

    def test_csv_export(self, repo, tmp_path):
        rows = self._populate(repo)
        target = export_datasets_csv(rows, tmp_path / "cat.csv")
        content = target.read_text(encoding="utf-8-sig")
        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) == len(rows) + 1
        assert lines[0].split(";")[1] == "Nom du produit"
        # séparateur point-virgule et encodage avec BOM (ouverture Excel)
        assert target.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_json_export(self, repo, tmp_path):
        rows = self._populate(repo)
        target = export_datasets_json(rows, tmp_path / "cat.json")
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["dataset_count"] == len(rows)
        assert payload["datasets"][0]["uid"]

    def test_geojson_export(self, repo, tmp_path):
        rows = self._populate(repo)
        target = export_datasets_geojson(rows, tmp_path / "cat.geojson")
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert len(payload["features"]) == len(rows)
        for feature in payload["features"]:
            assert feature["geometry"]["coordinates"][0][0] == feature["geometry"]["coordinates"][0][-1]

    def test_excel_export(self, repo, tmp_path):
        try:
            from openpyxl import load_workbook
        except ImportError:
            import pytest

            pytest.skip("openpyxl non installé")
        from app.exporters import export_excel

        rows = self._populate(repo)
        target = export_excel({"Catalogue": (EXPORT_COLUMNS, rows)}, tmp_path / "cat.xlsx")
        wb = load_workbook(target)
        ws = wb["Catalogue"]
        assert ws.max_row == len(rows) + 1
        assert ws["B1"].value == "Nom du produit"

    def test_export_keeps_missing_values_empty(self, repo, tmp_path):
        load_seed_data(repo)
        rows = [r for r in repo.list_dataset_rows() if r["resolution_m"] is None]
        assert rows
        target = export_datasets_csv(rows, tmp_path / "nulls.csv")
        content = target.read_text(encoding="utf-8-sig")
        assert "None" not in content and "nan" not in content.lower()
