# Sources surveillées, accès et limites — MBM

Résumé opérationnel des 8 familles exigées par la section 3 du cahier des charges.
La référence de code est `app/core/sources.py` ; ce document explicite les accès
privilégiés, les limites **et le plan de connecteur** de chaque famille.

> Hiérarchie d'accès imposée : **API officielle → catalogue STAC → service OGC →
> téléchargement documenté → scraping HTML (dernier recours, signalé)**.

---

## 1. EMODnet Bathymetry — `emodnet`

| | |
|---|---|
| Institutions | EMODnet Bathymetry Consortium (Ifremer, MARIS, Seabed2030…) |
| Portail | https://emodnet.ec.europa.eu/en/bathymetry |
| Accès privilégiés | API, OGC WMS, sous-ensemble par emprise, STAC, HTTP direct |
| Produits | DTM 2024 (1/16′), DTM 2022, DTM composite, *Bathymetric surveys* (CDI) |
| Classes attendues | **D** (DTM) et **A** (levés source) |
| Licences | CC-BY / licence ouverte UE |
| Phase | **2** |

**Limites retenues**
* Pas de grille ≈ 1/16′ (**≈ 115 m à 40° N**) : ce n'est **pas** la résolution effective.
* Le DTM composite interpole des levés d'âges et de qualités hétérogènes.
* Les requêtes de sous-ensemble doivent rester d'une taille raisonnable (quotas).

**Plan connecteur (phase 2)** : interroger l'index CDI (métadonnées de campagnes,
pas de gros volumes), extraire les emprises et les années, calculer les empreintes ;
les MNT ne seront téléchargés qu'à la demande, par emprise.

---

## 2. GEBCO — `gebco`

| | |
|---|---|
| Institutions | GEBCO / IHO-IOC (Nippon Foundation) |
| Portail | https://www.gebco.net/data-products |
| Accès privilégiés | HTTP direct, OGC WMS, sélection d'emprise (`download.gebco.net`) |
| Produits | GEBCO_2024 Grid, TID Grid, gazetteer |
| Classes attendues | **D** (grille), **B** (zones prédites par altimétrie) |
| Licences | usage ouvert avec attribution |
| Phase | **2** |

**Limites retenues**
* 15 arc-secondes ≈ **450 m** : inadapté à la bathymétrie côtière fine.
* Les zones sans levé sont des **prédictions altimétriques** (classe B) : profondeur
  lissée, à ne jamais utiliser comme vérité terrain.
* Précision verticale très variable selon les sources fusionnées.

**Plan connecteur (phase 2)** : suivre la publication annuelle de la grille
(version + date), télécharger la fiche technique et le TID ; la grille mondiale
n'est pas téléchargée en Phase 2.

---

## 3. Copernicus Marine Service — `copernicus`

| | |
|---|---|
| Institutions | Mercator Océan / Copernicus Marine (UE) |
| Portail | https://data.marine.copernicus.eu/ |
| Accès privilégiés | API (client Copernicus Marine), sous-ensemble, WCS, HTTP |
| Produits | Mediterranean Sea Physics (bathymétrie de support NEMO), Ocean Colour (Rrs, Kd490) |
| Classes attendues | **D** (grille de modèle), **C** (contexte optique SDB) |
| Licences | Licence Copernicus (attribution obligatoire) |
| Identifiants | **requis** (compte utilisateur) |
| Phase | **3** |

**Limites retenues**
* La bathymétrie diffusée est une **grille de forçage de modèle** (≈ 1/24°, ~4,6 km),
  pas un levé.
* Les variables optiques sont un **contexte pour le SDB**, pas une bathymétrie.
* Authentification obligatoire ; quotas et politique d'usage à respecter.

**Plan connecteur (phase 3)** : catalogue produit via l'API (liste des jeux et
versions), métadonnées seules ; aucun identifiant n'est stocké en clair, il est
lu dans l'environnement ou saisi par l'utilisateur dans les paramètres.

---

## 4. NASA ICESat-2 (ATL03 / ATL24) — `icesat2`

| | |
|---|---|
| Institutions | NASA GSFC / NSIDC (ATL24 : équipes scientifiques tierces) |
| Portail | https://icesat-2.gsfc.nasa.gov/science/data |
| Accès privilégiés | API/portail NSIDC, HTTP direct, STAC |
| Produits | ATL03 (photons géolocalisés), ATL24 (bathymétrie côtière dérivée) |
| Classes attendues | **A** (mesure laser) et **C** (dérivé) |
| Licences | usage ouvert (NASA) |
| Identifiants | **requis** (Earthdata) |
| Phase | **3** |

**Limites retenues**
* Pistes étroites et espacées : **couverture discontinue**, ce n'est pas un MNT.
* Profondeur utile limitée par la turbidité (≈ 10–25 m ; Méditerranée souvent < 20 m).
* ATL24 est distribué hors Earthdata par les équipes produit : disponibilité variable.
* Référence verticale **ellipsoïdale** → conversion en MSL nécessaire avant usage.

**Plan connecteur (phase 3)** : suivi des versions de produit (ATL03 v006, ATL24 v001)
et des notes de version ; pas de téléchargement massif de photons.

---

## 5. Portails hydrographiques nationaux — `national_hydrographic`

| | |
|---|---|
| Institutions | SHOM (FR), IHM (ES), IIM (IT), HNHS (GR), OHI/INOC (DZ), etc. |
| Portails | https://data.shom.fr/ et équivalents nationaux |
| Accès privilégiés | API, OGC WMS, téléchargement manuel, **scraping HTML en dernier recours** |
| Produits | ENC S-57/S-101, cartes marines raster, campagnes côtières |
| Classes attendues | **A** (sondes) et **D** (produits dérivés) |
| Licences | variable : ouverte, restreinte ou commerciale |
| Phase | **4** |

