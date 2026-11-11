-- ============================================================================
--  Mediterranean Bathymetry Monitor (MBM) — schéma de base relationnelle
--  Cible : SQLite (démarrage local) et PostgreSQL/PostGIS (production)
--  Ce fichier contient le sous-ensemble PORTABLE du schéma (types SQL communs).
--  Les enrichissements spatiaux (colonnes geometry, index GiST, triggers) sont
--  appliqués par `app/database/schema_postgis_extra.sql` en mode PostgreSQL.
--
--  Conventions :
--    * profondeurs en mètres POSITIFS (depth_min_m < depth_max_m) ;
--    * emprises en WGS84, stockées en JSON [minx, miny, maxx, maxy] ;
--    * horodatages ISO-8601 UTC en TEXT ;
--    * aucun champ numérique inconnu n'est rempli par une valeur arbitraire
--      (NULL = information non disponible).
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Métadonnées du schéma
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ---------------------------------------------------------------------------
-- Registre des sources (section 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_registry (
    source_id            TEXT PRIMARY KEY,
    label                TEXT NOT NULL,
    category             TEXT NOT NULL DEFAULT '',
    description          TEXT NOT NULL DEFAULT '',
    institutions         TEXT NOT NULL DEFAULT '',
    homepage             TEXT NOT NULL DEFAULT '',
    documentation        TEXT NOT NULL DEFAULT '',
    access_types         TEXT NOT NULL DEFAULT '[]',   -- JSON list
    products             TEXT NOT NULL DEFAULT '[]',   -- JSON list
    expected_classes     TEXT NOT NULL DEFAULT '[]',   -- JSON list (A-E)
    licenses             TEXT NOT NULL DEFAULT '[]',   -- JSON list
    known_limits         TEXT NOT NULL DEFAULT '[]',   -- JSON list
    requires_credentials INTEGER NOT NULL DEFAULT 0,
    implemented_phase    INTEGER NOT NULL DEFAULT 0,
    implemented          INTEGER NOT NULL DEFAULT 0,
    enabled              INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS source_status (
    source_id             TEXT PRIMARY KEY REFERENCES source_registry(source_id) ON DELETE CASCADE,
    last_run              TEXT,
    last_status           TEXT NOT NULL DEFAULT 'not_run', -- ok|partial|error|not_run|disabled
    last_message          TEXT NOT NULL DEFAULT '',
    items_seen            INTEGER NOT NULL DEFAULT 0,
    last_duration_s       REAL,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ---------------------------------------------------------------------------
-- Catalogue des jeux de données (section 5)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    uid                    TEXT NOT NULL UNIQUE,
    source_id              TEXT NOT NULL REFERENCES source_registry(source_id),
    source_item_id         TEXT NOT NULL DEFAULT '',
    name                   TEXT NOT NULL,
    producer               TEXT NOT NULL DEFAULT '',
    description            TEXT NOT NULL DEFAULT '',

    official_url           TEXT NOT NULL DEFAULT '',
    download_url           TEXT NOT NULL DEFAULT '',
    access_mode            TEXT NOT NULL DEFAULT 'http_direct',
    doi                    TEXT NOT NULL DEFAULT '',
    citation               TEXT NOT NULL DEFAULT '',

    publication_date       TEXT,
    update_date            TEXT,
    version                TEXT NOT NULL DEFAULT '',
    first_seen             TEXT NOT NULL,
    last_checked           TEXT,
    status                 TEXT NOT NULL DEFAULT 'new',

    bbox                   TEXT,                        -- JSON [minx,miny,maxx,maxy]
    bbox_minx              REAL,                        -- colonnes dénormalisées pour
    bbox_miny              REAL,                        -- le filtrage spatial portable
    bbox_maxx              REAL,
    bbox_maxy              REAL,
    footprint_geojson      TEXT,                        -- GeoJSON Polygon/MultiPolygon
    region                 TEXT NOT NULL DEFAULT '',
    countries              TEXT NOT NULL DEFAULT '[]',  -- JSON list ISO-2

    resolution_m           REAL,
    effective_resolution_m REAL,
    resolution_note        TEXT NOT NULL DEFAULT '',

    depth_min_m            REAL,
    depth_max_m            REAL,
    vertical_reference     TEXT NOT NULL DEFAULT '',
    vertical_datum         TEXT NOT NULL DEFAULT '',
    vertical_accuracy_m    REAL,
    uncertainty_note       TEXT NOT NULL DEFAULT '',

    acquisition_method     TEXT NOT NULL DEFAULT 'unknown',
    acquisition_class      TEXT NOT NULL DEFAULT 'D',
    platform               TEXT NOT NULL DEFAULT '',
    sensor                 TEXT NOT NULL DEFAULT '',

    license                TEXT NOT NULL DEFAULT 'unknown',
    license_url            TEXT NOT NULL DEFAULT '',
    data_format            TEXT NOT NULL DEFAULT '',
    file_size_mb           REAL,
    crs                    TEXT NOT NULL DEFAULT 'EPSG:4326',
    download_method        TEXT NOT NULL DEFAULT '',

    metadata_status        TEXT NOT NULL DEFAULT 'unverified',
    metadata_completeness  REAL NOT NULL DEFAULT 0.0,
    raw_metadata           TEXT NOT NULL DEFAULT '{}',
    tags                   TEXT NOT NULL DEFAULT '[]',
    notes                  TEXT NOT NULL DEFAULT '',

    coastal                INTEGER NOT NULL DEFAULT 0,
    distance_to_coast_km   REAL,
    in_algerian_waters     INTEGER NOT NULL DEFAULT 0,

    fingerprint            TEXT NOT NULL DEFAULT '',
    identity_key           TEXT NOT NULL DEFAULT '',
    data_origin            TEXT NOT NULL DEFAULT 'connector',  -- connector|seed|manual
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_datasets_source       ON datasets(source_id);
CREATE INDEX IF NOT EXISTS idx_datasets_class        ON datasets(acquisition_class);
CREATE INDEX IF NOT EXISTS idx_datasets_license      ON datasets(license);
CREATE INDEX IF NOT EXISTS idx_datasets_status       ON datasets(status);
CREATE INDEX IF NOT EXISTS idx_datasets_pubdate      ON datasets(publication_date);
CREATE INDEX IF NOT EXISTS idx_datasets_resolution   ON datasets(resolution_m);
CREATE INDEX IF NOT EXISTS idx_datasets_identity     ON datasets(identity_key);
CREATE INDEX IF NOT EXISTS idx_datasets_algeria      ON datasets(in_algerian_waters);
CREATE INDEX IF NOT EXISTS idx_datasets_bbox         ON datasets(bbox_minx, bbox_maxx, bbox_miny, bbox_maxy);
CREATE INDEX IF NOT EXISTS idx_datasets_origin       ON datasets(data_origin);

-- ---------------------------------------------------------------------------
-- Historique des versions (section 5)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dataset_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_uid     TEXT NOT NULL REFERENCES datasets(uid) ON DELETE CASCADE,
    version         TEXT NOT NULL DEFAULT '',
    update_date     TEXT,
    fingerprint     TEXT NOT NULL,
    changed_fields  TEXT NOT NULL DEFAULT '[]',
    detected_at     TEXT NOT NULL,
    source_snapshot TEXT NOT NULL DEFAULT '{}',
    comment         TEXT NOT NULL DEFAULT '',
    UNIQUE(dataset_uid, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_versions_dataset ON dataset_versions(dataset_uid, detected_at);

-- ---------------------------------------------------------------------------
-- Emprises calculées (section 6)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS footprints (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_uid         TEXT NOT NULL UNIQUE REFERENCES datasets(uid) ON DELETE CASCADE,
    bbox                TEXT,
    geom_geojson        TEXT,
    area_km2            REAL,
    coastal_share       REAL,
    distance_to_coast_km REAL,
    crs_original        TEXT NOT NULL DEFAULT 'EPSG:4326',
    computed_at         TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Exécutions de veille et journal des changements (section 4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watch_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    trigger         TEXT NOT NULL DEFAULT 'manual',
    status          TEXT NOT NULL DEFAULT 'running',
    sources_total   INTEGER NOT NULL DEFAULT 0,
    sources_ok      INTEGER NOT NULL DEFAULT 0,
    sources_failed  INTEGER NOT NULL DEFAULT 0,
    items_seen      INTEGER NOT NULL DEFAULT 0,
    new_count       INTEGER NOT NULL DEFAULT 0,
    updated_count   INTEGER NOT NULL DEFAULT 0,
    removed_count   INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    message         TEXT NOT NULL DEFAULT '',
    details         TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS watch_run_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES watch_runs(run_id) ON DELETE CASCADE,
    source_id   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'ok',
    items       INTEGER NOT NULL DEFAULT 0,
    new_count   INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    errors      INTEGER NOT NULL DEFAULT 0,
    duration_s  REAL,
    message     TEXT NOT NULL DEFAULT '',
    UNIQUE(run_id, source_id)
);

CREATE TABLE IF NOT EXISTS change_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_uid TEXT NOT NULL,
    run_id      TEXT NOT NULL DEFAULT '',
    change_type TEXT NOT NULL,                 -- new|updated|removed|duplicate|error|note
    field_name  TEXT NOT NULL DEFAULT '',
    old_value   TEXT NOT NULL DEFAULT '',
    new_value   TEXT NOT NULL DEFAULT '',
    detected_at TEXT NOT NULL,
    source_id   TEXT NOT NULL DEFAULT '',
    details     TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_changes_detected ON change_log(detected_at);
CREATE INDEX IF NOT EXISTS idx_changes_type     ON change_log(change_type);
CREATE INDEX IF NOT EXISTS idx_changes_dataset  ON change_log(dataset_uid);

-- ---------------------------------------------------------------------------
-- Publications suivies (section 4 et 10)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    doi                 TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    authors             TEXT NOT NULL DEFAULT '',
    journal             TEXT NOT NULL DEFAULT '',
    publication_date    TEXT,
    url                 TEXT NOT NULL DEFAULT '',
    abstract            TEXT NOT NULL DEFAULT '',
    source_id           TEXT NOT NULL DEFAULT '',
    related_dataset_uid TEXT,
    relevance_score     REAL,
    detected_at         TEXT NOT NULL,
    verified            INTEGER NOT NULL DEFAULT 0,   -- 0 = information non vérifiée
    notes               TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- Téléchargements (section 8)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS downloads (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_uid        TEXT NOT NULL REFERENCES datasets(uid) ON DELETE CASCADE,
    url                TEXT NOT NULL,
    local_path         TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending',
    bytes_total        INTEGER,
    checksum           TEXT NOT NULL DEFAULT '',
    checksum_algorithm TEXT NOT NULL DEFAULT 'sha256',
    started_at         TEXT,
    finished_at        TEXT,
    message            TEXT NOT NULL DEFAULT '',
    subset_bbox        TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(dataset_uid, url, local_path)
);

CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);

-- ---------------------------------------------------------------------------
-- Évaluations SDB (section 7 — table prête, alimentée en phase 6)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_uid           TEXT NOT NULL UNIQUE REFERENCES datasets(uid) ON DELETE CASCADE,
    resolution            REAL NOT NULL DEFAULT 0,
    vertical_accuracy     REAL NOT NULL DEFAULT 0,
    depth_coverage        REAL NOT NULL DEFAULT 0,
    temporal_proximity    REAL NOT NULL DEFAULT 0,
    metadata_quality      REAL NOT NULL DEFAULT 0,
    acquisition_method    REAL NOT NULL DEFAULT 0,
    raw_data_availability REAL NOT NULL DEFAULT 0,
    independent_validation REAL NOT NULL DEFAULT 0,
    total                 REAL NOT NULL DEFAULT 0,
    grade                 TEXT NOT NULL DEFAULT '',
    computed_at           TEXT NOT NULL,
    rationale             TEXT NOT NULL DEFAULT '[]'
);

-- ---------------------------------------------------------------------------
-- Lacunes de couverture (section 6 — alimentée en phase 5)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coverage_gaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_id      TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL DEFAULT '',
    bbox        TEXT,
    depth_class TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',
    note        TEXT NOT NULL DEFAULT '',
    computed_at TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Tags libres
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#7a8aa0'
);

CREATE TABLE IF NOT EXISTS dataset_tags (
    dataset_uid TEXT NOT NULL REFERENCES datasets(uid) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (dataset_uid, tag_id)
);

-- ---------------------------------------------------------------------------
-- Journal d'audit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    actor     TEXT NOT NULL DEFAULT 'system',
    action    TEXT NOT NULL,
    entity    TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    details   TEXT NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- VUES D'ANALYSE
-- ---------------------------------------------------------------------------

-- Vue principale du catalogue avec fenêtre SDB (0–100 m)
CREATE VIEW IF NOT EXISTS v_dataset_summary AS
SELECT
    d.uid,
    d.name,
    d.source_id,
    d.producer,
    d.acquisition_class,
    d.acquisition_method,
    d.resolution_m,
    d.effective_resolution_m,
    d.depth_min_m,
    d.depth_max_m,
    d.license,
    d.data_format,
    d.publication_date,
    d.update_date,
    d.last_checked,
    d.status,
    d.metadata_status,
    d.metadata_completeness,
    d.coastal,
    d.in_algerian_waters,
    d.data_origin,
    d.bbox,
    CAST(
        MAX(0.0, MIN(COALESCE(d.depth_max_m, 0.0), 100.0) - MAX(COALESCE(d.depth_min_m, 0.0), 0.0))
    AS REAL) AS sdb_overlap_m
FROM datasets d;

-- Répartition par bande de profondeur (un produit peut couvrir plusieurs bandes)
CREATE VIEW IF NOT EXISTS v_depth_bands AS
SELECT '0-20 m' AS band, COUNT(*) AS n FROM datasets
    WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL AND depth_min_m < 20 AND depth_max_m > 0
UNION ALL
SELECT '20-50 m', COUNT(*) FROM datasets
    WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL AND depth_min_m < 50 AND depth_max_m > 20
UNION ALL
SELECT '50-100 m', COUNT(*) FROM datasets
    WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL AND depth_min_m < 100 AND depth_max_m > 50
UNION ALL
SELECT '100-200 m', COUNT(*) FROM datasets
    WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL AND depth_min_m < 200 AND depth_max_m > 100
UNION ALL
SELECT '> 200 m', COUNT(*) FROM datasets
    WHERE depth_min_m IS NOT NULL AND depth_max_m IS NOT NULL AND depth_max_m > 200;

-- Répartition par classe d'acquisition A–E
CREATE VIEW IF NOT EXISTS v_class_distribution AS
SELECT acquisition_class AS class, COUNT(*) AS n
FROM datasets GROUP BY acquisition_class ORDER BY acquisition_class;

-- Santé des sources
CREATE VIEW IF NOT EXISTS v_source_health AS
SELECT
    r.source_id, r.label, r.category, r.implemented, r.implemented_phase, r.enabled,
    r.requires_credentials,
    COALESCE(s.last_status, 'not_run') AS last_status,
    s.last_run, s.last_message, COALESCE(s.items_seen, 0) AS items_seen,
    COALESCE(s.consecutive_failures, 0) AS consecutive_failures,
    (SELECT COUNT(*) FROM datasets d WHERE d.source_id = r.source_id) AS dataset_count,
    (SELECT COUNT(*) FROM datasets d WHERE d.source_id = r.source_id
        AND d.acquisition_class = 'A') AS class_a_count
FROM source_registry r
LEFT JOIN source_status s ON s.source_id = r.source_id;

-- Couverture du littoral algérien (produits touchant la fenêtre 0–100 m)
CREATE VIEW IF NOT EXISTS v_algeria_coverage AS
SELECT
    d.uid, d.name, d.source_id, d.acquisition_class,
    d.depth_min_m, d.depth_max_m, d.resolution_m, d.metadata_status,
    CAST(MAX(0.0, MIN(COALESCE(d.depth_max_m,0.0),100.0) - MAX(COALESCE(d.depth_min_m,0.0),0.0)) AS REAL) AS sdb_overlap_m
FROM datasets d
WHERE d.in_algerian_waters = 1;

-- Changements de la fenêtre glissante passée en paramètre via application
CREATE VIEW IF NOT EXISTS v_recent_changes AS
SELECT
    c.id, c.dataset_uid, d.name AS dataset_name, c.source_id, c.change_type,
    c.field_name, c.old_value, c.new_value, c.detected_at, c.run_id
FROM change_log c
LEFT JOIN datasets d ON d.uid = c.dataset_uid
ORDER BY c.detected_at DESC;
