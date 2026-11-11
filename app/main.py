"""Point d'entrée de Mediterranean Bathymetry Monitor.

Usage :
    python -m app.main                 # lance l'interface
    python -m app.main --no-seed       # démarre sans charger le jeu de référence
    python -m app.main --db PATH       # base SQLite alternative
    python -m app.main --check         # diagnostic de l'environnement (sans GUI)

L'application démarre en mode SQLite local par défaut : aucune installation
serveur n'est nécessaire pour la Phase 1.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Permet l'exécution directe : python app/main.py
if __package__ in (None, ""):  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import APP_NAME, APP_VERSION, PHASE, get_settings  # noqa: E402
from app.core.bootstrap import bootstrap  # noqa: E402


def configure_logging(log_dir: Path | None = None, verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_dir / "mbm.log", encoding="utf-8"))
        except OSError:
            pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s",
        handlers=handlers,
        force=True,
    )
    # Matplotlib et PIL sont bavards en DEBUG
    for noisy in ("matplotlib", "PIL", "fontTools"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_checks() -> int:
    """Diagnostic rapide de l'environnement (utilisé par --check et les tests)."""
    from app.core.sources import SOURCES
    from app.geospatial.geometry import GEOSPATIAL_CAPABILITIES

    settings = get_settings()
    print(f"{APP_NAME} — {APP_VERSION} ({PHASE})")
    print(f"Python      : {sys.version.split()[0]}")
    for module, purpose in (
        ("PySide6", "interface graphique"),
        ("sqlite3", "base locale"),
        ("numpy", "calcul numérique"),
        ("matplotlib", "graphiques"),
        ("shapely", "géométries"),
        ("pyproj", "projections"),
        ("geopandas", "analyse géospatiale"),
        ("rasterio", "raster (GDAL)"),
        ("xarray", "NetCDF"),
        ("requests", "connecteurs"),
        ("apscheduler", "planification"),
        ("openpyxl", "export Excel"),
        ("reportlab", "export PDF (phase 7)"),
    ):
        try:
            __import__(module)
            print(f"  ✓ {module:<12} {purpose}")
        except ImportError:
            print(f"  · {module:<12} {purpose} — non installé")

    ctx = bootstrap(settings=settings)
    repo = ctx.repo
    stats = repo.dashboard_stats()
    print(f"\nBase        : {ctx.db_info()}")
    print(f"Schéma      : {ctx.database.schema_version()}")
    print(f"Sources     : {stats['sources_total']} familles, "
          f"{stats['sources_implemented']} connecteur(s) implémenté(s)")
    print(f"Catalogue   : {stats['total']} produit(s)")
    print(f"Littoral DZ : {stats['algeria_core']} produit(s) en zone 0–100 m")
    print(f"Géospatial  : {GEOSPATIAL_CAPABILITIES}")
    ctx.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mediterranean Bathymetry Monitor")
    parser.add_argument("--no-seed", action="store_true", help="ne pas charger le jeu de référence")
    parser.add_argument("--db", help="chemin d'une base SQLite alternative")
    parser.add_argument("--check", action="store_true", help="diagnostic de l'environnement (sans interface)")
    parser.add_argument("--verbose", action="store_true", help="journalisation détaillée")
    args = parser.parse_args(argv)

    settings = get_settings(reload=True)
    if args.db:
        settings.database.backend = "sqlite"
        settings.database.sqlite_path = str(Path(args.db).expanduser())
    configure_logging(settings.log_dir(), args.verbose)

    if args.check:
        return run_checks()

    # Qt en mode « offscreen » si demandé (tests / captures)
    if os.environ.get("MBM_QT_OFFSCREEN"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    ctx = bootstrap(settings=settings, with_seed=not args.no_seed)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover
        print("PySide6 est requis pour l'interface : pip install PySide6-Essentials", file=sys.stderr)
        print(f"Détail : {exc}", file=sys.stderr)
        return 2

    from app.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("MBM")

    window = MainWindow(ctx)
    window.show()
    code = app.exec()
    ctx.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
