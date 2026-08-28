from __future__ import annotations

from datetime import time

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QComboBox


class TimeComboBox(QComboBox):
    def __init__(self, include_no_time: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.include_no_time = include_no_time
        if include_no_time:
            self.addItem("時刻なし", None)
        for hour in range(24):
            for minute in (0, 30):
                value = time(hour, minute)
                self.addItem(value.strftime("%H:%M"), value)
        self.setEditable(True)
        if self.lineEdit() is not None:
            expression = QRegularExpression(r"(?:[01]\d|2[0-3]):[0-5]\d")
            self.lineEdit().setValidator(QRegularExpressionValidator(expression, self))

    def set_time(self, value: time | None) -> None:
        if value is None and self.include_no_time:
            self.setCurrentIndex(0)
            return
        if value is None:
            value = time(17, 0)
        text = value.strftime("%H:%M")
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(text)

    def time_value(self) -> time | None:
        if self.include_no_time and self.currentIndex() == 0 and self.currentData() is None:
            return None
        value = self.currentText().strip()
        try:
            hour_text, minute_text = value.split(":", maxsplit=1)
            return time(int(hour_text), int(minute_text))
        except (TypeError, ValueError) as error:
            raise ValueError("期限時刻をHH:MM形式で入力してください。") from error
