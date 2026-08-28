from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

LIME = "#86BC25"


def load_bundled_fonts() -> list[str]:
    font_directory = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    loaded_families: list[str] = []
    for font_file in font_directory.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return loaded_families


DARK_STYLESHEET = """
QWidget {
    background: #0B0D0C;
    color: #F2F4F1;
    font-family: "Noto Sans JP", "Yu Gothic UI";
    font-size: 12px;
    font-weight: 500;
}
QLabel { background: transparent; }
QMainWindow, QDialog { background: #0B0D0C; }
QDialog#edgeWindow { border-left: 1px solid #363C36; }
QFrame#sidebar { background: #101310; border-right: 1px solid #2A2F2A; }
QFrame#surface, QFrame#detailSurface, QFrame#edgeCard {
    background: #151815;
    border: 1px solid #303530;
    border-radius: 12px;
}
QLabel#logo { font-size: 18px; font-weight: 700; letter-spacing: 2px; }
QLabel#pageTitle { font-size: 22px; font-weight: 700; }
QLabel#sectionLabel { color: #86BC25; font-size: 10px; font-weight: 700; }
QLabel#muted, QLabel#fieldLabel { color: #8F968F; }
QLabel#fieldLabel { font-size: 10px; font-weight: 700; }
QLabel#detailTitle { font-size: 17px; font-weight: 700; }
QLabel#edgeTitle { font-size: 15px; font-weight: 700; }
QLabel#edgeTaskTitle { font-size: 11px; font-weight: 700; }
QPushButton {
    min-height: 32px;
    padding: 0 11px;
    background: #1B1F1B;
    color: #DDE0DC;
    border: 1px solid #3A403A;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover { background: #252B25; }
QPushButton:pressed { background: #303730; }
QPushButton#primaryButton {
    background: #86BC25;
    color: #0B0D0B;
    border-color: #86BC25;
    font-weight: 700;
}
QPushButton#dangerButton { color: #FF7474; }
QPushButton#compactButton, QPushButton#edgeClose {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}
QPushButton#edgeClose { border: 0; background: transparent; font-size: 18px; }
QPushButton#edgeNav, QPushButton#edgeAction {
    min-height: 28px;
    padding: 0 5px;
    font-size: 10px;
}
QPushButton#navButton {
    border: 0;
    background: transparent;
    color: #A8AEA8;
    text-align: left;
    padding-left: 12px;
}
QPushButton#navButton:checked {
    color: #FFFFFF;
    background: #252B25;
    border-left: 3px solid #86BC25;
}
QPushButton#viewButton:checked {
    background: #86BC25;
    color: #0B0D0B;
    border-color: #86BC25;
}
QPushButton#calendarDay {
    min-height: 22px;
    max-height: 22px;
    min-width: 22px;
    max-width: 28px;
    padding: 0;
    border: 0;
    background: transparent;
}
QPushButton#calendarDayToday { background: #86BC25; color: #0B0D0B; border: 0; }
QPushButton#calendarTask {
    min-height: 16px;
    max-height: 18px;
    padding: 0 2px;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: #E1E5DF;
    text-align: left;
    font-size: 9px;
    font-weight: 700;
}
QFrame#calendarCell { border-right: 1px solid #2C312C; border-bottom: 1px solid #2C312C; }
QFrame#calendarCellSelected { background: #242B21; border: 1px solid #86BC25; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit {
    min-height: 34px;
    padding: 2px 8px;
    background: #1A1E1A;
    color: #F1F3F0;
    border: 1px solid #373D37;
    border-radius: 8px;
    selection-background-color: #86BC25;
    selection-color: #0B0D0B;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {
    border-color: #86BC25;
}
QTableWidget {
    background: #151815;
    alternate-background-color: #121512;
    border: 0;
    gridline-color: #292E29;
    selection-background-color: #252D22;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background: #151815;
    color: #8F968F;
    border: 0;
    border-bottom: 1px solid #303530;
    padding: 8px;
    font-size: 10px;
    font-weight: 700;
}
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #3D443D; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #242824; color: #FFFFFF; border: 1px solid #434943; }
"""


