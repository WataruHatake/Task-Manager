from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dandori.infrastructure.models import Task
from dandori.services.task_service import TaskService
from dandori.ui.task_views import TaskDetailWidget, format_due

WEEKDAY_NAMES = ("日", "月", "火", "水", "木", "金", "土")


class CalendarCell(QFrame):
    date_selected = Signal(QDate)
    task_selected = Signal(str)

    def __init__(self, cell_date: date, shown_month: int, parent=None) -> None:
        super().__init__(parent)
        self.cell_date = cell_date
        self.setObjectName("calendarCell")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.day_button = QPushButton(str(cell_date.day))
        self.day_button.setObjectName(
            "calendarDayToday" if cell_date == date.today() else "calendarDay"
        )
        self.day_button.clicked.connect(
            lambda: self.date_selected.emit(
                QDate(self.cell_date.year, self.cell_date.month, self.cell_date.day)
            )
        )
        if cell_date.month != shown_month:
            self.setProperty("outsideMonth", True)
            self.day_button.setProperty("outsideMonth", True)

        self.task_layout = QVBoxLayout()
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(1)
        day_row = QHBoxLayout()
        day_row.addStretch()
        day_row.addWidget(self.day_button)
        layout.addLayout(day_row)
        layout.addLayout(self.task_layout)
        layout.addStretch()

    def set_selected(self, selected: bool) -> None:
        self.setObjectName("calendarCellSelected" if selected else "calendarCell")
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.date_selected.emit(
                QDate(self.cell_date.year, self.cell_date.month, self.cell_date.day)
            )
        super().mouseReleaseEvent(event)

    def set_tasks(self, tasks: list[Task]) -> None:
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        for task in tasks[:2]:
            button = QPushButton(task.title[:4])
            button.setObjectName("calendarTask")
            button.setToolTip(task.title)
            button.clicked.connect(
                lambda _checked=False, task_id=task.id: self.task_selected.emit(task_id)
            )
            self.task_layout.addWidget(button)
        if len(tasks) > 2:
            more = QPushButton(f"他{len(tasks) - 2}件")
            more.setObjectName("calendarMore")
            more.clicked.connect(
                lambda: self.date_selected.emit(
                    QDate(self.cell_date.year, self.cell_date.month, self.cell_date.day)
                )
            )
            self.task_layout.addWidget(more)


class DayTaskList(QFrame):
    task_selected = Signal(str)
    add_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("detailSurface")
        self.heading = QLabel()
        self.heading.setObjectName("detailTitle")
        self.count_label = QLabel()
        self.count_label.setObjectName("muted")
        add_button = QPushButton("＋ この日に追加")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(lambda: self.add_requested.emit())

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(5)
        layout.addWidget(self.heading)
        layout.addWidget(self.count_label)
        layout.addWidget(add_button)
        layout.addSpacing(6)
        layout.addWidget(scroll)

    def set_date_and_tasks(self, target_date: date, tasks: list[Task]) -> None:
        weekdays = ("月", "火", "水", "木", "金", "土", "日")
        self.heading.setText(
            f"{target_date.month}月{target_date.day}日（{weekdays[target_date.weekday()]}）"
        )
        self.count_label.setText(f"{len(tasks)}件のタスク")
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        if not tasks:
            empty = QLabel("この日のタスクはありません")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            self.content_layout.insertWidget(0, empty)
            return
        for task in tasks:
            button = QPushButton(
                f"{task.title}\n"
                f"{format_due(task)} ・ {task.priority_enum.label} ・ {task.progress_percent}%"
            )
            button.setMinimumHeight(60)
            button.setStyleSheet("text-align: left; padding: 8px 4px; border-width: 0 0 1px 0;")
            button.clicked.connect(
                lambda _checked=False, task_id=task.id: self.task_selected.emit(task_id)
            )
            self.content_layout.insertWidget(self.content_layout.count() - 1, button)


