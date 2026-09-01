from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import func, select

from dandori.domain.enums import Priority, TaskStatus
from dandori.infrastructure.models import Category, ReminderEvent, TaskHistory, local_now
from dandori.services.task_service import RecurrenceInput, SubtaskInput, TaskInput


def test_database_initializes_default_category(database):
    with database.session() as session:
        category = session.scalar(select(Category))

    assert category is not None
    assert category.name == "未分類"
    assert category.color == "#8E8E93"


def test_settings_are_saved_as_json(task_service):
    expected = {"palette": "cotton-bloom", "appearance": "light"}

    task_service.set_setting("theme", expected)

    assert task_service.get_setting("theme", {}) == expected


def test_create_task_with_date_only_uses_internal_1700(task_service, database):
    due_date = date.today() + timedelta(days=1)

    task = task_service.create_task(
        TaskInput(
            title="提案資料をレビュー",
            memo="数値根拠を確認",
            priority=Priority.CRITICAL,
            due_date=due_date,
        )
    )

    assert task.due_at is not None
    assert task.due_at.date() == due_date
    assert task.due_at.time() == time(17, 0)
    assert task.due_has_time is False
    assert task.category.name == "未分類"
    with database.session() as session:
        history_count = session.scalar(select(func.count(TaskHistory.id)))
    assert history_count == 1


def test_create_update_and_complete_task(task_service):
    task = task_service.create_task(TaskInput(title="会議資料を作成"))

    updated = task_service.update_task(
        task.id,
        TaskInput(
            title="会議資料を作成",
            memo="15時まで",
            status=TaskStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            due_date=date.today(),
            due_time=time(15, 0),
            category_id=task.category_id,
        ),
    )

    assert updated.status_enum is TaskStatus.IN_PROGRESS
    assert updated.priority_enum is Priority.HIGH
    assert updated.due_has_time is True

    completed = task_service.complete_task(task.id)

    assert completed.status_enum is TaskStatus.COMPLETED
    assert completed.completed_at is not None
    assert task_service.list_active_tasks() == []


def test_progress_is_saved_separately_from_memo_and_completion(task_service):
    task = task_service.create_task(
        TaskInput(
            title="進捗管理",
            memo="完了条件を確認する",
            progress_note="資料を作成中",
            progress_percent=35,
        )
    )

    assert task.memo == "完了条件を確認する"
    assert task.progress_note == "資料を作成中"
    assert task.progress_percent == 35
    assert [item.id for item in task_service.list_active_tasks("資料を作成中")] == [
        task.id
    ]

    updated = task_service.update_task(
        task.id,
        TaskInput(
            title=task.title,
            memo=task.memo,
            progress_note="先方回答待ち",
            progress_percent=100,
            status=TaskStatus.IN_PROGRESS,
            category_id=task.category_id,
        ),
    )

    assert updated.progress_note == "先方回答待ち"
    assert updated.progress_percent == 100
    assert updated.status_enum is TaskStatus.IN_PROGRESS

    completed = task_service.complete_task(task.id)

    assert completed.progress_percent == 100
    assert completed.status_enum is TaskStatus.COMPLETED


@pytest.mark.parametrize("progress_percent", [-1, 101])
def test_progress_percent_must_be_between_zero_and_one_hundred(
    task_service, progress_percent
):
    with pytest.raises(ValueError, match="0～100"):
        task_service.create_task(
            TaskInput(title="不正な進捗", progress_percent=progress_percent)
        )


def test_task_views_and_restore(task_service):
    today_task = task_service.create_task(
        TaskInput(title="今日", due_date=date.today(), due_time=time(23, 59))
    )
    future_task = task_service.create_task(
        TaskInput(title="今後", due_date=date.today() + timedelta(days=2))
    )
    overdue_task = task_service.create_task(
        TaskInput(title="期限切れ", due_date=date.today() - timedelta(days=1))
    )
    completed_task = task_service.create_task(TaskInput(title="完了対象"))
    task_service.complete_task(completed_task.id)

    assert {task.id for task in task_service.list_tasks_for_view("today")} == {
        today_task.id
    }
    assert {task.id for task in task_service.list_tasks_for_view("overdue")} == {
        overdue_task.id
    }
    assert {task.id for task in task_service.list_tasks_for_view("all")} == {
        today_task.id,
        future_task.id,
        overdue_task.id,
    }
    assert [task.id for task in task_service.list_tasks_for_view("completed")] == [
        completed_task.id
    ]

    restored = task_service.restore_task(completed_task.id)

    assert restored.status_enum is TaskStatus.TODO
    assert task_service.list_tasks_for_view("completed") == []


