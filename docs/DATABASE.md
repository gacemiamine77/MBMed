# Schéma de base de données — MBM 1.0.0

Deux implémentations pour un même modèle logique :

| Backend | Fichier | Usage |
|---|---|---|
| SQLite | `app/database/schema.sql` | démarrage local, tests, poste isolé |
| PostgreSQL/PostGIS | `schema.sql` + `schema_postgis_extra.sql` | production, multiusager, analyses spatiales |

## Conventions

* Horodatages : **ISO-8601 UTC** (`2026-11-11T13:41:41+00:00`).
* Coordonnées : **EPSG:4326** (WGS84) ; emprise stockée en JSON `[minx,miny,maxx,maxy]`
  **et** en colonnes `bbox_minx/miny/maxx/maxy` pour le filtrage.
* Profondeurs : **mètres positifs** (`depth_min_m` < `depth_max_m`).
* Informations absentes : **NULL**, jamais 0 ni valeur inventée.
* Listes : JSON texte (`countries`, `tags`, `changed_fields`…).

## Tables

### `source_registry` — registre des sources (section 3)
`source_id` (PK), `label`, `category`, `description`, `institutions`,
`homepage`, `documentation`, `access_types` (JSON), `products` (JSON),
`expected_classes` (JSON), `licenses` (JSON), `known_limits` (JSON),
`requires_credentials`, `implemented_phase`, **`implemented`** (0/1),
`enabled`, `created_at`, `updated_at`.

> `implemented = 0` signifie que le connecteur n'existe pas encore : c'est la
> source de vérité utilisée par le tableau de bord pour ne jamais afficher une
> source planifiée comme opérationnelle.

### `source_status` — état d'exécution
`source_id` (PK/FK), `last_run`, `last_status` (`ok|partial|error|not_run|disabled`),
`last_message`, `items_seen`, `last_duration_s`, `consecutive_failures`, `updated_at`.

### `datasets` — catalogue (section 5)
54 colonnes organisées en blocs :

| Bloc | Colonnes |
|---|---|
| Identité | `uid` (unique), `source_id`, `source_item_id`, `name`, `producer`, `description` |
| Accès | `official_url`, `download_url`, `access_mode`, `doi`, `citation` |
| Dates / versions | `publication_date`, `update_date`, `version`, `first_seen`, `last_checked`, `status` |
| Emprise | `bbox`, `bbox_minx/miny/maxx/maxy`, `footprint_geojson`, `region`, `countries` |
| Résolution | `resolution_m`, `effective_resolution_m`, `resolution_note` |
| Vertical | `depth_min_m`, `depth_max_m`, `vertical_reference`, `vertical_datum`, `vertical_accuracy_m`, `uncertainty_note` |
| Méthode | `acquisition_method`, `acquisition_class` (A–E), `platform`, `sensor` |
| Technique | `license`, `license_url`, `data_format`, `file_size_mb`, `crs`, `download_method` |
| Qualité | `metadata_status`, `metadata_completeness`, `raw_metadata`, `tags`, `notes` |
| Dérivés | `coastal`, `distance_to_coast_km`, `in_algerian_waters` |
| Traçabilité | `fingerprint`, `identity_key`, `data_origin` (`connector|seed|manual`), `created_at`, `updated_at` |

Index : `source_id`, `acquisition_class`, `license`, `status`, `publication_date`,
`resolution_m`, `identity_key`, `in_algerian_waters`, `data_origin`, `bbox_*`.

### `dataset_versions` — historique (section 5)
`dataset_uid` (FK), `version`, `update_date`, `fingerprint`, `changed_fields` (JSON),
`detected_at`, `source_snapshot` (JSON), `comment`.
Contrainte `UNIQUE(dataset_uid, fingerprint)` : une même empreinte n'est jamais
enregistrée deux fois.

### `footprints` — emprises calculées (section 6)
`dataset_uid` (unique), `bbox`, `geom_geojson`, `area_km2`, `coastal_share`,
`distance_to_coast_km`, `crs_original`, `computed_at`.

