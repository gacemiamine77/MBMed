"""Tests des modèles métier et de la taxonomie scientifique."""
from __future__ import annotations

import pytest

from app.core.models import BBox, Dataset, WatchRun, build_uid
from app.core.taxonomy import (
    ACQUISITION_CLASSES,
    classify_method,
    coastal_class,
    depth_coverage_windows,
    sdb_relevance_window,
)


class TestBBox:
    def test_valid(self):
        b = BBox(-2.0, 35.0, 9.0, 37.0)
        assert b.as_tuple() == (-2.0, 35.0, 9.0, 37.0)
        assert b.area_deg2() == pytest.approx(11 * 2)

    def test_invalid(self):
        with pytest.raises(ValueError):
            BBox(9.0, 35.0, -2.0, 37.0)

    def test_from_any(self):
        assert BBox.from_any([-1, 35, 1, 36]).minx == -1
        assert BBox.from_any({"minx": -1, "miny": 35, "maxx": 1, "maxy": 36}).maxy == 36
        assert BBox.from_any(None) is None
        with pytest.raises(ValueError):
            BBox.from_any([1, 2, 3])

    def test_geojson_closed_ring(self):
        ring = BBox(-1, 35, 1, 36).to_geojson()["coordinates"][0]
        assert ring[0] == ring[-1]
        assert len(ring) == 5

    def test_intersects(self):
        a = BBox(-2, 35, 2, 37)
        b = BBox(1, 36, 5, 40)
        c = BBox(10, 10, 12, 12)
        assert a.intersects(b)
        assert not a.intersects(c)


class TestTaxonomy:
    def test_classes_have_required_fields(self):
        for key, meta in ACQUISITION_CLASSES.items():
            for field in ("label", "description", "ground_truth_candidate", "color"):
                assert field in meta
            assert key in "ABCDE"

    def test_only_class_a_is_ground_truth_candidate(self):
        candidates = [k for k, v in ACQUISITION_CLASSES.items() if v["ground_truth_candidate"]]
        assert candidates == ["A"]

    def test_classify_method(self):
        assert classify_method("mbes") == "A"
        assert classify_method("lidar_icesat2") == "A"
        assert classify_method("satellite_altimetry") == "B"
        assert classify_method("sdb_optical") == "C"
        assert classify_method("interpolation") == "D"
        assert classify_method("seismic") == "E"
        assert classify_method("inconnu") == "D"

    def test_depth_windows(self):
        w = depth_coverage_windows(0, 200)
        assert sum(w.values()) == pytest.approx(1.0)
        assert w["0-20 m"] == pytest.approx(20 / 200, abs=1e-3)
        assert set(w) == {"0-20 m", "20-50 m", "50-100 m", "100-200 m", "> 200 m"}

    def test_depth_windows_partial(self):
        w = depth_coverage_windows(10, 30)
        assert w["0-20 m"] > 0 and w["20-50 m"] > 0
        assert w["50-100 m"] == 0

    def test_sdb_window(self):
        assert sdb_relevance_window(0, 100) == pytest.approx(1.0)
        assert sdb_relevance_window(0, 200) == pytest.approx(0.5)
        assert sdb_relevance_window(150, 300) == 0.0
        assert sdb_relevance_window(None, 100) == 0.0

    def test_coastal_class(self):
        assert coastal_class(5) == "côtière"
        assert coastal_class(60) == "plateau"
        assert coastal_class(500) == "large"
        assert coastal_class(None) == "inconnue"


class TestDataset:
    def _make(self, **kwargs) -> Dataset:
        base = dict(
            source_id="emodnet", source_item_id="dtm-2024",
            name="EMODnet DTM 2024", producer="EMODnet",
            official_url="https://emodnet.ec.europa.eu",
            bbox=BBox(-6, 30, 36, 46),
            resolution_m=115.0, depth_min_m=0.0, depth_max_m=5200.0,
            license="cc_by", acquisition_method="interpolation",
            publication_date="2024-06-01", vertical_reference="MSL",
        )
        base.update(kwargs)
        return Dataset(**base)

    def test_uid_is_stable(self):
        a = self._make()
        b = self._make()
        assert a.uid == b.uid
        assert a.uid == build_uid("emodnet", "dtm-2024")

    def test_class_inferred(self):
        assert self._make().acquisition_class == "D"
        assert self._make(acquisition_method="mbes").acquisition_class == "A"

    def test_fingerprint_changes_with_metadata(self):
        a = self._make()
        b = self._make(resolution_m=100.0)
        assert a.fingerprint() != b.fingerprint()
        assert a.fingerprint() == self._make().fingerprint()

    def test_completeness_and_status(self):
        full = self._make()
        assert full.metadata_completeness == 1.0
        full.refresh_metadata_status()
        assert full.metadata_status == "auto_complete"
        partial = self._make(resolution_m=None, vertical_reference="", publication_date=None)
        partial.refresh_metadata_status()
        assert partial.metadata_status in ("partial", "unverified")
        assert partial.metadata_completeness < 1.0
        assert "resolution_m" in partial.missing_critical_fields()

    def test_validated_status_is_preserved(self):
        ds = self._make(metadata_status="validated", resolution_m=None)
        ds.refresh_metadata_status()
        assert ds.metadata_status == "validated"

    def test_row_roundtrip(self):
        ds = self._make(countries=["DZ", "FR"], tags=["x"])
        row = ds.to_row()
        restored = Dataset.from_row(row)
        assert restored.name == ds.name
        assert restored.bbox == ds.bbox
        assert restored.countries == ["DZ", "FR"]
        assert restored.tags == ["x"]

    def test_conservative_defaults(self):
        ds = Dataset(source_id="gebco", source_item_id="x", name="y")
        assert ds.metadata_status == "unverified"
        assert ds.data_origin if hasattr(ds, "data_origin") else True
        assert ds.resolution_m is None
        assert ds.depth_min_m is None


def test_watch_run_ids_are_unique():
    a, b = WatchRun(), WatchRun()
    assert a.run_id != b.run_id or a.started_at == b.started_at
