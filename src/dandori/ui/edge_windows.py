from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QCloseEvent, QCursor, QKeySequence, QMouseEvent, QShortcut
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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import Priority, TaskStatus
from dandori.infrastructure.models import Task, local_now
from dandori.services.task_service import TaskInput, TaskService
from dandori.ui.category_dialog import CategoryManagerDialog
from dandori.ui.task_dialog import TaskDialog
from dandori.ui.task_extras import (
    AttachmentEditor,
    ReminderControls,
    RetentionControls,
    SubtaskEditor,
)
from dandori.ui.task_views import format_due
from dandori.ui.time_combo import TimeComboBox
from dandori.ui.undo_bar import UndoBar


class EdgeTaskCard(QFrame):
    clicked = Signal(str)

    def __init__(self, task_id: str, parent=None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.task_id)
        super().mouseReleaseEvent(event)


class EdgeTaskDetail(QWidget):
    back_requested = Signal()
    edit_requested = Signal(str)
    complete_requested = Signal(str)
    restore_requested = Signal(str)
    planned_today_requested = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.task: Task | None = None
        back_button = QPushButton("← 一覧へ")
        back_button.setObjectName("edgeNav")
        back_button.clicked.connect(self.back_requested)

        self.title = QLabel()
        self.title.setObjectName("edgeTitle")
        self.title.setWordWrap(True)
        self.status = QLabel()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p%")
        self.progress.setObjectName("taskProgress")
        self.progress_note = QLabel()
        self.progress_note.setWordWrap(True)
        self.due = QLabel()
        self.priority = QLabel()
        self.category = QLabel()
        self.memo = QLabel()
        self.memo.setWordWrap(True)
        self.subtasks = QLabel()
        self.subtasks.setWordWrap(True)
        self.attachments = QLabel()
        self.attachments.setWordWrap(True)
        self.reminder = QLabel()
        self.reminder.setWordWrap(True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(5)
        content_layout.addWidget(self.title)
        for label, value in (
            ("状態", self.status),
            ("進捗率", self.progress),
            ("現在の進捗", self.progress_note),
            ("期限", self.due),
            ("重要度", self.priority),
            ("カテゴリ", self.category),
            ("メモ", self.memo),
            ("サブタスク", self.subtasks),
            ("添付ファイル", self.attachments),
            ("リマインド", self.reminder),
        ):
            field = QLabel(label)
            field.setObjectName("fieldLabel")
            content_layout.addSpacing(5)
            content_layout.addWidget(field)
            content_layout.addWidget(value)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        self.edit_button = QPushButton("編集")
        self.today_button = QPushButton("今日やる")
        self.primary_button = QPushButton("完了")
        self.primary_button.setObjectName("primaryButton")
        self.edit_button.clicked.connect(self._edit)
        self.today_button.clicked.connect(self._planned_today)
        self.primary_button.clicked.connect(self._primary_action)
        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.primary_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(back_button)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.today_button)
        layout.addLayout(actions)

    def set_task(self, task: Task) -> None:
        self.task = task
        self.title.setText(task.title)
        self.status.setText(task.status_enum.label)
        self.progress.setValue(task.progress_percent)
        self.progress_note.setText(task.progress_note or "未入力")
        self.due.setText(format_due(task))
        self.priority.setText(task.priority_enum.label)
        self.category.setText(task.category.name)
        self.memo.setText(task.memo or "メモなし")
        completed = sum(1 for item in task.subtasks if item.completed)
        subtask_lines = [f"{completed}/{len(task.subtasks)} 完了"] if task.subtasks else []
        subtask_lines.extend(
            f"{'✓' if item.completed else '○'} {item.title}"
            for item in sorted(task.subtasks, key=lambda value: value.position)
        )
        self.subtasks.setText("\n".join(subtask_lines) or "なし")
        self.attachments.setText(
            "\n".join(item.original_name for item in task.attachments) or "なし"
        )
        self.reminder.setText(
            {
                "priority": "重要度の標準設定",
                "custom": "個別設定",
                "off": "通知しない",
            }.get(task.reminder_mode, "重要度の標準設定")
        )
        terminal = task.status_enum in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        self.primary_button.setText("元に戻す" if terminal else "完了")
        self.today_button.setVisible(not terminal)
        due_today = bool(task.due_at and task.due_at.date() == date.today())
        planned_today = task.planned_for_date == date.today()
        if due_today:
            self.today_button.setText("本日期限（今日に表示）")
            self.today_button.setEnabled(False)
        else:
            self.today_button.setText("今日から外す" if planned_today else "今日やる")
            self.today_button.setEnabled(True)

    def _edit(self) -> None:
        if self.task:
            self.edit_requested.emit(self.task.id)

    def _primary_action(self) -> None:
        if self.task is None:
            return
        if self.task.status_enum in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            self.restore_requested.emit(self.task.id)
        else:
            self.complete_requested.emit(self.task.id)

    def _planned_today(self) -> None:
        if self.task is None:
            return
        due_today = bool(self.task.due_at and self.task.due_at.date() == date.today())
        if not due_today:
            self.planned_today_requested.emit(
                self.task.id,
                self.task.planned_for_date != date.today(),
            )


