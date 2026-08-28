from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QRadioButton

from dandori.ui.theme import (
    COLOR_PALETTES,
    apply_theme,
    build_stylesheet,
    get_palette,
    theme_accent_colors,
)
from dandori.ui.theme_dialog import ThemeDialog

EXPECTED_PALETTES = {
    "default": ("#1C1C1E", "#8E8E93", "#F2F2F7"),
    "cocoa-dusk": ("#6F4E37", "#A67B5B", "#F5E6D3"),
    "blue-horizon": ("#3D5A80", "#6B90B2", "#DCE8F2"),
    "blush-harmony": ("#ED6A5A", "#5CA4A9", "#9BC1BC"),
    "violet-dream": ("#7868D0", "#B076C8", "#F0E8F6"),
    "cotton-bloom": ("#F2A0B4", "#F4B0C4", "#FFF0F4"),
    "earthy-moss": ("#84AE92", "#9ABF8A", "#F2E4D8"),
    "crystal-mist": ("#8EC5D6", "#B4D8E7", "#EDF5FA"),
    "candy-pop": ("#B7B1F2", "#FDB7EA", "#FFDCCC"),
    "midnight-linen": ("#123458", "#D4C9BE", "#F1EFEC"),
    "rosy-overcast": ("#8A7A7F", "#C4A8B1", "#FBF9FA"),
}


def test_all_reference_palettes_are_available():
    assert {palette.key: palette.colors for palette in COLOR_PALETTES} == EXPECTED_PALETTES


def test_every_palette_builds_dark_and_light_stylesheets():
    for palette_key, colors in EXPECTED_PALETTES.items():
        assert get_palette(palette_key).colors == colors
        for appearance in ("dark", "light"):
            stylesheet = build_stylesheet(palette_key, appearance)
            assert "QWidget" in stylesheet
            assert "$" not in stylesheet


def test_accent_button_text_keeps_readable_contrast():
    def luminance(color: str) -> float:
        channels = []
        for index in (1, 3, 5):
            normalized = int(color[index : index + 2], 16) / 255
            channels.append(
                normalized / 12.92
                if normalized <= 0.04045
                else ((normalized + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    for palette_key in EXPECTED_PALETTES:
        for appearance in ("dark", "light"):
            accent, foreground = theme_accent_colors(palette_key, appearance)
            lighter, darker = sorted((luminance(accent), luminance(foreground)), reverse=True)
            assert (lighter + 0.05) / (darker + 0.05) >= 4.5


def test_switching_to_light_resets_palette_colors(qapp):
    apply_theme(qapp, "blue-horizon", "dark")
    apply_theme(qapp, "cotton-bloom", "light")

    palette = qapp.palette()
    assert palette.color(QPalette.ColorRole.Base).name().upper() == "#FFFFFF"
    assert palette.color(QPalette.ColorRole.ButtonText).name().upper() == "#1C1C1E"
    assert palette.color(QPalette.ColorRole.PlaceholderText).name().upper() == "#66666B"


def test_theme_dialog_lists_every_palette(qtbot):
    dialog = ThemeDialog("blue-horizon", "light")
    qtbot.addWidget(dialog)

    palette_radios = [
        radio
        for radio in dialog.findChildren(QRadioButton)
        if radio.property("paletteKey") is not None
    ]

    assert len(palette_radios) == 11
    assert next(radio for radio in palette_radios if radio.isChecked()).property(
        "paletteKey"
    ) == "blue-horizon"
