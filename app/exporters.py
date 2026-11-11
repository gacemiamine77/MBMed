"""Exports de données (CSV, Excel, JSON, GeoJSON).

Une seule implémentation, réutilisée par les pages Recherche, Catalogue,
Rapports et Téléchargements. Les exports conservent les valeurs originales :
aucune conversion implicite d'unité ni de datum.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

log = logging.getLogger(__name__)

#: Colonnes exportées (ordre stable, libellés français)
EXPORT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("uid", "Identifiant"),
    ("name", "Nom du produit"),
    ("source_id", "Source"),
    ("producer", "Producteur"),
    ("official_url", "URL officielle"),
    ("doi", "DOI"),
    ("publication_date", "Date de publication"),
    ("update_date", "Dernière mise à jour"),
    ("version", "Version"),
    ("acquisition_class", "Classe"),
    ("acquisition_method", "Méthode d'acquisition"),
    ("resolution_m", "Résolution nominale (m)"),
    ("effective_resolution_m", "Résolution effective (m)"),
    ("depth_min_m", "Profondeur min (m)"),
    ("depth_max_m", "Profondeur max (m)"),
    ("vertical_reference", "Référence verticale"),
    ("vertical_accuracy_m", "Précision verticale (m)"),
    ("license", "Licence"),
    ("data_format", "Format"),
    ("file_size_mb", "Taille (Mo)"),
    ("access_mode", "Mode d'accès"),
    ("download_url", "URL de téléchargement"),
    ("metadata_status", "Statut métadonnées"),
    ("metadata_completeness", "Complétude (%)"),
    ("last_checked", "Dernière vérification"),
    ("status", "Statut"),
    ("in_algerian_waters", "Littoral algérien"),
    ("coastal", "Côtier"),
    ("bbox_minx", "Lon min"),
    ("bbox_miny", "Lat min"),
    ("bbox_maxx", "Lon max"),
    ("bbox_maxy", "Lat max"),
    ("data_origin", "Origine des données"),
)


def _rows_to_dicts(rows: Iterable[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
        else:  # Dataset
            out.append(row.to_row())
    return out


def export_datasets_csv(rows: Iterable[Any], path: str | Path,
                        columns: Sequence[tuple[str, str]] = EXPORT_COLUMNS) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _rows_to_dicts(rows)
    # utf-8-sig : ouverture correcte des accents dans Excel
    with target.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow([label for _, label in columns])
        for row in data:
            writer.writerow([_cell(row.get(key)) for key, _ in columns])
    log.info("Export CSV: %s (%d lignes)", target, len(data))
    return target


def export_datasets_json(rows: Iterable[Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _rows_to_dicts(rows)
    target.write_text(json.dumps({
        "generator": "MBM — Mediterranean Bathymetry Monitor",
        "schema_version": "1.0.0",
        "dataset_count": len(data),
        "datasets": data,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return target


def export_datasets_geojson(rows: Iterable[Any], path: str | Path) -> Path:
    """GeoJSON des emprises (EPSG:4326), avec propriétés de catalogue."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    features: list[dict[str, Any]] = []
    for row in _rows_to_dicts(rows):
        bbox = row.get("bbox")
        if isinstance(bbox, str):
            try:
                bbox = json.loads(bbox)
            except Exception:
                bbox = None
        if not bbox:
            continue
        minx, miny, maxx, maxy = [float(v) for v in bbox]
        properties = {
            "uid": row.get("uid"),
            "name": row.get("name"),
            "source_id": row.get("source_id"),
            "producer": row.get("producer"),
            "acquisition_class": row.get("acquisition_class"),
            "acquisition_method": row.get("acquisition_method"),
            "resolution_m": row.get("resolution_m"),
            "depth_min_m": row.get("depth_min_m"),
            "depth_max_m": row.get("depth_max_m"),
            "license": row.get("license"),
            "metadata_status": row.get("metadata_status"),
            "data_origin": row.get("data_origin"),
            "official_url": row.get("official_url"),
        }
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]],
            },
            "properties": properties,
        })
    target.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return target


def report_rows_to_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise des lignes de rapport en lignes exportables (dict)."""
    return _rows_to_dicts(rows)


def export_excel(sheets: dict[str, tuple[Sequence[tuple[str, str]], Sequence[Any]]],
                 path: str | Path, title: str = "MBM") -> Path:
    """Classeur Excel multi-feuilles.

    ``sheets`` : {nom_feuille: (colonnes [(clé, libellé)], lignes)}
    Nécessite openpyxl.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openpyxl est requis pour l'export Excel (pip install openpyxl)") from exc

    wb = Workbook()
    wb.remove(wb.active)
    header_fill = PatternFill("solid", fgColor="1D2836")
    header_font = Font(color="E6EDF6", bold=True, size=10)

    for sheet_name, (columns, rows) in sheets.items():
        ws = wb.create_sheet(title=sheet_name[:31])
        ws.append([label for _, label in columns])
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in rows:
            if not isinstance(row, dict):
                row = row.to_row()
            ws.append([_cell(row.get(key)) for key, _ in columns])
        ws.freeze_panes = "A2"
        for idx, (_, lbl) in enumerate(columns, start=1):
            width = max(12, min(48, len(str(lbl)) + 4))
            ws.column_dimensions[get_column_letter(idx)].width = width
        ws.auto_filter.ref = ws.dimensions
    wb.properties.title = title
    wb.properties.creator = "MBM — Mediterranean Bathymetry Monitor"
    wb.save(target)
    log.info("Export Excel: %s", target)
    return target


def _cell(value: Any) -> Any:
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str) and len(value) > 32000:
        return value[:32000]
    return value
