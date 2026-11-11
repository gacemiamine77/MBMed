"""Thème visuel de l'application (QSS + palette + styles de graphiques).

Un seul endroit définit l'apparence. Le thème sombre « laboratoire » est
optimisé pour la lecture de tableaux denses et de cartes bathymétriques.
"""
from __future__ import annotations

# Palette principale
COLORS = {
    "bg": "#131a24",
    "bg_alt": "#182231",
    "surface": "#1d2836",
    "surface_alt": "#233043",
    "surface_hover": "#2a3a50",
    "border": "#2c3a4d",
    "border_soft": "#243244",
    "text": "#e6edf6",
    "text_muted": "#93a4bb",
    "text_dim": "#6d7f96",
    "accent": "#3fa7d6",
    "accent_dark": "#2b7fa6",
    "accent_soft": "#1d3f52",
    "success": "#3ec98a",
    "warning": "#e8b64c",
    "danger": "#e46f6f",
    "info": "#9d8cf0",
    # Couleurs des classes d'acquisition A-E
    "class_A": "#2f9e6e",
    "class_B": "#3d7ebe",
    "class_C": "#c8912a",
    "class_D": "#8a6dbf",
    "class_E": "#b2564f",
    "class_none": "#4a5b70",
    # Bathymétrie
    "sea_shallow": "#8ed0c8",
    "sea_mid": "#3f7fa8",
    "sea_deep": "#16283d",
}

FONT_FAMILY = "Segoe UI, Inter, Cantarell, DejaVu Sans, sans-serif"
MONO_FAMILY = "JetBrains Mono, Consolas, DejaVu Sans Mono, monospace"

CLASS_COLORS = {
    "A": COLORS["class_A"],
    "B": COLORS["class_B"],
    "C": COLORS["class_C"],
    "D": COLORS["class_D"],
    "E": COLORS["class_E"],
}

STATUS_COLORS = {
    "ok": COLORS["success"],
    "partial": COLORS["warning"],
    "error": COLORS["danger"],
    "not_run": COLORS["text_dim"],
    "disabled": COLORS["text_dim"],
    "running": COLORS["accent"],
    "success": COLORS["success"],
    "failed": COLORS["danger"],
    "new": COLORS["accent"],
    "updated": COLORS["warning"],
    "unchanged": COLORS["text_muted"],
    "removed": COLORS["danger"],
    "pending": COLORS["text_muted"],
    "done": COLORS["success"],
    "manual_required": COLORS["warning"],
    "skipped": COLORS["text_dim"],
    "validated": COLORS["success"],
    "auto_complete": COLORS["accent"],
    "unverified": COLORS["text_dim"],
    "conflict": COLORS["danger"],
}

SEQUENCE = ["#3fa7d6", "#2f9e6e", "#c8912a", "#8a6dbf", "#e46f6f", "#4fb3a5", "#9d8cf0", "#d98c5f"]


def chart_style() -> dict:
    """Réglages Matplotlib cohérents avec le thème Qt."""
    return {
        "figure.facecolor": COLORS["surface"],
        "axes.facecolor": COLORS["surface"],
        "axes.edgecolor": COLORS["border"],
        "axes.labelcolor": COLORS["text_muted"],
        "text.color": COLORS["text"],
        "xtick.color": COLORS["text_muted"],
        "ytick.color": COLORS["text_muted"],
        "grid.color": COLORS["border_soft"],
        "grid.linewidth": 0.6,
        "font.size": 8.5,
        "axes.titlesize": 9.5,
        "axes.titleweight": "600",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "savefig.facecolor": COLORS["surface"],
    }


