from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dandori.ui.theme import COLOR_PALETTES, get_palette, normalize_appearance


class ColorSwatch(QFrame):
    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setStyleSheet(
            f"background-color: {color}; border: 1px solid rgba(128,128,128,0.35); "
            "border-radius: 16px;"
        )


class ThemeDialog(QDialog):
    theme_selected = Signal(str, str)

    def __init__(self, palette_key: str, appearance: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("カラーテーマ")
        self.setMinimumSize(500, 620)
        self.palette_key = get_palette(palette_key).key
        self.appearance = normalize_appearance(appearance)

        title = QLabel("カラーテーマ")
        title.setObjectName("pageTitle")

        dark_radio = QRadioButton("ダーク")
        light_radio = QRadioButton("ライト")
        dark_radio.setChecked(self.appearance == "dark")
        light_radio.setChecked(self.appearance == "light")
        appearance_group = QButtonGroup(self)
        appearance_group.addButton(dark_radio)
        appearance_group.addButton(light_radio)
        dark_radio.toggled.connect(lambda checked: self._set_appearance("dark", checked))
        light_radio.toggled.connect(lambda checked: self._set_appearance("light", checked))
        appearance_layout = QHBoxLayout()
        appearance_layout.setSpacing(18)
        appearance_layout.addWidget(dark_radio)
        appearance_layout.addWidget(light_radio)
        appearance_layout.addStretch()

        palette_widget = QWidget()
        palette_layout = QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(8)
        palette_group = QButtonGroup(self)
        for palette in COLOR_PALETTES:
            row = QFrame()
            row.setObjectName("paletteRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 9, 14, 9)
            row_layout.setSpacing(10)
            for color in palette.colors:
                row_layout.addWidget(ColorSwatch(color))
            radio = QRadioButton(palette.label)
            radio.setProperty("paletteKey", palette.key)
            radio.setChecked(palette.key == self.palette_key)
            radio.toggled.connect(
                lambda checked, key=palette.key: self._set_palette(key, checked)
            )
            palette_group.addButton(radio)
            row_layout.addSpacing(8)
            row_layout.addWidget(radio, 1)
            palette_layout.addWidget(row)
        palette_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(palette_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("キャンセル")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(appearance_layout)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

    def _set_palette(self, palette_key: str, checked: bool) -> None:
        if checked:
            self.palette_key = palette_key

    def _set_appearance(self, appearance: str, checked: bool) -> None:
        if checked:
            self.appearance = appearance

    def _save(self) -> None:
        self.theme_selected.emit(self.palette_key, self.appearance)
        self.accept()
