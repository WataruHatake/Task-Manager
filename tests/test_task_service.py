from __future__ import annotations

from datetime import date, time, timedelta

from sqlalchemy import func, select

from dandori.domain.enums import Priority, TaskStatus
from dandori.infrastructure.models import Category, TaskHistory
from dandori.services.task_service import TaskInput


def test_database_initializes_default_category(database):
    with database.session() as session:
        category_names = list(session.scalars(select(Category.name)))

    assert category_names == ["未分類"]


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
