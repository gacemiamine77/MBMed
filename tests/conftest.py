"""Fixtures partagées des tests MBM.

Chaque test travaille sur une base SQLite temporaire : aucun test ne touche la
base de travail de l'utilisateur.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import Settings  # noqa: E402
from app.core.context import AppContext  # noqa: E402
from app.database.connection import Database  # noqa: E402
from app.database.repository import Repository  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch):
    """Empêche tout test d'écrire dans config/settings.toml du dépôt."""
    monkeypatch.setenv("MBM_CONFIG_FILE", str(tmp_path / "settings.toml"))
    monkeypatch.setenv("MBM_DATA_DIR", str(tmp_path / "data"))
    yield


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    s = Settings()
    s.data_dir = str(tmp_path / "data")
    s.database.backend = "sqlite"
    s.database.sqlite_path = str(tmp_path / "data" / "test.sqlite3")
    s.ensure_directories()
    return s


@pytest.fixture()
def database(settings: Settings) -> Database:
    db = Database(settings)
    db.initialize()
    yield db
    db.close()


@pytest.fixture()
def repo(database: Database) -> Repository:
    repository = Repository(database)
    repository.sync_sources()
    return repository


@pytest.fixture()
def context(settings: Settings) -> AppContext:
    ctx = AppContext(settings=settings)
    ctx.open_database(initialize=True)
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def qapp():
    """Application Qt hors écran (nécessaire pour tester l'interface)."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PySide6 indisponible: {exc}")
    app = QApplication.instance() or QApplication([])
    yield app
