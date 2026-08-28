from __future__ import annotations

from datetime import date

from dandori.services.task_service import TaskInput
from dandori.ui.main_window import MainWindow


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
