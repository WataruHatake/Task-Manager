from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select

from dandori.domain.enums import Priority, TaskStatus
from dandori.infrastructure.models import Category, TaskHistory, local_now
from dandori.services.task_service import TaskInput


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
