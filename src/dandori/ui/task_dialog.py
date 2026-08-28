from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from dandori.domain.enums import Priority, TaskStatus
from dandori.infrastructure.models import Task
from dandori.services.task_service import TaskInput, TaskService


class TaskDialog(QDialog):
    def __init__(
        self,
        task_service: TaskService,
        task: Task | None = None,
        initial_date: date | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.task = task
        self.saved_task: Task | None = None
        self.setWindowTitle("タスクを編集" if task else "タスクを追加")
        self.setMinimumWidth(460)

        title = QLabel("タスクを編集" if task else "タスクを追加")
        title.setObjectName("pageTitle")

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("補足、完了条件、確認事項など")
        self.memo_edit.setMinimumHeight(90)

        self.status_combo = QComboBox()
        for status in TaskStatus:
            self.status_combo.addItem(status.label, status)

        self.priority_combo = QComboBox()
        for priority in Priority:
            self.priority_combo.addItem(priority.label, priority)

        self.category_combo = QComboBox()
        for category in self.task_service.list_categories():
            self.category_combo.addItem(category.name, category.id)

        self.due_enabled = QCheckBox("期限を設定")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy/MM/dd")
        base_date = initial_date or date.today()
        self.due_date_edit.setDate(QDate(base_date.year, base_date.month, base_date.day))
        self.due_time_enabled = QCheckBox("時刻を指定")
        self.due_time_edit = QTimeEdit()
        self.due_time_edit.setDisplayFormat("HH:mm")
        self.due_time_edit.setTime(QTime(17, 0))

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("タスク名", self.title_edit)
        form.addRow("メモ", self.memo_edit)
        form.addRow("状態", self.status_combo)
        form.addRow("重要度", self.priority_combo)
        form.addRow("カテゴリ", self.category_combo)
        form.addRow("", self.due_enabled)
        form.addRow("期限日", self.due_date_edit)
        form.addRow("", self.due_time_enabled)
        form.addRow("期限時刻", self.due_time_edit)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("キャンセル")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.due_enabled.toggled.connect(self._sync_due_controls)
        self.due_time_enabled.toggled.connect(self._sync_due_controls)
        self._load_task(task)
        self._sync_due_controls()
        self.title_edit.setFocus()

    def _load_task(self, task: Task | None) -> None:
        if task is None:
            self.priority_combo.setCurrentIndex(int(Priority.NORMAL) - 1)
            self.status_combo.setCurrentIndex(0)
            return
        self.title_edit.setText(task.title)
        self.memo_edit.setPlainText(task.memo)
        self.status_combo.setCurrentIndex(self.status_combo.findData(task.status_enum))
        self.priority_combo.setCurrentIndex(self.priority_combo.findData(task.priority_enum))
        self.category_combo.setCurrentIndex(self.category_combo.findData(task.category_id))
        if task.due_at:
            self.due_enabled.setChecked(True)
            self.due_date_edit.setDate(QDate(task.due_at.year, task.due_at.month, task.due_at.day))
            self.due_time_enabled.setChecked(task.due_has_time)
            self.due_time_edit.setTime(QTime(task.due_at.hour, task.due_at.minute))

    def _sync_due_controls(self) -> None:
        enabled = self.due_enabled.isChecked()
        self.due_date_edit.setEnabled(enabled)
        self.due_time_enabled.setEnabled(enabled)
        self.due_time_edit.setEnabled(enabled and self.due_time_enabled.isChecked())

    def _task_input(self) -> TaskInput:
        due_date_value = None
        due_time_value = None
        if self.due_enabled.isChecked():
            selected_date = self.due_date_edit.date()
            due_date_value = date(selected_date.year(), selected_date.month(), selected_date.day())
            if self.due_time_enabled.isChecked():
                selected_time = self.due_time_edit.time()
                due_time_value = time(selected_time.hour(), selected_time.minute())
        return TaskInput(
            title=self.title_edit.text(),
            memo=self.memo_edit.toPlainText(),
            status=self.status_combo.currentData(),
            priority=self.priority_combo.currentData(),
            due_date=due_date_value,
            due_time=due_time_value,
            category_id=self.category_combo.currentData(),
        )

    def _save(self) -> None:
        try:
            task_input = self._task_input()
            if self.task:
                self.saved_task = self.task_service.update_task(self.task.id, task_input)
            else:
                self.saved_task = self.task_service.create_task(task_input)
        except (ValueError, LookupError) as error:
            QMessageBox.warning(self, "保存できません", str(error))
            return
        self.accept()
