# Plan de développement — Phases 1 à 8

Chaque phase livre du **code exécutable**, ses **tests** et sa **documentation**,
sans casser les modules précédents. Les phases ne sont pas déclarées terminées
tant que leurs critères d'acceptation ne sont pas satisfaits.

---

## ✅ Phase 1 — Architecture, base de données, interface initiale *(livrée)*

**Livré**
* Arborescence modulaire `app/{config,core,database,geospatial,gui,reports,exporters}` + dossiers réservés.
* Schéma SQL portable (16 tables, 6 vues) + enrichissements PostGIS.
* Dépôt de données complet : CRUD, filtres avancés, versions, journal, statistiques.
* Modèles métier et taxonomie scientifique (classes A→E, méthodes, licences, formats).
* Registre des 8 familles de sources avec état d'implémentation honnête et limites.
* Géospatial : surfaces géodésiques, distance au littoral de référence, recouvrements algériens, GeoJSON.
* Interface 9 pages, thème sombre, graphiques Matplotlib, carte interactive hors ligne.
* Exports CSV / JSON / GeoJSON / Excel ; rapport d'inventaire HTML.
* Jeu de référence de 15 fiches, explicitement étiqueté « démonstration ».
* 98 tests (unitaires, base, géo, exports, GUI offscreen) ; `--check` de diagnostic.

**Critères d'acceptation**
* [x] `python -m app.main` démarre et affiche les 9 pages sans erreur.
* [x] Le schéma se crée sans intervention et reste idempotent.
* [x] Aucun connecteur non livré n'apparaît comme opérationnel.
* [x] Aucune valeur numérique manquante n'est remplacée par une estimation.
* [x] `pytest -q` → 98 réussis.

**Hors périmètre assumé** : aucun accès réseau, aucune donnée réelle téléchargée,
pas de scoring SDB, pas de PDF, pas de planification active.

---

## Phase 2 — Connecteurs EMODnet et GEBCO

**Objectifs**
* `app/connectors/base.py` : interface commune (`fetch`, `normalize`, `probe`),
  gestion des erreurs, délais, tentatives, quotas, journalisation.
* `connectors/emodnet.py` : index CDI + fiches DTM (versions, emprises, dates).
* `connectors/gebco.py` : versions de grille, TID, notes de publication.
* `app/connectors/registry.py` : découverte des connecteurs, activation par source.
* Moteur de veille minimal : exécution manuelle d'un connecteur, écriture des
  `change_log` et `watch_runs`.
* Tests : cassettes de réponses HTTP (aucun appel réseau en CI), parsing, erreurs 429/500, changement de schéma.

**Critères d'acceptation** : un run manuel remplit la base avec les métadonnées
EMODnet et GEBCO ; les compteurs du tableau de bord deviennent non nuls ; les
sources passent en `ok` ; un rapport de run est écrit même sans nouveauté.

---

## Phase 3 — Copernicus Marine et ICESat-2

* Authentification par variables d'environnement uniquement (jamais en base en clair).
* Catalogue produit Copernicus (produits, versions, dates), variables optiques de contexte.
* ICESat-2 : suivi des versions ATL03/ATL24, notes de version, emprises de pistes.
* Gestion explicite des identifiants manquants : statut `partial` avec message clair.
* Tests de non-régression et tests spécifiques aux échecs d'authentification.

**Critères d'acceptation** : sans identifiants, l'application reste pleinement
fonctionnelle et l'indique ; avec identifiants, les produits sont catalogués.

---

## Phase 4 — Autres sources institutionnelles et scientifiques

* Sous-connecteurs nationaux (SHOM, IHM, IIM, HNHS, OHI/INOC) avec capacités déclaratives.
* Dépôts scientifiques (PANGAEA, Zenodo, SEANOE, DataCite/Crossref) : veille bibliographique.
* Levés sonar (NCEI, Sextant) : index de campagnes.
* MNT côtiers et cartes marines.
* Déduplication inter-sources (similarité nom + emprise + résolution).

**Critères d'acceptation** : les 8 familles ont un état réel dans `source_registry` ;
au moins une source de levés directs alimente la classe A.

---

## Phase 5 — Carte interactive avancée et analyse des emprises

* Fond vectoriel réel (Natural Earth/GSHHG embarqué) + fonds raster optionnels (WMS/XYZ).
* Projection équivalente pour les surfaces, calcul des **surfaces couvertes par bande**
  (0–20, 20–50, 50–100 m) en tenant compte du masque terre/mer.
* Matrice de **lacunes de couverture** (table `coverage_gaps`) par cellule de grille
  côtière algérienne.
* Superposition multi-sources, transparence, ordre par classe, export carte (PNG/SVG).
* Tests sur surfaces et détection de lacunes avec jeux synthétiques.

**Critères d'acceptation** : le tableau de bord affiche un pourcentage de couverture
côtière algérienne calculé, pas seulement un nombre de produits.

---

## Phase 6 — Évaluation scientifique et fiche produit

* Moteur de scoring 8 critères, pondérations configurables et **explicites**.
* Règles bloquantes : un produit interpolé ne peut pas obtenir le grade de vérité terrain.
* Fiche scientifique générée (avantages, limites, usage SDB, vérifications requises).
* Comparateur de produits avec traçabilité des scores et justification par critère.
* Tests de monotonie (meilleure résolution ⇒ meilleur score) et de règles bloquantes.

**Critères d'acceptation** : toute note est explicable et reproductible ; aucune
fiche ne contient de valeur non sourcée.

---

## Phase 7 — Téléchargements, rapports et planification

* Moteur de téléchargement : reprise, sous-ensemble par emprise, SHA-256, arborescence
  versionnée, détection des doublons, fil d'exécution dans l'interface.
* Procédure de **dépôt manuel** (déclaration d'un fichier + métadonnées + empreinte).
* APScheduler : tâche hebdomadaire configurable, exécution en arrière-plan, rapport
  produit **même sans nouveauté**.
* Rapport hebdomadaire en français : PDF (reportlab), HTML, Excel — nouveautés,
  mises à jour, publications, caractéristiques, zones, résolutions, licences, limites,
  intérêt SDB, liens officiels.
* Tests : planification, génération des trois formats, téléchargement simulé.

**Critères d'acceptation** : une veille planifiée tourne sans intervention et dépose
le rapport dans `~/MBM_Data/reports/`.

---

## Phase 8 — Tests, documentation, packaging

* Couverture de tests > 80 % sur `core`, `database`, `geospatial`, `evaluation`.
* Documentation utilisateur (guide), documentation API (docstrings → Sphinx/MkDocs).
* Packaging : `pyproject.toml`, exécutable PyInstaller (Windows/Linux/macOS), script d'installation.
* Journalisation, gestion des erreurs, page de diagnostic, procédure de sauvegarde.
* Recette finale et jeu de démonstration documenté.

**Critères d'acceptation** : installation reproductible sur machine vierge, exécutable
livré, documentation complète.

---

## Module IA (optionnel, après la Phase 6)

* Lecture et synthèse de publications (résumé, caractéristiques extraites).
* **Interdiction d'inventer** résolution, précision ou emprise : toute valeur doit
  être liée à un extrait source et marquée `verified = 0` jusqu'à validation humaine.
* Comparaison de produits et explication des limites méthodologiques.
* Chaque sortie inclut les références et liens vers les sources originales.
