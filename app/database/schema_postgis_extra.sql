-- ============================================================================
--  Enrichissements PostgreSQL / PostGIS
--  Appliqués uniquement en mode backend = postgresql, APRÈS le schéma portable.
--  Objectif : géométries indexées (GiST), surfaces calculées en CRS projeté,
--  et recherche spatiale performante (phase 5).
--  Remarque : PostGIS conserve l'emprise d'origine en EPSG:4326 ; les surfaces
--  sont calculées dans un CRS adapté (LAEA Méditerranée) sans altérer la donnée.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- Colonne géométrique principale (emprise du produit)
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS geom geometry(Polygon, 4326);
CREATE INDEX IF NOT EXISTS idx_datasets_geom ON datasets USING GIST (geom);

ALTER TABLE footprints ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);
CREATE INDEX IF NOT EXISTS idx_footprints_geom ON footprints USING GIST (geom);

-- Alimente automatiquement geom depuis le JSON d'emprise si absent
CREATE OR REPLACE FUNCTION mbm_sync_dataset_geom() RETURNS trigger AS $$
BEGIN
    IF NEW.bbox IS NOT NULL AND NEW.geom IS NULL THEN
        NEW.geom := ST_MakeEnvelope(
            (NEW.bbox::jsonb ->> 0)::float8,
            (NEW.bbox::jsonb ->> 1)::float8,
            (NEW.bbox::jsonb ->> 2)::float8,
            (NEW.bbox::jsonb ->> 3)::float8,
            4326
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_datasets_geom ON datasets;
CREATE TRIGGER trg_datasets_geom
    BEFORE INSERT OR UPDATE ON datasets
    FOR EACH ROW EXECUTE FUNCTION mbm_sync_dataset_geom();

-- Surfaces exactes en projection LAEA Méditerranée (m² -> km²)
CREATE OR REPLACE VIEW v_dataset_areas AS
SELECT
    d.uid,
    d.name,
    d.acquisition_class,
    ST_Area(ST_Transform(d.geom, '+proj=laea +lat_0=38 +lon_0=15 +datum=WGS84 +units=m')) / 1e6 AS area_km2
FROM datasets d
WHERE d.geom IS NOT NULL;

-- Emprises intersectant le littoral algérien (buffer côtier de 50 km)
CREATE OR REPLACE VIEW v_algeria_intersect AS
SELECT d.uid, d.name, d.source_id, d.acquisition_class,
       ST_Area(ST_Intersection(
           ST_Transform(d.geom, '+proj=laea +lat_0=38 +lon_0=15 +datum=WGS84 +units=m'),
           ST_Transform(ST_MakeEnvelope(-2.5, 35.0, 9.5, 37.6, 4326),
                        '+proj=laea +lat_0=38 +lon_0=15 +datum=WGS84 +units=m')
       )) / 1e6 AS intersect_km2
FROM datasets d
WHERE d.geom IS NOT NULL;
