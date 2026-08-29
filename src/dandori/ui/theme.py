from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class ColorPalette:
    key: str
    label: str
    colors: tuple[str, str, str]


COLOR_PALETTES = (
    ColorPalette("default", "デフォルト", ("#1C1C1E", "#8E8E93", "#F2F2F7")),
    ColorPalette("cocoa-dusk", "Cocoa Dusk", ("#6F4E37", "#A67B5B", "#F5E6D3")),
    ColorPalette("blue-horizon", "Blue Horizon", ("#3D5A80", "#6B90B2", "#DCE8F2")),
    ColorPalette("blush-harmony", "Blush Harmony", ("#ED6A5A", "#5CA4A9", "#9BC1BC")),
    ColorPalette("violet-dream", "Violet Dream", ("#7868D0", "#B076C8", "#F0E8F6")),
    ColorPalette("cotton-bloom", "Cotton Bloom", ("#F2A0B4", "#F4B0C4", "#FFF0F4")),
    ColorPalette("earthy-moss", "Earthy Moss", ("#84AE92", "#9ABF8A", "#F2E4D8")),
    ColorPalette("crystal-mist", "Crystal Mist", ("#8EC5D6", "#B4D8E7", "#EDF5FA")),
    ColorPalette("candy-pop", "Candy Pop", ("#B7B1F2", "#FDB7EA", "#FFDCCC")),
    ColorPalette("midnight-linen", "Midnight Linen", ("#123458", "#D4C9BE", "#F1EFEC")),
    ColorPalette("rosy-overcast", "Rosy Overcast", ("#8A7A7F", "#C4A8B1", "#FBF9FA")),
)
PALETTE_BY_KEY = {palette.key: palette for palette in COLOR_PALETTES}
APPEARANCES = {"dark", "light"}


def load_bundled_fonts() -> list[str]:
    font_directory = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    loaded_families: list[str] = []
    for font_file in font_directory.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id >= 0:
            loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return loaded_families


def get_palette(key: str) -> ColorPalette:
    return PALETTE_BY_KEY.get(key, PALETTE_BY_KEY["default"])


def normalize_appearance(appearance: str) -> str:
    return appearance if appearance in APPEARANCES else "dark"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(first: str, second: str, second_weight: float) -> str:
    first_rgb = _rgb(first)
    second_rgb = _rgb(second)
    channels = (
        round(a * (1 - second_weight) + b * second_weight)
        for a, b in zip(first_rgb, second_rgb, strict=True)
    )
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _relative_luminance(color: str) -> float:
    channels = []
    for channel in _rgb(color):
        normalized = channel / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_color(background: str) -> str:
    background_luminance = _relative_luminance(background)
    dark = "#000000"
    dark_ratio = (background_luminance + 0.05) / (_relative_luminance(dark) + 0.05)
    light_ratio = 1.05 / (background_luminance + 0.05)
    return dark if dark_ratio >= light_ratio else "#FFFFFF"


def theme_accent_colors(palette_key: str, appearance: str) -> tuple[str, str]:
    palette = get_palette(palette_key)
    accent = palette.colors[1] if normalize_appearance(appearance) == "dark" else palette.colors[0]
    return accent, _contrast_color(accent)