def stylesheet() -> str:
    c = COLORS
    return f"""
    QWidget {{
        background-color: {c['bg']};
        color: {c['text']};
        font-family: {FONT_FAMILY};
        font-size: 12px;
    }}
    QMainWindow, QDialog {{ background-color: {c['bg']}; }}

    /* ---- Barre latérale ---- */
    #Sidebar {{ background-color: {c['bg_alt']}; border-right: 1px solid {c['border']}; }}
    #BrandTitle {{ font-size: 14px; font-weight: 700; color: {c['text']}; }}
    #BrandSubtitle {{ font-size: 10px; color: {c['text_dim']}; }}
    #BrandBadge {{
        background-color: {c['accent_soft']}; color: {c['accent']};
        border-radius: 4px; padding: 2px 6px; font-size: 9px; font-weight: 600;
    }}
    #NavList {{
        background: transparent; border: none; outline: 0;
    }}
    #NavList::item {{
        padding: 8px 10px; margin: 1px 6px; border-radius: 6px; color: {c['text_muted']};
    }}
    #NavList::item:hover {{ background-color: {c['surface']}; color: {c['text']}; }}
    #NavList::item:selected {{
        background-color: {c['accent_soft']}; color: {c['text']}; font-weight: 600;
        border-left: 3px solid {c['accent']};
    }}
    #SidebarFooter {{ color: {c['text_dim']}; font-size: 10px; }}

    /* ---- En-têtes de page ---- */
    #PageTitle {{ font-size: 19px; font-weight: 700; color: {c['text']}; }}
    #PageSubtitle {{ font-size: 11px; color: {c['text_muted']}; }}
    #SectionTitle {{ font-size: 12px; font-weight: 700; color: {c['text']}; }}
    #SectionHint {{ font-size: 10px; color: {c['text_dim']}; }}
    #Muted {{ color: {c['text_muted']}; }}
    #Dim {{ color: {c['text_dim']}; font-size: 10px; }}

    /* ---- Cartes ---- */
    #Card {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
    }}
    #CardAlt {{
        background-color: {c['bg_alt']};
        border: 1px solid {c['border_soft']};
        border-radius: 10px;
    }}
    #StatValue {{ font-size: 24px; font-weight: 700; color: {c['text']}; }}
    #StatLabel {{ font-size: 10px; color: {c['text_muted']}; text-transform: uppercase; letter-spacing: 0.5px; }}
    #StatHint {{ font-size: 10px; color: {c['text_dim']}; }}

    /* ---- Boutons ---- */
    QPushButton {{
        background-color: {c['surface_alt']}; color: {c['text']};
        border: 1px solid {c['border']}; border-radius: 6px;
        padding: 6px 12px; font-weight: 500;
    }}
    QPushButton:hover {{ background-color: {c['surface_hover']}; border-color: {c['accent_dark']}; }}
    QPushButton:pressed {{ background-color: {c['accent_soft']}; }}
    QPushButton:disabled {{ color: {c['text_dim']}; background-color: {c['bg_alt']}; }}
    QPushButton#Primary {{
        background-color: {c['accent_dark']}; border-color: {c['accent']}; color: #ffffff; font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {c['accent']}; }}
    QPushButton#Ghost {{ background-color: transparent; border: 1px solid {c['border']}; }}
    QPushButton#Ghost:hover {{ background-color: {c['surface']}; }}
    QPushButton#Danger {{ border-color: {c['danger']}; color: {c['danger']}; background: transparent; }}

    /* ---- Champs ---- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {{
        background-color: {c['bg_alt']}; border: 1px solid {c['border']};
        border-radius: 6px; padding: 5px 8px; color: {c['text']};
        selection-background-color: {c['accent_dark']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
        border-color: {c['accent']};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['surface']}; border: 1px solid {c['border']};
        selection-background-color: {c['accent_soft']}; outline: 0;
    }}
    QCheckBox {{ spacing: 6px; color: {c['text_muted']}; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px; border-radius: 3px;
        border: 1px solid {c['border']}; background: {c['bg_alt']};
    }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
    QRadioButton {{ color: {c['text_muted']}; spacing: 6px; }}

    /* ---- Tableaux ---- */
    QTableView, QTableWidget {{
        background-color: {c['surface']}; alternate-background-color: {c['bg_alt']};
        border: 1px solid {c['border']}; border-radius: 8px;
        gridline-color: {c['border_soft']}; selection-background-color: {c['accent_soft']};
        selection-color: {c['text']};
    }}
    QHeaderView::section {{
        background-color: {c['bg_alt']}; color: {c['text_muted']};
        padding: 6px 8px; border: none; border-bottom: 1px solid {c['border']};
        border-right: 1px solid {c['border_soft']}; font-weight: 600; font-size: 10px;
    }}
    QTableView::item {{ padding: 4px 6px; }}
    QTableCornerButton::section {{ background-color: {c['bg_alt']}; border: none; }}

    /* ---- Onglets ---- */
    QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 8px; background: {c['surface']}; }}
    QTabBar::tab {{
        background: transparent; color: {c['text_muted']};
        padding: 7px 14px; margin-right: 4px; border-radius: 6px;
    }}
    QTabBar::tab:selected {{ background-color: {c['surface_alt']}; color: {c['text']}; font-weight: 600; }}
    QTabBar::tab:hover {{ color: {c['text']}; }}

    /* ---- Barres de défilement ---- */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['surface_hover']}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c['surface_hover']}; border-radius: 4px; min-width: 24px; }}

    /* ---- Barre d'état ---- */
    QStatusBar {{
        background-color: {c['bg_alt']}; color: {c['text_muted']};
        border-top: 1px solid {c['border']}; font-size: 10px;
    }}
    QStatusBar::item {{ border: none; }}

    /* ---- GroupBox ---- */
    QGroupBox {{
        border: 1px solid {c['border']}; border-radius: 8px;
        margin-top: 14px; padding-top: 8px; font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {c['text_muted']};
    }}

    /* ---- Divers ---- */
    QToolTip {{
        background-color: {c['surface_alt']}; color: {c['text']};
        border: 1px solid {c['border']}; padding: 4px; border-radius: 4px;
    }}
    QSplitter::handle {{ background-color: {c['border_soft']}; }}
    QProgressBar {{
        background-color: {c['bg_alt']}; border: 1px solid {c['border']};
        border-radius: 6px; text-align: center; color: {c['text']}; height: 14px;
    }}
    QProgressBar::chunk {{ background-color: {c['accent_dark']}; border-radius: 5px; }}
    QListWidget {{
        background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
    }}
    #Banner {{
        background-color: {c['accent_soft']}; border: 1px solid {c['accent_dark']};
        border-radius: 8px; color: {c['text_muted']}; padding: 8px 12px;
    }}
    #WarningBanner {{
        background-color: #3a2f1c; border: 1px solid #6b5525;
        border-radius: 8px; color: {c['warning']}; padding: 8px 12px;
    }}
    """
