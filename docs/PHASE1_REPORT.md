# Rapport de livraison — Phase 1

**Version** : 0.1.0 · **Date** : 11 novembre 2026 · **Périmètre** : architecture, base de données, interface graphique initiale.

---

## 1. Résultat

La Phase 1 livre une application **exécutable et testée** :

* `python -m app.main` ouvre une interface professionnelle de 9 pages ;
* la base SQLite est créée automatiquement au premier lancement ;
* 15 fiches produits pré-chargées permettent de tester le catalogue, la carte,
  la recherche, la comparaison et les rapports ;
* 98 tests automatisés passent (dont 12 sur l'interface en mode hors écran).

---

## 2. Livrables

### 2.1 Code

| Fichier / module | Lignes | Rôle |
|---|---:|---|
| `app/config/settings.py` | ~300 | configuration typée, TOML, variables `MBM_*` |
| `app/core/models.py` | ~380 | modèles métier (Dataset, BBox, versions, runs, downloads…) |
| `app/core/taxonomy.py` | ~250 | classes A→E, méthodes, licences, formats, profondeurs |
| `app/core/sources.py` | ~300 | registre des 8 familles + limites connues |
| `app/core/context.py`, `bootstrap.py` | ~120 | contexte applicatif, initialisation |
| `app/database/schema.sql` | ~380 | 16 tables, 6 vues, index |
| `app/database/schema_postgis_extra.sql` | ~70 | géométries, GiST, vues surfaciques |
| `app/database/connection.py` | ~210 | connexion SQLite/PostgreSQL, schéma idempotent |
| `app/database/repository.py` | ~700 | dépôt de données (catalogue, veille, stats, filtres) |
| `app/database/seed.py` | ~450 | 15 fiches de référence étiquetées |
| `app/geospatial/geometry.py` | ~420 | surfaces, distances, recouvrements, GeoJSON |
| `app/gui/*` (10 fichiers) | ~3600 | thème, widgets, graphiques, 9 pages, fenêtre principale |
| `app/reports/inventory.py` | ~230 | rapport d'inventaire HTML |
| `app/exporters.py` | ~230 | CSV, JSON, GeoJSON, Excel |
| `app/main.py` | ~160 | CLI, diagnostic, lancement GUI |
| `tests/*` (6 fichiers) | ~900 | 98 tests |
| `scripts/*`, `docs/*` | — | vérification, captures, documentation |

### 2.2 Documentation

`README.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`,
`docs/SOURCES_AND_LIMITS.md`, `docs/PHASES.md`, ce rapport, 9 captures d'écran.

### 2.3 Mise en route

```bash
pip install -r requirements.txt
python -m app.main --check     # diagnostic
python -m app.main             # interface
pytest -q                      # 98 tests
```

---

## 3. Conformité au cahier des charges

| Exigence | Statut Phase 1 | Où |
|---|---|---|
| Technologies imposées (PySide6, SQLite/PostGIS, GDAL/Rasterio/GeoPandas/Shapely/Xarray, APScheduler, Matplotlib, exports CSV/Excel/GeoJSON/PDF) | PySide6, SQLite+PostGIS, Shapely/pyproj/GeoPandas/Rasterio/Xarray installés et utilisés ; APScheduler installé (branché en P7) ; Matplotlib actif ; CSV/Excel/GeoJSON opérationnels, PDF en P7 | `requirements.txt`, `app/main.py --check` |
| Un connecteur indépendant par source (8 familles) | Registre complet et indépendant ; connecteurs **non livrés** et affichés comme planifiés | `app/core/sources.py` |
| Pas de dépendance au scraping HTML | `html_scraping` déclaré uniquement en dernier recours pour les portails nationaux | `docs/SOURCES_AND_LIMITS.md` |
| Gestion erreurs / quotas / formats par connecteur | Contrat posé (`source_status`, statuts, délais, tentatives) ; implémentation en P2-P4 | `repository.update_source_status` |
| Veille périodique, nouveautés, versions, doublons, date de vérification, rapport même vide | **Mécanique de détection livrée** (empreinte, versions, journal, `watch_runs`) ; planification et rapport hebdo en P7 | `repository.upsert_dataset`, tables dédiées |
| Catalogue : 20 champs de la section 5 | Tous présents et affichés dans la fiche produit | `schema.sql`, `pages/catalogue.py` |
| Historique des versions | Opérationnel (`dataset_versions`, `changed_fields`) | `tests/test_database.py` |
| Carte interactive (emprises, filtres, côtière/offshore, algérien, superposition) | Fonctionnelle hors ligne ; couverture par bandes et lacunes en P5 | `pages/map.py` |
| CRS adapté aux surfaces, références originales conservées | Surfaces géodésiques + LAEA optionnelle ; EPSG:4326 conservé | `geospatial/geometry.py` |
| Évaluation 8 critères, classes A→E, pas de vérité terrain automatique, pas de confusion pas de grille / résolution effective | Taxonomie + rappels dans l'UI + comparaison des valeurs documentées ; score pondéré en P6 | `taxonomy.py`, `pages/analyze.py` |
| Téléchargement, intégrité, versions, doublons, arborescence, mode manuel | Schéma, arborescence, SHA-256, liste des produits manuels ; moteur réseau en P7 | `schema.sql`, `pages/downloads.py` |
| Interface 9 pages + tableau de bord (tous les indicateurs) | 9 pages livrées, tous les indicateurs présents (à zéro tant qu'aucune veille n'a tourné) | `gui/main_window.py` |
| Module IA optionnel avec sources obligatoires, pas d'invention | Non livré (hors Phase 1) ; règles inscrites dans `docs/PHASES.md` | — |
| Rapports hebdomadaires FR (PDF/HTML/Excel) | Rapport d'inventaire HTML + Excel livré ; hebdo + PDF en P7 | `reports/inventory.py` |
| Architecture modulaire `app/{gui,core,connectors,database,geospatial,evaluation,downloads,reports,scheduler,ai,config,tests}` | Toutes les séparations existent ; dossiers des phases futures créés | arborescence |
| Développement par phases, code exécutable, pas de fonction fictive | Respecté : chaque module non livré est explicitement « planifié » | bannière du tableau de bord |

---

## 4. Points d'attention scientifiques

1. **Le jeu de démonstration n'est pas un catalogue validé.** Les 15 fiches décrivent
   des produits publics réels, mais leurs chiffres (résolution, emprises, profondeurs)
   viennent de la documentation publique et doivent être confirmés par les connecteurs.
   Elles sont marquées : `data_origin = seed`, tag `jeu-de-demonstration`,
   statut `unverified`, avertissement visible dans la fiche et dans les rapports.
2. **Le trait de côte embarqué est simplifié (~0,25°).** Il sert uniquement à classer
   « côtier / plateau / large » et à calculer la distance au littoral. Un trait de côte
   de référence (GSHHG/EMODnet) est prévu en Phase 5 pour tout calcul de surface.
3. **Les surfaces actuelles portent sur l'emprise rectangulaire**, pas sur la zone
   marine réellement couverte. La quantification par bande de profondeur et la
   soustraction terre/mer arrivent en Phase 5.
4. **Aucun score agrégé n'est produit.** Les huit critères restent affichés séparément
   pour éviter une note trompeuse avant la Phase 6.
5. **`sources opérationnelles = 0 / 0`** est volontaire : la base ne contient aucun
   connecteur et l'interface le dit explicitement plutôt que d'afficher un faux positif.

---

## 5. Limites techniques connues

* PostgreSQL/PostGIS : code prêt mais non testé dans cet environnement (pas de serveur) ;
  `psycopg` n'est pas installé par défaut.
* Export PDF non disponible (reportlab non installé) — Phase 7.
* La carte est un rendu vectoriel schématique hors ligne : pas de fond raster, pas de
  tuiles, pas de WMS. Zoom/déplacement fonctionnels.
* APScheduler est installé mais aucune tâche n'est planifiée en Phase 1.
* Le tableau de bord défile verticalement sous 1400 px de largeur (mise en page pensée
  pour 1500-1600 px).

---

## 6. Validation demandée avant la Phase 2

Merci de confirmer les points suivants, qui conditionnent les connecteurs :

1. **Périmètre géographique** de la veille : Méditerranée entière ou bassin algérien
   prioritaire ? (le paramètre `research_bbox` existe déjà)
2. **Priorité des deux premiers connecteurs** : EMODnet puis GEBCO, ou l'inverse ?
3. **Métadonnées seulement** en veille périodique (recommandé) ou téléchargement
   automatique des MNT ? Cela conditionne les quotas et le volume disque.
4. **Traits de côte de référence** pour la Phase 5 : GSHHG embarqué (licence LGPL)
   ou extrait EMODnet (CC-BY) ?
5. **Fréquence de veille** souhaitée (hebdomadaire lundi 06:00 par défaut, fuseau
   Africa/Algiers).
6. **Comptes** : disposez-vous d'un accès Earthdata (ICESat-2) et Copernicus Marine ?
   Sans eux, les connecteurs P3 fonctionneront en mode « métadonnées seules ».
