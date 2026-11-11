"""Tests de l'interface (rendu hors écran avec Qt offscreen).

Ces tests vérifient que chaque page se construit et se rafraîchit sans erreur
et que les éléments clés du cahier des charges sont présents.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


@pytest.fixture()
def window(context, qapp):
    from app.database.seed import load_seed_data
    from app.gui.main_window import MainWindow

    load_seed_data(context.repo)
    win = MainWindow(context)
    win.resize(1500, 950)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_all_pages_built(window):
    from app.gui.main_window import PAGES

    assert window.stack.count() == len(PAGES) == 9
    titles = [window.stack.widget(i).page_title for i in range(window.stack.count())]
    assert "Tableau de bord" in titles
    assert "Carte interactive" in titles
    assert "Catalogue des données" in titles


def test_navigation_refreshes_every_page(window, qapp):
    for i in range(window.stack.count()):
        window.nav_list.setCurrentRow(i)
        qapp.processEvents()
        assert window.stack.currentIndex() == i


def test_dashboard_counters_reflect_database(window, context):
    from app.database.seed import SEED_DATASETS

    page = window.pages["dashboard"]
    assert page.tile_total.value_label.text() == str(len(SEED_DATASETS))
    # aucune veille exécutée -> zéro affiché, pas de valeur simulée
    assert page.tile_new.value_label.text() == "0"
    assert page.tile_updated.value_label.text() == "0"
    assert page.tile_sources.value_label.text() == "0 / 0"


def test_honesty_banner_present(window):
    page = window.pages["dashboard"]
    text = page.banner.text()
    assert "Phase 1" in text
    assert "démonstration" in text.lower() or "démonstration" in text


def test_catalogue_lists_seed_and_detail(window, qapp):
    from app.database.seed import SEED_DATASETS

    page = window.pages["catalogue"]
    assert page.table.rowCount() == len(SEED_DATASETS)
    page.table.selectRow(0)
    qapp.processEvents()
    assert page.raw_view.toPlainText()
    assert "uid" in page.raw_view.toPlainText()


def test_catalogue_filters(window, qapp):
    page = window.pages["catalogue"]
    total = page.table.rowCount()
    page.search.setText("GEBCO")
    qapp.processEvents()
    page.refresh()
    assert 0 < page.table.rowCount() < total
    page.search.clear()
    page.algeria_only.setChecked(True)
    page.refresh()
    assert page.table.rowCount() <= total
    page.algeria_only.setChecked(False)
    page.refresh()


def test_search_page_filters_and_counts(window):
    page = window.pages["recherche"]
    page.refresh()
    assert "produit(s)" in page.summary.text()
    page.chk_gt.setChecked(True)
    page.refresh()
    assert page.table.rowCount() > 0
    page.chk_gt.setChecked(False)
    page.refresh()


def test_map_page_renders_empties(window, qapp):
    page = window.pages["carte"]
    qapp.processEvents()
    assert page.view.scene_.items(), "la carte doit contenir le fond et les emprises"
    assert "emprise(s)" in page.filter_summary.text()
    assert page.class_combo.count() == 6  # « Toutes » + A→E


def test_map_mercator_orientation():
    from app.gui.pages.map import MediterraneanView

    _, y_north = MediterraneanView.mercator(0, 45)
    _, y_south = MediterraneanView.mercator(0, 30)
    assert y_north < y_south  # le nord doit être plus haut à l'écran


def test_analyze_page_preselects_and_compares(window, qapp):
    page = window.pages["analyse"]
    qapp.processEvents()
    assert page.list.count() > 0
    assert len(page._selected()) >= 1
    assert page.table.rowCount() == len(page._criteres()) if hasattr(page, "_criteres") else True
    assert page.table.columnCount() >= 2


def test_downloads_page_tree(window):
    page = window.pages["telechargements"]
    assert page.table.rowCount() > 0
    assert "sans accès automatique" in page.manual_info.text()
    # au moins un produit sans accès automatique doit être marqué « manuel requis »
    statuses = [
        page.table.item(r, 5).text()
        for r in range(page.table.rowCount())
        if page.table.item(r, 5) is not None
    ]
    assert "manuel requis" in statuses


def test_history_and_reports_pages(window):
    history = window.pages["historique"]
    history.refresh()
    assert history.changes_table.rowCount() >= 1
    assert history.product_combo.count() > 0

    reports = window.pages["rapports"]
    reports._preview()
    assert "Rapport d'inventaire" in reports.browser.toHtml()


def test_report_html_export(tmp_path, context):
    from app.database.seed import load_seed_data
    from app.reports.inventory import build_inventory_report, render_inventory_html

    load_seed_data(context.repo)
    rows = context.repo.list_dataset_rows()
    report = build_inventory_report(rows, context.repo.dashboard_stats(), "Test")
    html = render_inventory_html(report, standalone=True)
    assert html.startswith("<!DOCTYPE html>")
    assert "Limites et réserves scientifiques" in html
    for row in rows:
        assert row["name"].replace("&", "&amp;") in html


def test_settings_pages(window):
    page = window.pages["parametres"]
    assert page.sources_table.rowCount() == 8
    page._save_schedule()
    assert context_scheduler_value(window) is not None


def context_scheduler_value(window):
    return window.ctx.settings.scheduler.weekly_day


def test_navigation_signal_from_dashboard(window, qapp):
    page = window.pages["dashboard"]
    page.navigate.emit("catalogue", None)
    qapp.processEvents()
    from app.gui.main_window import PAGES

    keys = [k for k, _, _ in PAGES]
    assert window.stack.currentIndex() == keys.index("catalogue")
