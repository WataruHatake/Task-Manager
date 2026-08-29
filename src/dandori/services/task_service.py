from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, or_, select, update
from sqlalchemy.orm import selectinload

from dandori.domain.enums import ACTIVE_STATUSES, Priority, TaskStatus
from dandori.infrastructure.database import Database
from dandori.infrastructure.models import Category, Setting, Task, TaskHistory, local_now


@dataclass(frozen=True)
class TaskInput:
    title: str
    memo: str = ""
    progress_note: str = ""
    progress_percent: int = 0
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.NORMAL
    due_date: date | None = None
    due_time: time | None = None
    category_id: str | None = None


class TaskService:
    TRASH_RETENTION_DAYS = 30

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _task_query() -> Select:
        return select(Task).options(
            selectinload(Task.category),
            selectinload(Task.subtasks),
            selectinload(Task.tags),
        )

    def list_categories(self) -> list[Category]:
        with self.database.session() as session:
            return list(session.scalars(select(Category).order_by(Category.name)))

    def default_category(self) -> Category:
        categories = self.list_categories()
        for category in categories:
            if category.name == "未分類":
                return category
        if not categories:
            raise RuntimeError("初期カテゴリがありません。")
        return categories[0]

    def create_category(self, name: str, color: str = "#8E8E93") -> Category:
        normalized_name = self._validate_category(name, color)
        with self.database.session() as session:
            categories = list(session.scalars(select(Category)))
            if any(category.name.casefold() == normalized_name.casefold() for category in categories):
                raise ValueError("同じ名前のカテゴリが既にあります。")
            category = Category(name=normalized_name, color=color.upper())
            session.add(category)
            session.commit()
            session.refresh(category)
            return category

    def update_category(self, category_id: str, name: str, color: str) -> Category:
        normalized_name = self._validate_category(name, color)
        with self.database.session() as session:
            category = session.get(Category, category_id)
            if category is None:
                raise LookupError("カテゴリが見つかりません。")
            if category.name == "未分類" and normalized_name != "未分類":
                raise ValueError("「未分類」の名称は変更できません。")
            categories = list(session.scalars(select(Category).where(Category.id != category_id)))
            if any(item.name.casefold() == normalized_name.casefold() for item in categories):
                raise ValueError("同じ名前のカテゴリが既にあります。")
            category.name = normalized_name
            category.color = color.upper()
            category.updated_at = local_now()
            session.commit()
            session.refresh(category)
            return category

    def delete_category(self, category_id: str) -> None:
        with self.database.session() as session:
            category = session.get(Category, category_id)
            if category is None:
                raise LookupError("カテゴリが見つかりません。")
            if category.name == "未分類":
                raise ValueError("「未分類」は削除できません。")
            default = session.scalar(select(Category).where(Category.name == "未分類"))
            if default is None:
                raise RuntimeError("初期カテゴリがありません。")
            session.execute(
                update(Task)
                .where(Task.category_id == category.id)
                .values(category_id=default.id, updated_at=local_now())
            )
            session.delete(category)
            session.commit()

    @staticmethod
    def _validate_category(name: str, color: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("カテゴリ名を入力してください。")
        if len(normalized_name) > 80:
            raise ValueError("カテゴリ名は80文字以内で入力してください。")
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError("カテゴリ色の形式が正しくありません。")
        try:
            int(color[1:], 16)
        except ValueError as error:
            raise ValueError("カテゴリ色の形式が正しくありません。") from error
        return normalized_name

    def get_setting(self, key: str, default=None):
        with self.database.session() as session:
            setting = session.get(Setting, key)
            if setting is None:
                return default
            try:
                return json.loads(setting.value_json)
            except json.JSONDecodeError:
                return default

    def set_setting(self, key: str, value) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        with self.database.session() as session:
            setting = session.get(Setting, key)
            if setting is None:
                session.add(Setting(key=key, value_json=serialized))
            else:
                setting.value_json = serialized
                setting.updated_at = local_now()
            session.commit()

    def list_active_tasks(self, search_text: str = "") -> list[Task]:
        with self.database.session() as session:
            statement = self._task_query().where(
                Task.deleted_at.is_(None),
                Task.status.in_([status.value for status in ACTIVE_STATUSES]),
            )
            if search_text.strip():
                value = f"%{search_text.strip()}%"
                statement = statement.where(
                    or_(
                        Task.title.like(value),
                        Task.memo.like(value),
                        Task.progress_note.like(value),
                    )
                )
            tasks = list(session.scalars(statement))
        return sorted(tasks, key=self._sort_key)

    def list_tasks_for_view(self, view: str, search_text: str = "") -> list[Task]:
        if view == "trash":
            with self.database.session() as session:
                statement = self._task_query().where(Task.deleted_at.is_not(None))
                if search_text.strip():
                    value = f"%{search_text.strip()}%"
                    statement = statement.where(
                        or_(
                            Task.title.like(value),
                            Task.memo.like(value),
                            Task.progress_note.like(value),
                        )
                    )
                tasks = list(session.scalars(statement))
            return sorted(
                tasks,
                key=lambda task: task.deleted_at or datetime.min,
                reverse=True,
            )

        if view == "completed":
            with self.database.session() as session:
                statement = self._task_query().where(
                    Task.deleted_at.is_(None),
                    Task.status.in_(
                        (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value)
                    ),
                )
                if search_text.strip():
                    value = f"%{search_text.strip()}%"
                    statement = statement.where(
                        or_(
                            Task.title.like(value),
                            Task.memo.like(value),
                            Task.progress_note.like(value),
                        )
                    )
                tasks = list(session.scalars(statement))
            return sorted(
                tasks,
                key=lambda task: (
                    task.completed_at or task.cancelled_at or task.updated_at
                ),
                reverse=True,
            )

        tasks = self.list_active_tasks(search_text)
        now = local_now()
        if view == "today":
            return [
                task
                for task in tasks
                if task.due_at is not None and task.due_at.date() == now.date()
            ]
        if view == "overdue":
            return [
                task
                for task in tasks
                if task.due_at is not None and task.due_at < now
            ]
        return tasks

    def list_tasks_for_date(self, target_date: date) -> list[Task]:
        return [
            task
            for task in self.list_active_tasks()
            if task.due_at is not None and task.due_at.date() == target_date
        ]

    def get_task(self, task_id: str) -> Task | None:
        with self.database.session() as session:
            return session.scalar(self._task_query().where(Task.id == task_id))

    def create_task(self, task_input: TaskInput) -> Task:
        title = task_input.title.strip()
        if not title:
            raise ValueError("タスク名を入力してください。")
        progress_percent = self._validate_progress_percent(task_input.progress_percent)
        category_id = task_input.category_id or self.default_category().id
        due_at, due_has_time = self._to_due_at(task_input.due_date, task_input.due_time)
        task = Task(
            title=title,
            memo=task_input.memo.strip(),
            progress_note=task_input.progress_note.strip(),
            progress_percent=progress_percent,
            status=task_input.status.value,
            priority=int(task_input.priority),
            due_at=due_at,
            due_has_time=due_has_time,
            category_id=category_id,
        )
        with self.database.session() as session:
            session.add(task)
            session.flush()
            session.add(
                TaskHistory(
                    task_id=task.id,
                    action="created",
                    after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                )
            )
            session.commit()
            return session.scalar(self._task_query().where(Task.id == task.id))

    def update_task(self, task_id: str, task_input: TaskInput) -> Task:
        title = task_input.title.strip()
        if not title:
            raise ValueError("タスク名を入力してください。")
        progress_percent = self._validate_progress_percent(task_input.progress_percent)
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("タスクが見つかりません。")
            before = self._snapshot(task)
            due_at, due_has_time = self._to_due_at(task_input.due_date, task_input.due_time)
            task.title = title
            task.memo = task_input.memo.strip()
            task.progress_note = task_input.progress_note.strip()
            task.progress_percent = progress_percent
            task.status = task_input.status.value
            task.priority = int(task_input.priority)
            task.due_at = due_at
            task.due_has_time = due_has_time
            task.category_id = task_input.category_id or self.default_category().id
            task.updated_at = local_now()
            task.version += 1
            self._apply_terminal_dates(task)
            session.flush()
            session.add(
                TaskHistory(
                    task_id=task.id,
                    action="updated",
                    before_json=json.dumps(before, ensure_ascii=False),
                    after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                )
            )
            session.commit()
            return session.scalar(self._task_query().where(Task.id == task.id))

    def complete_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise LookupError("タスクが見つかりません。")
        return self.update_task(
            task_id,
            TaskInput(
                title=task.title,
                memo=task.memo,
                progress_note=task.progress_note,
                progress_percent=task.progress_percent,
                status=TaskStatus.COMPLETED,
                priority=task.priority_enum,
                due_date=task.due_at.date() if task.due_at else None,
                due_time=task.due_at.time() if task.due_at and task.due_has_time else None,
                category_id=task.category_id,
            ),
        )

    def restore_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if task is None:
            raise LookupError("タスクが見つかりません。")
        return self.update_task(
            task_id,
            TaskInput(
                title=task.title,
                memo=task.memo,
                progress_note=task.progress_note,
                progress_percent=task.progress_percent,
                status=TaskStatus.TODO,
                priority=task.priority_enum,
                due_date=task.due_at.date() if task.due_at else None,
                due_time=task.due_at.time() if task.due_at and task.due_has_time else None,
                category_id=task.category_id,
            ),
        )

    def trash_task(self, task_id: str) -> Task:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("タスクが見つかりません。")
            if task.deleted_at is not None:
                return session.scalar(self._task_query().where(Task.id == task_id))
            before = self._snapshot(task)
            deleted_at = local_now()
            task.deleted_at = deleted_at
            task.purge_at = deleted_at + timedelta(days=self.TRASH_RETENTION_DAYS)
            task.updated_at = deleted_at
            task.version += 1
            session.flush()
            session.add(
                TaskHistory(
                    task_id=task.id,
                    action="trashed",
                    before_json=json.dumps(before, ensure_ascii=False),
                    after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                )
            )
            session.commit()
            return session.scalar(self._task_query().where(Task.id == task_id))

    def restore_trashed_task(self, task_id: str) -> Task:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("タスクが見つかりません。")
            if task.deleted_at is None:
                return session.scalar(self._task_query().where(Task.id == task_id))
            before = self._snapshot(task)
            task.deleted_at = None
            task.purge_at = None
            task.updated_at = local_now()
            task.version += 1
            session.flush()
            session.add(
                TaskHistory(
                    task_id=task.id,
                    action="restored_from_trash",
                    before_json=json.dumps(before, ensure_ascii=False),
                    after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                )
            )
            session.commit()
            return session.scalar(self._task_query().where(Task.id == task_id))

    def permanently_delete_task(self, task_id: str) -> None:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("タスクが見つかりません。")
            if task.deleted_at is None:
                raise ValueError("完全削除はゴミ箱内のタスクだけ実行できます。")
            session.delete(task)
            session.commit()

    def purge_expired_tasks(self) -> int:
        now = local_now()
        with self.database.session() as session:
            tasks = list(
                session.scalars(
                    select(Task).where(
                        Task.deleted_at.is_not(None),
                        Task.purge_at.is_not(None),
                        Task.purge_at <= now,
                    )
                )
            )
            for task in tasks:
                session.delete(task)
            session.commit()
            return len(tasks)

    @staticmethod
    def _validate_progress_percent(value: int) -> int:
        try:
            progress_percent = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("進捗率は0～100%で入力してください。") from error
        if not 0 <= progress_percent <= 100:
            raise ValueError("進捗率は0～100%で入力してください。")
        return progress_percent

    @staticmethod
    def _to_due_at(due_date: date | None, due_time: time | None) -> tuple[datetime | None, bool]:
        if due_date is None:
            return None, False
        if due_time is None:
            return datetime.combine(due_date, time(17, 0)), False
        return datetime.combine(due_date, due_time.replace(second=0, microsecond=0)), True

    @staticmethod
    def _apply_terminal_dates(task: Task) -> None:
        if task.status == TaskStatus.COMPLETED.value:
            task.completed_at = task.completed_at or local_now()
            task.cancelled_at = None
        elif task.status == TaskStatus.CANCELLED.value:
            task.cancelled_at = task.cancelled_at or local_now()
            task.completed_at = None
        else:
            task.completed_at = None
            task.cancelled_at = None

    @staticmethod
    def _snapshot(task: Task) -> dict[str, object]:
        return {
            "title": task.title,
            "memo": task.memo,
            "progress_note": task.progress_note,
            "progress_percent": task.progress_percent,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "due_has_time": task.due_has_time,
            "category_id": task.category_id,
            "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
            "purge_at": task.purge_at.isoformat() if task.purge_at else None,
        }

    @staticmethod
    def _sort_key(task: Task) -> tuple[int, datetime, int, str]:
        now = local_now()
        if task.due_at is None:
            bucket = 3
            due = datetime.max
        elif task.due_at < now:
            bucket = 0
            due = task.due_at
        elif task.due_at.date() == now.date():
            bucket = 1
            due = task.due_at
        else:
            bucket = 2
            due = task.due_at
        return bucket, due, -task.priority, task.title.casefold()
