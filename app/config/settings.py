"""
Configuration centralisée de Mediterranean Bathymetry Monitor (MBM).

Toute la configuration est lue depuis (par ordre de priorité) :
    1. les variables d'environnement préfixées par ``MBM_`` ;
    2. le fichier ``config/settings.toml`` (créé au premier lancement) ;
    3. les valeurs par défaut définies ici.

Aucune valeur secrète (mot de passe, clé API) n'est écrite en dur dans le code.
Les identifiants PostgreSQL sont lus dans l'environnement :
    MBM_DB_HOST, MBM_DB_PORT, MBM_DB_NAME, MBM_DB_USER, MBM_DB_PASSWORD
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Arborescence de l'application
# ---------------------------------------------------------------------------
APP_NAME = "Mediterranean Bathymetry Monitor"
APP_SHORT = "MBM"
APP_VERSION = "0.1.0"
PHASE = "Phase 1 — Architecture, base de données et interface initiale"

PACKAGE_ROOT = Path(__file__).resolve().parent          # .../app/config
APP_ROOT = PACKAGE_ROOT.parent                          # .../app
PROJECT_ROOT = APP_ROOT.parent                          # .../mbm

CONFIG_DIR = PROJECT_ROOT / "config"


def config_file() -> Path:
    """Fichier de configuration effectif.

    Surchargeable par ``MBM_CONFIG_FILE`` (utile pour les tests et les
    installations multi-utilisateurs où le dépôt n'est pas inscriptible).
    """
    override = os.environ.get("MBM_CONFIG_FILE")
    if override:
        return Path(override).expanduser().resolve()
    return CONFIG_DIR / "settings.toml"

# Racine des données : surchargeable par MBM_DATA_DIR
DEFAULT_DATA_DIR = Path(os.environ.get("MBM_DATA_DIR", Path.home() / "MBM_Data"))

# Emprise de référence (Méditerranée + marge)
MEDITERRANEAN_BBOX = (-6.5, 30.0, 36.5, 46.5)           # xmin, ymin, xmax, ymax
ALGERIA_COASTAL_BBOX = (-2.5, 35.0, 9.5, 37.6)          # façade maritime algérienne
ALGERIA_BBOX = (-8.7, 18.9, 12.0, 37.6)

# Classes de profondeur de référence du projet (en mètres positifs)
DEPTH_CLASSES = (
    ("0-20 m", 0.0, 20.0),
    ("20-50 m", 20.0, 50.0),
    ("50-100 m", 50.0, 100.0),
    ("100-200 m", 100.0, 200.0),
    ("> 200 m", 200.0, 12000.0),
)
SDB_DEPTH_WINDOW = (0.0, 100.0)

# CRS par défaut pour les calculs de surface (Méditerranée centrée sur 15°E)
DEFAULT_AREA_CRS = "+proj=laea +lat_0=38 +lon_0=15 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "oui"}


@dataclass(slots=True)
class DatabaseSettings:
    """Paramètres de connexion. ``sqlite`` par défaut, ``postgresql`` en production."""
    backend: str = "sqlite"
    sqlite_path: str = ""
    host: str = "localhost"
    port: int = 5432
    name: str = "mbm"
    user: str = "mbm"
    password: str = ""
    srid: int = 4326

    def resolved_sqlite_path(self) -> Path:
        return Path(self.sqlite_path).expanduser().resolve()

    def postgres_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password}"
        )


@dataclass(slots=True)
class SchedulerSettings:
    """Planification de la veille (APScheduler)."""
    enabled: bool = True
    weekly_day: str = "monday"      # day_of_week APScheduler
    weekly_hour: int = 6
    weekly_minute: int = 0
    timezone: str = "Africa/Algiers"
    run_on_startup: bool = False
    request_timeout: int = 45
    request_retries: int = 3
    user_agent: str = "MBM/0.1 (scientific bathymetry watch; contact=lab@example.org)"


@dataclass(slots=True)
class DisplaySettings:
    language: str = "fr"
    theme: str = "dark"
    map_tile_url: str = ""          # vide => fond vectoriel local (aucun accès réseau)
    map_use_network: bool = False
    page_size: int = 100


@dataclass(slots=True)
class Settings:
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    data_dir: str = ""
    sources_enabled: dict[str, bool] = field(default_factory=dict)
    research_bbox: tuple[float, float, float, float] = MEDITERRANEAN_BBOX

    # -- résolution ---------------------------------------------------------
    @property
    def data_root(self) -> Path:
        return Path(self.data_dir).expanduser().resolve()

    def ensure_directories(self) -> None:
        for sub in ("catalogue", "downloads", "reports", "raster", "logs", "cache"):
            (self.data_root / sub).mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def download_dir(self) -> Path:
        return self.data_root / "downloads"

    def report_dir(self) -> Path:
        return self.data_root / "reports"

    def log_dir(self) -> Path:
        return self.data_root / "logs"

    def cache_dir(self) -> Path:
        return self.data_root / "cache"

    # -- persistance --------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self) -> None:
        target = config_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_to_toml(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        path = config_file()
        if path.exists():
            try:
                raw = tomllib.loads(path.read_text(encoding="utf-8"))
                settings = cls._from_dict(raw)
            except Exception:  # fichier corrompu -> on repart des défauts
                settings = cls()
        return settings._apply_env()

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> "Settings":
        db = DatabaseSettings(**(raw.get("database") or {}))
        sch = SchedulerSettings(**(raw.get("scheduler") or {}))
        disp = DisplaySettings(**(raw.get("display") or {}))
        bbox = tuple(raw.get("research_bbox") or MEDITERRANEAN_BBOX)
        s = cls(
            database=db,
            scheduler=sch,
            display=disp,
            data_dir=raw.get("data_dir") or str(DEFAULT_DATA_DIR),
            sources_enabled=raw.get("sources_enabled") or {},
            research_bbox=bbox,  # type: ignore[arg-type]
        )
        return s

    def _apply_env(self) -> "Settings":
        env_data_dir = _env("MBM_DATA_DIR")
        if env_data_dir:
            self.data_dir = env_data_dir
        elif not self.data_dir:
            self.data_dir = str(DEFAULT_DATA_DIR)
        self.database.backend = _env("MBM_DB_BACKEND") or self.database.backend
        self.database.sqlite_path = _env("MBM_SQLITE_PATH") or self.database.sqlite_path \
            or str(self.data_root / "mbm.sqlite3")
        self.database.host = _env("MBM_DB_HOST") or self.database.host
        self.database.name = _env("MBM_DB_NAME") or self.database.name
        self.database.user = _env("MBM_DB_USER") or self.database.user
        self.database.password = _env("MBM_DB_PASSWORD") or self.database.password
        if _env("MBM_DB_PORT"):
            self.database.port = int(_env("MBM_DB_PORT"))  # type: ignore[arg-type]
        self.scheduler.enabled = _env_bool("MBM_SCHEDULER_ENABLED", self.scheduler.enabled)
        self.display.map_use_network = _env_bool("MBM_MAP_NETWORK", self.display.map_use_network)
        return self


def _to_toml(data: dict[str, Any]) -> str:
    """Sérialisation TOML minimale (types simples) sans dépendance externe."""
    lines: list[str] = []

    def fmt(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(fmt(v) for v in value) + "]"
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

    scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
    for key, value in scalars.items():
        lines.append(f"{key} = {fmt(value)}")
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append("")
            lines.append(f"[{key}]")
            for sub_key, sub_value in value.items():
                lines.append(f"{sub_key} = {fmt(sub_value)}")
    return "\n".join(lines) + "\n"


_SETTINGS: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Retourne l'instance globale de configuration (singleton paresseux)."""
    global _SETTINGS
    if _SETTINGS is None or reload:
        _SETTINGS = Settings.load()
        _SETTINGS.ensure_directories()
    return _SETTINGS


def reset_settings_cache() -> None:
    global _SETTINGS
    _SETTINGS = None
