"""Contexte applicatif partagé par les pages de l'interface.

Un seul objet ``AppContext`` est créé au démarrage et transmis aux pages :
il encapsule la configuration, la base, le dépôt et les services. Cela évite
les variables globales dispersées et rend l'application testable (on peut
injecter une base temporaire).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.config.settings import Settings, get_settings
from app.database.connection import Database
from app.database.repository import Repository

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings = field(default_factory=get_settings)
    database: Database | None = None
    repository: Repository | None = None
    status_message: str = "Prêt"
    extra: dict[str, Any] = field(default_factory=dict)

    # -- cycle de vie -------------------------------------------------------
    def open_database(self, initialize: bool = True) -> Repository:
        self.database = Database(self.settings)
        if initialize:
            self.database.initialize()
        self.repository = Repository(self.database)
        self.repository.sync_sources()
        log.info("Base ouverte (%s)", self.settings.database.backend)
        return self.repository

    def close(self) -> None:
        if self.database is not None:
            self.database.close()
            self.database = None

    # -- accès simplifiés ---------------------------------------------------
    @property
    def repo(self) -> Repository:
        if self.repository is None:
            raise RuntimeError("La base n'est pas ouverte : appelez open_database().")
        return self.repository

    def db_info(self) -> str:
        db = self.settings.database
        if db.backend == "sqlite":
            return f"SQLite · {db.resolved_sqlite_path()}"
        return f"PostgreSQL/PostGIS · {db.host}:{db.port}/{db.name}"

    def set_status(self, message: str) -> None:
        self.status_message = message


def create_context(settings: Settings | None = None, initialize_db: bool = True) -> AppContext:
    ctx = AppContext(settings=settings or get_settings())
    ctx.open_database(initialize=initialize_db)
    return ctx
