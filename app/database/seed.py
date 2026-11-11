"""Jeu de données de référence de la Phase 1 (initialisation du catalogue).

⚠ IMPORTANT — NATURE DE CES DONNÉES
Ces fiches servent à peupler l'interface et à tester le schéma de base. Elles
décrivent des produits publics RÉELS (EMODnet DTM, GEBCO, ICESat-2, etc.),
mais leurs valeurs numériques (résolution, emprise, profondeurs, licences)
sont des ordres de grandeur issus de la documentation publique et doivent être
CONFIRMÉES par les connecteurs des phases 2 à 4 avant tout usage scientifique.

C'est pourquoi chaque fiche porte :
    * data_origin = "seed"  (distinguée de "connector" et "manual")
    * metadata_status = "unverified"
    * un tag « jeu-de-demonstration »
    * une note explicite affichée dans l'interface.

Le module ne prétend donc pas fournir un catalogue validé : il fournit un
catalogue de travail honnêtement étiqueté.
"""
from __future__ import annotations

from app.core.models import BBox, Dataset, utcnow
from app.database.repository import Repository

SEED_TAG = "jeu-de-demonstration"
SEED_NOTE = (
    "Fiche d'initialisation (Phase 1) : produit public réel, valeurs numériques "
    "à confirmer par le connecteur officiel avant usage scientifique."
)
SEED_TAG_LABEL = "Démonstration"


def _common(**kwargs) -> dict:
    kwargs.setdefault("tags", [SEED_TAG])
    kwargs.setdefault("metadata_status", "unverified")
    kwargs.setdefault("status", "new")
    kwargs.setdefault("notes", SEED_NOTE)
    return kwargs


