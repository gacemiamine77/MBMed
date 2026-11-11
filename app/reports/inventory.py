"""Génération du rapport d'inventaire du catalogue (HTML + données Excel).

Le rendu HTML est autonome (CSS inline, aucun accès réseau) pour être lisible
dans l'aperçu de l'application comme dans un navigateur. Le rapport
hebdomadaire de veille (Phase 7) réutilisera ce module en y ajoutant les
nouveautés, les publications et les limites scientifiques.

Aucune donnée n'est inventée : les champs absents sont marqués « non documenté ».
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Sequence

from app.core.sources import SOURCES
from app.core.taxonomy import ACQUISITION_CLASSES, LICENSE_TYPES, METADATA_STATUS, label_of

CSS = """
:root { color-scheme: dark; }
body { font-family: 'Segoe UI', Inter, sans-serif; background:#131a24; color:#e6edf6;
       margin:0; padding:26px 30px; font-size:13px; line-height:1.5; }
h1 { font-size:22px; margin:0 0 2px 0; }
h2 { font-size:15px; margin:26px 0 8px 0; padding-bottom:5px; border-bottom:1px solid #2c3a4d; }
h3 { font-size:13px; margin:16px 0 6px 0; color:#93a4bb; }
.sub { color:#93a4bb; font-size:12px; }
.badge { display:inline-block; padding:1px 7px; border-radius:4px; font-size:10px;
         font-weight:700; margin-right:4px; }
table { border-collapse:collapse; width:100%; margin:8px 0 14px 0; font-size:11.5px; }
th { text-align:left; color:#93a4bb; font-weight:600; padding:6px 8px;
     border-bottom:1px solid #2c3a4d; background:#182231; }
td { padding:5px 8px; border-bottom:1px solid #243244; vertical-align:top; }
tr:hover td { background:#1d2836; }
.
.kpi { border-collapse:separate; border-spacing:6px; width:100%; }
.kpi td { background:#1d2836; border:1px solid #2c3a4d; border-left:3px solid #3fa7d6;
          border-radius:8px; padding:9px 12px; vertical-align:top; }
.warn { background:#3a2f1c; border:1px solid #6b5525; color:#e8b64c;
        padding:9px 12px; border-radius:8px; margin:12px 0; font-size:11.5px; }
.info { background:#1d3f52; border:1px solid #2b7fa6; color:#c9e2ef;
        padding:9px 12px; border-radius:8px; margin:12px 0; font-size:11.5px; }
.footer { margin-top:30px; padding-top:10px; border-top:1px solid #2c3a4d;
          color:#6d7f96; font-size:10.5px; }
code { background:#182231; padding:1px 4px; border-radius:3px; font-size:11px; }
a { color:#3fa7d6; text-decoration:none; }
"""

CLASS_BADGE_COLORS = {
    "A": "#2f9e6e", "B": "#3d7ebe", "C": "#c8912a", "D": "#8a6dbf", "E": "#b2564f",
}


def build_inventory_report(rows: Sequence[dict], stats: dict[str, Any],
                           scope_label: str) -> dict[str, Any]:
    """Prépare la structure du rapport (indépendante du rendu)."""
    generated = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y à %H:%M")
    summary = {
        "Produits dans le périmètre": len(rows),
        "Total catalogué": stats.get("total", 0),
        "Produits couvrant le littoral algérien (0–100 m)": stats.get("algeria_core", 0),
        "Mesures directes (classe A)": stats.get("ground_truth_total", 0),
        "Dans la fenêtre SDB 0–100 m": stats.get("sdb_depth_total", 0),
        "Complétude moyenne des métadonnées": f"{stats.get('avg_completeness', 0) * 100:.0f} %",
        "Sources disposant d'un connecteur": f"{stats.get('sources_implemented', 0)} / {stats.get('sources_total', 0)}",
        "Dernière exécution de veille": (
            (stats.get("last_run") or {}).get("finished_at", "aucune")[:19].replace("T", " ")
            if stats.get("last_run") else "aucune"
        ),
    }
    return {
        "title": "Rapport d'inventaire — Mediterranean Bathymetry Monitor",
        "scope": scope_label,
        "generated_at": generated,
        "summary": summary,
        "rows": list(rows),
        "stats": stats,
    }


def render_inventory_html(report: dict[str, Any], standalone: bool = False) -> str:
    rows = report["rows"]
    stats = report["stats"]
    e = html.escape

    parts: list[str] = []
    parts.append(f"<h1>{e(report['title'])}</h1>")
    parts.append(
        f"<div class='sub'>Périmètre : <b>{e(report['scope'])}</b> · "
        f"généré le {e(report['generated_at'])}</div>"
    )
    parts.append(
        "<div class='warn'>Rapport d'inventaire. Il décrit l'état du catalogue à l'instant T "
        "et ne remplace pas le rapport hebdomadaire de veille (Phase 7). Les fiches marquées "
        "« démonstration » proviennent du jeu d'initialisation : leurs valeurs numériques "
        "doivent être confirmées par les connecteurs officiels.</div>"
    )

    # KPI (tableau : compatible avec le moteur HTML restreint de QTextBrowser)
    parts.append("<h2>Synthèse</h2><table class='kpi'><tr>")
    items = list(report["summary"].items())
    for i, (key, value) in enumerate(items):
        if i and i % 4 == 0:
            parts.append("</tr><tr>")
        parts.append(
            f"<td width='25%'><b style='font-size:18px'>{e(str(value))}</b><br>"
            f"<span style='color:#93a4bb;font-size:10.5px'>{e(key.upper())}</span></td>"
        )
    parts.append("</tr></table>")

    # Répartitions
    parts.append("<h2>Répartition par classe d'acquisition</h2><table>")
    parts.append("<tr><th>Classe</th><th>Nature</th><th>Produits (périmètre)</th>"
                 "<th>Vérité terrain</th></tr>")
    counts = _class_counts(rows)
    for key, meta in ACQUISITION_CLASSES.items():
        color = CLASS_BADGE_COLORS.get(key, "#4a5b70")
        parts.append(
            f"<tr><td><span class='badge' style='background:{color};color:#fff'>{key}</span></td>"
            f"<td>{e(str(meta['label']))}</td><td>{counts.get(key, 0)}</td>"
            f"<td>{'oui' if meta['ground_truth_candidate'] else 'non'}</td></tr>"
        )
    parts.append("</table>")

    # Tableau détaillé
    parts.append("<h2>Produits du périmètre</h2>")
    if not rows:
        parts.append("<p class='sub'>Aucun produit ne correspond à ce périmètre.</p>")
    else:
        parts.append(
            "<table><tr><th>Produit</th><th>Source</th><th>Classe</th><th>Résolution</th>"
            "<th>Profondeurs</th><th>Réf. verticale</th><th>Licence</th><th>Métadonnées</th>"
            "<th>Lien</th></tr>"
        )
        for row in rows:
            color = CLASS_BADGE_COLORS.get(row.get("acquisition_class", ""), "#4a5b70")
            resolution = (f"{row['resolution_m']:.0f} m" if row.get("resolution_m") else
                          "non documentée")
            depths = ("non documentées" if row.get("depth_min_m") is None
                      else f"{row['depth_min_m']:.0f} – {row['depth_max_m']:.0f} m")
            url = row.get("official_url") or ""
            link = f"<a href='{e(url)}'>source officielle</a>" if url else "—"
            parts.append(
                "<tr>"
                f"<td><b>{e(row.get('name') or '')}</b><br><span class='sub'>"
                f"{e(row.get('producer') or 'producteur non précisé')}</span></td>"
                f"<td>{e(_source(row.get('source_id')))}</td>"
                f"<td><span class='badge' style='background:{color};color:#fff'>"
                f"{e(row.get('acquisition_class') or '?')}</span></td>"
                f"<td>{e(resolution)}</td><td>{e(depths)}</td>"
                f"<td>{e(row.get('vertical_reference') or 'non documentée')}</td>"
                f"<td>{e(label_of(LICENSE_TYPES, row.get('license')).split('(')[0].strip())}</td>"
                f"<td>{e(label_of(METADATA_STATUS, row.get('metadata_status')))}</td>"
                f"<td>{link}</td>"
                "</tr>"
            )
        parts.append("</table>")

    # Limites
    parts.append("<h2>Limites et réserves scientifiques</h2><ul>")
    parts.append("<li>Le pas de grille annoncé n'est pas la résolution effective : les MNT "
                 "compilés (EMODnet, GEBCO) interpolent des levés de densités très inégales.</li>")
    parts.append("<li>Aucun produit interpolé n'est considéré comme vérité terrain. Seules les "
                 "mesures directes (classe A) peuvent prétendre à ce rôle, après contrôle de la "
                 "référence verticale et de l'incertitude.</li>")
    parts.append("<li>Les champs « non documentés » ne sont jamais complétés par une estimation.</li>")
    parts.append("<li>La couverture spatiale réelle (surfaces, lacunes par bande de profondeur) "
                 "sera quantifiée en Phase 5 avec une projection équivalente.</li>")
    parts.append("</ul>")

    parts.append(
        "<div class='footer'>Mediterranean Bathymetry Monitor — rapport généré automatiquement. "
        "Les liens renvoient vers les portails officiels des producteurs ; les licences et "
        "conditions d'utilisation de chaque source doivent être respectées.</div>"
    )

    body = "".join(parts)
    if standalone:
        return (
            "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
            f"<title>{e(report['title'])}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>"
        )
    return f"<html><head><style>{CSS}</style></head><body>{body}</body></html>"


def _class_counts(rows: Sequence[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get("acquisition_class") or "?"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _source(source_id: str | None) -> str:
    if not source_id:
        return "—"
    src = SOURCES.get(source_id)
    return src.label if src else source_id
