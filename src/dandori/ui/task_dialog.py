from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QDate
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import ACTIVE_STATUSES, Priority, TaskStatus
from dandori.infrastructure.models import Task
from dandori.services.task_service import TaskInput, TaskService
from dandori.ui.category_dialog import CategoryManagerDialog
from dandori.ui.time_combo import TimeComboBox


class TaskDialog(QDialog):
    def __init__(
        self,
        task_service: TaskService,
        task: Task | None = None,
        initial_date: date | None = None,
        initial_input: TaskInput | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.task = task
        self.saved_task: Task | None = None
        self.initial_date = initial_date
        self._allow_close = False
        self.setWindowTitle("タスクを編集" if task else "タスクを追加")
        self.setMinimumSize(360, 400)
        self.resize(520, 620)

        title = QLabel("タスクを編集" if task else "タスクを追加")
        title.setObjectName("pageTitle")

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("補足、完了条件、確認事項など")
        self.memo_edit.setMinimumHeight(90)

        self.status_combo = QComboBox()
        statuses = tuple(TaskStatus) if task else ACTIVE_STATUSES
        for status in statuses:
            self.status_combo.addItem(status.label, status)

        self.priority_combo = QComboBox()
        for priority in Priority:
            self.priority_combo.addItem(priority.label, priority)

        self.category_combo = QComboBox()
        self._reload_categories()
        category_manage_button = QPushButton("管理")
        category_manage_button.clicked.connect(self._manage_categories)
        category_row = QWidget()
        category_layout = QHBoxLayout(category_row)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(6)
        category_layout.addWidget(self.category_combo, 1)
        category_layout.addWidget(category_manage_button)

        self.due_mode = QComboBox()
        self.due_mode.addItem("期限なし", "none")
        self.due_mode.addItem("日付のみ", "date")
        self.due_mode.addItem("日時を指定", "datetime")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy/MM/dd")
        base_date = initial_date or date.today()
        self.due_date_edit.setDate(QDate(base_date.year, base_date.month, base_date.day))
        self.due_time_edit = TimeComboBox()
        self.due_time_edit.set_time(time(17, 0))

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.addRow("タスク名 *", self.title_edit)
        form.addRow("メモ", self.memo_edit)
        form.addRow("状態", self.status_combo)
        form.addRow("重要度", self.priority_combo)
        form.addRow("カテゴリ", category_row)
        form.addRow("期限", self.due_mode)
        form.addRow("期限日", self.due_date_edit)
        form.addRow("期限時刻", self.due_time_edit)
        self.due_date_label = form.labelForField(self.due_date_edit)
        self.due_time_label = form.labelForField(self.due_time_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(form_widget)

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
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.buttons)

        self.due_mode.currentIndexChanged.connect(self._sync_due_controls)
        self._load_task(task, initial_input)
        self._sync_due_controls()
        self._initial_state = self._draft_state()
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self._save)
        self.title_edit.setFocus()

    def _load_task(self, task: Task | None, initial_input: TaskInput | None) -> None:
        if task is None:
            self.priority_combo.setCurrentIndex(int(Priority.NORMAL) - 1)
            self.status_combo.setCurrentIndex(0)
            default_id = self.task_service.default_category().id
            self.category_combo.setCurrentIndex(self.category_combo.findData(default_id))
            if initial_input is not None:
                self.title_edit.setText(initial_input.title)
                self.memo_edit.setPlainText(initial_input.memo)
                self.status_combo.setCurrentIndex(
                    max(0, self.status_combo.findData(initial_input.status))
                )
                self.priority_combo.setCurrentIndex(
                    self.priority_combo.findData(initial_input.priority)
                )
                category_id = initial_input.category_id or default_id
                self.category_combo.setCurrentIndex(
                    self.category_combo.findData(category_id)
                )
                if initial_input.due_date is not None:
                    self.due_date_edit.setDate(
                        QDate(
                            initial_input.due_date.year,
                            initial_input.due_date.month,
                            initial_input.due_date.day,
                        )
                    )
                    self.due_mode.setCurrentIndex(
                        2 if initial_input.due_time is not None else 1
                    )
                    if initial_input.due_time is not None:
                        self.due_time_edit.set_time(initial_input.due_time)
            elif self.initial_date is not None:
                self.due_mode.setCurrentIndex(1)
            return
        self.title_edit.setText(task.title)
        self.memo_edit.setPlainText(task.memo)
        self.status_combo.setCurrentIndex(self.status_combo.findData(task.status_enum))
        self.priority_combo.setCurrentIndex(self.priority_combo.findData(task.priority_enum))
        self.category_combo.setCurrentIndex(self.category_combo.findData(task.category_id))
        if task.due_at:
            self.due_date_edit.setDate(QDate(task.due_at.year, task.due_at.month, task.due_at.day))
            self.due_mode.setCurrentIndex(2 if task.due_has_time else 1)
            self.due_time_edit.set_time(time(task.due_at.hour, task.due_at.minute))

    def _reload_categories(self, preferred_id: str | None = None) -> None:
        preferred_id = (
            preferred_id
            or self.category_combo.currentData()
            or self.task_service.default_category().id
        )
        self.category_combo.clear()
        for category in self.task_service.list_categories():
            self.category_combo.addItem(category.name, category.id)
        index = self.category_combo.findData(preferred_id)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)

    def _manage_categories(self) -> None:
        preferred_id = self.category_combo.currentData()
        dialog = CategoryManagerDialog(self.task_service, self)
        dialog.categories_changed.connect(lambda: self._reload_categories(preferred_id))
        dialog.exec()
        self._reload_categories(preferred_id)

    def _sync_due_controls(self) -> None:
        mode = self.due_mode.currentData()
        has_date = mode in ("date", "datetime")
        has_time = mode == "datetime"
        self.due_date_label.setVisible(has_date)
        self.due_date_edit.setVisible(has_date)
        self.due_time_label.setVisible(has_time)
        self.due_time_edit.setVisible(has_time)

    def _task_input(self) -> TaskInput:
        due_date_value = None
        due_time_value = None
        if self.due_mode.currentData() in ("date", "datetime"):
            selected_date = self.due_date_edit.date()
            due_date_value = date(selected_date.year(), selected_date.month(), selected_date.day())
            if self.due_mode.currentData() == "datetime":
                due_time_value = self.due_time_edit.time_value()
        return TaskInput(
            title=self.title_edit.text(),
            memo=self.memo_edit.toPlainText(),
            status=TaskStatus(self.status_combo.currentData()),
            priority=Priority(int(self.priority_combo.currentData())),
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
        self._allow_close = True
        self.accept()

    def _draft_state(self) -> tuple[object, ...]:
        return (
            self.title_edit.text(),
            self.memo_edit.toPlainText(),
            self.status_combo.currentData(),
            self.priority_combo.currentData(),
            self.category_combo.currentData(),
            self.due_mode.currentData(),
            self.due_date_edit.date().toString("yyyy-MM-dd"),
            self.due_time_edit.currentText(),
        )

    def _confirm_discard(self) -> bool:
        if (
            self._allow_close
            or not self.isVisible()
            or self._draft_state() == self._initial_state
        ):
            return True
        answer = QMessageBox.question(
            self,
            "変更を破棄",
            "入力中の変更を破棄して閉じますか？",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def reject(self) -> None:
        if self._confirm_discard():
            self._allow_close = True
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            self._allow_close = True
            event.accept()
        else:
            event.ignore()
