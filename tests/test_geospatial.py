"""Tests du module géospatial (surfaces, distances, enrichissement)."""
from __future__ import annotations

import pytest

from app.config.settings import ALGERIA_COASTAL_BBOX, MEDITERRANEAN_BBOX
from app.core.models import BBox
from app.geospatial import geometry as geo


class TestAreas:
    def test_area_of_one_degree_square(self):
        # 1° x 1° à 35°N ≈ 10 000 km² (111 km x 91 km)
        area = geo.bbox_area_km2(BBox(0, 35, 1, 36))
        assert 9000 < area < 10500

    def test_spherical_fallback_matches_geodetic(self):
        bbox = BBox(0, 35, 2, 37)
        exact = geo.bbox_area_km2(bbox)
        approx = geo._spherical_bbox_area_km2(bbox)
        assert approx == pytest.approx(exact, rel=0.01)

    def test_mediterranean_area_is_plausible(self):
        area = geo.bbox_area_km2(BBox.from_any(MEDITERRANEAN_BBOX))
        # ~2,5 millions de km² pour la mer + les terres de l'emprise
        assert area > 2_000_000

    def test_projected_area_available(self):
        area = geo.bbox_area_km2_projected(BBox(0, 35, 2, 37))
        if geo._HAS_PYPROJ and geo._HAS_SHAPELY:
            assert area is not None and area > 0


class TestDistances:
    def test_haversine_reference(self):
        # Alger (3.06E, 36.75N) — Oran (0.63W, 35.70N) ≈ 360 km
        d = geo.haversine_km(3.06, 36.75, -0.63, 35.70)
        assert 330 < d < 390

    def test_distance_to_coast_zero_at_sea_level_point(self):
        # point situé sur le trait de côte embarqué (Alger)
        assert geo.distance_to_coast_km(3.20, 36.80) < 30

    def test_distance_decreases_towards_coast(self):
        far = geo.distance_to_coast_km(6.0, 38.0)
        near = geo.distance_to_coast_km(3.3, 36.85)
        assert far > near

    def test_bbox_distance_intersection_is_zero(self):
        a = BBox(0, 35, 2, 37)
        b = BBox(1, 36, 3, 38)
        assert geo.bbox_distance_km(a, b) == 0.0


class TestCoastalAndAlgeria:
    def test_is_coastal(self):
        coastal = BBox(0.0, 36.4, 3.0, 36.9)     # proche du littoral algérien
        # centré sur la mer Ionienne, à plus de 200 km de tout littoral
        offshore = BBox(17.0, 34.0, 19.0, 35.5)
        assert geo.is_coastal(coastal)
        assert not geo.is_coastal(offshore)
        assert not geo.is_coastal(offshore, threshold_km=120.0)

    def test_touches_algeria(self):
        assert geo.touches_algeria(BBox(0, 36, 5, 37))
        assert not geo.touches_algeria(BBox(20, 35, 30, 40))

    def test_algeria_coastal_overlap_fraction(self):
        window = BBox.from_any(ALGERIA_COASTAL_BBOX)
        assert geo.algeria_coastal_overlap_fraction(window) == pytest.approx(1.0)
        # la fonction retourne la part de la FENÊTRE couverte par l'emprise :
        # fenêtre 12° x 2,6° = 31,2 °² ; emprise de 5° x 1° = 5 °² -> 16,03 %
        assert geo.algeria_coastal_overlap_fraction(BBox(0, 36, 5, 37)) == pytest.approx(5 / 31.2, rel=0.02)
        assert geo.algeria_coastal_overlap_fraction(BBox(-6, 30, 20, 45)) == pytest.approx(1.0)

    def test_mediterranean_fraction(self):
        assert geo.mediterranean_overlap_fraction(BBox.from_any(MEDITERRANEAN_BBOX)) == pytest.approx(1.0)


class TestEnrichment:
    def test_enrich_sets_flags(self):
        from app.core.models import Dataset

        ds = Dataset(source_id="emodnet", source_item_id="x", name="x",
                     bbox=BBox(0.0, 36.0, 6.0, 37.5))
        geo.enrich_geometry(ds)
        assert ds.coastal is True
        assert ds.distance_to_coast_km < geo.COASTAL_THRESHOLD_KM
        assert ds.in_algerian_waters is True
        assert ds.distance_to_coast_km is not None
        assert ds.footprint_geojson is not None

    def test_enrich_without_bbox(self):
        from app.core.models import Dataset

        ds = Dataset(source_id="gebco", source_item_id="y", name="y")
        geo.enrich_geometry(ds)
        assert ds.coastal is False
        assert ds.distance_to_coast_km is None


class TestGeoJsonExport:
    def test_geojson_export(self, tmp_path, repo):
        from app.core.models import Dataset
        from app.exporters import export_datasets_geojson

        ds = Dataset(source_id="emodnet", source_item_id="g", name="Geo test",
                     bbox=BBox(0, 36, 5, 38))
        repo.upsert_dataset(ds)
        target = tmp_path / "out.geojson"
        export_datasets_geojson(repo.list_dataset_rows(), target)
        import json

        payload = json.loads(target.read_text())
        assert payload["type"] == "FeatureCollection"
        assert len(payload["features"]) == 1
        props = payload["features"][0]["properties"]
        assert props["name"] == "Geo test"
        assert payload["features"][0]["geometry"]["type"] == "Polygon"


class TestWkt:
    def test_wkt(self):
        wkt = geo.bbox_to_wkt(BBox(0, 35, 1, 36))
        assert wkt.startswith("POLYGON((")
        assert wkt.endswith("))")
