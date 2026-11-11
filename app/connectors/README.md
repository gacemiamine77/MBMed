# Connecteurs de sources (Phases 2 à 4)

Ce dossier est **volontairement vide de code** en Phase 1 : aucun connecteur
n'est livré, et l'application l'indique dans l'interface.

## Contrat prévu

Chaque source dispose d'un connecteur indépendant exposant :

```python
class BaseConnector:
    source_id: str                       # clé de app/core/sources.py

    def probe(self) -> dict:             # disponibilité + version d'API
        ...

    def fetch(self, ctx, bbox=None, since=None) -> list[Dataset]:
        """Retourne des Dataset normalisés (métadonnées uniquement)."""

    def download(self, ctx, dataset, bbox=None, target_dir=None):
        """Phase 7 : téléchargement, sous-ensemble, vérification d'intégrité."""
```

## Règles imposées

* API officielles, STAC, OGC > téléchargement documenté > scraping HTML (dernier recours, signalé).
* Aucune donnée inventée : un champ non renseigné reste `None`.
* Erreurs normalisées : `transient` (réessai), `quota` (attente), `auth` (identifiants),
  `schema_changed` (statut `partial` + message), `unavailable` (source hors ligne).
* Timeout, nombre de tentatives et User-Agent lus dans `SchedulerSettings`.
* Aucun identifiant stocké dans le code ou en base : uniquement l'environnement.

## Ordre de livraison

| Phase | Connecteur |
|---|---|
| 2 | `emodnet.py`, `gebco.py` |
| 3 | `copernicus.py`, `icesat2.py` |
| 4 | `national_hydrographic.py`, `scientific_repositories.py`, `sonar_surveys.py`, `coastal_dtm.py` |