SEED_DATASETS: list[Dataset] = [
    # ---------------------------------------------------------------- EMODnet
    Dataset(**_common(
        source_id="emodnet",
        source_item_id="emodnet-dtm-2024",
        name="EMODnet Bathymetry DTM 2024 (Méditerranée)",
        producer="EMODnet Bathymetry Consortium",
        description=(
            "MNT bathymétrique européen harmonisé, grille à 1/16 d'arc-minute "
            "(≈ 115 m à 40° N). Compilation de levés hétérogènes (multifaisceaux, "
            "monofaisceaux, cartes marines, altimétrie prédite)."
        ),
        official_url="https://emodnet.ec.europa.eu/en/bathymetry",
        download_url="https://emodnet.ec.europa.eu/en/bathymetry",
        access_mode="subset",
        publication_date="2024-06-01",
        update_date="2024-06-01",
        version="2024",
        bbox=BBox(-6.0, 30.0, 36.2, 46.0),
        region="Méditerranée",
        countries=["FR", "ES", "IT", "GR", "DZ", "MA", "TN", "LY", "EG", "TR"],
        resolution_m=115.0,
        effective_resolution_m=None,
        resolution_note="Pas de grille ≈ 1/16 arc-min ; résolution effective variable selon les levés sources.",
        depth_min_m=0.0,
        depth_max_m=5200.0,
        vertical_reference="MSL (référence verticale du DTM)",
        vertical_accuracy_m=None,
        uncertainty_note="Incertitude fournie par bandes d'erreur EMODnet ; non renseignée ici.",
        acquisition_method="interpolation",
        acquisition_class="D",
        platform="Multiple (navires, données historiques)",
        license="cc_by",
        license_url="https://emodnet.ec.europa.eu/en/bathymetry",
        data_format="netcdf",
        file_size_mb=None,
        download_method="Sous-ensemble par emprise (service de sélection EMODnet)",
    )),
    Dataset(**_common(
        source_id="emodnet",
        source_item_id="emodnet-dtm-2022",
        name="EMODnet Bathymetry DTM 2022 (Méditerranée)",
        producer="EMODnet Bathymetry Consortium",
        description="Version antérieure du DTM EMODnet, utile pour l'analyse de versions et la comparaison.",
        official_url="https://emodnet.ec.europa.eu/en/bathymetry",
        publication_date="2022-05-01",
        update_date="2022-05-01",
        version="2022",
        bbox=BBox(-6.0, 30.0, 36.2, 46.0),
        region="Méditerranée",
        resolution_m=115.0,
        resolution_note="Pas de grille 1/16 arc-min.",
        depth_min_m=0.0,
        depth_max_m=5200.0,
        vertical_reference="MSL",
        acquisition_method="interpolation",
        acquisition_class="D",
        license="cc_by",
        data_format="netcdf",
        download_method="Sous-ensemble par emprise",
    )),
    Dataset(**_common(
        source_id="emodnet",
        source_item_id="emodnet-surveys-cdi",
        name="EMODnet Bathymetric Surveys (CDI) — Méditerranée",
        producer="EMODnet Bathymetry Consortium",
        description=(
            "Catalogue des levés bathymétriques source (index CDI) : campagnes "
            "multifaisceaux et monofaisceaux géoréférencées, avec métadonnées de campagne."
        ),
        official_url="https://emodnet.ec.europa.eu/geoviewer/",
        access_mode="api",
        publication_date="2024-01-01",
        update_date="2024-09-01",
        version="continu",
        bbox=BBox(-5.9, 30.5, 36.0, 45.8),
        region="Méditerranée",
        resolution_m=None,
        resolution_note="Levés ponctuels : pas de résolution de grille.",
        depth_min_m=0.0,
        depth_max_m=4000.0,
        vertical_reference="Variable selon campagne",
        acquisition_method="mbes",
        acquisition_class="A",
        platform="Navires océanographiques",
        license="cc_by",
        data_format="xyz",
        download_method="API CDI / téléchargement par campagne",
    )),
    # ------------------------------------------------------------------ GEBCO
    Dataset(**_common(
        source_id="gebco",
        source_item_id="gebco-2024-grid",
        name="GEBCO_2024 Grid",
        producer="GEBCO / IHO-IOC",
        description=(
            "Grille mondiale à 15 secondes d'arc (≈ 450 m) combinant levés "
            "acoustiques et prédictions par altimétrie satellitaire."
        ),
        official_url="https://www.gebco.net/data-products-gridded-bathymetry-data",
        download_url="https://download.gebco.net/",
        access_mode="subset",
        publication_date="2024-04-25",
        update_date="2024-04-25",
        version="2024",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée (extrait d'un produit mondial)",
        resolution_m=450.0,
        resolution_note="15 arc-second ≈ 463 m à l'équateur, ≈ 355 m à 40° N.",
        depth_min_m=0.0,
        depth_max_m=5200.0,
        vertical_reference="MSL",
        acquisition_method="interpolation",
        acquisition_class="D",
        license="open_government",
        data_format="netcdf",
        download_method="Sélection d'emprise sur download.gebco.net (manuel ou scriptable)",
    )),
    Dataset(**_common(
        source_id="gebco",
        source_item_id="gebco-2024-tid",
        name="GEBCO TID Grid 2024",
        producer="GEBCO / IHO-IOC",
        description="Grille d'identification des sources (TID) indiquant le type de donnée à l'origine de chaque cellule.",
        official_url="https://www.gebco.net/data-products-gridded-bathymetry-data",
        publication_date="2024-04-25",
        version="2024",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée",
        resolution_m=450.0,
        depth_min_m=0.0,
        depth_max_m=5200.0,
        acquisition_method="interpolation",
        acquisition_class="D",
        license="open_government",
        data_format="netcdf",
        download_method="Téléchargement direct",
    )),
    # ------------------------------------------------------------ Copernicus
    Dataset(**_common(
        source_id="copernicus",
        source_item_id="cmems-med-physics",
        name="Copernicus Marine — Mediterranean Sea Physics (bathymétrie de support)",
        producer="Mercator Océan / Copernicus Marine Service",
        description=(
            "Grille de bathymétrie utilisée par le modèle physique méditerranéen "
            "(≈ 1/24°). Sert de support de modèle, pas de levé bathymétrique."
        ),
        official_url="https://data.marine.copernicus.eu/product/MEDSEA_MULTIYEAR_PHY_006_004/description",
        access_mode="api",
        publication_date="2023-01-01",
        update_date="2025-01-01",
        version="v3",
        bbox=BBox(-18.13, 30.19, 36.29, 45.98),
        region="Méditerranée",
        resolution_m=4600.0,
        resolution_note="1/24° ≈ 4,6 km ; grille de forçage de modèle.",
        depth_min_m=0.0,
        depth_max_m=5000.0,
        vertical_reference="Non applicable (grille de support)",
        acquisition_method="interpolation",
        acquisition_class="D",
        license="copernicus",
        data_format="netcdf",
        download_method="Client Copernicus Marine (authentification requise)",
    )),
    Dataset(**_common(
        source_id="copernicus",
        source_item_id="cmems-oc-med",
        name="Copernicus Marine — Ocean Colour Méditerranée (Rrs, Kd490)",
        producer="Copernicus Marine Service",
        description=(
            "Variables optiques (réflectance marine, coefficient d'atténuation) "
            "indispensables à la correction atmosphérique et à l'inversion SDB. "
            "Ce n'est pas une bathymétrie : produit de contexte pour la classe C."
        ),
        official_url="https://data.marine.copernicus.eu/products",
        access_mode="api",
        publication_date="2023-06-01",
        update_date="2025-06-01",
        version="v2",
        bbox=BBox(-18.13, 30.19, 36.29, 45.98),
        region="Méditerranée",
        resolution_m=1000.0,
        resolution_note="≈ 1 km (L3) pour les produits océan couleur.",
        depth_min_m=None,
        depth_max_m=None,
        acquisition_method="sdb_optical",
        acquisition_class="C",
        platform="Sentinel-3 OLCI / MODIS / VIIRS",
        sensor="OLCI, MODIS-Aqua",
        license="copernicus",
        data_format="netcdf",
        download_method="Client Copernicus Marine (authentification requise)",
        notes=("Produit de contexte optique, non bathymétrique. " + SEED_NOTE),
    )),
    # -------------------------------------------------------------- ICESat-2
    Dataset(**_common(
        source_id="icesat2",
        source_item_id="atl03-v006",
        name="ICESat-2 ATL03 — photons géolocalisés (Méditerranée)",
        producer="NASA Goddard Space Flight Center",
        description=(
            "Nuages de photons géolocalisés (ATL03) : matière première du lidar "
            "spatial, exploitable en eaux claires pour la tranche 0-20 m."
        ),
        official_url="https://icesat-2.gsfc.nasa.gov/science/data",
        access_mode="api",
        publication_date="2019-01-01",
        update_date="2025-01-01",
        version="006",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée (extrait d'un produit mondial)",
        resolution_m=0.7,
        resolution_note="Empreinte laser ≈ 17 m ; échantillonnage le long de pistes espacées de plusieurs km.",
        depth_min_m=0.0,
        depth_max_m=25.0,
        vertical_reference="Ellipsoïde WGS84 (photon) / MSL après correction",
        vertical_accuracy_m=0.1,
        acquisition_method="lidar_icesat2",
        acquisition_class="A",
        platform="ICESat-2 (ATLAS)",
        sensor="ATLAS",
        license="open_government",
        data_format="las",
        download_method="Earthdata (authentification) / API NSIDC",
    )),
    Dataset(**_common(
        source_id="icesat2",
        source_item_id="atl24",
        name="ICESat-2 ATL24 — bathymétrie côtière dérivée",
        producer="NASA / équipes scientifiques ATL24",
        description=(
            "Produit dérivé d'ATL03 fournissant des classifications de photons "
            "de fond et des estimations de profondeur en zone côtière."
        ),
        official_url="https://icesat-2.gsfc.nasa.gov/science/data",
        access_mode="http_direct",
        publication_date="2023-06-01",
        update_date="2025-01-01",
        version="001",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée (extrait)",
        resolution_m=0.7,
        resolution_note="Pistes lidar ; couverture spatiale discontinue.",
        depth_min_m=0.0,
        depth_max_m=20.0,
        vertical_reference="Ellipsoïde WGS84 (à convertir en MSL)",
        vertical_accuracy_m=None,
        acquisition_method="lidar_icesat2",
        acquisition_class="A",
        platform="ICESat-2",
        license="open_government",
        data_format="netcdf",
        download_method="Téléchargement par équipe produit / Earthdata",
    )),
    # --------------------------------------------------- Services nationaux
    Dataset(**_common(
        source_id="national_hydrographic",
        source_item_id="shom-mnt-med",
        name="SHOM — MNT bathymétrique de façade Méditerranée",
        producer="SHOM (France)",
        description=(
            "Modèles numériques de terrain bathymétriques des façades maritimes "
            "françaises, issus de levés hydrographiques et de cartes marines."
        ),
        official_url="https://data.shom.fr/",
        access_mode="ogc_wcs",
        publication_date="2023-01-01",
        version="non précisée",
        bbox=BBox(2.5, 41.3, 7.7, 43.9),
        region="Golfe du Lion / Provence / Corse",
        resolution_m=10.0,
        resolution_note="Résolution annoncée de l'ordre de 10 m en zone levée ; variable.",
        depth_min_m=0.0,
        depth_max_m=2600.0,
        vertical_reference="ZH (zéro hydrographique)",
        acquisition_method="mbes",
        acquisition_class="A",
        license="open_government",
        data_format="geotiff",
        download_method="Diffusion via data.shom.fr (WCS / téléchargement)",
    )),
    Dataset(**_common(
        source_id="national_hydrographic",
        source_item_id="enc-s57-med",
        name="Cartes marines électroniques (ENC S-57) — Méditerranée",
        producer="Services hydrographiques nationaux (coordination OHI)",
        description=(
            "Attributs bathymétriques des ENC : sondes ponctuelles, courbes "
            "bathymétriques, zones de profondeur. Couverture côtière dense là où "
            "les cellules ENC sont disponibles."
        ),
        official_url="https://www.iho.int/",
        access_mode="manual",
        publication_date="2024-01-01",
        update_date="2025-01-01",
        version="mise à jour hebdomadaire",
        bbox=BBox(-5.9, 30.2, 36.2, 45.9),
        region="Méditerranée",
        resolution_m=None,
        resolution_note="Sondes ponctuelles et courbes ; pas de grille régulière.",
        depth_min_m=0.0,
        depth_max_m=4000.0,
        vertical_reference="ZH / LAT selon pays",
        acquisition_method="nautical_chart",
        acquisition_class="A",
        license="restricted",
        data_format="bathy_att",
        download_method="Accès national ou commercial (variable)",
    )),
    # ------------------------------------------- Dépôts scientifiques / littérature
    Dataset(**_common(
        source_id="scientific_repositories",
        source_item_id="pangaea-bathy-med",
        name="PANGAEA — jeux bathymétriques publiés (Méditerranée)",
        producer="PANGAEA / MARUM / AWI",
        description=(
            "Dépôt de données de campagnes publiées, avec DOI. Contient des jeux "
            "de profondeur ponctuels, des compilations et des levés rattachés à "
            "des publications scientifiques."
        ),
        official_url="https://www.pangaea.de/",
        access_mode="api",
        update_date="2025-01-01",
        version="continu",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée",
        resolution_m=None,
        depth_min_m=0.0,
        depth_max_m=5000.0,
        vertical_reference="Variable selon jeu",
        acquisition_method="unknown",
        acquisition_class="A",
        license="cc_by",
        data_format="csv",
        download_method="API PANGAEA (REST) / DOI",
    )),
    # ------------------------------------------------------ Levés sonar
    Dataset(**_common(
        source_id="sonar_surveys",
        source_item_id="ncei-multibeam-med",
        name="NCEI Multibeam Bathymetry Database — extraits Méditerranée",
        producer="NOAA National Centers for Environmental Information",
        description=(
            "Archive mondiale de levés multifaisceaux (BAG, XYZ, grids) avec "
            "métadonnées de campagne. Source de vérité terrain de premier ordre."
        ),
        official_url="https://www.ncei.noaa.gov/maps/bathymetry/",
        access_mode="api",
        publication_date="2024-01-01",
        update_date="2025-01-01",
        version="continu",
        bbox=BBox(-6.0, 30.0, 36.5, 46.0),
        region="Méditerranée (extraits de campagnes)",
        resolution_m=None,
        resolution_note="Résolution dépendante du levé (quelques mètres à quelques dizaines de mètres).",
        depth_min_m=5.0,
        depth_max_m=4500.0,
        vertical_reference="Variable selon campagne (souvent MSL)",
        acquisition_method="mbes",
        acquisition_class="A",
        platform="Navires de recherche",
        license="open_government",
        data_format="las",
        download_method="Serveur de téléchargement NCEI (par campagne)",
    )),
    Dataset(**_common(
        source_id="sonar_surveys",
        source_item_id="sextant-campagnes-med",
        name="Ifremer Sextant — campagnes océanographiques Méditerranée",
        producer="Ifremer",
        description=(
            "Catalogue de campagnes (SISMER/Sextant) avec données bathymétriques "
            "associées : levés côtiers et hauturiers en Méditerranée occidentale."
        ),
        official_url="https://sextant.ifremer.fr/",
        access_mode="api",
        publication_date="2023-01-01",
        update_date="2025-01-01",
        version="continu",
        bbox=BBox(-2.0, 35.5, 9.5, 44.0),
        region="Méditerranée occidentale / bassin algérien",
        resolution_m=None,
        depth_min_m=5.0,
        depth_max_m=4000.0,
        vertical_reference="Variable selon campagne",
        acquisition_method="mbes",
        acquisition_class="A",
        platform="Navires Ifremer (Pourquoi pas ?, Thalassa…)",
        license="research_only",
        data_format="other",
        download_method="Demande / téléchargement via Sextant",
    )),
    # ---------------------------------------------- MNT côtiers / produits dérivés
    Dataset(**_common(
        source_id="coastal_dtm",
        source_item_id="emodnet-coastal-dtm",
        name="MNT topo-bathymétrique côtier intégré — Méditerranée",
        producer="Projets européens / agences côtières",
        description=(
            "Modèles topo-bathymétriques continus (terre-mer) destinés aux études "
            "côtières : fusion de lidar topographique, levés bathymétriques et "
            "cartes marines. À utiliser avec prudence (précisions hétérogènes)."
        ),
        official_url="https://emodnet.ec.europa.eu/en/bathymetry",
        access_mode="http_direct",
        update_date="2025-01-01",
        version="non précisée",
        bbox=BBox(-2.5, 35.0, 9.5, 37.6),
        region="Littoral algérien (zone de démonstration)",
        resolution_m=25.0,
        resolution_note="Résolution affichée ≠ résolution effective : vérifier la provenance des cellules.",
        depth_min_m=-10.0,
        depth_max_m=150.0,
        vertical_reference="Variable (souvent MSL pour la partie marine)",
        acquisition_method="interpolation",
        acquisition_class="D",
        license="cc_by",
        data_format="geotiff",
        download_method="Téléchargement direct (selon produit)",
        notes=("Emprise de démonstration sur le littoral algérien. " + SEED_NOTE),
    )),
]


def seed_is_loaded(repo: Repository) -> bool:
    n = repo.db.scalar(
        "SELECT COUNT(*) FROM datasets WHERE data_origin = 'seed'", ()
    )
    return bool(n)


def load_seed_data(repo: Repository, force: bool = False) -> dict[str, int]:
    """Charge le jeu de référence. Idempotent (upsert par uid)."""
    from app.geospatial.geometry import enrich_geometry  # import tardif (dépendances)

    if not force and seed_is_loaded(repo):
        return {"inserted": 0, "updated": 0, "skipped": len(SEED_DATASETS)}

    inserted = updated = 0
    for ds in SEED_DATASETS:
        candidate = _clone(ds)
        enrich_geometry(candidate)
        candidate.last_checked = None
        outcome = repo.upsert_dataset(candidate, origin="seed")
        if outcome == "new":
            inserted += 1
        elif outcome == "updated":
            updated += 1
    repo.audit("seed_loaded", entity="catalogue",
               details={"inserted": inserted, "updated": updated})
    return {"inserted": inserted, "updated": updated, "skipped": 0}


def _clone(ds: Dataset) -> Dataset:
    """Copie défensive : le seed peut être rechargé sans effet de bord."""
    from dataclasses import replace

    clone = replace(ds)
    clone.countries = list(ds.countries)
    clone.tags = list(ds.tags)
    clone.raw_metadata = dict(ds.raw_metadata)
    clone.first_seen = utcnow()
    return clone


def seed_summary() -> dict[str, object]:
    return {
        "count": len(SEED_DATASETS),
        "sources": sorted({d.source_id for d in SEED_DATASETS}),
        "tag": SEED_TAG,
        "note": SEED_NOTE,
    }
