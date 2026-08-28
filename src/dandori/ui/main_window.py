from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dandori.services.task_service import TaskService
from dandori.ui.calendar_page import CalendarPage
from dandori.ui.category_dialog import CategoryManagerDialog
from dandori.ui.task_dialog import TaskDialog
from dandori.ui.task_views import TaskTablePage


class MainWindow(QMainWindow):
    edge_tasks_requested = Signal()
    edge_add_requested = Signal()
    theme_requested = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.hide_to_tray = False
        self.setWindowTitle("タスク管理")
        self.resize(1160, 760)
        self.setMinimumSize(860, 600)

        self.sidebar = self._build_sidebar()
        self.table_page = TaskTablePage()
        self.calendar_page = CalendarPage(task_service)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.table_page)
        self.pages.addWidget(self.calendar_page)

        self.page_title = QLabel("タスク一覧")
        self.page_title.setObjectName("pageTitle")
        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(1)
        heading_layout.addWidget(self.page_title)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("タスク名・メモを検索")
        self.search_edit.textChanged.connect(self.refresh)

        self.list_button = QPushButton("一覧")
        self.calendar_button = QPushButton("カレンダー")
        for button in (self.list_button, self.calendar_button):
            button.setObjectName("viewButton")
            button.setCheckable(True)
        self.list_button.setChecked(True)
        view_group = QButtonGroup(self)
        view_group.setExclusive(True)
        view_group.addButton(self.list_button, 0)
        view_group.addButton(self.calendar_button, 1)
        view_group.idClicked.connect(self._change_view)

        add_button = QPushButton("＋ タスク追加")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._create_task)
        actions = QHBoxLayout()
        actions.setSpacing(7)
        actions.addWidget(self.list_button)
        actions.addWidget(self.calendar_button)
        actions.addWidget(add_button)

        header = QHBoxLayout()
        header.addLayout(heading_layout)
        header.addStretch()
        header.addLayout(actions)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 20)
        content_layout.setSpacing(12)
        content_layout.addLayout(header)
        content_layout.addWidget(self.search_edit)
        content_layout.addWidget(self.pages, 1)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.table_page.edit_requested.connect(self._edit_task)
        self.table_page.complete_requested.connect(self._complete_task)
        self.calendar_page.edit_requested.connect(self._edit_task)
        self.calendar_page.complete_requested.connect(self._complete_task)
        self.refresh()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        today = QPushButton("▣  今日")
        today.setObjectName("navButton")
        today.setCheckable(True)
        today.setChecked(True)
        all_tasks = QPushButton("□  すべて")
        all_tasks.setObjectName("navButton")
        overdue = QPushButton("！  期限切れ")
        overdue.setObjectName("navButton")
        completed = QPushButton("✓  完了済み")
        completed.setObjectName("navButton")
        trash = QPushButton("○  ゴミ箱")
        trash.setObjectName("navButton")
        for button in (all_tasks, overdue, completed, trash):
            button.setEnabled(False)
            button.setToolTip("第二段階で実装予定")

        theme_button = QPushButton("カラーテーマ")
        theme_button.clicked.connect(lambda: self.theme_requested.emit())
        category_button = QPushButton("カテゴリ管理")
        category_button.clicked.connect(self._manage_categories)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(13, 22, 13, 16)
        layout.setSpacing(4)
        layout.addSpacing(8)
        for button in (today, all_tasks, overdue, completed, trash):
            layout.addWidget(button)
        layout.addStretch()
        layout.addWidget(category_button)
        layout.addWidget(theme_button)
        return sidebar

    def _manage_categories(self) -> None:
        dialog = CategoryManagerDialog(self.task_service, self)
        dialog.categories_changed.connect(self.refresh)
        dialog.exec()
        self.refresh()

    def refresh(self, preferred_task_id: str | None = None) -> None:
        tasks = self.task_service.list_active_tasks(self.search_edit.text())
        self.table_page.set_tasks(tasks, preferred_task_id)
        self.calendar_page.refresh()

    def _change_view(self, view_id: int) -> None:
        self.pages.setCurrentIndex(view_id)
        self.page_title.setText("タスク一覧" if view_id == 0 else "カレンダー")
        self.search_edit.setVisible(view_id == 0)

    def _create_task(self) -> None:
        dialog = TaskDialog(self.task_service, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.refresh(dialog.saved_task.id)

    def _edit_task(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            QMessageBox.warning(self, "タスクなし", "タスクが見つかりません。")
            return
        dialog = TaskDialog(self.task_service, task=task, parent=self)
        if dialog.exec():
            self.refresh(task_id)

    def _complete_task(self, task_id: str) -> None:
        self.task_service.complete_task(task_id)
        self.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_to_tray:
            event.ignore()
            self.hide()
            return
        event.accept()