def test_today_view_combines_manual_planning_and_tasks_due_today(task_service):
    due_today = task_service.create_task(
        TaskInput(title="本日期限", due_date=date.today(), due_time=time(23, 59))
    )
    manually_planned = task_service.create_task(
        TaskInput(
            title="今日やる",
            due_date=date.today() + timedelta(days=5),
            planned_for_date=date.today(),
        )
    )
    not_today = task_service.create_task(
        TaskInput(title="後日", due_date=date.today() + timedelta(days=5))
    )

    assert {task.id for task in task_service.list_tasks_for_view("today")} == {
        due_today.id,
        manually_planned.id,
    }

    task_service.set_planned_for_today(manually_planned.id, False)
    assert {task.id for task in task_service.list_tasks_for_view("today")} == {
        due_today.id
    }

    task_service.set_planned_for_today(not_today.id, True)
    assert {task.id for task in task_service.list_tasks_for_view("today")} == {
        due_today.id,
        not_today.id,
    }


def test_trash_restore_and_permanent_delete(task_service):
    task = task_service.create_task(TaskInput(title="削除対象"))

    trashed = task_service.trash_task(task.id)

    assert trashed.deleted_at is not None
    assert trashed.purge_at is not None
    assert (trashed.purge_at - trashed.deleted_at).days == 30
    assert task_service.list_active_tasks() == []
    assert [item.id for item in task_service.list_tasks_for_view("trash")] == [
        task.id
    ]

    restored = task_service.restore_trashed_task(task.id)

    assert restored.deleted_at is None
    assert restored.purge_at is None
    assert [item.id for item in task_service.list_active_tasks()] == [task.id]

    task_service.trash_task(task.id)
    task_service.permanently_delete_task(task.id)

    assert task_service.get_task(task.id) is None


def test_expired_trash_is_purged(task_service, database):
    task = task_service.create_task(TaskInput(title="期限切れの削除対象"))
    task_service.trash_task(task.id)
    with database.session() as session:
        stored = session.get(type(task), task.id)
        assert stored is not None
        stored.purge_at = local_now() - timedelta(minutes=1)
        session.commit()

    assert task_service.purge_expired_tasks() == 1
    assert task_service.get_task(task.id) is None


def test_list_tasks_for_selected_date(task_service):
    target = date.today() + timedelta(days=3)
    matching = task_service.create_task(TaskInput(title="対象タスク", due_date=target))
    task_service.create_task(TaskInput(title="別日タスク", due_date=target + timedelta(days=1)))

    tasks = task_service.list_tasks_for_date(target)

    assert [task.id for task in tasks] == [matching.id]


def test_search_matches_title_and_memo(task_service):
    task_service.create_task(TaskInput(title="経費精算", memo="交通費を確認"))
    task_service.create_task(TaskInput(title="アジェンダ", memo="進捗を記載"))

    assert [task.title for task in task_service.list_active_tasks("交通費")] == ["経費精算"]
    assert [task.title for task in task_service.list_active_tasks("アジェンダ")] == ["アジェンダ"]


def test_category_create_update_and_delete_reassigns_tasks(task_service):
    category = task_service.create_category("プロジェクトA", "#4B8DFF")
    task = task_service.create_task(TaskInput(title="カテゴリ確認", category_id=category.id))

    updated = task_service.update_category(category.id, "プロジェクトB", "#F5A623")

    assert updated.name == "プロジェクトB"
    assert updated.color == "#F5A623"

    task_service.delete_category(category.id)

    reassigned = task_service.get_task(task.id)
    assert reassigned is not None
    assert reassigned.category.name == "未分類"


def test_default_category_cannot_be_deleted(task_service):
    default = task_service.default_category()

    with pytest.raises(ValueError, match="削除できません"):
        task_service.delete_category(default.id)


def test_recurring_tasks_generate_selected_weekdays_and_skip_holidays(task_service):
    tasks = task_service.create_recurring_tasks(
        TaskInput(title="平日タスク", due_time=time(10, 0)),
        RecurrenceInput(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 5),
            weekdays=(0, 1, 2, 3, 4),
            include_holidays=False,
        ),
        [SubtaskInput("確認する")],
    )

    assert [task.due_at.date() for task in tasks] == [date(2026, 1, 2), date(2026, 1, 5)]
    assert all(task.recurrence_group_id for task in tasks)
    assert all([subtask.title for subtask in task.subtasks] == ["確認する"] for task in tasks)


def test_recurring_task_changes_can_be_applied_to_active_siblings(task_service):
    tasks = task_service.create_recurring_tasks(
        TaskInput(title="定例作業", due_time=time(10, 0)),
        RecurrenceInput(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            weekdays=(1, 2, 3),
            include_holidays=True,
        ),
        [SubtaskInput("変更前")],
    )
    task_service.complete_task(tasks[2].id)
    source = task_service.update_task(
        tasks[0].id,
        TaskInput(
            title="更新した定例作業",
            memo="共通メモ",
            priority=Priority.CRITICAL,
            due_date=tasks[0].due_at.date(),
            due_time=time(15, 30),
            category_id=tasks[0].category_id,
        ),
    )

    updated = task_service.apply_recurrence_changes(
        source.id, [SubtaskInput("共通の確認事項")]
    )

    assert {item.id for item in updated} == {tasks[0].id, tasks[1].id}
    sibling = task_service.get_task(tasks[1].id)
    assert sibling.title == "更新した定例作業"
    assert sibling.memo == "共通メモ"
    assert sibling.priority_enum is Priority.CRITICAL
    assert sibling.due_at.date() == tasks[1].due_at.date()
    assert sibling.due_at.time() == time(15, 30)
    assert [item.title for item in sibling.subtasks] == ["共通の確認事項"]
    completed = task_service.get_task(tasks[2].id)
    assert completed.title == "定例作業"


