"""Initialisation applicative : base, schéma, sources, jeu de référence.

Appelé par ``main.py`` et par les tests : centralise la séquence de démarrage
pour garantir un état de base cohérent et reproductible.
"""
from __future__ import annotations

import logging

from app.config.settings import Settings, get_settings
from app.core.context import AppContext
from app.database.seed import load_seed_data, seed_is_loaded

log = logging.getLogger(__name__)


def bootstrap(settings: Settings | None = None, with_seed: bool = True) -> AppContext:
    """Ouvre la base, crée le schéma, synchronise les sources, charge le seed."""
    settings = settings or get_settings()
    settings.ensure_directories()
    ctx = AppContext(settings=settings)
    ctx.open_database(initialize=True)
    repo = ctx.repo
    repo.sync_sources()
    if with_seed and not seed_is_loaded(repo):
        counts = load_seed_data(repo)
        log.info("Jeu de référence chargé: %s", counts)
    return ctx


def ensure_single_instance_marker(ctx: AppContext) -> None:
    """Écrit un fichier de session (version applicative + schéma) pour diagnostic."""
    marker = ctx.settings.data_root / "session.txt"
    try:
        marker.write_text(
            f"MBM {ctx.settings.database.backend} | schema={ctx.database.schema_version() if ctx.database else 'n/a'}\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover
        log.debug("Impossible d'écrire le marqueur de session")