STYLESHEET_TEMPLATE = Template(
    """
QWidget {
    background: $background;
    color: $text;
    font-family: "Noto Sans JP", "Yu Gothic UI";
    font-size: 12px;
    font-weight: 500;
}
QLabel { background: transparent; }
QMainWindow, QDialog { background: $background; }
QDialog#edgeWindow { border-left: 1px solid $border; }
QFrame#sidebar { background: $sidebar; border-right: 1px solid $border; }
QFrame#surface, QFrame#detailSurface, QFrame#edgeCard, QFrame#paletteRow {
    background: $surface;
    border: 1px solid $border;
    border-radius: 11px;
}
QFrame#undoBar {
    background: $selection;
    border: 1px solid $accent;
    border-radius: 9px;
}
QPushButton#undoButton {
    min-height: 26px;
    padding: 0 7px;
    background: transparent;
    color: $text;
    border-color: $border_strong;
}
QFrame#paletteRow { min-height: 66px; }
QFrame#paletteRow[selected="true"] {
    background: $selection;
    border: 2px solid $accent;
}
QLabel#pageTitle { color: $text; font-size: 22px; font-weight: 700; }
QLabel#sectionLabel { color: $accent; font-size: 10px; font-weight: 700; }
QLabel#muted, QLabel#fieldLabel { color: $muted; }
QLabel#fieldLabel { font-size: 10px; font-weight: 700; }
QLabel#detailTitle { color: $text; font-size: 17px; font-weight: 700; }
QLabel#edgeTitle { color: $text; font-size: 15px; font-weight: 700; }
QLabel#edgeTaskTitle { color: $text; font-size: 11px; font-weight: 700; }
QPushButton {
    min-height: 32px;
    padding: 0 11px;
    background: $control;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton:hover { background: $control_hover; }
QPushButton:pressed { background: $selection; }
QPushButton:disabled { color: $disabled_text; background: $surface; border-color: $border; }
QPushButton#primaryButton {
    background: $accent;
    color: $accent_text;
    border-color: $accent;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#dangerButton { color: $danger; }
QProgressBar#taskProgress {
    min-height: 18px;
    max-height: 18px;
    background: $control;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 6px;
    text-align: center;
    font-size: 10px;
    font-weight: 700;
}
QProgressBar#taskProgress::chunk {
    background: $accent;
    border-radius: 5px;
}
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
    color: $muted;
    text-align: left;
    padding-left: 12px;
}
QPushButton#navButton:checked {
    color: $text;
    background: $selection;
    border-left: 3px solid $accent;
}
QPushButton#viewButton:checked {
    background: $accent;
    color: $accent_text;
    border-color: $accent;
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
QPushButton#calendarDayToday { background: $accent; color: $accent_text; border: 0; }
QPushButton#calendarTask {
    min-height: 16px;
    max-height: 18px;
    padding: 0 2px;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: $text;
    text-align: left;
    font-size: 9px;
    font-weight: 700;
}
QPushButton#calendarMore {
    min-height: 16px;
    max-height: 18px;
    padding: 0 2px;
    border: 0;
    background: transparent;
    color: $muted;
    text-align: left;
    font-size: 9px;
}
QPushButton#calendarDay[outsideMonth="true"] { color: $disabled_text; }
QFrame#calendarCell { background: $surface; border-right: 1px solid $border; border-bottom: 1px solid $border; }
QFrame#calendarCellSelected { background: $selection; border: 1px solid $accent; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit {
    min-height: 34px;
    padding: 2px 8px;
    background: $input;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {
    border-color: $accent;
}
QComboBox QAbstractItemView {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    selection-background-color: $selection;
    selection-color: $text;
    outline: 0;
}
QTableWidget, QListWidget {
    background: $surface;
    alternate-background-color: $surface_alt;
    border: 0;
    gridline-color: $border;
    selection-background-color: $selection;
    selection-color: $text;
    outline: 0;
}
QListWidget::item { padding: 6px; }
QHeaderView::section {
    background: $surface;
    color: $muted;
    border: 0;
    border-bottom: 1px solid $border;
    padding: 8px;
    font-size: 10px;
    font-weight: 700;
}
QRadioButton { spacing: 8px; background: transparent; }
QRadioButton::indicator { width: 16px; height: 16px; }
QRadioButton::indicator:unchecked { border: 1px solid $muted; border-radius: 8px; background: transparent; }
QRadioButton::indicator:checked { border: 5px solid $accent; border-radius: 8px; background: $surface; }
QCheckBox { spacing: 7px; background: transparent; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: $scrollbar; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: $surface_alt; color: $text; border: 1px solid $border_strong; }
"""
)


def _theme_tokens(palette_key: str, appearance: str) -> dict[str, str]:
    palette = get_palette(palette_key)
    appearance = normalize_appearance(appearance)
    first, second, third = palette.colors
    if appearance == "dark":
        accent = second
        return {
            "background": "#000000",
            "surface": "#141415",
            "surface_alt": "#1C1C1E",
            "sidebar": "#0B0B0C",
            "control": "#1C1C1E",
            "control_hover": _mix("#1C1C1E", second, 0.16),
            "input": "#1C1C1E",
            "text": "#F2F2F7",
            "muted": "#A1A1A6",
            "disabled_text": "#636368",
            "border": "#2C2C2E",
            "border_strong": "#3A3A3C",
            "selection": _mix("#1C1C1E", first, 0.34),
            "accent": accent,
            "accent_hover": _mix(accent, third, 0.18),
            "accent_text": _contrast_color(accent),
            "danger": "#FF6961",
            "scrollbar": _mix("#3A3A3C", second, 0.18),
        }
    accent = first
    return {
        "background": _mix("#FFFFFF", third, 0.20),
        "surface": "#FFFFFF",
        "surface_alt": _mix("#FFFFFF", third, 0.42),
        "sidebar": _mix("#FFFFFF", third, 0.55),
        "control": "#FFFFFF",
        "control_hover": _mix("#FFFFFF", third, 0.58),
        "input": "#FFFFFF",
        "text": "#1C1C1E",
        "muted": "#66666B",
        "disabled_text": "#9B9BA0",
        "border": _mix("#D8D8DC", second, 0.14),
        "border_strong": _mix("#C6C6CA", second, 0.20),
        "selection": _mix("#FFFFFF", second, 0.30),
        "accent": accent,
        "accent_hover": _mix(accent, second, 0.28),
        "accent_text": _contrast_color(accent),
        "danger": "#C63D36",
        "scrollbar": _mix("#B8B8BC", second, 0.20),
    }


def build_stylesheet(palette_key: str, appearance: str) -> str:
    return STYLESHEET_TEMPLATE.substitute(_theme_tokens(palette_key, appearance))


def apply_theme(application: QApplication, palette_key: str, appearance: str) -> None:
    appearance = normalize_appearance(appearance)
    tokens = _theme_tokens(palette_key, appearance)
    application.setStyle("Fusion")
    application.setStyleSheet(build_stylesheet(palette_key, appearance))
    palette = application.style().standardPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(tokens["background"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(tokens["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(tokens["control"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["text"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(tokens["accent"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["accent_text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["muted"]))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            QColor(tokens["disabled_text"]),
        )
    application.setPalette(palette)
    application.setFont(QFont("Noto Sans JP", 10, QFont.Weight.Medium))