def test_subtasks_can_be_added_updated_completed_and_removed(task_service):
    task = task_service.create_task(TaskInput(title="親タスク"))
    subtasks = task_service.replace_subtasks(
        task.id,
        [SubtaskInput("資料作成"), SubtaskInput("レビュー", completed=True)],
    )

    assert [item.title for item in subtasks] == ["資料作成", "レビュー"]
    assert subtasks[1].completed is True

    task_service.set_subtask_completed(subtasks[0].id, True)
    remaining = task_service.replace_subtasks(
        task.id,
        [SubtaskInput("資料確定", True, subtasks[0].id)],
    )

    assert [(item.title, item.completed) for item in remaining] == [("資料確定", True)]


def test_attachments_are_copied_and_removed(task_service, tmp_path):
    task = task_service.create_task(TaskInput(title="添付あり"))
    source = tmp_path / "資料.txt"
    source.write_text("content", encoding="utf-8")

    attachment = task_service.add_attachment(task.id, source)
    stored = task_service.attachment_path(attachment)

    assert stored.read_text(encoding="utf-8") == "content"
    assert task_service.get_task(task.id).attachments[0].original_name == "資料.txt"

    task_service.remove_attachment(attachment.id)

    assert not stored.exists()
    assert task_service.get_task(task.id).attachments == []


def test_completed_task_is_archived_after_individual_retention(task_service, database):
    task = task_service.create_task(TaskInput(title="短期保存", retention_days=1))
    task_service.complete_task(task.id)
    with database.session() as session:
        stored = session.get(type(task), task.id)
        stored.completed_at = local_now() - timedelta(days=2)
        session.commit()

    assert task_service.archive_expired_completed_tasks() == 1
    archived = task_service.get_task(task.id)
    assert archived.deleted_at is not None
    assert archived.purge_at is not None


def test_priority_and_custom_reminder_schedules(task_service):
    due_date = date.today() + timedelta(days=2)
    critical = task_service.create_task(
        TaskInput(
            title="超最優先",
            priority=Priority.CRITICAL,
            due_date=due_date,
            due_time=time(17, 0),
        )
    )
    schedule = task_service.reminder_schedule(
        critical, datetime.combine(due_date - timedelta(days=1), time(9, 0))
    )

    assert datetime.combine(due_date - timedelta(days=1), time(17, 0)) in schedule
    assert datetime.combine(due_date, time(16, 50)) in schedule

    custom = task_service.create_task(
        TaskInput(
            title="個別通知",
            due_date=due_date,
            due_time=time(12, 0),
            reminder_mode="custom",
            reminder_config={
                "start_minutes": 60,
                "interval_minutes": 30,
                "final_window_minutes": 0,
                "final_interval_minutes": 0,
                "previous_day_17": False,
                "work_start_hour": 9,
                "work_end_hour": 17,
            },
        )
    )
    custom_schedule = task_service.reminder_schedule(
        custom, datetime.combine(due_date, time(10, 0))
    )

    assert custom_schedule == [
        datetime.combine(due_date, time(11, 0)),
        datetime.combine(due_date, time(11, 30)),
        datetime.combine(due_date, time(12, 0)),
    ]


def test_due_reminders_are_claimed_and_can_be_snoozed(task_service, database):
    task = task_service.create_task(
        TaskInput(title="通知対象", due_date=date.today() + timedelta(days=1))
    )
    with database.session() as session:
        session.add(
            ReminderEvent(
                task_id=task.id,
                scheduled_at=local_now() - timedelta(minutes=1),
            )
        )
        session.commit()

    deliveries = task_service.claim_due_reminders()

    assert any(item.task_id == task.id for item in deliveries)
    snoozed = task_service.snooze_task(task.id, 10)
    assert snoozed.action == "snoozed_10"


def test_snoozed_reminder_survives_startup_schedule_rebuild(task_service, database):
    task = task_service.create_task(
        TaskInput(title="再起動後も再通知", due_date=date.today() + timedelta(days=1))
    )
    snoozed = task_service.snooze_task(task.id, 10)

    task_service.rebuild_all_reminders()

    with database.session() as session:
        stored = session.get(ReminderEvent, snoozed.id)
        assert stored is not None
        assert stored.status == "pending"
        assert stored.action == "snoozed_10"