LIGHT_STYLESHEET = """
QWidget {
    background: #EEF0EC;
    color: #181B18;
    font-family: "Noto Sans JP", "Yu Gothic UI";
    font-size: 12px;
    font-weight: 500;
}
QLabel { background: transparent; }
QMainWindow, QDialog { background: #EEF0EC; }
QDialog#edgeWindow { border-left: 1px solid #C8CEC5; }
QFrame#sidebar { background: #F8F9F6; border-right: 1px solid #D4D9D2; }
QFrame#surface, QFrame#detailSurface, QFrame#edgeCard {
    background: #FFFFFF;
    border: 1px solid #D2D7CF;
    border-radius: 12px;
}
QLabel#logo { color: #111411; font-size: 18px; font-weight: 700; letter-spacing: 2px; }
QLabel#pageTitle { color: #111411; font-size: 22px; font-weight: 700; }
QLabel#sectionLabel { color: #527F08; font-size: 10px; font-weight: 700; }
QLabel#muted, QLabel#fieldLabel { color: #687068; }
QLabel#fieldLabel { font-size: 10px; font-weight: 700; }
QLabel#detailTitle { color: #111411; font-size: 17px; font-weight: 700; }
QLabel#edgeTitle { color: #111411; font-size: 15px; font-weight: 700; }
QLabel#edgeTaskTitle { color: #111411; font-size: 11px; font-weight: 700; }
QPushButton {
    min-height: 32px;
    padding: 0 11px;
    background: #FFFFFF;
    color: #2A302A;
    border: 1px solid #CDD2CA;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover { background: #F1F4EE; }
QPushButton#primaryButton { background: #86BC25; color: #0B0D0B; border-color: #75A61E; font-weight: 700; }
QPushButton#dangerButton { color: #C73737; }
QPushButton#compactButton, QPushButton#edgeClose { min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; padding: 0; }
QPushButton#edgeClose { border: 0; background: transparent; font-size: 18px; }
QPushButton#edgeNav, QPushButton#edgeAction { min-height: 28px; padding: 0 5px; font-size: 10px; }
QPushButton#navButton { border: 0; background: transparent; color: #505850; text-align: left; padding-left: 12px; }
QPushButton#navButton:checked { color: #171A17; background: #E7EDE2; border-left: 3px solid #86BC25; }
QPushButton#viewButton:checked { background: #86BC25; color: #0B0D0B; border-color: #75A61E; }
QPushButton#calendarDay { min-height: 22px; max-height: 22px; min-width: 22px; max-width: 28px; padding: 0; border: 0; background: transparent; }
QPushButton#calendarDayToday { background: #86BC25; color: #0B0D0B; border: 0; }
QPushButton#calendarTask { min-height: 16px; max-height: 18px; padding: 0 2px; border: 0; border-radius: 0; background: transparent; color: #273126; text-align: left; font-size: 9px; font-weight: 700; }
QFrame#calendarCell { background: #FFFFFF; border-right: 1px solid #D9DDD7; border-bottom: 1px solid #D9DDD7; }
QFrame#calendarCellSelected { background: #EDF4E5; border: 1px solid #86BC25; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit {
    min-height: 34px;
    padding: 2px 8px;
    background: #FFFFFF;
    color: #191C19;
    border: 1px solid #CBD1C8;
    border-radius: 8px;
    selection-background-color: #86BC25;
    selection-color: #0B0D0B;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus { border-color: #6E9E19; }
QTableWidget { background: #FFFFFF; alternate-background-color: #F7F8F5; border: 0; gridline-color: #E0E4DE; selection-background-color: #EDF4E5; selection-color: #171A17; }
QHeaderView::section { background: #FFFFFF; color: #626A62; border: 0; border-bottom: 1px solid #D7DCD4; padding: 8px; font-size: 10px; font-weight: 700; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #B8BFB5; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #FFFFFF; color: #171A17; border: 1px solid #C8CEC5; }
"""


def apply_theme(application: QApplication, theme: str) -> None:
    application.setStyle("Fusion")
    application.setStyleSheet(LIGHT_STYLESHEET if theme == "light" else DARK_STYLESHEET)
    palette = application.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor(LIME))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0B0D0B"))
    application.setPalette(palette)
    application.setFont(QFont("Noto Sans JP", 10, QFont.Weight.Medium))