**Limites retenues**
* Hétérogénéité totale des portails, des formats et des conditions d'accès.
* Beaucoup de jeux ne sont disponibles que **sur demande** ou sous licence restrictive.
* Les ENC ne contiennent **pas** une couverture exhaustive de sondes : attributs
  bathymétriques partiels, sélection historique.

**Plan connecteur (phase 4)** : un sous-connecteur par pays, capacités déclaratives,
repli systématique sur « accès manuel » avec lien officiel (déjà géré par l'UI
Téléchargements).

---

## 6. Dépôts scientifiques et institutionnels — `scientific_repositories`

| | |
|---|---|
| Institutions | PANGAEA, Zenodo, SEANOE, DataCite, Crossref, HAL |
| Accès privilégiés | API REST documentées, STAC (Zenodo), HTTP |
| Produits | jeux de données publiés, articles, DOI de données |
| Classes attendues | **A**, **C**, **D** |
| Licences | CC-BY, CC-BY-NC, usage recherche, parfois non précisée |
| Phase | **4** |

**Limites retenues**
* Métadonnées hétérogènes, souvent muettes sur la précision verticale.
* Un DOI ne garantit pas la disponibilité effective du fichier.
* Doublons fréquents entre dépôts → déduplication obligatoire (`identity_key`).

**Plan connecteur (phase 4)** : interrogation par mots-clés (`bathymetry`,
`Mediterranean`, `multibeam`, `SDB`), avec emprise et date ; chaque publication
est enregistrée avec `verified = 0` tant qu'un humain n'a pas validé.

---

## 7. Levés sonar multifaisceaux / monofaisceaux — `sonar_surveys`

| | |
|---|---|
| Institutions | Ifremer (Sextant/SISMER), NOAA NCEI, IEO, OGS, universités |
| Accès privilégiés | API, OGC WMS, HTTP direct, sous-ensemble, manuel |
| Produits | jeux MBES, jeux SBES, nuages de points nettoyés (BAG, XYZ, LAS) |
| Classes attendues | **A** |
| Licences | ouverte, CC-BY ou recherche |
| Phase | **4** |

**Limites retenues**
* Volumétrie importante ; les données diffusées sont souvent **filtrées/nettoyées**.
* Précision verticale fréquemment absente des métadonnées.
* Couverture discontinue, dépendante des campagnes réalisées.

**Plan connecteur (phase 4)** : indexation des campagnes (nom, année, emprise,
navire, capteur), sans aspirer les fichiers bruts. C'est la source prioritaire
pour constituer la vérité terrain du projet SDB.

---

## 8. MNT côtiers et cartes marines numérisées — `coastal_dtm`

| | |
|---|---|
| Institutions | universités, agences côtières, projets européens |
| Accès privilégiés | HTTP direct, sous-ensemble, OGC WMS, manuel |
| Produits | MNT topo-bathymétriques intégrés, GEBCO TID, cartes géoréférencées |
| Classes attendues | **D**, **C**, **A** selon la provenance des cellules |
| Licences | CC-BY, licence ouverte, restreinte |
| Phase | **4** |

**Limites retenues**
* Les MNT topo-bathy fusionnent des sources de précisions très inégales : la
  résolution affichée masque souvent des données de qualité très variable.
* Les cartes numérisées conservent biais et sélection historique des sondes.

**Plan connecteur (phase 4)** : collecte des fiches produit et de la documentation
technique (rapport de production), indispensables pour qualifier la « résolution
effective » exigée par le cahier des charges.

---

## 9. Matrice de synthèse

| Source | Accès | Identifiants | Classe dominante | Profondeur utile | Phase |
|---|---|---|---|---|---|
| EMODnet | API/WCS/STAC | non | D (+A pour les levés) | 0–5000 m | 2 |
| GEBCO | HTTP/WMS | non | D/B | 0–5500 m | 2 |
| Copernicus Marine | API | **oui** | D (support de modèle) | non pertinent en bathymétrie | 3 |
| ICESat-2 (ATL03/24) | API/STAC | **oui** (Earthdata) | A | 0–25 m | 3 |
| Portails nationaux | API/WMS/manuel | variable | A | 0–4000 m | 4 |
| Dépôts scientifiques | API REST | parfois | A/C/D | variable | 4 |
| Levés sonar | API/HTTP | parfois | **A** | 5–4500 m | 4 |
| MNT côtiers / cartes | HTTP/manuel | parfois | D | -10 à 150 m | 4 |

## 10. Règles de conformité appliquées

1. **Licences** : la licence de chaque produit est stockée (`license`, `license_url`)
   et affichée ; aucune donnée n'est redistribuée par l'application.
2. **Limites d'accès** : délai d'expiration, nombre de tentatives et *user-agent*
   identifiant le projet sont paramétrables (`SchedulerSettings`).
3. **Quotas** : la veille privilégie les **métadonnées** (catalogues, index, STAC)
   et ne télécharge les MNT que sur action explicite de l'utilisateur.
4. **Scraping** : uniquement lorsque aucune API n'existe, signalé par
   `html_scraping` dans `access_types`, et jamais utilisé pour des données
   volumineuses.
5. **Changements de format** : chaque connecteur devra encapsuler son parseur et
   signaler un `status = partial` plutôt que produire des métadonnées douteuses ;
   les erreurs sont journalisées (`source_status.last_message`, `change_log`).