class CalendarPage(QWidget):
    edit_requested = Signal(str)
    complete_requested = Signal(str)
    add_requested = Signal(object)

    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        today = date.today()
        self.shown_year = today.year
        self.shown_month = today.month
        self.selected_date = today
        self.cells: list[CalendarCell] = []

        self.previous_button = QPushButton("‹")
        self.next_button = QPushButton("›")
        self.today_button = QPushButton("今日")
        self.month_label = QLabel()
        self.month_label.setObjectName("detailTitle")
        self.previous_button.clicked.connect(lambda: self._change_month(-1))
        self.next_button.clicked.connect(lambda: self._change_month(1))
        self.today_button.clicked.connect(self._go_today)

        month_header = QHBoxLayout()
        month_header.addWidget(self.month_label)
        month_header.addStretch()
        month_header.addWidget(self.today_button)
        month_header.addWidget(self.previous_button)
        month_header.addWidget(self.next_button)

        self.grid_frame = QFrame()
        self.grid_frame.setObjectName("surface")
        self.grid = QGridLayout(self.grid_frame)
        self.grid.setContentsMargins(1, 1, 1, 1)
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(0)

        calendar_panel = QWidget()
        calendar_layout = QVBoxLayout(calendar_panel)
        calendar_layout.setContentsMargins(0, 0, 0, 0)
        calendar_layout.setSpacing(8)
        calendar_layout.addLayout(month_header)
        calendar_layout.addWidget(self.grid_frame)

        self.day_list = DayTaskList()
        self.day_list.task_selected.connect(self._show_task)
        self.day_list.add_requested.connect(
            lambda: self.add_requested.emit(self.selected_date)
        )
        self.task_detail = TaskDetailWidget()
        self.task_detail.edit_requested.connect(self.edit_requested)
        self.task_detail.complete_requested.connect(self.complete_requested)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = QPushButton("← この日のタスク")
        self.back_button.clicked.connect(lambda: self.side_stack.setCurrentWidget(self.day_list))
        detail_layout.addWidget(self.back_button)
        detail_layout.addWidget(self.task_detail)

        self.side_stack = QStackedWidget()
        self.side_stack.setMinimumWidth(210)
        self.side_stack.setMaximumWidth(320)
        self.side_stack.addWidget(self.day_list)
        self.side_stack.addWidget(detail_container)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(calendar_panel, 1)
        layout.addWidget(self.side_stack)

        self._rebuild_grid()
        self.refresh()

    def refresh(self) -> None:
        tasks = self.task_service.list_active_tasks()
        tasks_by_date: dict[date, list[Task]] = defaultdict(list)
        for task in tasks:
            if task.due_at:
                tasks_by_date[task.due_at.date()].append(task)
        for cell in self.cells:
            cell.set_tasks(tasks_by_date.get(cell.cell_date, []))
            cell.set_selected(cell.cell_date == self.selected_date)
        self._show_day(self.selected_date)

    def _rebuild_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self.cells.clear()
        self.month_label.setText(f"{self.shown_year}年{self.shown_month}月")
        for column, name in enumerate(WEEKDAY_NAMES):
            label = QLabel(name)
            label.setObjectName("muted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(24)
            self.grid.addWidget(label, 0, column)

        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(
            self.shown_year, self.shown_month
        )
        while len(weeks) < 6:
            next_start = weeks[-1][-1]
            weeks.append(
                [date.fromordinal(next_start.toordinal() + offset) for offset in range(1, 8)]
            )
        for row, week in enumerate(weeks[:6], start=1):
            for column, cell_date in enumerate(week):
                cell = CalendarCell(cell_date, self.shown_month)
                cell.setMinimumHeight(52)
                cell.date_selected.connect(self._qdate_selected)
                cell.task_selected.connect(self._task_label_selected)
                self.grid.addWidget(cell, row, column)
                self.cells.append(cell)

    def _change_month(self, delta: int) -> None:
        month_index = (self.shown_year * 12 + self.shown_month - 1) + delta
        self.shown_year, month_zero = divmod(month_index, 12)
        self.shown_month = month_zero + 1
        self.selected_date = date(self.shown_year, self.shown_month, 1)
        self._rebuild_grid()
        self.refresh()

    def _go_today(self) -> None:
        self.selected_date = date.today()
        self.shown_year = self.selected_date.year
        self.shown_month = self.selected_date.month
        self._rebuild_grid()
        self.refresh()

    def _qdate_selected(self, selected: QDate) -> None:
        self.selected_date = date(selected.year(), selected.month(), selected.day())
        if (
            self.selected_date.year != self.shown_year
            or self.selected_date.month != self.shown_month
        ):
            self.shown_year = self.selected_date.year
            self.shown_month = self.selected_date.month
            self._rebuild_grid()
        self.refresh()

    def _task_label_selected(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task and task.due_at:
            self.selected_date = task.due_at.date()
            self.refresh()
            self._show_task(task_id)

    def _show_day(self, target_date: date) -> None:
        tasks = self.task_service.list_tasks_for_date(target_date)
        self.day_list.set_date_and_tasks(target_date, tasks)
        self.side_stack.setCurrentWidget(self.day_list)

    def _show_task(self, task_id: str) -> None:
        task = self.task_service.get_task(task_id)
        if task is None:
            return
        self.task_detail.set_task(task)
        self.side_stack.setCurrentIndex(1)
