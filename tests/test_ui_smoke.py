from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from dandori.services.task_service import TaskInput
from dandori.ui.edge_windows import EdgeAddWindow, EdgeTaskWindow
from dandori.ui.main_window import MainWindow
from dandori.ui.time_combo import TimeComboBox


def test_main_window_loads_tasks_and_switches_calendar(qtbot, task_service):
    task = task_service.create_task(TaskInput(title="表示確認", due_date=date.today()))
    window = MainWindow(task_service)
    qtbot.addWidget(window)

    window.refresh(task.id)

    assert window.table_page.table.rowCount() == 1
    assert window.table_page.selected_task_id() == task.id
    window.calendar_button.click()
    assert window.pages.currentWidget() is window.calendar_page
    assert window.search_edit.isHidden()


def test_calendar_date_to_day_tasks_to_detail(qtbot, task_service):
    task = task_service.create_task(TaskInput(title="カレンダー確認", due_date=date.today()))
    window = MainWindow(task_service)
    qtbot.addWidget(window)
    window.calendar_button.click()

    window.calendar_page._show_day(date.today())

    assert "1件" in window.calendar_page.day_list.count_label.text()
    window.calendar_page._show_task(task.id)
    assert window.calendar_page.task_detail.title_label.text() == "カレンダー確認"
    assert window.calendar_page.side_stack.currentIndex() == 1


def test_edge_windows_are_fixed_and_can_navigate(qtbot, task_service):
    task_window = EdgeTaskWindow(task_service)
    add_window = EdgeAddWindow(task_service)
    qtbot.addWidget(task_window)
    qtbot.addWidget(add_window)

    assert task_window.minimumWidth() == task_window.maximumWidth() == 180
    assert task_window.windowFlags() & Qt.WindowType.FramelessWindowHint

    add_button = next(
        button for button in task_window.findChildren(QPushButton) if button.text() == "＋ 追加"
    )
    with qtbot.waitSignal(task_window.open_add_requested):
        add_button.click()

    tasks_button = next(
        button for button in add_window.findChildren(QPushButton) if button.text() == "タスク"
    )
    with qtbot.waitSignal(add_window.open_tasks_requested):
        tasks_button.click()


def test_time_combo_supports_dropdown_and_direct_input(qtbot):
    combo = TimeComboBox()
    qtbot.addWidget(combo)

    assert combo.count() == 48
    combo.setCurrentText("18:30")
    assert combo.time_value() == time(18, 30)
    combo.setEditText("18:15")
    assert combo.time_value() == time(18, 15)
