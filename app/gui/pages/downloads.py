"""Page 6 — Gestion des téléchargements (section 8).

État en Phase 1 : l'interface, le schéma de base (table ``downloads``), le
calcul d'empreinte d'intégrité et l'organisation de l'arborescence locale sont
opérationnels. Le moteur de téléchargement réseau (reprise, sous-ensemble par
emprise, vérification d'intégrité) est développé en Phase 7.

Aucun bouton de téléchargement n'est présenté comme fonctionnel alors qu'il ne
le serait pas : la page liste les produits et leur mode d'accès, indique ce qui
relève du téléchargement manuel, et signale explicitement l'état du moteur.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from app.core.taxonomy import ACQUISITION_METHODS, label_of
from app.gui.pages.base import BasePage
from app.gui.theme import COLORS, CLASS_COLORS
from app.gui.widgets import (
    Badge, Card, CardLayout, DataTable, SectionHeader, hline, kv_row, label, status_color,
)

COLUMNS = ["Produit", "Source", "Mode d'accès", "Format", "Taille", "Statut local", "Emplacement"]


class DownloadsPage(BasePage):
    def build_content(self) -> None:
        self.banner = label(
            "ⓘ  Phase 1 : l'interface et le schéma de gestion des téléchargements sont en place. "
            "Le moteur de téléchargement (reprise, sous-ensemble par emprise, vérification "
            "d'intégrité) est livré en Phase 7. Les produits à récupérer manuellement sont "
            "signalés « manuel requis ».",
            "Banner", word_wrap=True,
        )
        self.content.addWidget(self.banner)

        row = QHBoxLayout()
        row.setSpacing(12)

        # ---- inventaire ----------------------------------------------------
        left = Card()
        ll = CardLayout(left, spacing=8)
        head = SectionHeader("Produits et accessibilité", "État local calculé sur l'arborescence de données")
        self.chk_manual_only = QCheckBox("Accès manuel uniquement")
        self.chk_manual_only.stateChanged.connect(lambda _: self.refresh())
        head.add_action(self.chk_manual_only)
        ll.addWidget(head)
        self.table = DataTable(COLUMNS, stretch_column=0)
        self.table.setColumnWidth(0, 300)
        ll.addWidget(self.table, 1)

        tools = QHBoxLayout()
        open_btn = QPushButton("Ouvrir le dossier de données")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(self._open_folder)
        tools.addWidget(open_btn)
        verify_btn = QPushButton("Calculer les empreintes des fichiers présents")
        verify_btn.setObjectName("Ghost")
        verify_btn.clicked.connect(self._hash_files)
        tools.addWidget(verify_btn)
        tools.addStretch(1)
        ll.addLayout(tools)
        row.addWidget(left, 3)

        # ---- arborescence + intégrité --------------------------------------
        right = Card()
        rl = CardLayout(right, spacing=8)
        rl.addWidget(SectionHeader("Arborescence locale", "Organisation prévue des données"))
        self.tree_view = QWidget()
        self.tree_layout = QVBoxLayout(self.tree_view)
        self.tree_layout.setContentsMargins(0, 0, 0, 0)
        self.tree_layout.setSpacing(2)
        rl.addWidget(self.tree_view)

        rl.addWidget(hline())
        rl.addWidget(SectionHeader("Téléchargement manuel", "Produits sans accès automatique"))
        self.manual_info = label("", "Dim", word_wrap=True)
        rl.addWidget(self.manual_info)

        rl.addWidget(hline())
        rl.addWidget(SectionHeader("Vérification d'intégrité", "Empreinte SHA-256 des fichiers locaux"))
        self.hash_output = label("Aucun fichier vérifié.", "Dim", word_wrap=True)
        rl.addWidget(self.hash_output)
        rl.addStretch(1)
        right.setMinimumWidth(330)
        row.addWidget(right, 2)

        self.content.addLayout(row, 1)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rows = self.repo.list_dataset_rows()
        downloads = {(d["dataset_uid"], d["local_path"]): d for d in self.repo.list_downloads()}
        data_dir = self.ctx.settings.download_dir()

        display, colors, data = [], [], []
        manual_count = 0
        for row in rows:
            manual = row["access_mode"] in ("manual", "restricted")
            if manual:
                manual_count += 1
            if self.chk_manual_only.isChecked() and not manual:
                continue
            local = _find_local(data_dir, row)
            status = "absent"
            location = "—"
            if downloads:
                match = [d for (uid, _), d in downloads.items() if uid == row["uid"]]
                if match:
                    status = match[0]["status"]
                    location = match[0]["local_path"] or "—"
            if local:
                status = "présent (local)"
                location = str(local.relative_to(data_dir))
            elif manual:
                status = "manuel requis"
            display.append([
                row["name"], row["source_id"], row["access_mode"], row["data_format"],
                f"{row['file_size_mb']:.1f} Mo" if row["file_size_mb"] else "—",
                status, location,
            ])
            colors.append(status_color("manual_required" if manual else "pending"))
            data.append(row["uid"])
        self.table.set_rows(display, colors, data, sortable_numbers=False)

        self.manual_info.setText(
            f"{manual_count} produit(s) sans accès automatique documenté. "
            "Pour ceux-ci, la procédure est : cliquer sur l'URL officielle depuis la fiche "
            "produit (page Catalogue), déposer le fichier dans "
            f"« {data_dir} », puis le déclarer ici (Phase 7) pour enregistrer les métadonnées "
            "et l'empreinte d'intégrité."
        )
        self._render_tree()

    def _render_tree(self) -> None:
        while self.tree_layout.count():
            item = self.tree_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        root = self.ctx.settings.data_root
        structure = [
            ("mbm.sqlite3", "base catalogue locale"),
            ("downloads/", "produits téléchargés, organisés par source / produit / version"),
            ("catalogue/", "instantanés des métadonnées (JSON) par version"),
            ("raster/", "grilles bathymétriques converties si nécessaire"),
            ("reports/", "rapports hebdomadaires PDF / HTML / Excel"),
            ("cache/", "réponses API temporaires et index STAC"),
            ("logs/", "journaux d'exécution et erreurs de connecteurs"),
        ]
        self.tree_layout.addWidget(label(str(root), "SectionTitle", word_wrap=True))
        for name, desc in structure:
            exists = (root / name.rstrip("/")).exists()
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lay.addWidget(Badge("✓" if exists else "·",
                                COLORS["success"] if exists else COLORS["text_dim"]))
            lay.addWidget(label(name, "Mono" if False else "Dim"))
            lay.addWidget(label(desc, "Dim", word_wrap=True), 1)
            self.tree_layout.addWidget(w)

    def _open_folder(self) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        path = self.ctx.settings.data_root
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.notify(f"Dossier : {path}")

    def _hash_files(self) -> None:
        data_dir = self.ctx.settings.download_dir()
        files = [p for p in data_dir.rglob("*") if p.is_file()][:20]
        if not files:
            self.hash_output.setText(
                f"Aucun fichier dans {data_dir}. "
                "La vérification SHA-256 s'appliquera aux téléchargements de la Phase 7."
            )
            return
        lines = []
        for path in files:
            digest = _sha256(path)
            lines.append(f"{path.name} · {path.stat().st_size / 1e6:.1f} Mo · sha256:{digest[:16]}…")
        self.hash_output.setText("\n".join(lines))


def _find_local(data_dir: Path, row: dict) -> Path | None:
    if not data_dir.exists():
        return None
    slug = "".join(c if c.isalnum() else "_" for c in row["name"].lower())[:40]
    for candidate in data_dir.rglob(f"*{slug}*"):
        if candidate.is_file():
            return candidate
    return None


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()