### `watch_runs` / `watch_run_sources` — exécutions de veille (section 4)
`run_id`, `started_at`, `finished_at`, `trigger` (`manual|scheduler|startup`),
`status` (`running|success|partial|failed`), `sources_total/ok/failed`,
`items_seen`, `new_count`, `updated_count`, `removed_count`, `duplicate_count`,
`message`, `details`. Détail par source : `items`, `new_count`, `updated_count`,
`errors`, `duration_s`, `message`.

### `change_log` — journal des changements
`dataset_uid`, `run_id`, `change_type` (`new|updated|removed|duplicate|error|note`),
`field_name`, `old_value`, `new_value`, `detected_at`, `source_id`, `details`.

### `publications` — veille bibliographique (sections 4 et 10)
`doi` (unique), `title`, `authors`, `journal`, `publication_date`, `url`, `abstract`,
`source_id`, `related_dataset_uid`, `relevance_score`, `detected_at`,
**`verified`** (0 = information non vérifiée), `notes`.

### `downloads` — gestion des téléchargements (section 8)
`dataset_uid`, `url`, `local_path`, `status` (`pending|running|done|failed|manual_required|skipped`),
`bytes_total`, `checksum`, `checksum_algorithm`, `started_at`, `finished_at`,
`message`, `subset_bbox`.
Contrainte `UNIQUE(dataset_uid, url, local_path)` : détection des fichiers déjà
téléchargés.

### `evaluations` — scores SDB (phase 6)
8 critères (`resolution`, `vertical_accuracy`, `depth_coverage`,
`temporal_proximity`, `metadata_quality`, `acquisition_method`,
`raw_data_availability`, `independent_validation`), `total`, `grade`,
`computed_at`, `rationale` (JSON).

### `coverage_gaps`, `tags`, `dataset_tags`, `audit_log`, `schema_meta`
Lacunes de couverture (phase 5), étiquettes libres, journal d'audit
(`actor`, `action`, `entity`, `entity_id`, `details`) et version du schéma.

## Vues

| Vue | Rôle |
|---|---|
| `v_dataset_summary` | catalogue + `sdb_overlap_m` (recouvrement 0–100 m) |
| `v_depth_bands` | nombre de produits par tranche (0-20, 20-50, 50-100, 100-200, >200 m) |
| `v_class_distribution` | répartition A→E |
| `v_source_health` | statut + nombre de produits + nombre de classe A par source |
| `v_algeria_coverage` | produits touchant le littoral algérien avec recouvrement SDB |
| `v_recent_changes` | journal des changements joint au nom du produit |
| `v_dataset_areas` *(PostGIS)* | surfaces en km² en projection LAEA Méditerranée |
| `v_algeria_intersect` *(PostGIS)* | intersection surfacique avec la fenêtre côtière algérienne |

## Migrations

Le schéma est **idempotent** (`CREATE TABLE IF NOT EXISTS`) et versionné par
`schema_meta.schema_version`. Pour une évolution :

1. incrémenter la version dans `Database.initialize()` ;
2. ajouter un fichier `schema_migration_<version>.sql` idempotent ;
3. appliquer dans `initialize()` si la version stockée est antérieure.

Les données existantes ne sont jamais supprimées par une migration.

## Requêtes de contrôle utiles

```sql
-- produits couvrant la fenêtre SDB sur le littoral algérien
SELECT name, resolution_m, depth_min_m, depth_max_m, acquisition_class
FROM datasets
WHERE in_algerian_waters = 1 AND depth_min_m < 100 AND depth_max_m > 0
ORDER BY acquisition_class, resolution_m;

-- sources jamais exécutées alors qu'un connecteur est annoncé
SELECT r.source_id, r.implemented_phase
FROM source_registry r JOIN source_status s USING (source_id)
WHERE r.implemented = 1 AND s.last_status = 'not_run';

-- produits sans référence verticale (métadonnées incomplètes)
SELECT name, source_id FROM datasets WHERE vertical_reference = '';
```
