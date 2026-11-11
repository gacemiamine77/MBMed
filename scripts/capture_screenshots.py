#!/usr/bin/env python3
"""Régénère les captures d'écran de la documentation (Qt hors écran).

Usage :  python scripts/capture_screenshots.py [--width 1600] [--height 980]
Nécessite un environnement Qt fonctionnel (sous Linux : libxkbcommon, libegl…).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PAGE_NAMES = [
    "01_tableau", "02_carte", "03_catalogue", "04_recherche",
    "05_analyse", "06_telechargements", "07_historique",
    "08_rapports", "09_parametres",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=980)
    parser.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    args = parser.parse_args()

    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import bootstrap
    from app.gui.main_window import MainWindow

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ctx = bootstrap()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(ctx)
    window.resize(args.width, args.height)
    window.show()
    app.processEvents()

    for index, name in enumerate(PAGE_NAMES):
        window.nav_list.setCurrentRow(index)
        app.processEvents()
        app.processEvents()
        target = out / f"{name}.png"
        window.stack.widget(index).grab().save(str(target))
        print(f"  ✓ {target.relative_to(ROOT)}")
    window.close()
    ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