class EdgeTaskEditor(QWidget):
    saved = Signal(str)
    cancel_requested = Signal(str)

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.task: Task | None = None
        self._initial_state: tuple[object, ...] = ()

        back_button = QPushButton("← 詳細へ")
        back_button.setObjectName("edgeNav")
        back_button.clicked.connect(self.request_cancel)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("補足、完了条件、確認事項など")
        self.memo_edit.setMinimumHeight(76)
        self.progress_note_edit = QTextEdit()
        self.progress_note_edit.setPlaceholderText("現在どこまで進んでいるか")
        self.progress_note_edit.setMinimumHeight(68)
        self.progress_percent_spin = QSpinBox()
        self.progress_percent_spin.setRange(0, 100)
        self.progress_percent_spin.setSingleStep(5)
        self.progress_percent_spin.setSuffix(" %")

        self.status_combo = QComboBox()
        for status in TaskStatus:
            self.status_combo.addItem(status.label, status)
        self.priority_combo = QComboBox()
        for priority in Priority:
            self.priority_combo.addItem(priority.label, priority)

        self.category_combo = QComboBox()
        self._reload_categories()
        category_manage = QPushButton("…")
        category_manage.setObjectName("compactButton")
        category_manage.setToolTip("カテゴリ管理")
        category_manage.clicked.connect(self._manage_categories)
        category_row = QHBoxLayout()
        category_row.setSpacing(4)
        category_row.addWidget(self.category_combo, 1)
        category_row.addWidget(category_manage)

        self.due_mode = QComboBox()
        self.due_mode.addItem("期限なし", "none")
        self.due_mode.addItem("日付のみ", "date")
        self.due_mode.addItem("日時を指定", "datetime")
        self.due_date_edit = QDateEdit(QDate.currentDate())
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat("yyyy/MM/dd")
        self.due_time_edit = TimeComboBox()
        self.due_time_edit.set_time(time(17, 0))
        self.planned_today = QCheckBox("今日やる")
        self.planned_today.setToolTip(
            "期限とは別に今日の作業対象へ追加します。本日期限は自動的に表示されます。"
        )
        self.reminder_controls = ReminderControls()
        self.retention_controls = RetentionControls()
        self.subtask_editor = SubtaskEditor()
        self.attachment_editor = AttachmentEditor(task_service)

        form_widget = QWidget()
        form = QVBoxLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.addWidget(self._field_label("タスク名 *"))
        form.addWidget(self.title_edit)
        form.addWidget(self._field_label("メモ"))
        form.addWidget(self.memo_edit)
        form.addWidget(self._field_label("現在の進捗"))
        form.addWidget(self.progress_note_edit)
        form.addWidget(self._field_label("進捗率"))
        form.addWidget(self.progress_percent_spin)
        form.addWidget(self._field_label("状態"))
        form.addWidget(self.status_combo)
        form.addWidget(self._field_label("重要度"))
        form.addWidget(self.priority_combo)
        form.addWidget(self._field_label("カテゴリ"))
        form.addLayout(category_row)
        form.addWidget(self.planned_today)
        form.addWidget(self._field_label("期限"))
        form.addWidget(self.due_mode)
        self.due_date_label = self._field_label("期限日")
        form.addWidget(self.due_date_label)
        form.addWidget(self.due_date_edit)
        self.due_time_label = self._field_label("期限時刻")
        form.addWidget(self.due_time_label)
        form.addWidget(self.due_time_edit)
        form.addWidget(self._field_label("リマインド"))
        form.addWidget(self.reminder_controls)
        form.addWidget(self._field_label("完了後の保存"))
        form.addWidget(self.retention_controls)
        form.addWidget(self._field_label("サブタスク"))
        form.addWidget(self.subtask_editor)
        form.addWidget(self._field_label("添付ファイル"))
        form.addWidget(self.attachment_editor)
        form.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_widget)

        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.request_cancel)
        save_button = QPushButton("保存")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save)
        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(back_button)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)

        self.due_mode.currentIndexChanged.connect(self._sync_due_controls)
        for key in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._save)
        cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        cancel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        cancel_shortcut.activated.connect(self.request_cancel)
        self._sync_due_controls()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def set_task(self, task: Task) -> None:
        self.task = task
        self.attachment_editor.set_task(task)
        self.title_edit.setText(task.title)
        self.memo_edit.setPlainText(task.memo)
        self.progress_note_edit.setPlainText(task.progress_note)
        self.progress_percent_spin.setValue(task.progress_percent)
        self.status_combo.setCurrentIndex(
            self.status_combo.findData(task.status_enum)
        )
        self.priority_combo.setCurrentIndex(
            self.priority_combo.findData(task.priority_enum)
        )
        self._reload_categories(task.category_id)
        self.planned_today.setChecked(task.planned_for_date == date.today())
        self.retention_controls.set_value(task.retention_days)
        self.reminder_controls.set_values(
            task.reminder_mode,
            self.task_service._reminder_json(task),
            task.priority_enum,
        )
        self.subtask_editor.set_subtasks(task.subtasks)
        if task.due_at:
            self.due_date_edit.setDate(
                QDate(task.due_at.year, task.due_at.month, task.due_at.day)
            )
            self.due_mode.setCurrentIndex(2 if task.due_has_time else 1)
            self.due_time_edit.set_time(time(task.due_at.hour, task.due_at.minute))
        else:
            self.due_mode.setCurrentIndex(0)
            self.due_date_edit.setDate(QDate.currentDate())
            self.due_time_edit.set_time(time(17, 0))
        self._sync_due_controls()
        self._initial_state = self._draft_state()
        self.title_edit.setFocus()

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
        if index < 0:
            index = self.category_combo.findData(
                self.task_service.default_category().id
            )
        self.category_combo.setCurrentIndex(max(0, index))

    def _manage_categories(self) -> None:
        preferred_id = self.category_combo.currentData()
        dialog = CategoryManagerDialog(self.task_service, self)
        dialog.categories_changed.connect(
            lambda: self._reload_categories(preferred_id)
        )
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
            due_date_value = date(
                selected_date.year(), selected_date.month(), selected_date.day()
            )
            if self.due_mode.currentData() == "datetime":
                due_time_value = self.due_time_edit.time_value()
        return TaskInput(
            title=self.title_edit.text(),
            memo=self.memo_edit.toPlainText(),
            progress_note=self.progress_note_edit.toPlainText(),
            progress_percent=self.progress_percent_spin.value(),
            status=TaskStatus(self.status_combo.currentData()),
            priority=Priority(int(self.priority_combo.currentData())),
            due_date=due_date_value,
            due_time=due_time_value,
            planned_for_date=date.today() if self.planned_today.isChecked() else None,
            category_id=self.category_combo.currentData(),
            retention_days=self.retention_controls.value(),
            reminder_mode=self.reminder_controls.mode(),
            reminder_config=self.reminder_controls.config(),
        )

    def _save(self) -> None:
        if self.task is None:
            return
        try:
            self.task = self.task_service.update_task(
                self.task.id, self._task_input()
            )
            self.task_service.replace_subtasks(
                self.task.id, self.subtask_editor.inputs()
            )
            self.attachment_editor.apply([self.task.id])
            self.task = self.task_service.get_task(self.task.id)
        except (ValueError, LookupError) as error:
            QMessageBox.warning(self, "保存できません", str(error))
            return
        self._initial_state = self._draft_state()
        self.saved.emit(self.task.id)

    def _draft_state(self) -> tuple[object, ...]:
        return (
            self.title_edit.text(),
            self.memo_edit.toPlainText(),
            self.progress_note_edit.toPlainText(),
            self.progress_percent_spin.value(),
            self.status_combo.currentData(),
            self.priority_combo.currentData(),
            self.category_combo.currentData(),
            self.planned_today.isChecked(),
            self.due_mode.currentData(),
            self.due_date_edit.date().toString("yyyy-MM-dd"),
            self.due_time_edit.currentText(),
            self.retention_controls.state(),
            self.reminder_controls.state(),
            self.subtask_editor.state(),
            self.attachment_editor.state(),
        )

    def has_unsaved_changes(self) -> bool:
        return bool(self.task) and self._draft_state() != self._initial_state

    def request_cancel(self) -> None:
        if self.task is None:
            return
        if self.has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "変更を破棄",
                "入力中の変更を破棄して詳細へ戻りますか？",
                QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                return
        self.cancel_requested.emit(self.task.id)


