"""Tests de la configuration (valeurs par défaut, sérialisation, environnement)."""
from __future__ import annotations

import os

from app.config.settings import (
    ALGERIA_COASTAL_BBOX,
    DEPTH_CLASSES,
    MEDITERRANEAN_BBOX,
    Settings,
    _to_toml,
)


def test_defaults():
    s = Settings()
    assert s.database.backend == "sqlite"
    assert s.scheduler.weekly_day == "monday"
    assert s.scheduler.timezone == "Africa/Algiers"
    assert s.research_bbox == MEDITERRANEAN_BBOX


def test_depth_classes_are_ordered():
    values = [(lo, hi) for _, lo, hi in DEPTH_CLASSES]
    assert values == sorted(values)
    assert values[0][0] == 0.0


def test_algeria_window_is_inside_mediterranean():
    m = MEDITERRANEAN_BBOX
    a = ALGERIA_COASTAL_BBOX
    assert m[0] <= a[0] < a[2] <= m[2]
    assert m[1] <= a[1] < a[3] <= m[3]


def test_toml_roundtrip(tmp_path, monkeypatch):
    s = Settings()
    s.data_dir = str(tmp_path)
    s.database.sqlite_path = str(tmp_path / "x.sqlite3")
    s.scheduler.weekly_day = "friday"
    s.scheduler.weekly_hour = 4
    text = _to_toml(s.to_dict())
    assert 'weekly_day = "friday"' in text
    assert "weekly_hour = 4" in text
    assert "[database]" in text


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("MBM_DATA_DIR", str(tmp_path / "envdata"))
    monkeypatch.setenv("MBM_DB_BACKEND", "sqlite")
    monkeypatch.setenv("MBM_SQLITE_PATH", str(tmp_path / "env.sqlite3"))
    monkeypatch.setenv("MBM_SCHEDULER_ENABLED", "false")
    s = Settings()._apply_env()
    assert s.data_dir == str(tmp_path / "envdata")
    assert s.database.sqlite_path == str(tmp_path / "env.sqlite3")
    assert s.scheduler.enabled is False


def test_data_directories_created(tmp_path):
    s = Settings()
    s.data_dir = str(tmp_path / "d")
    s.ensure_directories()
    for sub in ("downloads", "reports", "catalogue", "cache", "logs", "raster"):
        assert (s.data_root / sub).is_dir()
