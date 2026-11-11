"""Registre des sources surveillées (section 3 du cahier des charges).

Une source = une famille de produits, avec ses portails officiels, ses modes
d'accès privilégiés (API, STAC, OGC, téléchargement documenté) et son état
d'implémentation RÉEL.

⚠ Honnêteté d'implémentation : le champ ``implemented`` vaut ``False`` tant que
le connecteur n'est pas livré dans une phase ultérieure. L'interface affiche
ces sources comme « planifiée » et jamais comme opérationnelles.
Le moteur de veille ignore les connecteurs non implémentés au lieu de simuler
des résultats.

Le scraping HTML n'est utilisé qu'en dernier recours, et signalé explicitement
dans ``access_types`` par la valeur ``html_scraping``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.models import ConnectorInfo


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    source_id: str
    label: str
    category: str
    description: str
    institutions: str
    homepage: str
    documentation: str
    access_types: tuple[str, ...]
    products: tuple[str, ...]
    expected_classes: tuple[str, ...]
    licenses: tuple[str, ...]
    requires_credentials: bool = False
    implemented_phase: int = 2
    implemented: bool = False
    known_limits: tuple[str, ...] = field(default_factory=tuple)
    reliability: str = "haute"     # haute | moyenne | variable

    def to_info(self, enabled: bool = True) -> ConnectorInfo:
        return ConnectorInfo(
            source_id=self.source_id,
            label=self.label,
            category=self.category,
            description=self.description,
            homepage=self.homepage,
            documentation=self.documentation,
            access_types=list(self.access_types),
            requires_credentials=self.requires_credentials,
            implemented_phase=self.implemented_phase,
            implemented=self.implemented,
            enabled=enabled,
        )


SOURCES: dict[str, SourceDefinition] = {
    "emodnet": SourceDefinition(
        source_id="emodnet",
        label="EMODnet Bathymetry",
        category="Bathymétrie régionale / compilation",
        description=(
            "Service de bathymétrie européen (consortium EMODnet) : MNT intégrés "
            "à pas variable, produits composites et jeux de mesures source. "
            "Couverture complète de la Méditerranée, y compris le littoral algérien."
        ),
        institutions="EMODnet Bathymetry Consortium (Seabed2030, Ifremer, MARIS…)",
        homepage="https://emodnet.ec.europa.eu/en/bathymetry",
        documentation="https://emodnet.ec.europa.eu/en/bathymetry",
        access_types=("api", "ogc_wms", "subset", "stac", "http_direct"),
        products=("DTM 2024 (1/16 arc-min)", "DTM 2022", "Composite DTM", "Bathymetric surveys", "CDI"),
        expected_classes=("D", "A"),
        licenses=("cc_by", "open_government"),
        implemented_phase=2,
        known_limits=(
            "Le pas de grille (1/16 arc-min ≈ 115 m à 40°N) n'est pas la résolution effective.",
            "Les MNT composites interpolent des levés hétérogènes et anciens.",
            "Le service de sous-ensemble WCS/WMTS doit être interrogé avec des emprises raisonnables.",
        ),
        reliability="haute",
    ),
    "gebco": SourceDefinition(
        source_id="gebco",
        label="GEBCO",
        category="Bathymétrie mondiale / compilation",
        description=(
            "Grille mondiale GEBCO (General Bathymetric Chart of the Oceans), "
            "compilation de levés acoustiques et de prédictions par altimétrie. "
            "Produit de référence pour la couverture régionale et les grandes profondeurs."
        ),
        institutions="GEBCO / IHO-IOC (Nippon Foundation)",
        homepage="https://www.gebco.net/",
        documentation="https://www.gebco.net/data-products",
        access_types=("http_direct", "ogc_wms", "subset"),
        products=("GEBCO_2024 Grid", "GEBCO Sub-ice Topo", "TID Grid", "GEBCO Gazetteer"),
        expected_classes=("D", "B"),
        licenses=("open_government",),
        implemented_phase=2,
        known_limits=(
            "Grille à 15 arc-second (~450 m) : inadaptée à la bathymétrie côtière fine.",
            "Les zones sans levé reposent sur des prédictions altimétriques (classe B).",
            "Mélange de sources non homogènes : la précision verticale varie fortement.",
        ),
        reliability="haute",
    ),
    "copernicus": SourceDefinition(
        source_id="copernicus",
        label="Copernicus Marine Service",
        category="Service opérationnel européen",
        description=(
            "Service Copernicus Marine (CMEMS) : produits physiques et biogéochimiques, "
            "dont la bathymétrie de support des modèles et les variables optiques "
            "nécessaires au SDB (Kd490, Rrs, turbidité)."
        ),
        institutions="Mercator Océan / Copernicus Marine Service (UE)",
        homepage="https://marine.copernicus.eu/",
        documentation="https://data.marine.copernicus.eu/",
        access_types=("api", "subset", "ogc_wcs", "http_direct"),
        products=("Mediterranean Sea Physics", "Ocean Colour", "Bathymétrie de support NEMO"),
        expected_classes=("D", "C"),
        licenses=("copernicus",),
        requires_credentials=True,
        implemented_phase=3,
        known_limits=(
            "Authentification Copernicus obligatoire (compte utilisateur).",
            "Les produits de bathymétrie y sont des grilles de support de modèle, non des levés.",
            "Quotas et politique d'usage à respecter (attribution obligatoire).",
        ),
        reliability="haute",
    ),
    "icesat2": SourceDefinition(
        source_id="icesat2",
        label="NASA ICESat-2 (ATL03 / ATL24)",
        category="Altimétrie laser spatiale",
        description=(
            "Photons ATL03 et produits bathymétriques dérivés ATL24 : mesures de "
            "profondeur côtière en eaux claires, précieuses pour la tranche 0–20 m "
            "et la validation de SDB."
        ),
        institutions="NASA Goddard Space Flight Center / NSIDC",
        homepage="https://icesat-2.gsfc.nasa.gov/",
        documentation="https://icesat-2.gsfc.nasa.gov/science/data",
        access_types=("api", "http_direct", "stac"),
        products=("ATL03 (geolocated photons)", "ATL24 (coastal bathymetry)", "ATL08 (land/veg)"),
        expected_classes=("A", "C"),
        licenses=("open_government",),
        requires_credentials=True,
        implemented_phase=3,
        known_limits=(
            "Compte Earthdata requis ; ATL24 est distribué par des équipes tierces.",
            "Pistes étroites : la couverture spatiale est lacunaire, pas un MNT.",
            "Profondeur maximale limitée par la turbidité (≈ 10–25 m selon les eaux).",
        ),
        reliability="moyenne",
    ),
    "national_hydrographic": SourceDefinition(
        source_id="national_hydrographic",
        label="Portails hydrographiques nationaux méditerranéens",
        category="Sources institutionnelles nationales",
        description=(
            "Services hydrographiques et océanographiques des États riverains "
            "(SHOM France, IHM Espagne, IIM/ISM Italie, NHO Grèce, OHI/INOC Algérie, "
            "etc.) : ENC, cartes marines numérisées, campagnes côtières."
        ),
        institutions="SHOM, IHM, IIM, HNHS, OHI…",
        homepage="https://data.shom.fr/",
        documentation="https://data.shom.fr/",
        access_types=("api", "ogc_wms", "manual", "html_scraping"),
        products=("ENC S-57/S-101", "Cartes marines raster", "Campagnes côtières"),
        expected_classes=("A", "D"),
        licenses=("open_government", "restricted", "commercial"),
        implemented_phase=4,
        known_limits=(
            "Hétérogénéité totale des portails et des conditions d'accès.",
            "Beaucoup de jeux ne sont disponibles que sur demande ou sous licence restreinte.",
            "Les ENC ne contiennent pas de sonde exhaustive : attributs bathymétriques partiels.",
        ),
        reliability="variable",
    ),
    "scientific_repositories": SourceDefinition(
        source_id="scientific_repositories",
        label="Dépôts scientifiques et institutionnels",
        category="Dépôts de données et publications",
        description=(
            "Dépôts de données et littérature scientifique : PANGAEA, Zenodo, SEANOE, "
            "Dryad, OpenAIRE, Crossref, DataCite, HAL — pour détecter les nouvelles "
            "publications décrivant des jeux bathymétriques."
        ),
        institutions="PANGAEA, Zenodo, SEANOE, DataCite, Crossref, HAL",
        homepage="https://www.pangaea.de/",
        documentation="https://zenodo.org/api",
        access_types=("api", "stac", "http_direct"),
        products=("Jeux de données publiés", "Articles et preprints", "DOI de données"),
        expected_classes=("A", "C", "D"),
        licenses=("cc_by", "cc_by_nc", "research_only", "unknown"),
        implemented_phase=4,
        known_limits=(
            "Métadonnées hétérogènes, souvent incomplètes sur la précision verticale.",
            "Les DOI ne garantissent pas la disponibilité effective du fichier.",
            "Nécessite une déduplication croisée entre dépôts.",
        ),
        reliability="moyenne",
    ),
    "sonar_surveys": SourceDefinition(
        source_id="sonar_surveys",
        label="Levés sonar multifaisceaux et monofaisceaux",
        category="Données brutes de levés",
        description=(
            "Campagnes acoustiques : archives de levés MBES/SBES, jeux de points "
            "hydrographiques, bases de campagnes océanographiques. Cœur de la "
            "vérité terrain pour la validation SDB."
        ),
        institutions="Ifremer (Sextant), NCEI, NOAA, IEO, OGS, universités",
        homepage="https://sextant.ifremer.fr/",
        documentation="https://www.ncei.noaa.gov/maps/bathymetry/",
        access_types=("api", "ogc_wms", "http_direct", "subset", "manual"),
        products=("Jeux MBES", "Jeux SBES", "Nuages de points nettoyés"),
        expected_classes=("A",),
        licenses=("open_government", "cc_by", "research_only"),
        implemented_phase=4,
        known_limits=(
            "Les données brutes sont volumineuses et souvent filtrées avant diffusion.",
            "Les métadonnées de précision verticale sont fréquemment absentes.",
            "Couverture spatiale discontinue, dépendante des campagnes.",
        ),
        reliability="moyenne",
    ),
    "coastal_dtm": SourceDefinition(
        source_id="coastal_dtm",
        label="MNT côtiers et cartes marines numérisées",
        category="MNT côtiers / produits dérivés",
        description=(
            "MNT bathymétriques côtiers à haute résolution, modèles topo-bathymétriques "
            "intégrés et cartes marines numérisées (raster, GEBCO TID, produits nationaux)."
        ),
        institutions="Universités, agences côtières, projets européens (Emodnet, Copernicus)",
        homepage="https://emodnet.ec.europa.eu/en/bathymetry",
        documentation="https://www.gebco.net/data-products",
        access_types=("http_direct", "subset", "manual", "ogc_wms"),
        products=("MNT topo-bathy intégrés", "TID Grid", "Cartes marines géoréférencées"),
        expected_classes=("D", "C", "A"),
        licenses=("cc_by", "open_government", "restricted"),
        implemented_phase=4,
        known_limits=(
            "Les MNT topo-bathy fusionnent souvent des sources de précisions très inégales.",
            "Les cartes numérisées conservent les biais et la sélection historique des sondes.",
            "Résolution affichée souvent confondue avec la résolution effective.",
        ),
        reliability="variable",
    ),
}

SOURCE_ORDER = tuple(SOURCES.keys())


def get_source(source_id: str) -> SourceDefinition | None:
    return SOURCES.get(source_id)


def list_sources(implemented_only: bool = False) -> list[SourceDefinition]:
    sources = [SOURCES[sid] for sid in SOURCE_ORDER]
    if implemented_only:
        return [s for s in sources if s.implemented]
    return sources


def implemented_source_ids() -> tuple[str, ...]:
    return tuple(s.source_id for s in SOURCES.values() if s.implemented)


def source_label(source_id: str) -> str:
    src = SOURCES.get(source_id)
    return src.label if src else source_id


def source_url(source_id: str) -> str:
    src = SOURCES.get(source_id)
    return src.homepage if src else ""
