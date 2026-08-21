"""
Theme — color palette + the global QSS stylesheet applied to the app.

TWEAK: edit COLORS below to re-theme the entire application (every
widget reads from this dict). The QSS in build_stylesheet() controls
per-widget styling (borders, padding, hover states, etc.).
"""

from __future__ import annotations

# TWEAK: the whole app palette
COLORS = {
    "bg": "#0a0a0a",
    "panel": "#121212",
    "card": "#1e1e1e",
    "border": "#2d2d2d",
    "hover": "#252525",
    "accent": "#ff6b6b",
    "accent_dim": "#3a1a1a",
    "success": "#51cf66",
    "warning": "#ffd43b",
    "info": "#74c0fc",
    "text": "#e0e0e0",
    "muted": "#888888",
}

FONT_MAIN = '"Segoe UI", "Ubuntu", "DejaVu Sans", sans-serif'
FONT_CODE = '"Consolas", "DejaVu Sans Mono", monospace'

SECTION_LABEL_QSS = (
    f"color: {COLORS['muted']}; font-size: 10px; font-weight: 700; letter-spacing: 1px;"
)


def build_stylesheet() -> str:
    c = COLORS
    return f"""
QMainWindow, QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-family: {FONT_MAIN};
    font-size: 12px;
}}
QLabel {{ background: transparent; }}

QFrame#header {{
    background-color: {c['accent']};
}}
QFrame#header QLabel {{
    color: white; background: transparent;
}}

QLineEdit {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 5px 8px;
    color: {c['text']};
    selection-background-color: {c['border']};
}}
QLineEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit[readOnly="true"] {{ color: {c['text']}; }}

QPushButton {{
    background-color: {c['border']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {c['hover']}; }}
QPushButton:pressed {{ background-color: {c['card']}; }}
QPushButton:disabled {{ color: {c['muted']}; background-color: {c['panel']}; }}

QPushButton[variant="accent"] {{
    background-color: {c['accent']}; color: white; border-color: {c['accent']};
}}
QPushButton[variant="success"] {{
    background-color: {c['success']}; color: #101010; border-color: {c['success']};
    font-size: 13px; padding: 9px;
}}
QPushButton[variant="danger"] {{
    background-color: {c['accent_dim']}; color: {c['accent']};
}}

QComboBox {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 6px 10px;
    color: {c['text']};
    font-family: {FONT_CODE};
}}
QComboBox:hover {{ border-color: {c['muted']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    selection-background-color: {c['border']};
    selection-color: {c['text']};
    outline: none;
}}
QComboBox:disabled {{ color: {c['muted']}; }}

QCheckBox {{
    background: transparent; spacing: 6px; color: {c['text']};
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['border']};
    border-radius: 3px;
    background: {c['card']};
}}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
    image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png);
}}

QTabWidget::pane {{
    border: none; background: {c['bg']}; top: -1px;
}}
QTabBar::tab {{
    background: {c['panel']};
    color: {c['muted']};
    padding: 7px 14px;
    margin-right: 2px;
    font-weight: 700;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{ background: {c['card']}; color: {c['text']}; }}
QTabBar::tab:hover:!selected {{ background: {c['hover']}; }}

QProgressBar {{
    background: {c['border']};
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 4px;
}}
QProgressBar[variant="queue"]::chunk {{ background-color: {c['success']}; }}

QTextEdit#log {{
    background-color: {c['bg']};
    color: {c['info']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    font-family: {FONT_CODE};
    font-size: 11px;
}}

QListWidget {{
    background-color: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    outline: none;
    font-family: {FONT_CODE};
    font-size: 11px;
}}
QListWidget::item {{ padding: 5px; }}
QListWidget::item:selected {{ background: {c['border']}; color: {c['text']}; }}

QTableWidget {{
    background-color: {c['card']};
    alternate-background-color: {c['panel']};
    border: 1px solid {c['border']};
    gridline-color: {c['border']};
    outline: none;
    font-family: {FONT_CODE};
    font-size: 11px;
}}
QTableWidget::item:selected {{ background: {c['border']}; color: {c['text']}; }}
QHeaderView::section {{
    background-color: {c['panel']};
    color: {c['text']};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {c['border']};
    font-weight: 700;
    font-family: {FONT_MAIN};
    font-size: 11px;
}}

QScrollBar:vertical {{
    background: {c['panel']}; width: 10px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {c['border']}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{
    background: {c['panel']}; height: 10px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']}; border-radius: 5px; min-width: 30px;
}}

QMessageBox, QDialog {{ background-color: {c['panel']}; }}
"""
