# Mediterranean Bathymetry Monitor (MBM)

Application de bureau de **veille scientifique des données bathymétriques ouvertes de Méditerranée**, avec priorité au **bassin algérien**, aux **zones côtières** et à la **tranche 0–100 m**, en vue de développer et valider des modèles de **Satellite-Derived Bathymetry (SDB)**.

| | |
|---|---|
| Version | **0.1.0 — Phase 1 / 8** |
| État | Architecture, schéma de base de données et interface graphique opérationnels |
| Connecteurs réseau | **aucun actif** (Phases 2 à 4) — affiché comme tel dans l'interface |
| Tests | **98 tests** exécutés, tous verts |

---

## 1. Ce qui fonctionne réellement en Phase 1

| Domaine | État | Preuve |
|---|---|---|
| Schéma de base de données complet (16 tables + 6 vues) | ✅ opérationnel | `app/database/schema.sql`, `tests/test_database.py` |
| Backend SQLite local, backend PostgreSQL/PostGIS (schéma géométrique) | ✅ SQLite ; PostGIS prêt | `app/database/connection.py`, `schema_postgis_extra.sql` |
| Dépôt de données (CRUD, filtres, versions, journal, statistiques) | ✅ opérationnel | `app/database/repository.py` |
| Détection « nouveau / mis à jour / inchangé » par empreinte | ✅ opérationnel | `Repository.upsert_dataset`, tests |
| Interface 9 pages (thème sombre, graphiques Matplotlib) | ✅ opérationnelle | `app/gui/`, captures dans `docs/screenshots/` |
| Calculs géospatiaux (surfaces géodésiques, distance au littoral, recouvrement algérien) | ✅ opérationnel | `app/geospatial/geometry.py`, `tests/test_geospatial.py` |
| Carte interactive hors ligne (emprises, filtres, Mercator, zoom) | ✅ fonctionnelle (fond schématique) | `app/gui/pages/map.py` |
| Exports **CSV / JSON / GeoJSON / Excel** | ✅ opérationnels | `app/exporters.py`, `tests/test_seed_and_exports.py` |
| Rapport d'inventaire **HTML** (et classeur Excel) | ✅ opérationnel | `app/reports/inventory.py` |
| Diagnostic d'environnement (`--check`) | ✅ opérationnel | `python -m app.main --check` |
| Connecteurs EMODnet / GEBCO / Copernicus / ICESat-2 | ⛔ **non livrés** (Phases 2–3) | marqués « planifiée » dans l'UI |
| Moteur de veille planifiée (APScheduler) | ⛔ **non livré** (Phase 7) | paramètres enregistrables, exécution non branchée |
| Moteur de téléchargement réseau | ⛔ **non livré** (Phase 7) | schéma + arborescence + SHA-256 posés |
| Export PDF | ⛔ **non livré** (Phase 7) | dépendance `reportlab` listée |

> **Aucune fonction fictive n'est présentée comme opérationnelle.** Tout ce qui relève des phases suivantes apparaît dans l'interface comme « planifié », « Phase N » ou « manuel requis ».

---

## 2. Installation

### 2.1 Prérequis

* Python **3.12 ou 3.13** (testé sur 3.13.16)
* Linux, macOS ou Windows
* Sous Linux, Qt a besoin de bibliothèques système (`libxkbcommon`, `libegl1`, `libgl1`, polices). Sur Debian/Ubuntu :

```bash
sudo apt install -y libxkbcommon0 libegl1 libgl1 libfontconfig1 libdbus-1-3 \
                    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
                    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
```

### 2.2 Environnement Python

```bash
git clone <dépôt> mbm && cd mbm          # ou décompressez l'archive
python3 -m venv .venv
source .venv/bin/activate                # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` installe PySide6, Matplotlib, NumPy, Shapely, pyproj, GeoPandas, Rasterio (GDAL), Xarray, Requests, APScheduler, openpyxl, pytest.

### 2.3 Lancement

```bash
# interface graphique (base SQLite créée au premier lancement)
python -m app.main

# diagnostic complet de l'environnement, sans interface
python -m app.main --check

# base alternative / sans jeu de démonstration
python -m app.main --db /chemin/ma_base.sqlite3
python -m app.main --no-seed
```

Les données sont écrites par défaut dans `~/MBM_Data/` (base, téléchargements, rapports, journaux). Surchargez avec `MBM_DATA_DIR`.

### 2.4 Tests

```bash
pytest -q                       # 98 tests
pytest -q tests/test_gui.py     # interface hors écran (Qt offscreen)
QT_QPA_PLATFORM=offscreen pytest -q
```

---

## 3. Architecture

```
mbm/
├── app/
│   ├── main.py                  # point d'entrée CLI + GUI
│   ├── config/settings.py       # configuration typée (TOML + variables MBM_*)
│   ├── core/
│   │   ├── models.py            # modèles métier (Dataset, BBox, versions, runs…)
│   │   ├── taxonomy.py          # classes A→E, méthodes, licences, formats
│   │   ├── sources.py           # registre des 8 familles de sources
│   │   ├── context.py           # contexte applicatif (base + dépôt + config)
│   │   └── bootstrap.py         # séquence d'initialisation
│   ├── database/
│   │   ├── schema.sql           # schéma portable SQLite/PostgreSQL
│   │   ├── schema_postgis_extra.sql
│   │   ├── connection.py        # connexion unifiée + création du schéma
│   │   ├── repository.py        # dépôt de données (unique point d'accès SQL)
│   │   └── seed.py              # jeu de référence, explicitement étiqueté
│   ├── geospatial/geometry.py   # surfaces, distances, recouvrements, GeoJSON
│   ├── gui/
│   │   ├── main_window.py       # fenêtre principale, navigation, barre d'état
│   │   ├── theme.py             # palette + QSS
│   │   ├── widgets.py           # composants réutilisables
│   │   ├── charts.py            # graphiques Matplotlib
│   │   └── pages/               # 9 pages (dashboard, carte, catalogue, …)
│   ├── reports/inventory.py     # rapport d'inventaire HTML
│   ├── exporters.py             # CSV / JSON / GeoJSON / Excel
│   ├── connectors/              # (Phases 2-4 — vide en Phase 1)
│   ├── evaluation/              # (Phase 6)
│   ├── downloads/               # (Phase 7)
│   ├── scheduler/               # (Phase 7)
│   └── ai/                      # (module optionnel, phase ultérieure)
├── tests/                       # 98 tests (unitaire, base, géo, exports, GUI)
├── docs/                        # architecture, base de données, captures
├── scripts/                     # vérification, capture d'écran, build
├── config/                      # settings.toml généré à l'exécution
└── requirements.txt
```

