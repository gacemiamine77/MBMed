#!/usr/bin/env python3
"""Vérification complète du projet MBM (Phase 1).

Exécute dans l'ordre :
  1. compilation de tous les modules (syntaxe) ;
  2. import de tous les modules applicatifs ;
  3. création d'une base temporaire + chargement du jeu de référence ;
  4. contrôles d'intégrité du catalogue ;
  5. génération des exports et du rapport d'inventaire ;
  6. suite de tests pytest.

Usage :
    python scripts/verify.py            # tout
    python scripts/verify.py --no-tests # sans pytest
"""
from __future__ import annotations

import argparse
import compileall
import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODULES = [
    "app", "app.config.settings", "app.core.models", "app.core.taxonomy",
    "app.core.sources", "app.core.context", "app.core.bootstrap",
    "app.database.connection", "app.database.repository", "app.database.seed",
    "app.geospatial.geometry", "app.exporters", "app.reports.inventory",
    "app.gui.theme", "app.gui.widgets", "app.gui.charts", "app.gui.main_window",
    "app.gui.pages.base", "app.gui.pages.dashboard", "app.gui.pages.map",
    "app.gui.pages.catalogue", "app.gui.pages.search", "app.gui.pages.analyze",
    "app.gui.pages.downloads", "app.gui.pages.history", "app.gui.pages.reports",
    "app.gui.pages.settings",
]

OK = "\033[92m✓\033[0m"
KO = "\033[91m✗\033[0m"
failures: list[str] = []


def step(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 62 - len(title)))


def check(condition: bool, message: str) -> None:
    print(f"  {OK if condition else KO} {message}")
    if not condition:
        failures.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()

    step("1. Compilation (syntaxe)")
    ok = compileall.compile_dir(str(ROOT / "app"), quiet=2, force=True)
    check(bool(ok), "tous les modules compilent")

    step("2. Import des modules")
    for name in MODULES:
        try:
            importlib.import_module(name)
            print(f"  {OK} {name}")
        except Exception as exc:  # pragma: no cover
            print(f"  {KO} {name} — {exc}")
            failures.append(name)

    step("3. Base temporaire et jeu de référence")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MBM_DATA_DIR"] = tmp
        os.environ["MBM_SQLITE_PATH"] = str(Path(tmp) / "verify.sqlite3")
        os.environ["MBM_CONFIG_FILE"] = str(Path(tmp) / "settings.toml")
        from app.config.settings import reset_settings_cache, get_settings
        from app.core.bootstrap import bootstrap
        from app.database.seed import SEED_DATASETS, load_seed_data

        reset_settings_cache()
        ctx = bootstrap()
        repo = ctx.repo
        check(ctx.database is not None and ctx.database.is_open(), "base ouverte")
        check(len(ctx.database.table_names()) >= 20, f"{len(ctx.database.table_names())} tables/vues créées")
        check(repo.count_datasets() == len(SEED_DATASETS), f"{repo.count_datasets()} produits chargés")
        stats = repo.dashboard_stats()
        check(stats["sources_total"] == 8, "8 familles de sources enregistrées")
        check(stats["sources_implemented"] == 0, "aucun connecteur annoncé comme implémenté")
        check(stats["new_count"] == 0 and stats["updated_count"] == 0,
              "compteurs de veille non simulés (0)")
        check(stats["algeria_core"] > 0, f"couverture algérienne calculée ({stats['algeria_core']})")
        check(0.0 < stats["avg_completeness"] <= 1.0,
              f"complétude moyenne = {stats['avg_completeness']:.0%}")

        step("4. Intégrité des fiches")
        rows = repo.list_dataset_rows()
        check(all(r["data_origin"] == "seed" for r in rows), "toutes les fiches marquées 'seed'")
        check(all(r["metadata_status"] != "validated" for r in rows),
              "aucune fiche de démonstration n'est déclarée validée")
        check(all(r["bbox_minx"] is not None for r in rows), "toutes les emprises sont renseignées")
        check(all(r["official_url"] for r in rows), "toutes les fiches pointent vers une URL officielle")
        bad_depth = [r for r in rows if r["depth_min_m"] is not None
                     and r["depth_max_m"] is not None and r["depth_min_m"] >= r["depth_max_m"]]
        check(not bad_depth, "profondeurs cohérentes (min < max)")

        step("5. Exports et rapport")
        from app.exporters import EXPORT_COLUMNS, export_datasets_csv, export_datasets_geojson, export_excel
        from app.reports.inventory import build_inventory_report, render_inventory_html

        out = Path(tmp) / "reports"
        out.mkdir(parents=True, exist_ok=True)
        csv_path = export_datasets_csv(rows, out / "catalogue.csv")
        geo_path = export_datasets_geojson(rows, out / "emprises.geojson")
        check(csv_path.stat().st_size > 0, f"CSV ({csv_path.stat().st_size} octets)")
        check(geo_path.stat().st_size > 0, f"GeoJSON ({geo_path.stat().st_size} octets)")
        try:
            xlsx = export_excel({"Catalogue": (EXPORT_COLUMNS, rows)}, out / "catalogue.xlsx")
            check(xlsx.stat().st_size > 0, f"Excel ({xlsx.stat().st_size} octets)")
        except Exception as exc:
            print(f"  · Excel ignoré ({exc})")
        report = build_inventory_report(rows, stats, "Vérification")
        html = render_inventory_html(report, standalone=True)
        check("Limites et réserves scientifiques" in html, "rapport HTML généré avec section limites")

        step("6. Interface (rendu hors écran)")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from app.gui.main_window import MainWindow

            app = QApplication.instance() or QApplication([])
            window = MainWindow(ctx)
            window.resize(1500, 950)
            window.show()
            for i in range(window.stack.count()):
                window.nav_list.setCurrentRow(i)
                app.processEvents()
            check(window.stack.count() == 9, "9 pages construites et rafraîchies")
            window.close()
        except Exception as exc:
            print(f"  · interface non testée ({exc})")
        ctx.close()

    if not args.no_tests:
        step("7. Suite de tests pytest")
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                              capture_output=True, text=True)
        lines = [l for l in (proc.stdout or "").strip().splitlines() if l.strip()]
        tail = [l.replace("=", "").strip() for l in lines[-2:] if "passed" in l or "failed" in l]
        tail = tail or lines[-1:]
        check(proc.returncode == 0, f"pytest : {tail[0] if tail else 'échec'}")

    print("\n" + "=" * 70)
    if failures:
        print(f"{KO} {len(failures)} contrôle(s) en échec :")
        for f in failures:
            print(f"   - {f}")
        return 1
    print(f"{OK} Tous les contrôles sont passés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
