"""Page 9 — Paramètres des sources et de la planification (sections 3 et 4).

Trois onglets :
  * Sources : activation/désactivation, état d'implémentation réel, limites connues ;
  * Planification : paramètres de la veille hebdomadaire (persistés) ;
  * Données et stockage : chemins, backend de base, diagnostics du schéma.

Les paramètres de planification sont enregistrés mais APScheduler n'est démarré
qu'à partir de la Phase 7 : l'interface l'indique clairement.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from app.config.settings import APP_VERSION, PHASE
from app.core.sources import SOURCES
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS
from app.gui.widgets import (
    Badge, Card, CardLayout, DataTable, SectionHeader, StatusDot, hline, kv_row, label,
    status_color,
)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class SettingsPage(BasePage):
    def build_content(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_sources_tab(), "Sources")
        tabs.addTab(self._build_schedule_tab(), "Planification")
        tabs.addTab(self._build_storage_tab(), "Données et stockage")
        tabs.addTab(self._build_about_tab(), "À propos")
        self.content.addWidget(tabs, 1)

    # ==================================================================
    # Onglet Sources
    # ==================================================================
    def _build_sources_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        lay.addWidget(label(
            "Huit familles de sources sont prévues par le cahier des charges. "
            "Chaque ligne indique la phase de livraison de son connecteur ; une source "
            "« planifiée » n'est pas interrogée par le moteur de veille et n'apparaît pas "
            "comme opérationnelle dans le tableau de bord.",
            "Dim", word_wrap=True))

        self.sources_table = DataTable(
            ["Source", "Catégorie", "Accès privilégié", "Connecteur", "Active"],
            stretch_column=0)
        from PySide6.QtWidgets import QHeaderView

        table_header = self.sources_table.horizontalHeader()
        table_header.setSectionResizeMode(QHeaderView.Fixed)
        for col, width in {1: 236, 2: 200, 3: 124, 4: 66}.items():
            self.sources_table.setColumnWidth(col, width)
        table_header.setSectionResizeMode(0, QHeaderView.Stretch)
        table_header.setStretchLastSection(False)
        self.sources_table.setMinimumHeight(232)
        lay.addWidget(self.sources_table)

        self.detail_browser = QTextBrowser()
        self.detail_browser.setMinimumHeight(150)
        self.sources_table.itemSelectionChanged.connect(self._show_source_detail)
        lay.addWidget(self.detail_browser)

        actions = QHBoxLayout()
        toggle = QPushButton("Activer / désactiver la source sélectionnée")
        toggle.setObjectName("Ghost")
        toggle.clicked.connect(self._toggle_selected)
        actions.addWidget(toggle)
        actions.addStretch(1)
        lay.addLayout(actions)

        self._fill_sources()
        return w

    def _fill_sources(self) -> None:
        rows, colors, data = [], [], []
        for info in self.repo.connector_infos():
            src = SOURCES[info.source_id]
            access = ", ".join(_access_label(a) for a in src.access_types)
            connector = (f"phase {info.implemented_phase}"
                         if not info.implemented else "actif")
            rows.append([info.label, info.category, access, connector,
                         "oui" if info.enabled else "non"])
            colors.append(COLORS["success"] if info.implemented else COLORS["text_muted"])
            data.append(info.source_id)
        self.sources_table.set_rows(rows, colors, data, sortable_numbers=False)
        if rows:
            self.sources_table.selectRow(0)

    def _show_source_detail(self) -> None:
        sid = self.sources_table.selected_data()
        if not sid or sid not in SOURCES:
            return
        src = SOURCES[sid]
        e = json.dumps(list(src.known_limits), ensure_ascii=False)
        access = "".join(f"<li>{_access_label(a)}</li>" for a in src.access_types)
        limits = "".join(f"<li>{l}</li>" for l in src.known_limits) or "<li>—</li>"
        licenses = ", ".join(src.licenses)
        html = (
            "<html><body style='font-family:Segoe UI,sans-serif;font-size:11.5px;color:#e6edf6'>"
            f"<h3 style='margin-top:0'>{src.label}</h3>"
            f"<p style='color:#93a4bb'>{src.description}</p>"
            f"<p><b>Institutions :</b> {src.institutions}<br>"
            f"<b>Portail :</b> {src.homepage}<br>"
            f"<b>Documentation :</b> {src.documentation}<br>"
            f"<b>Produits suivis :</b> {', '.join(src.products)}<br>"
            f"<b>Classes attendues :</b> {', '.join(src.expected_classes)}<br>"
            f"<b>Licences typiques :</b> {licenses}<br>"
            f"<b>Identifiants requis :</b> {'oui' if src.requires_credentials else 'non'}<br>"
            f"<b>Fiabilité estimée :</b> {src.reliability}</p>"
            f"<p><b>Modes d'accès privilégiés :</b></p><ul>{access}</ul>"
            f"<p><b>Limites connues :</b></p><ul>{limits}</ul>"
            "</body></html>"
        )
        self.detail_browser.setHtml(html)

    def _toggle_selected(self) -> None:
        sid = self.sources_table.selected_data()
        if not sid:
            return
        enabled = self.repo.source_enabled(sid)
        self.repo.set_source_enabled(sid, not enabled)
        self.repo.audit("source_toggle", entity="source", entity_id=sid,
                        details={"enabled": not enabled}, actor="user")
        self._fill_sources()
        self.notify(f"{'Activée' if not enabled else 'Désactivée'} : {SOURCES[sid].label}")

    # ==================================================================
    # Onglet Planification
    # ==================================================================
    def _build_schedule_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        lay.addWidget(label(
            "La veille est hebdomadaire et configurable. Les paramètres sont enregistrés "
            "dans config/settings.toml ; la planification effective (APScheduler) est activée "
            "en Phase 7 avec le moteur de veille.",
            "Dim", word_wrap=True))

        card = Card()
        cl = CardLayout(card, spacing=10)
        cl.addWidget(SectionHeader("Fréquence de la veille", "Planification hebdomadaire"))
        form = QFormLayout()
        form.setSpacing(8)
        self.chk_enabled = QCheckBox("Veille automatique activée")
        form.addRow("", self.chk_enabled)
        self.day_combo = QComboBox()
        for d, fr in zip(DAYS, DAYS_FR):
            self.day_combo.addItem(fr, d)
        form.addRow("Jour", self.day_combo)
        self.hour_spin = QSpinBox(); self.hour_spin.setRange(0, 23); self.hour_spin.setSuffix(" h")
        form.addRow("Heure", self.hour_spin)
        self.minute_spin = QSpinBox(); self.minute_spin.setRange(0, 59); self.minute_spin.setSuffix(" min")
        form.addRow("Minute", self.minute_spin)
        self.tz_label = QLabel()
        form.addRow("Fuseau horaire", self.tz_label)
        self.timeout_spin = QSpinBox(); self.timeout_spin.setRange(5, 300); self.timeout_spin.setSuffix(" s")
        form.addRow("Délai d'expiration réseau", self.timeout_spin)
        self.retries_spin = QSpinBox(); self.retries_spin.setRange(0, 10)
        form.addRow("Tentatives par requête", self.retries_spin)
        cl.addLayout(form)

        save = QPushButton("Enregistrer la planification")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_schedule)
        cl.addWidget(save, 0, Qt.AlignLeft)
        lay.addWidget(card)

        layout_card = Card()
        ll = CardLayout(layout_card, spacing=6)
        ll.addWidget(SectionHeader("Déroulé prévu d'une exécution", "Moteur de veille (Phase 7)"))
        steps = [
            "1. Interrogation séquentielle des connecteurs activés (API/STAC/OGC).",
            "2. Normalisation des métadonnées et calcul de l'empreinte de chaque produit.",
            "3. Comparaison avec l'état en base : nouveau / mis à jour / inchangé / retiré.",
            "4. Déduplication croisée par clé d'identité (nom + producteur + version).",
            "5. Enregistrement des versions, du journal de changements et de la date de vérification.",
            "6. Génération du rapport hebdomadaire (même sans nouveauté) en PDF, HTML et Excel.",
        ]
        for s in steps:
            ll.addWidget(label(s, "Dim", word_wrap=True))
        lay.addWidget(layout_card)
        lay.addStretch(1)

        self._load_schedule()
        return w

    def _load_schedule(self) -> None:
        sch = self.ctx.settings.scheduler
        self.chk_enabled.setChecked(sch.enabled)
        idx = DAYS.index(sch.weekly_day) if sch.weekly_day in DAYS else 0
        self.day_combo.setCurrentIndex(idx)
        self.hour_spin.setValue(sch.weekly_hour)
        self.minute_spin.setValue(sch.weekly_minute)
        self.tz_label.setText(sch.timezone)
        self.timeout_spin.setValue(sch.request_timeout)
        self.retries_spin.setValue(sch.request_retries)

    def _save_schedule(self) -> None:
        sch = self.ctx.settings.scheduler
        sch.enabled = self.chk_enabled.isChecked()
        sch.weekly_day = self.day_combo.currentData()
        sch.weekly_hour = self.hour_spin.value()
        sch.weekly_minute = self.minute_spin.value()
        sch.request_timeout = self.timeout_spin.value()
        sch.request_retries = self.retries_spin.value()
        try:
            self.ctx.settings.save()
            self.repo.audit("settings_saved", entity="scheduler",
                            details={"day": sch.weekly_day, "hour": sch.weekly_hour}, actor="user")
            self.notify(f"Planification enregistrée : {DAYS_FR[DAYS.index(sch.weekly_day)]} "
                        f"à {sch.weekly_hour:02d}:{sch.weekly_minute:02d} ({sch.timezone})")
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))

    # ==================================================================
    # Onglet Stockage
    # ==================================================================
    def _build_storage_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        card = Card()
        cl = CardLayout(card, spacing=6)
        cl.addWidget(SectionHeader("Base de données", "SQLite pour le démarrage, PostgreSQL/PostGIS en production"))
        cl.addWidget(kv_row("Backend actif", self.ctx.settings.database.backend))
        cl.addWidget(kv_row("Chemin SQLite", str(self.ctx.settings.database.resolved_sqlite_path()), mono=True))
        cl.addWidget(kv_row("Version du schéma", str(self.ctx.database.schema_version() if self.ctx.database else "—")))
        cl.addWidget(kv_row("Tables et vues", str(len(self.ctx.database.table_names()) if self.ctx.database else 0)))
        cl.addWidget(kv_row("Jeux catalogués", str(self.repo.count_datasets())))
        for var in ("MBM_DB_HOST", "MBM_DB_PORT", "MBM_DB_NAME", "MBM_DB_USER"):
            import os

            value = os.environ.get(var)
            cl.addWidget(kv_row(var, value if value else "non défini",
                                value_color=None if value else COLORS["text_dim"]))
        cl.addWidget(label(
            "Pour PostgreSQL : exportez MBM_DB_BACKEND=postgresql et les variables MBM_DB_*. "
            "Le schéma PostGIS (colonnes geometry, index GiST, surfaces projetées) est appliqué "
            "automatiquement au premier démarrage.",
            "Dim", word_wrap=True))
        lay.addWidget(card)

        paths = Card()
        pl = CardLayout(paths, spacing=6)
        pl.addWidget(SectionHeader("Arborescence des données", "Créée automatiquement"))
        for sub, desc in (
            ("downloads", "produits téléchargés (source / produit / version)"),
            ("catalogue", "instantanés JSON des métadonnées"),
            ("raster", "grilles converties"),
            ("reports", "rapports exportés"),
            ("cache", "réponses API temporaires"),
            ("logs", "journaux d'exécution"),
        ):
            pl.addWidget(kv_row(sub, f"{self.ctx.settings.data_root / sub} — {desc}", mono=False))
        open_btn = QPushButton("Ouvrir le dossier de données")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.ctx.settings.data_root))))
        pl.addWidget(open_btn, 0, Qt.AlignLeft)
        lay.addWidget(paths)
        lay.addStretch(1)
        return w

    # ==================================================================
    # Onglet À propos
    # ==================================================================
    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        browser = QTextBrowser()
        browser.setHtml(
            "<html><body style='font-family:Segoe UI,sans-serif;font-size:12px;color:#e6edf6'>"
            "<h2 style='margin-top:0'>Mediterranean Bathymetry Monitor</h2>"
            f"<p style='color:#93a4bb'>Version {APP_VERSION} — {PHASE}</p>"
            "<h3>Objectif scientifique</h3>"
            "<p>Assurer une veille permanente des données bathymétriques ouvertes de Méditerranée, "
            "en priorité sur le bassin algérien et la tranche 0–100 m, afin de constituer un "
            "catalogue utilisable pour développer et valider des modèles de Satellite-Derived "
            "Bathymetry (SDB).</p>"
            "<h3>Principes de conception</h3>"
            "<ul>"
            "<li>Séparation stricte : interface, sources, connecteurs, base, géospatial, "
            "évaluation, téléchargement, rapports, planification.</li>"
            "<li>Hiérarchie des sources : API officielles, catalogues STAC, services OGC, "
            "téléchargements documentés ; le scraping HTML reste un dernier recours signalé.</li>"
            "<li>Aucune donnée inventée : un champ inconnu vaut « non documenté ».</li>"
            "<li>Le pas de grille n'est jamais présenté comme la résolution effective.</li>"
            "<li>Un produit interpolé n'est jamais une vérité terrain.</li>"
            "<li>Les modules non encore livrés apparaissent comme « planifiés », jamais comme "
            "opérationnels.</li>"
            "</ul>"
            "<h3>Pile technique</h3>"
            "<p>Python, PySide6, SQLite / PostgreSQL+PostGIS, Rasterio/GDAL, GeoPandas, Shapely, "
            "Xarray, pyproj, Matplotlib, APScheduler, Requests.</p>"
            "<h3>Licences des sources</h3>"
            "<p>Chaque fiche produit renvoie à la licence de sa source. L'utilisateur doit "
            "vérifier les conditions d'utilisation et les obligations d'attribution avant toute "
            "redistribution.</p>"
            "</body></html>"
        )
        lay.addWidget(browser, 1)
        return w


def _access_label(code: str) -> str:
    return {
        "api": "API", "stac": "STAC", "ogc_wms": "OGC WMS", "ogc_wcs": "OGC WCS",
        "subset": "sous-ensemble", "http_direct": "HTTP direct", "manual": "manuel",
        "restricted": "restreint", "html_scraping": "scraping HTML (dernier recours)",
    }.get(code, code)


def _status_fr(status: str) -> str:
    return {"ok": "OK", "partial": "partiel", "error": "erreur",
            "not_run": "jamais exécuté", "disabled": "désactivé"}.get(status, status)
