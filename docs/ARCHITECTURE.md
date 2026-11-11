# Architecture logicielle — MBM

## 1. Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│  GUI (PySide6)                                                      │
│  MainWindow → 9 pages → widgets réutilisables + charts Matplotlib   │
└───────────────┬─────────────────────────────────────────────────────┘
                │ Appels Python (jamais de SQL, jamais de réseau)
┌───────────────▼─────────────────────────────────────────────────────┐
│  Couche de services                                                 │
│  AppContext (config + base + dépôt)                                 │
└───────────────┬─────────────────────────────────────────────────────┘
                │
   ┌────────────┴───────────────┬──────────────────┬─────────────────┐
   │                            │                  │                 │
┌──▼──────────────┐   ┌─────────▼────────┐  ┌──────▼────────┐  ┌─────▼──────┐
│ Repository      │   │ geospatial       │  │ exporters     │  │ reports    │
│ (SQL unique)    │   │ geometry.py      │  │ csv/json/geo/ │  │ inventory  │
│                 │   │                  │  │ xlsx          │  │ html       │
└──┬──────────────┘   └──────────────────┘  └───────────────┘  └────────────┘
   │
┌──▼──────────────────────────────────────────────────────────────────┐
│  Database : SQLite (local) ou PostgreSQL/PostGIS (production)       │
└─────────────────────────────────────────────────────────────────────┘

   Modules prévus (non livrés en Phase 1) :
   connectors/  → phases 2-4     evaluation/ → phase 6
   scheduler/   → phase 7        downloads/  → phase 7        ai/ → optionnel
```

## 2. Flux de données

### 2.1 Démarrage

```
main.py
 ├─ get_settings()            → config/settings.toml + variables MBM_*
 ├─ bootstrap()
 │   ├─ Settings.ensure_directories()   → ~/MBM_Data/{downloads,reports,…}
 │   ├─ Database.initialize()           → schema.sql (+ PostGIS si pg)
 │   ├─ Repository.sync_sources()       → source_registry ← core/sources.py
 │   └─ load_seed_data() si base vide   → 15 fiches étiquetées « seed »
 └─ MainWindow(ctx) → 9 pages → refresh()
```

### 2.2 Ingestion d'un produit (Phase 2+, déjà implémentée côté dépôt)

```
Connector.fetch() → Dataset (modèle normalisé)
                   → geospatial.enrich_geometry()   (coastal, distance, DZ)
                   → Repository.upsert_dataset()
                        ├─ empreinte (fingerprint) comparable ?
                        ├─ nouveau        → INSERT + version initiale + change_log
                        ├─ modifié        → UPDATE + nouvelle version + changed_fields
                        └─ inchangé       → UPDATE last_checked seulement
```

C'est ce mécanisme qui garantit les exigences de la section 4 : détection des
mises à jour, des nouvelles versions, comparaison avec les recherches
précédentes, déduplication et enregistrement de la date de dernière vérification.

### 2.3 Déduplication

Deux clés coexistent :

* `uid` = SHA-256(`source_id` + `source_item_id`) → identité *dans* une source ;
* `identity_key` = SHA-256(nom normalisé + producteur + version) → détection des
  doublons *entre* sources (même produit publié par deux portails).

Une similarité floue (nom + emprise + résolution) sera ajoutée au moteur de
veille en Phase 7 ; le schéma prévoit `change_type = 'duplicate'`.

## 3. Décisions techniques

| Décision | Justification |
|---|---|
| **SQL portable**, pas d'ORM | Zéro dépendance lourde, requêtes lisibles, migration SQLite→PostGIS sans réécriture. Le SQL spécifique est isolé (ex. `NULLS LAST`). |
| **Emprises en `bbox_minx…maxy` dénormalisées** | Filtrage spatial rapide et portable sur SQLite comme sur PostgreSQL, sans extension. Les colonnes `geometry` PostGIS sont ajoutées en production. |
| **Emprises stockées en JSON + GeoJSON** | Conservation de la référence originale (EPSG:4326) ; les surfaces sont calculées en projection équivalente, jamais stockées comme vérité. |
| **Profondeurs en mètres positifs** | Convention unique évitant les erreurs de signe entre sources. |
| **`AppContext` injectable** | Les tests construisent un contexte sur base temporaire : l'interface est testable sans mock réseau. |
| **Matplotlib (et non PyQtGraph)** | Courbes statiques, export PDF/PNG direct en Phase 7, meilleure lisibilité typographique pour des rapports. PyQtGraph reste possible pour la carte temps réel. |
| **Carte Qt native** | Aucun accès réseau au démarrage, fonctionnement hors ligne garanti. Le fond raster/WMS et la quantification surfacique arrivent en Phase 5. |
| **Qt `offscreen` pour les tests** | La CI peut tester le rendu de chaque page sans serveur X. |

## 4. Mode PostgreSQL / PostGIS

1. `pip install 'psycopg[binary]'` et créer la base avec l'extension PostGIS.
2. Définir les variables :

```bash
export MBM_DB_BACKEND=postgresql
export MBM_DB_HOST=localhost MBM_DB_PORT=5432
export MBM_DB_NAME=mbm        MBM_DB_USER=mbm MBM_DB_PASSWORD=***
```

3. Au démarrage, `Database.initialize()` applique `schema.sql` puis
   `schema_postgis_extra.sql` : colonne `geom geometry(Polygon,4326)`, index GiST,
   triggers de synchronisation `bbox → geom`, vues `v_dataset_areas` (surfaces en
   LAEA) et `v_algeria_intersect` (intersection avec la fenêtre côtière).
4. Aucun identifiant n'est stocké dans le code ni dans le TOML : uniquement
   l'environnement (voir `app/config/settings.py`).

## 5. Extensibilité

* **Nouveau connecteur** : créer `app/connectors/<source>.py` exposant
  `fetch(ctx, bbox, since) -> list[Dataset]`, mettre `implemented=True` et
  `implemented_phase` dans `app/core/sources.py`. L'interface et le tableau de
  bord se mettent à jour sans autre modification.
* **Nouveau critère d'évaluation** : étendre `app/evaluation/` (Phase 6) et la
  table `evaluations` déjà présente.
* **Nouvelle page** : ajouter une entrée dans `PAGES` (`gui/main_window.py`) et
  une sous-classe de `BasePage`.
* **Thème** : tout est centralisé dans `app/gui/theme.py` (palette + QSS).

## 6. Performance et robustesse

* Index sur `source_id`, `acquisition_class`, `publication_date`, `resolution_m`,
  `in_algerian_waters`, `bbox_*`, `identity_key`.
* Vues d'agrégation (`v_depth_bands`, `v_class_distribution`, `v_source_health`)
  pour éviter de recalculer les répartitions en Python.
* WAL activé sur SQLite (lectures concurrentes), transactions explicites par
  opération d'écriture.
* Toute erreur d'affichage d'une page est journalisée et affichée dans la barre
  d'état sans faire tomber l'application.