class EdgeWindowBase(QDialog):
    BASE_WIDTH = 180
    WIDTH_OPTIONS = (180, 240, 320)

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.setObjectName("edgeWindow")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._apply_saved_width()
        self.resize(self.width(), 600)

    def _saved_width(self) -> int:
        value = self.task_service.get_setting("edge_panel_width", self.BASE_WIDTH)
        try:
            width = int(value)
        except (TypeError, ValueError):
            return self.BASE_WIDTH
        return width if width in self.WIDTH_OPTIONS else self.BASE_WIDTH

    def _apply_saved_width(self) -> None:
        self.setFixedWidth(self._saved_width())

    def _cycle_width(self) -> None:
        current = self.width()
        try:
            index = self.WIDTH_OPTIONS.index(current)
        except ValueError:
            index = 0
        width = self.WIDTH_OPTIONS[(index + 1) % len(self.WIDTH_OPTIONS)]
        self.task_service.set_setting("edge_panel_width", width)
        self.setFixedWidth(width)
        if self.isVisible():
            self.show_at_screen_edge()

    def show_at_screen_edge(self) -> None:
        self._apply_saved_width()
        screen = self._screen_at_cursor()
        geometry = screen.availableGeometry()
        self.setGeometry(
            geometry.right() - self.width() + 1,
            geometry.top(),
            self.width(),
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
        width_button = QPushButton("↔")
        width_button.setObjectName("compactButton")
        width_button.setToolTip("パネル幅を変更（180 / 240 / 320px）")
        width_button.clicked.connect(self._cycle_width)
        header = QHBoxLayout()
        header.setSpacing(5)
        header.addWidget(title, 1)
        header.addWidget(width_button)
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
        super().__init__(task_service, parent)
        self.setWindowTitle("タスク")

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

        self.detail = EdgeTaskDetail()
        self.detail.back_requested.connect(self._show_list)
        self.detail.edit_requested.connect(self._edit)
        self.detail.complete_requested.connect(self._complete)
        self.detail.restore_requested.connect(self._restore)
        self.detail.planned_today_requested.connect(self._set_planned_today)
        self.editor = EdgeTaskEditor(self.task_service)
        self.editor.saved.connect(self._editor_saved)
        self.editor.cancel_requested.connect(self._editor_cancelled)
        self.stack = QStackedWidget()
        self.stack.addWidget(scroll)
        self.stack.addWidget(self.detail)
        self.stack.addWidget(self.editor)

        self.undo_bar = UndoBar()
        self.undo_bar.undo_requested.connect(self._restore)

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
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.undo_bar)
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

        now = local_now()
        today_tasks = [
            task
            for task in tasks
            if task.planned_for_date == now.date()
            or (task.due_at is not None and task.due_at.date() == now.date())
        ]
        today_ids = {task.id for task in today_tasks}
        groups: tuple[tuple[str, list[Task]], ...] = (
            (
                "期限切れ",
                [
                    task
                    for task in tasks
                    if task.id not in today_ids and task.due_at and task.due_at < now
                ],
            ),
            ("今日やる", today_tasks),
            (
                "今後",
                [
                    task
                    for task in tasks
                    if task.id not in today_ids
                    and task.due_at
                    and task.due_at.date() > now.date()
                ],
            ),
            (
                "期限なし",
                [task for task in tasks if task.id not in today_ids and task.due_at is None],
            ),
        )
        for heading, grouped_tasks in groups:
            if not grouped_tasks:
                continue
            section = QLabel(f"{heading}  {len(grouped_tasks)}")
            section.setObjectName("sectionLabel")
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, section)
            for task in grouped_tasks:
                self.cards_layout.insertWidget(
                    self.cards_layout.count() - 1, self._task_card(task)
                )

    def _task_card(self, task: Task) -> QFrame:
        card = EdgeTaskCard(task.id)
        card.setObjectName("edgeCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.clicked.connect(self._show_task)

        title = QLabel(task.title)
        title.setObjectName("edgeTaskTitle")
        title.setWordWrap(True)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        meta = QLabel(
            f"{format_due(task)}\n"
            f"進捗 {task.progress_percent}%\n"
            f"{task.priority_enum.label} ・ {task.status_enum.label}"
        )
        meta.setObjectName("muted")
        meta.setWordWrap(True)
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        complete = QPushButton("完了")
        complete.setObjectName("edgeAction")
        edit = QPushButton("詳細")
        edit.setObjectName("edgeAction")
        complete.clicked.connect(lambda _checked=False, task_id=task.id: self._complete(task_id))
        edit.clicked.connect(
            lambda _checked=False, task_id=task.id: self._show_task(task_id)
        )
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
        self._show_list()
        self.refresh()
        self.tasks_changed.emit()
        self.undo_bar.show_for_task(task_id)

    def _restore(self, task_id: str) -> None:
        self.task_service.restore_task(task_id)
        self.refresh()
        self.tasks_changed.emit()

    def _set_planned_today(self, task_id: str, enabled: bool) -> None:
        self.task_service.set_planned_for_today(task_id, enabled)
        self.refresh()
        self.tasks_changed.emit()
        self._show_task(task_id)

    def _show_list(self) -> None:
        self.stack.setCurrentIndex(0)

    def _show_task(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        self.detail.set_task(task)
        self.stack.setCurrentWidget(self.detail)

    def _edit(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        self.editor.set_task(task)
        self.stack.setCurrentWidget(self.editor)

    def _editor_saved(self, task_id: str) -> None:
        self.refresh()
        self.tasks_changed.emit()
        updated = self.task_service.get_task(task_id)
        if updated is None:
            self._show_list()
            return
        self.detail.set_task(updated)
        self.stack.setCurrentWidget(self.detail)

    def _editor_cancelled(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            self._show_list()
            return
        self.detail.set_task(task)
        self.stack.setCurrentWidget(self.detail)

    def show_at_screen_edge(self) -> None:
        keep_draft = (
            self.stack.currentWidget() is self.editor
            and self.editor.has_unsaved_changes()
        )
        self.refresh()
        if not keep_draft:
            self._show_list()
        super().show_at_screen_edge()


class EdgeAddWindow(EdgeWindowBase):
    task_created = Signal(str)
    open_main_requested = Signal()
    open_tasks_requested = Signal()

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(task_service, parent)
        self.setWindowTitle("タスク追加")

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("タスク名")
        self.title_edit.returnPressed.connect(self._create)
        self.planned_today = QCheckBox("今日やる")
        self.planned_today.setToolTip(
            "期限とは別に今日の作業対象へ追加します。本日期限は自動的に表示されます。"
        )
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
        form.addWidget(self.planned_today)
        form.addWidget(self.due_enabled)
        self.due_date_label = self._field_label("期限日")
        form.addWidget(self.due_date_label)
        form.addWidget(self.due_date)
        self.due_time_label = self._field_label("期限時刻")
        form.addWidget(self.due_time_label)
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
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._create)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self._create)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.hide)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _load_categories(self, preferred_id: str | None = None) -> None:
        preferred_id = (
            preferred_id
            or self.category.currentData()
            or self.task_service.default_category().id
        )
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
        self.due_date_label.setVisible(enabled)
        self.due_date.setVisible(enabled)
        self.due_time_label.setVisible(enabled)
        self.due_time.setVisible(enabled)

    def _current_task_input(self) -> TaskInput:
        selected_date = self.due_date.date()
        due_date_value = None
        due_time_value = None
        if self.due_enabled.isChecked():
            due_date_value = date(
                selected_date.year(), selected_date.month(), selected_date.day()
            )
            due_time_value = self.due_time.time_value()
        return TaskInput(
            title=self.title_edit.text(),
            priority=Priority(int(self.priority.currentData())),
            due_date=due_date_value,
            due_time=due_time_value,
            planned_for_date=date.today() if self.planned_today.isChecked() else None,
            category_id=self.category.currentData(),
        )

    def _create(self) -> None:
        try:
            task = self.task_service.create_task(self._current_task_input())
        except ValueError as error:
            QMessageBox.warning(self, "追加できません", str(error))
            return
        self._reset_form()
        self.task_created.emit(task.id)
        self.hide()

    def _open_full_dialog(self) -> None:
        dialog = TaskDialog(
            self.task_service,
            initial_input=self._current_task_input(),
            parent=self,
        )
        if dialog.exec() and dialog.saved_task:
            self._reset_form()
            self.task_created.emit(dialog.saved_task.id)
            self.hide()

    def _reset_form(self) -> None:
        self.title_edit.clear()
        self.planned_today.setChecked(False)
        self.due_enabled.setChecked(False)
        self.due_date.setDate(QDate.currentDate())
        self.due_time.set_time(time(17, 0))
        self.priority.setCurrentIndex(int(Priority.NORMAL) - 1)
        self._load_categories(self.task_service.default_category().id)

    def show_at_screen_edge(self) -> None:
        self._load_categories()
        if not self.title_edit.text().strip() and not self.due_enabled.isChecked():
            self.due_date.setDate(QDate.currentDate())
        super().show_at_screen_edge()
        self.title_edit.setFocus()