**Règle d'architecture** : l'interface ne parle jamais directement à SQL ni au réseau. `GUI → Repository → Database` et, en Phase 2+, `GUI → WatchEngine → Connectors`.

---

## 4. Interface — 9 pages

| # | Page | Contenu réel |
|---|---|---|
| 1 | **Tableau de bord** | 4 indicateurs, couverture du littoral algérien, répartitions profondeur / classe / méthode, état des sources, activité mensuelle, derniers changements |
| 2 | **Carte interactive** | Emprises réelles depuis la base, Mercator, zoom/déplacement, filtre source/classe/côtier/large/algérien, curseur, export GeoJSON |
| 3 | **Catalogue** | Tableau triable + fiche produit complète (20 champs de la section 5), onglet métadonnées brutes, avertissement sur les fiches de démonstration |
| 4 | **Recherche avancée** | Texte, source, classe, licence, format, validation, profondeurs, résolution, emprise, filtres SDB/algérien/côtier, export CSV/JSON/GeoJSON |
| 5 | **Analyse & comparaison** | Comparaison de 4 produits max sur **15 lignes de critères**, graphiques résolution (log) / complétude, rappel des classes A→E et des règles |
| 6 | **Téléchargements** | Accessibilité par produit, arborescence locale, statut local, calcul SHA-256, procédure manuelle |
| 7 | **Historique** | Exécutions de veille, journal des changements filtrable, historique des versions par produit |
| 8 | **Rapports** | 5 périmètres, aperçu HTML, export HTML et Excel |
| 9 | **Paramètres** | Activation des sources + limites connues, planification hebdomadaire persistée, stockage/base/schéma, à propos |

Captures : `docs/screenshots/01_tableau.png` … `09_parametres.png`.

---

## 5. Choix scientifiques structurants

1. **Le pas de grille n'est jamais la résolution effective.** EMODnet 1/16′ (≈ 115 m) et GEBCO 15″ (≈ 450 m) sont affichés comme résolution *nominale*, avec une note explicite.
2. **Aucune vérité terrain automatique.** Seule la classe **A** (mesures directes) est candidate ; les classes B à E sont signalées comme produits dérivés.
3. **Champs inconnus = « non documenté »**, jamais une estimation inventée. La complétude des métadonnées est calculée sur 11 champs critiques.
4. **Les 8 critères d'évaluation restent séparés** en Phase 1 ; le score pondéré et la fiche scientifique sont livrés en Phase 6 avec pondérations traçables.
5. **Les surfaces sont géodésiques** (ellipsoïde WGS84) ou calculées en LAEA Méditerranée, jamais en degrés² bruts.
6. **Le jeu de démonstration est étiqueté** : `data_origin = "seed"`, tag `jeu-de-demonstration`, statut `unverified`, note affichée dans la fiche et le rapport.

---

## 6. Documentation détaillée

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture logicielle, flux de données, décisions techniques, mode PostgreSQL.
* [`docs/DATABASE.md`](docs/DATABASE.md) — schéma complet, tables, vues, conventions, migrations.
* [`docs/SOURCES_AND_LIMITS.md`](docs/SOURCES_AND_LIMITS.md) — les 8 familles de sources, accès privilégiés, limites connues, plan des connecteurs.
* [`docs/PHASES.md`](docs/PHASES.md) — plan de développement Phase 1 → 8 avec critères d'acceptation.
* [`docs/PHASE1_REPORT.md`](docs/PHASE1_REPORT.md) — rapport de livraison de la Phase 1 (ce qui est fait, ce qui ne l'est pas).

---

## 7. Exploration manuelle recommandée

1. `python -m app.main` puis **Tableau de bord** : vérifier que « sources opérationnelles » affiche `0 / 0` et que le bandeau explique pourquoi.
2. **Catalogue** → sélectionner *EMODnet DTM 2024* : lire la fiche (résolution nominale vs effective, référence verticale, fenêtre SDB).
3. **Carte** → cocher « Littoral algérien » : les emprises se réduisent aux produits touchant la façade algérienne.
4. **Analyse** → comparer *ICESat-2 ATL03* (classe A) et *GEBCO_2024* (classe D) : observer les lignes « Résolution effective » et « Validation indépendante ».
5. **Rapports** → *Produits couvrant le littoral algérien* → **Exporter HTML**, ouvrir le fichier dans un navigateur.

---

## 8. Licence et attribution

Le code de l'application est fourni pour usage scientifique. **Les données ne sont pas redistribuées** : chaque fiche pointe vers la source officielle et rappelle sa licence (CC-BY, Copernicus, licence ouverte, accès restreint…). L'utilisateur doit vérifier les conditions d'utilisation et les obligations d'attribution de chaque producteur avant tout usage ou rediffusion.
