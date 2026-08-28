from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QDate, Qt, Signal
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
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import Priority
from dandori.infrastructure.models import Task
from dandori.services.task_service import TaskInput, TaskService
from dandori.ui.category_dialog import CategoryManagerDialog
from dandori.ui.task_dialog import TaskDialog
from dandori.ui.task_views import format_due
from dandori.ui.time_combo import TimeComboBox


class EdgeWindowBase(QDialog):
    BASE_WIDTH = 180

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("edgeWindow")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(self.BASE_WIDTH)
        self.resize(self.BASE_WIDTH, 600)

    def show_at_screen_edge(self) -> None:
        screen = self._screen_at_cursor()
        geometry = screen.availableGeometry()
        self.setGeometry(
            geometry.right() - self.BASE_WIDTH + 1,
            geometry.top(),
            self.BASE_WIDTH,
            geometry.height(),
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def make_header(self, title_text: str) -> QHBoxLayout:
        title = QLabel(title_text)
        title.setObjectName("edgeTitle")
        title.setWordWrap(True)
        close_button = QPushButton("×")
        close_button.setObjectName("edgeClose")
        close_button.setToolTip("閉じる")
        close_button.clicked.connect(self.hide)
        header = QHBoxLayout()
        header.setSpacing(5)
        header.addWidget(title, 1)
        header.addWidget(close_button)
        return header

    @staticmethod
    def make_nav_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("edgeNav")
        return button

    @staticmethod
    def _screen_at_cursor():
        from PySide6.QtGui import QGuiApplication

        return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()


class EdgeTaskWindow(EdgeWindowBase):
    tasks_changed = Signal()
    open_main_requested = Signal()
    open_add_requested = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.setWindowTitle("DANDORI - タスク")

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(7)
        self.cards_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.cards_widget)

        add_button = self.make_nav_button("＋ 追加")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.open_add_requested)
        open_main = self.make_nav_button("全表示")
        open_main.clicked.connect(self.open_main_requested)
        navigation = QHBoxLayout()
        navigation.setSpacing(5)
        navigation.addWidget(add_button)
        navigation.addWidget(open_main)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 10, 9, 10)
        layout.setSpacing(9)
        layout.addLayout(self.make_header("タスク"))
        layout.addWidget(scroll, 1)
        layout.addLayout(navigation)

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
        title.setObjectName("edgeTaskTitle")
        title.setWordWrap(True)
        meta = QLabel(f"{format_due(task)}\n{task.priority_enum.label} ・ {task.status_enum.label}")
        meta.setObjectName("muted")
        meta.setWordWrap(True)

        complete = QPushButton("完了")
        complete.setObjectName("edgeAction")
        edit = QPushButton("編集")
        edit.setObjectName("edgeAction")
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
    open_main_requested = Signal()
    open_tasks_requested = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.setWindowTitle("DANDORI - タスク追加")

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.due_enabled = QCheckBox("期限を設定")
        self.due_date = QDateEdit(QDate.currentDate())
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("yyyy/MM/dd")
        self.due_time = TimeComboBox(include_no_time=True)
        self.due_time.set_time(time(17, 0))
        self.priority = QComboBox()
        for priority in Priority:
            self.priority.addItem(priority.label, priority)
        self.priority.setCurrentIndex(int(Priority.NORMAL) - 1)
        self.category = QComboBox()
        self._load_categories()
        category_manage = QPushButton("…")
        category_manage.setObjectName("compactButton")
        category_manage.setToolTip("カテゴリ管理")
        category_manage.clicked.connect(self._manage_categories)
        category_row = QHBoxLayout()
        category_row.setSpacing(4)
        category_row.addWidget(self.category, 1)
        category_row.addWidget(category_manage)

        form_widget = QWidget()
        form = QVBoxLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.addWidget(self._field_label("タスク名"))
        form.addWidget(self.title_edit)
        form.addWidget(self.due_enabled)
        form.addWidget(self._field_label("期限日"))
        form.addWidget(self.due_date)
        form.addWidget(self._field_label("期限時刻"))
        form.addWidget(self.due_time)
        form.addWidget(self._field_label("重要度"))
        form.addWidget(self.priority)
        form.addWidget(self._field_label("カテゴリ"))
        form.addLayout(category_row)
        form.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_widget)

        add_button = QPushButton("タスクを追加")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._create)
        details_button = QPushButton("詳細入力")
        details_button.setObjectName("edgeNav")
        details_button.clicked.connect(self._open_full_dialog)

        tasks_button = self.make_nav_button("タスク")
        tasks_button.clicked.connect(self.open_tasks_requested)
        main_button = self.make_nav_button("全表示")
        main_button.clicked.connect(self.open_main_requested)
        navigation = QHBoxLayout()
        navigation.setSpacing(5)
        navigation.addWidget(tasks_button)
        navigation.addWidget(main_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 10, 9, 10)
        layout.setSpacing(8)
        layout.addLayout(self.make_header("タスク追加"))
        layout.addWidget(scroll, 1)
        layout.addWidget(details_button)
        layout.addWidget(add_button)
        layout.addLayout(navigation)
        self.due_enabled.toggled.connect(self._sync_due)
        self._sync_due()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _load_categories(self, preferred_id: str | None = None) -> None:
        preferred_id = preferred_id or self.category.currentData()
        self.category.clear()
        for category in self.task_service.list_categories():
            self.category.addItem(category.name, category.id)
        index = self.category.findData(preferred_id)
        if index >= 0:
            self.category.setCurrentIndex(index)

    def _manage_categories(self) -> None:
        preferred_id = self.category.currentData()
        dialog = CategoryManagerDialog(self.task_service, self)
        dialog.categories_changed.connect(lambda: self._load_categories(preferred_id))
        dialog.exec()
        self._load_categories(preferred_id)

    def _sync_due(self) -> None:
        enabled = self.due_enabled.isChecked()
        self.due_date.setEnabled(enabled)
        self.due_time.setEnabled(enabled)

    def _create(self) -> None:
        selected_date = self.due_date.date()
        due_date_value = None
        due_time_value = None
        if self.due_enabled.isChecked():
            due_date_value = date(selected_date.year(), selected_date.month(), selected_date.day())
            due_time_value = self.due_time.time_value()
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
        self.hide()

    def _open_full_dialog(self) -> None:
        dialog = TaskDialog(self.task_service, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.task_created.emit(dialog.saved_task.id)
            self.hide()

    def show_at_screen_edge(self) -> None:
        self._load_categories()
        self.title_edit.clear()
        super().show_at_screen_edge()
        self.title_edit.setFocus()
