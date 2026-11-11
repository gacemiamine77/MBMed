"""Connexion unifiée à la base MBM (SQLite en local, PostgreSQL/PostGIS en production).

Le reste de l'application n'utilise que cette classe : aucun module métier ne
manipule directement ``sqlite3`` ou ``psycopg``.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from app.config.settings import Settings, get_settings

log = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
POSTGIS_EXTRA_FILE = Path(__file__).with_name("schema_postgis_extra.sql")


class DatabaseError(RuntimeError):
    """Erreur de base de données normalisée (message destiné à l'utilisateur)."""


class Database:
    """Façade de connexion.

    ``backend="sqlite"``  -> fichier local, aucune installation requise.
    ``backend="postgresql"`` -> nécessite psycopg (v3), PostGIS installé.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.backend = self.settings.database.backend.lower()
        self._conn: Any | None = None

    # -- cycle de vie -------------------------------------------------------
    def connect(self) -> Any:
        if self._conn is not None:
            return self._conn
        if self.backend == "postgresql":
            self._conn = self._connect_postgres()
        elif self.backend == "sqlite":
            self._conn = self._connect_sqlite()
        else:
            raise DatabaseError(f"Backend inconnu: {self.backend!r} (attendu: sqlite, postgresql)")
        return self._conn

    def _connect_sqlite(self) -> sqlite3.Connection:
        path = self.settings.database.resolved_sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        log.info("SQLite connecté: %s", path)
        return conn

    def _connect_postgres(self) -> Any:
        try:
            import psycopg  # type: ignore[import-not-found]
            from psycopg.rows import dict_row  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - dépend de l'environnement
            raise DatabaseError(
                "psycopg n'est pas installé. Installez-le (pip install 'psycopg[binary]') "
                "ou repassez en backend SQLite (mettez MBM_DB_BACKEND=sqlite)."
            ) from exc
        try:
            conn = psycopg.connect(self.settings.database.postgres_dsn(), row_factory=dict_row)
        except Exception as exc:  # pragma: no cover
            raise DatabaseError(f"Connexion PostgreSQL impossible: {exc}") from exc
        log.info("PostgreSQL connecté: %s:%s/%s", self.settings.database.host,
                 self.settings.database.port, self.settings.database.name)
        return conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def is_open(self) -> bool:
        return self._conn is not None

    # -- transactions -------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[Any]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # -- SQL ---------------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> Any:
        conn = self.connect()
        if self.backend == "sqlite":
            return conn.execute(sql, params)
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        conn = self.connect()
        if self.backend == "sqlite":
            conn.executemany(sql, rows)
        else:  # pragma: no cover
            cur = conn.cursor()
            cur.executemany(sql, rows)

    def query(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> list[dict[str, Any]]:
        cur = self.execute(sql, params)
        rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            else:  # sqlite3.Row
                result.append({k: row[k] for k in row.keys()})
        return result

    def scalar(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    # -- schéma -------------------------------------------------------------
    def initialize(self) -> None:
        """Crée le schéma portable, puis les extensions PostGIS si nécessaire."""
        schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
        with self.transaction() as conn:
            if self.backend == "sqlite":
                conn.executescript(schema_sql)
            else:  # pragma: no cover
                cur = conn.cursor()
                for statement in _split_sql(schema_sql.replace("AUTOINCREMENT", "")):
                    cur.execute(statement)
                if POSTGIS_EXTRA_FILE.exists():
                    for statement in _split_sql(POSTGIS_EXTRA_FILE.read_text(encoding="utf-8")):
                        cur.execute(statement)
        self.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1.0.0') "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        )
        if self.backend != "sqlite":
            self.connect().commit()
        else:
            self.connect().commit()
        log.info("Schéma initialisé (backend=%s)", self.backend)

    def schema_version(self) -> str | None:
        try:
            return self.scalar("SELECT value FROM schema_meta WHERE key = 'schema_version'")
        except Exception:
            return None

    def table_names(self) -> list[str]:
        if self.backend == "sqlite":
            rows = self.query("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
        else:  # pragma: no cover
            rows = self.query(
                "SELECT table_name AS name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        return [r["name"] for r in rows]


def _split_sql(script: str) -> list[str]:
    """Découpe un script SQL en instructions (suffisant pour nos fichiers)."""
    statements: list[str] = []
    buffer: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    if buffer:
        statements.append("\n".join(buffer))
    return statements
