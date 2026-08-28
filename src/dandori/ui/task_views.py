from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dandori.infrastructure.models import Task


def format_due(task: Task) -> str:
    if task.due_at is None:
        return "期限なし"
    if task.due_has_time:
        return task.due_at.strftime("%Y/%m/%d %H:%M")
    return task.due_at.strftime("%Y/%m/%d")


class TaskDetailWidget(QFrame):
    edit_requested = Signal(str)
    complete_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("detailSurface")
        self._task: Task | None = None

        self.title_label = QLabel("タスクを選択してください")
        self.title_label.setObjectName("detailTitle")
        self.title_label.setWordWrap(True)

        self.status_value = QLabel("—")
        self.due_value = QLabel("—")
        self.priority_value = QLabel("—")
        self.category_value = QLabel("—")
        self.memo_value = QLabel("—")
        self.memo_value.setWordWrap(True)
        self.subtask_value = QLabel("—")

        self.edit_button = QPushButton("編集")
        self.complete_button = QPushButton("完了")
        self.complete_button.setObjectName("primaryButton")
        self.edit_button.clicked.connect(self._emit_edit)
        self.complete_button.clicked.connect(self._emit_complete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(7)
        layout.addWidget(self.title_label)
        self._add_field(layout, "状態", self.status_value)
        self._add_field(layout, "期限", self.due_value)
        self._add_field(layout, "重要度", self.priority_value)
        self._add_field(layout, "カテゴリ", self.category_value)
        self._add_field(layout, "メモ", self.memo_value)
        self._add_field(layout, "サブタスク", self.subtask_value)
        layout.addStretch()

        actions = QHBoxLayout()
        actions.addWidget(self.edit_button)
        actions.addWidget(self.complete_button)
        layout.addLayout(actions)
        self.set_task(None)

    @staticmethod
    def _add_field(layout: QVBoxLayout, label: str, value: QLabel) -> None:
        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")
        layout.addSpacing(6)
        layout.addWidget(field_label)
        layout.addWidget(value)

    def set_task(self, task: Task | None) -> None:
        self._task = task
        enabled = task is not None
        self.edit_button.setEnabled(enabled)
        self.complete_button.setEnabled(
            enabled and task.status_enum.label not in ("完了", "取り消し") if task else False
        )
        if task is None:
            self.title_label.setText("タスクを選択してください")
            for label in (
                self.status_value,
                self.due_value,
                self.priority_value,
                self.category_value,
                self.memo_value,
                self.subtask_value,
            ):
                label.setText("—")
            return
        self.title_label.setText(task.title)
        self.status_value.setText(task.status_enum.label)
        self.due_value.setText(format_due(task))
        self.priority_value.setText(task.priority_enum.label)
        self.category_value.setText(task.category.name)
        self.memo_value.setText(task.memo or "メモなし")
        completed = sum(1 for subtask in task.subtasks if subtask.completed)
        self.subtask_value.setText(f"{completed}/{len(task.subtasks)}" if task.subtasks else "なし")

    def _emit_edit(self) -> None:
        if self._task:
            self.edit_requested.emit(self._task.id)

    def _emit_complete(self) -> None:
        if self._task:
            self.complete_requested.emit(self._task.id)


class TaskTablePage(QWidget):
    task_selected = Signal(str)
    edit_requested = Signal(str)
    complete_requested = Signal(str)

    HEADERS = ("タスク", "状態", "重要度", "期限", "カテゴリ")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tasks: list[Task] = []
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(self.HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)

        table_surface = QFrame()
        table_surface.setObjectName("surface")
        table_layout = QVBoxLayout(table_surface)
        table_layout.setContentsMargins(1, 1, 1, 1)
        table_layout.addWidget(self.table)

        self.detail = TaskDetailWidget()
        self.detail.setMinimumWidth(245)
        self.detail.setMaximumWidth(330)
        self.detail.edit_requested.connect(self.edit_requested)
        self.detail.complete_requested.connect(self.complete_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(table_surface)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def set_tasks(self, tasks: list[Task], preferred_task_id: str | None = None) -> None:
        self.tasks = tasks
        self.table.setRowCount(len(tasks))
        selected_row = -1
        for row, task in enumerate(tasks):
            values = (
                task.title,
                task.status_enum.label,
                task.priority_enum.label,
                format_due(task),
                task.category.name,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                item.setToolTip(task.memo if column == 0 and task.memo else value)
                self.table.setItem(row, column, item)
            if task.id == preferred_task_id:
                selected_row = row

        if tasks:
            target_row = selected_row if selected_row >= 0 else 0
            self.table.selectRow(target_row)
        else:
            self.detail.set_task(None)

    def selected_task_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.tasks):
            return None
        return self.tasks[row].id

    def _selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.tasks):
            self.detail.set_task(None)
            return
        task = self.tasks[row]
        self.detail.set_task(task)
        self.task_selected.emit(task.id)
