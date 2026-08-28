from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import TaskStatus
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
    restore_requested = Signal(str)

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
        self.complete_button.clicked.connect(self._emit_primary_action)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(7)
        content_layout.addWidget(self.title_label)
        self._add_field(content_layout, "状態", self.status_value)
        self._add_field(content_layout, "期限", self.due_value)
        self._add_field(content_layout, "重要度", self.priority_value)
        self._add_field(content_layout, "カテゴリ", self.category_value)
        self._add_field(content_layout, "メモ", self.memo_value)
        self.subtask_field_label = self._add_field(
            content_layout, "サブタスク", self.subtask_value
        )
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        actions = QHBoxLayout()
        actions.addWidget(self.edit_button)
        actions.addWidget(self.complete_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(7)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)
        self.set_task(None)

    @staticmethod
    def _add_field(layout: QVBoxLayout, label: str, value: QLabel) -> QLabel:
        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")
        layout.addSpacing(6)
        layout.addWidget(field_label)
        layout.addWidget(value)
        return field_label

    def set_task(self, task: Task | None) -> None:
        self._task = task
        enabled = task is not None
        self.edit_button.setEnabled(enabled)
        terminal = bool(
            task
            and task.status_enum in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        )
        self.complete_button.setEnabled(enabled)
        self.complete_button.setText("元に戻す" if terminal else "完了")
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
            self.subtask_field_label.hide()
            self.subtask_value.hide()
            return
        self.title_label.setText(task.title)
        self.status_value.setText(task.status_enum.label)
        self.due_value.setText(format_due(task))
        self.priority_value.setText(task.priority_enum.label)
        self.category_value.setText(task.category.name)
        self.memo_value.setText(task.memo or "メモなし")
        completed = sum(1 for subtask in task.subtasks if subtask.completed)
        self.subtask_value.setText(f"{completed}/{len(task.subtasks)}" if task.subtasks else "なし")
        self.subtask_field_label.setVisible(bool(task.subtasks))
        self.subtask_value.setVisible(bool(task.subtasks))

    def _emit_edit(self) -> None:
        if self._task:
            self.edit_requested.emit(self._task.id)

    def _emit_primary_action(self) -> None:
        if self._task is None:
            return
        if self._task.status_enum in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            self.restore_requested.emit(self._task.id)
        else:
            self.complete_requested.emit(self._task.id)


class TaskTablePage(QWidget):
    task_selected = Signal(str)
    edit_requested = Signal(str)
    complete_requested = Signal(str)
    restore_requested = Signal(str)
    add_requested = Signal()

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
        self.table.verticalHeader().setDefaultSectionSize(36)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(self.HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_edit())

        empty_widget = QWidget()
        self.empty_title = QLabel("表示するタスクはありません")
        self.empty_title.setObjectName("detailTitle")
        self.empty_hint = QLabel("新しいタスクを追加すると、ここに表示されます。")
        self.empty_hint.setObjectName("muted")
        self.empty_hint.setWordWrap(True)
        self.empty_button = QPushButton("＋ タスクを追加")
        self.empty_button.setObjectName("primaryButton")
        self.empty_button.clicked.connect(lambda: self.add_requested.emit())
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(28, 28, 28, 28)
        empty_layout.addStretch()
        empty_layout.addWidget(self.empty_title, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_hint, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addSpacing(8)
        empty_layout.addWidget(self.empty_button, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()

        self.table_stack = QStackedWidget()
        self.table_stack.addWidget(self.table)
        self.table_stack.addWidget(empty_widget)

        table_surface = QFrame()
        table_surface.setObjectName("surface")
        table_layout = QVBoxLayout(table_surface)
        table_layout.setContentsMargins(1, 1, 1, 1)
        table_layout.addWidget(self.table_stack)

        self.detail = TaskDetailWidget()
        self.detail.setMinimumWidth(220)
        self.detail.setMaximumWidth(320)
        self.detail.edit_requested.connect(self.edit_requested)
        self.detail.complete_requested.connect(self.complete_requested)
        self.detail.restore_requested.connect(self.restore_requested)

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
        self.table_stack.setCurrentIndex(0 if tasks else 1)
        self.detail.setVisible(bool(tasks))
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
            self.detail.set_task(tasks[target_row])
        else:
            self.detail.set_task(None)

    def set_empty_context(self, view: str) -> None:
        messages = {
            "today": (
                "今日が期限のタスクはありません",
                "必要なタスクがあれば追加できます。",
                True,
            ),
            "all": (
                "表示するタスクはありません",
                "新しいタスクを追加すると、ここに表示されます。",
                True,
            ),
            "overdue": (
                "期限切れのタスクはありません",
                "現在、対応が遅れているタスクはありません。",
                False,
            ),
            "completed": (
                "完了済みのタスクはありません",
                "完了または取り消したタスクがここに表示されます。",
                False,
            ),
        }
        title, hint, show_add = messages.get(view, messages["all"])
        self.empty_title.setText(title)
        self.empty_hint.setText(hint)
        self.empty_button.setVisible(show_add)

    def _emit_edit(self) -> None:
        task_id = self.selected_task_id()
        if task_id:
            self.edit_requested.emit(task_id)

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
