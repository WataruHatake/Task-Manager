from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
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
from dandori.ui.undo_bar import UndoBar


class MainWindow(QMainWindow):
    edge_tasks_requested = Signal()
    edge_add_requested = Signal()
    theme_requested = Signal()
    hidden_to_tray = Signal()

    VIEW_TITLES = {
        "today": "今日やる",
        "all": "すべてのタスク",
        "overdue": "期限切れ",
        "completed": "完了済み・取り消し",
        "trash": "ゴミ箱",
    }

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.current_task_view = "today"
        self._undo_kind = "complete"
        self.hide_to_tray = False
        self.setWindowTitle("タスク管理")
        self.resize(1080, 720)
        self.setMinimumSize(720, 480)

        self.sidebar = self._build_sidebar()
        self.table_page = TaskTablePage()
        self.calendar_page = CalendarPage(task_service)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.table_page)
        self.pages.addWidget(self.calendar_page)

        self.page_title = QLabel(self.VIEW_TITLES[self.current_task_view])
        self.page_title.setObjectName("pageTitle")
        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(1)
        heading_layout.addWidget(self.page_title)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("タスク名・メモを検索")
        self.search_edit.setClearButtonEnabled(True)
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
        self.undo_bar = UndoBar()
        self.undo_bar.undo_requested.connect(self._undo_last_action)
        content_layout.addWidget(self.undo_bar)
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
        self.table_page.restore_requested.connect(self._restore_task)
        self.table_page.trash_requested.connect(self._trash_task)
        self.table_page.restore_trash_requested.connect(self._restore_trashed_task)
        self.table_page.permanent_delete_requested.connect(
            self._permanently_delete_task
        )
        self.table_page.planned_today_requested.connect(self._set_planned_today)
        self.table_page.add_requested.connect(self._create_task)
        self.calendar_page.edit_requested.connect(self._edit_task)
        self.calendar_page.complete_requested.connect(self._complete_task)
        self.calendar_page.add_requested.connect(self._create_task_for_date)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._create_task)
        self.table_page.set_compact(self.width() < 900)
        self.refresh()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        navigation = (
            ("today", "▣  今日やる"),
            ("all", "□  すべて"),
            ("overdue", "！  期限切れ"),
            ("completed", "✓  完了済み"),
            ("trash", "♲  ゴミ箱"),
        )
        self.nav_buttons: dict[str, QPushButton] = {}
        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        for view, text in navigation:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setChecked(view == self.current_task_view)
            button.clicked.connect(
                lambda _checked=False, selected_view=view: self._set_task_view(
                    selected_view
                )
            )
            nav_group.addButton(button)
            self.nav_buttons[view] = button

        theme_button = QPushButton("カラーテーマ")
        theme_button.clicked.connect(lambda: self.theme_requested.emit())
        category_button = QPushButton("カテゴリ管理")
        category_button.clicked.connect(self._manage_categories)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(13, 22, 13, 16)
        layout.setSpacing(4)
        layout.addSpacing(8)
        for button in self.nav_buttons.values():
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
        self.table_page.set_empty_context(self.current_task_view)
        tasks = self.task_service.list_tasks_for_view(
            self.current_task_view, self.search_edit.text()
        )
        self.table_page.set_tasks(tasks, preferred_task_id)
        self.calendar_page.refresh()

    def _set_task_view(self, view: str) -> None:
        if self.pages.currentWidget() is self.calendar_page:
            self.list_button.click()
        self.current_task_view = view
        self.page_title.setText(self.VIEW_TITLES[view])
        self.calendar_button.setEnabled(view not in ("completed", "trash"))
        if view in ("completed", "trash") and self.pages.currentWidget() is self.calendar_page:
            self.list_button.click()
        self.refresh()

    def show_task(self, task_id: str) -> None:
        self.current_task_view = "all"
        self.nav_buttons["all"].setChecked(True)
        self.list_button.setChecked(True)
        self.pages.setCurrentWidget(self.table_page)
        self.page_title.setText(self.VIEW_TITLES["all"])
        self.search_edit.clear()
        self.search_edit.setVisible(True)
        self.refresh(task_id)

    def _change_view(self, view_id: int) -> None:
        if view_id == 1 and self.current_task_view != "all":
            self.current_task_view = "all"
            self.nav_buttons["all"].setChecked(True)
            self.refresh()
        self.pages.setCurrentIndex(view_id)
        self.page_title.setText(
            self.VIEW_TITLES[self.current_task_view] if view_id == 0 else "カレンダー"
        )
        self.search_edit.setVisible(view_id == 0)

    def _create_task(self) -> None:
        initial_date = (
            self.calendar_page.selected_date
            if self.pages.currentWidget() is self.calendar_page
            else None
        )
        dialog = TaskDialog(self.task_service, initial_date=initial_date, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.refresh(dialog.saved_task.id)

    def _create_task_for_date(self, selected_date: date) -> None:
        dialog = TaskDialog(self.task_service, initial_date=selected_date, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.refresh(dialog.saved_task.id)

    def _edit_task(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            QMessageBox.warning(self, "タスクなし", "タスクが見つかりません。")
            return
        dialog = TaskDialog(self.task_service, task=task, parent=self)
        if dialog.exec() and dialog.saved_task:
            self.refresh(task_id)

    def _complete_task(self, task_id: str) -> None:
        self.task_service.complete_task(task_id)
        self.refresh()
        self._undo_kind = "complete"
        self.undo_bar.show_for_task(task_id)

    def _restore_task(self, task_id: str) -> None:
        self.task_service.restore_task(task_id)
        self.refresh(task_id)

    def _set_planned_today(self, task_id: str, enabled: bool) -> None:
        self.task_service.set_planned_for_today(task_id, enabled)
        self.refresh(task_id if enabled else None)

    def _trash_task(self, task_id: str) -> None:
        self.task_service.trash_task(task_id)
        self.refresh()
        self._undo_kind = "trash"
        self.undo_bar.show_for_task(task_id, "タスクをゴミ箱へ移動しました")

    def _restore_trashed_task(self, task_id: str) -> None:
        self.task_service.restore_trashed_task(task_id)
        self.refresh(task_id)

    def _permanently_delete_task(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            self.refresh()
            return
        answer = QMessageBox.question(
            self,
            "完全に削除",
            f"「{task.title}」を完全に削除しますか？\nこの操作は元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.task_service.permanently_delete_task(task_id)
        self.refresh()

    def _undo_last_action(self, task_id: str) -> None:
        if self._undo_kind == "trash":
            self._restore_trashed_task(task_id)
        else:
            self._restore_task(task_id)

    def _focus_search(self) -> None:
        if self.pages.currentWidget() is not self.table_page:
            self.list_button.click()
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.sidebar.setFixedWidth(140 if event.size().width() < 900 else 176)
        if hasattr(self, "table_page"):
            self.table_page.set_compact(event.size().width() < 900)
        super().resizeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_to_tray:
            event.ignore()
            self.hide()
            self.hidden_to_tray.emit()
            return
        event.accept()
