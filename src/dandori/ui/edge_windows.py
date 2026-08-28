from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QDate, Qt, QTime, Signal
from PySide6.QtGui import QCloseEvent, QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import Priority
from dandori.infrastructure.models import Task
from dandori.services.task_service import TaskInput, TaskService
from dandori.ui.task_dialog import TaskDialog
from dandori.ui.task_views import format_due


class EdgeWindowBase(QDialog):
    BASE_WIDTH = 180

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setMinimumWidth(160)
        self.setMaximumWidth(320)
        self.resize(self.BASE_WIDTH, 600)

    def show_at_screen_edge(self) -> None:
        screen = self._screen_at_cursor()
        geometry = screen.availableGeometry()
        width = max(self.minimumWidth(), min(self.width(), self.maximumWidth()))
        self.setGeometry(geometry.right() - width + 1, geometry.top(), width, geometry.height())
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _screen_at_cursor():
        from PySide6.QtGui import QGuiApplication

        return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()


class EdgeTaskWindow(EdgeWindowBase):
    tasks_changed = Signal()
    open_main_requested = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.setWindowTitle("DANDORI - タスク")

        title = QLabel("今日と次のタスク")
        title.setObjectName("detailTitle")
        title.setWordWrap(True)
        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)
        header = QHBoxLayout()
        header.addWidget(title, 1)
        header.addWidget(close_button)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(7)
        self.cards_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.cards_widget)

        open_main = QPushButton("全表示を開く")
        open_main.setObjectName("primaryButton")
        open_main.clicked.connect(self.open_main_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 12, 9, 12)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(scroll, 1)
        layout.addWidget(open_main)

    def refresh(self) -> None:
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tasks = self.task_service.list_active_tasks()
        if not tasks:
            empty = QLabel("表示するタスクはありません")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            self.cards_layout.insertWidget(0, empty)
            return
        for task in tasks:
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, self._task_card(task))

    def _task_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setObjectName("edgeCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        title = QLabel(task.title)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700;")
        meta = QLabel(f"{format_due(task)}\n{task.priority_enum.label} ・ {task.status_enum.label}")
        meta.setObjectName("muted")
        meta.setWordWrap(True)

        complete = QPushButton("完了")
        edit = QPushButton("編集")
        complete.clicked.connect(lambda _checked=False, task_id=task.id: self._complete(task_id))
        edit.clicked.connect(lambda _checked=False, task_id=task.id: self._edit(task_id))
        actions = QHBoxLayout()
        actions.setSpacing(4)
        actions.addWidget(complete)
        actions.addWidget(edit)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 9, 8, 8)
        layout.setSpacing(5)
        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addLayout(actions)
        return card

    def _complete(self, task_id: str) -> None:
        self.task_service.complete_task(task_id)
        self.refresh()
        self.tasks_changed.emit()

    def _edit(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        dialog = TaskDialog(self.task_service, task=task, parent=self)
        if dialog.exec():
            self.refresh()
            self.tasks_changed.emit()

    def show_at_screen_edge(self) -> None:
        self.refresh()
        super().show_at_screen_edge()


class EdgeAddWindow(EdgeWindowBase):
    task_created = Signal(str)

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.setWindowTitle("DANDORI - タスク追加")

        title = QLabel("タスクを追加")
        title.setObjectName("detailTitle")
        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)
        header = QHBoxLayout()
        header.addWidget(title, 1)
        header.addWidget(close_button)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.due_enabled = QCheckBox("期限を設定")
        self.due_date = QDateEdit(QDate.currentDate())
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("yyyy/MM/dd")
        self.due_time = QTimeEdit(QTime(17, 0))
        self.due_time.setDisplayFormat("HH:mm")
        self.priority = QComboBox()
        for priority in Priority:
            self.priority.addItem(priority.label, priority)
        self.priority.setCurrentIndex(int(Priority.NORMAL) - 1)
        self.category = QComboBox()
        self._load_categories()

        add_button = QPushButton("タスクを追加")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._create)
        details_button = QPushButton("詳細入力")
        details_button.clicked.connect(self._open_full_dialog)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 12, 9, 12)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(QLabel("タスク名"))
        layout.addWidget(self.title_edit)
        layout.addWidget(self.due_enabled)
        layout.addWidget(self.due_date)
        layout.addWidget(self.due_time)
        layout.addWidget(QLabel("重要度"))
        layout.addWidget(self.priority)
        layout.addWidget(QLabel("カテゴリ"))
        layout.addWidget(self.category)
        layout.addStretch()
        layout.addWidget(details_button)
        layout.addWidget(add_button)
        self.due_enabled.toggled.connect(self._sync_due)
        self._sync_due()

    def _load_categories(self) -> None:
        self.category.clear()
        for category in self.task_service.list_categories():
            self.category.addItem(category.name, category.id)

    def _sync_due(self) -> None:
        self.due_date.setEnabled(self.due_enabled.isChecked())
        self.due_time.setEnabled(self.due_enabled.isChecked())

    def _create(self) -> None:
        selected_date = self.due_date.date()
        selected_time = self.due_time.time()
        due_date_value = None
        due_time_value = None
        if self.due_enabled.isChecked():
            due_date_value = date(selected_date.year(), selected_date.month(), selected_date.day())
            due_time_value = time(selected_time.hour(), selected_time.minute())
        try:
            task = self.task_service.create_task(
                TaskInput(
                    title=self.title_edit.text(),
                    priority=self.priority.currentData(),
                    due_date=due_date_value,
                    due_time=due_time_value,
                    category_id=self.category.currentData(),
                )
            )
        except ValueError as error:
            QMessageBox.warning(self, "追加できません", str(error))
            return
        self.title_edit.clear()
        self.task_created.emit(task.id)
        self.close()

    def _open_full_dialog(self) -> None:
        dialog = TaskDialog(self.task_service, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.task_created.emit(dialog.saved_task.id)
            self.close()

    def show_at_screen_edge(self) -> None:
        self._load_categories()
        self.title_edit.clear()
        super().show_at_screen_edge()
        self.title_edit.setFocus()
