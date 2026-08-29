from __future__ import annotations

from datetime import date, time, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QPushButton

from dandori.domain.enums import TaskStatus
from dandori.services.task_service import TaskInput
from dandori.ui.calendar_page import CalendarPage
from dandori.ui.edge_windows import EdgeAddWindow, EdgeTaskWindow
from dandori.ui.main_window import MainWindow
from dandori.ui.task_dialog import TaskDialog
from dandori.ui.theme_dialog import ThemeDialog
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
    assert window.current_task_view == "all"
    assert window.nav_buttons["all"].isChecked()


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


def test_main_navigation_matches_task_views_and_can_restore(qtbot, task_service):
    today_task = task_service.create_task(TaskInput(title="今日", due_date=date.today()))
    future_task = task_service.create_task(
        TaskInput(title="今後", due_date=date.today() + timedelta(days=2))
    )
    window = MainWindow(task_service)
    qtbot.addWidget(window)

    assert window.page_title.text() == "今日のタスク"
    assert window.table_page.table.rowCount() == 1

    window.nav_buttons["all"].click()
    assert window.table_page.table.rowCount() == 2

    window._complete_task(today_task.id)
    assert not window.undo_bar.isHidden()
    assert window.table_page.detail.title_label.text() == future_task.title
    window.nav_buttons["completed"].click()
    assert window.table_page.table.rowCount() == 1
    assert window.table_page.detail.complete_button.text() == "元に戻す"

    window._restore_task(today_task.id)
    assert window.table_page.table.rowCount() == 0


def test_completed_task_can_be_edited(qtbot, task_service):
    task = task_service.create_task(
        TaskInput(title="編集前", progress_note="対応中", progress_percent=40)
    )
    task_service.complete_task(task.id)
    dialog = TaskDialog(task_service, task=task_service.get_task(task.id))
    qtbot.addWidget(dialog)

    assert TaskStatus(dialog.status_combo.currentData()) is TaskStatus.COMPLETED
    assert dialog.progress_note_edit.toPlainText() == "対応中"
    assert dialog.progress_percent_spin.value() == 40
    dialog.title_edit.setText("編集後")
    dialog.progress_note_edit.setPlainText("確認待ち")
    dialog.progress_percent_spin.setValue(75)
    dialog._save()

    updated = task_service.get_task(task.id)
    assert updated is not None
    assert updated.title == "編集後"
    assert updated.progress_note == "確認待ち"
    assert updated.progress_percent == 75
    assert updated.status_enum.value == "completed"


def test_trash_view_can_restore_tasks_and_has_clear_empty_message(
    qtbot, task_service
):
    task = task_service.create_task(TaskInput(title="ゴミ箱へ移動"))
    window = MainWindow(task_service)
    qtbot.addWidget(window)
    window.nav_buttons["all"].click()

    window._trash_task(task.id)
    window.nav_buttons["trash"].click()

    assert window.page_title.text() == "ゴミ箱"
    assert window.table_page.table.rowCount() == 1
    assert window.table_page.detail.complete_button.text() == "復元"
    assert window.table_page.detail.delete_button.text() == "完全に削除"

    window._restore_trashed_task(task.id)

    assert window.table_page.table.rowCount() == 0
    assert window.table_page.empty_title.text() == "ゴミ箱は空です"
    assert "30日間" in window.table_page.empty_hint.text()


def test_quick_add_values_are_carried_into_detail_dialog(qtbot, task_service):
    task_service.create_category("AAA", "#6B90B2")
    add_window = EdgeAddWindow(task_service)
    qtbot.addWidget(add_window)
    default_id = task_service.default_category().id

    assert add_window.category.currentData() == default_id
    add_window.title_edit.setText("引き継ぐタスク")
    add_window.due_enabled.setChecked(True)
    add_window.due_date.setDate(QDate.currentDate().addDays(1))
    draft = add_window._current_task_input()

    dialog = TaskDialog(task_service, initial_input=draft)
    qtbot.addWidget(dialog)

    assert dialog.title_edit.text() == "引き継ぐタスク"
    assert dialog.due_mode.currentData() == "datetime"
    assert dialog.category_combo.currentData() == default_id


def test_calendar_add_uses_selected_date(qtbot, task_service):
    calendar = CalendarPage(task_service)
    qtbot.addWidget(calendar)
    selected = date.today() + timedelta(days=3)
    calendar._show_day(selected)
    calendar.selected_date = selected

    with qtbot.waitSignal(calendar.add_requested) as signal:
        calendar.day_list.add_requested.emit()

    assert signal.args == [selected]


def test_edge_panel_width_is_saved(qtbot, task_service):
    task_window = EdgeTaskWindow(task_service)
    qtbot.addWidget(task_window)

    task_window._cycle_width()

    assert task_window.width() == 240
    add_window = EdgeAddWindow(task_service)
    qtbot.addWidget(add_window)
    assert add_window.width() == 240


def test_quick_add_refreshes_date_when_there_is_no_draft(qtbot, task_service):
    add_window = EdgeAddWindow(task_service)
    qtbot.addWidget(add_window)
    add_window.due_date.setDate(QDate.currentDate().addDays(-1))

    add_window.show_at_screen_edge()

    assert add_window.due_date.date() == QDate.currentDate()
    add_window.hide()


def test_theme_rows_are_clickable_and_dialog_is_small_screen_friendly(qtbot):
    dialog = ThemeDialog("default", "dark")
    qtbot.addWidget(dialog)
    target = dialog.palette_rows["cotton-bloom"]

    target.selected.emit("cotton-bloom")

    assert dialog.palette_key == "cotton-bloom"
    assert dialog.minimumHeight() <= 420
