from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class UndoBar(QFrame):
    undo_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("undoBar")
        self._task_id: str | None = None
        self.message = QLabel("タスクを完了しました")
        self.message.setWordWrap(True)
        undo_button = QPushButton("元に戻す")
        undo_button.setObjectName("undoButton")
        undo_button.clicked.connect(self._undo)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 8, 7)
        layout.setSpacing(6)
        layout.addWidget(self.message, 1)
        layout.addWidget(undo_button)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_for_task(self, task_id: str, message: str = "タスクを完了しました") -> None:
        self._task_id = task_id
        self.message.setText(message)
        self.show()
        self.raise_()
        self.timer.start(8000)

    def _undo(self) -> None:
        if self._task_id is None:
            return
        task_id = self._task_id
        self._task_id = None
        self.timer.stop()
        self.hide()
        self.undo_requested.emit(task_id)
