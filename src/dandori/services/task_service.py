from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import jpholiday
from sqlalchemy import Select, delete, or_, select, update
from sqlalchemy.orm import selectinload

from dandori.domain.enums import ACTIVE_STATUSES, Priority, TaskStatus
from dandori.infrastructure.database import Database
from dandori.infrastructure.models import (
    Attachment,
    Category,
    RecurrenceGroup,
    ReminderEvent,
    Setting,
    Subtask,
    Task,
    TaskHistory,
    local_now,
)

REMINDER_MODES = ("priority", "custom", "off")
DEFAULT_REMINDER_PROFILES: dict[int, dict[str, Any]] = {
    int(Priority.LOW): {
        "start_minutes": 30,
        "interval_minutes": 0,
        "final_window_minutes": 0,
        "final_interval_minutes": 0,
        "previous_day_17": False,
        "work_start_hour": 9,
        "work_end_hour": 17,
    },
    int(Priority.NORMAL): {
        "start_minutes": 1440,
        "interval_minutes": 60,
        "final_window_minutes": 0,
        "final_interval_minutes": 0,
        "previous_day_17": False,
        "work_start_hour": 9,
        "work_end_hour": 17,
    },
    int(Priority.HIGH): {
        "start_minutes": 1440,
        "interval_minutes": 60,
        "final_window_minutes": 180,
        "final_interval_minutes": 60,
        "previous_day_17": False,
        "work_start_hour": 9,
        "work_end_hour": 17,
    },
    int(Priority.URGENT): {
        "start_minutes": 1440,
        "interval_minutes": 60,
        "final_window_minutes": 180,
        "final_interval_minutes": 30,
        "previous_day_17": True,
        "work_start_hour": 9,
        "work_end_hour": 17,
    },
    int(Priority.CRITICAL): {
        "start_minutes": 1440,
        "interval_minutes": 60,
        "final_window_minutes": 180,
        "final_interval_minutes": 10,
        "previous_day_17": True,
        "work_start_hour": 9,
        "work_end_hour": 17,
    },
}


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
    planned_for_date: date | None = None
    category_id: str | None = None
    retention_days: int | None = 365
    reminder_mode: str = "priority"
    reminder_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecurrenceInput:
    start_date: date
    end_date: date
    weekdays: tuple[int, ...]
    include_holidays: bool = False


@dataclass(frozen=True)
class SubtaskInput:
    title: str
    completed: bool = False
    subtask_id: str | None = None


@dataclass(frozen=True)
class ReminderDelivery:
    event_id: str
    task_id: str
    title: str
    due_at: datetime | None
    priority: Priority


class TaskService:
    TRASH_RETENTION_DAYS = 30
    MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
    MAX_RECURRING_TASKS = 1000

    def __init__(self, database: Database) -> None:
        self.database = database
        self.attachments_dir = database.database_file.parent / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _task_query() -> Select:
        return select(Task).options(
            selectinload(Task.category),
            selectinload(Task.subtasks),
            selectinload(Task.tags),
            selectinload(Task.attachments),
            selectinload(Task.recurrence_group),
        )

    @staticmethod
    def default_reminder_config(priority: Priority | int) -> dict[str, Any]:
        return dict(DEFAULT_REMINDER_PROFILES[int(priority)])

    @classmethod
    def validate_reminder_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        source = config or {}
        result = cls.default_reminder_config(Priority.NORMAL)
        integer_ranges = {
            "start_minutes": (1, 60 * 24 * 30),
            "interval_minutes": (0, 60 * 24 * 7),
            "final_window_minutes": (0, 60 * 24 * 7),
            "final_interval_minutes": (0, 60 * 24),
            "work_start_hour": (0, 23),
            "work_end_hour": (0, 23),
        }
        for key, (minimum, maximum) in integer_ranges.items():
            try:
                value = int(source.get(key, result[key]))
            except (TypeError, ValueError) as error:
                raise ValueError("リマインド設定の値が正しくありません。") from error
            if not minimum <= value <= maximum:
                raise ValueError("リマインド設定の値が範囲外です。")
            result[key] = value
        result["previous_day_17"] = bool(source.get("previous_day_17", False))
        if result["work_start_hour"] > result["work_end_hour"]:
            raise ValueError("通知時間帯の開始は終了以前にしてください。")
        if result["final_window_minutes"] and not result["final_interval_minutes"]:
            raise ValueError("期限直前の通知間隔を設定してください。")
        return result

    @staticmethod
    def _validate_retention_days(value: int | None) -> int | None:
        if value is None:
            return None
        try:
            days = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("保存期間を正しく入力してください。") from error
        if not 1 <= days <= 3650:
            raise ValueError("保存期間は1～3650日で入力してください。")
        return days

    @classmethod
    def _validate_reminder_mode(cls, mode: str) -> str:
        normalized = str(mode or "priority")
        if normalized not in REMINDER_MODES:
            raise ValueError("リマインド設定が正しくありません。")
        return normalized

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
                if task.planned_for_date == now.date()
                or (task.due_at is not None and task.due_at.date() == now.date())
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
        retention_days = self._validate_retention_days(task_input.retention_days)
        reminder_mode = self._validate_reminder_mode(task_input.reminder_mode)
        reminder_config = (
            self.validate_reminder_config(task_input.reminder_config)
            if reminder_mode == "custom"
            else {}
        )
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
            planned_for_date=task_input.planned_for_date,
            category_id=category_id,
            retention_days=retention_days,
            reminder_mode=reminder_mode,
            reminder_config_json=json.dumps(reminder_config, ensure_ascii=False),
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
            task_id = task.id
        self.rebuild_reminders(task_id)
        return self.get_task(task_id)

    def update_task(self, task_id: str, task_input: TaskInput) -> Task:
        title = task_input.title.strip()
        if not title:
            raise ValueError("タスク名を入力してください。")
        progress_percent = self._validate_progress_percent(task_input.progress_percent)
        retention_days = self._validate_retention_days(task_input.retention_days)
        reminder_mode = self._validate_reminder_mode(task_input.reminder_mode)
        reminder_config = (
            self.validate_reminder_config(task_input.reminder_config)
            if reminder_mode == "custom"
            else {}
        )
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
            task.planned_for_date = task_input.planned_for_date
            task.category_id = task_input.category_id or self.default_category().id
            task.retention_days = retention_days
            task.reminder_mode = reminder_mode
            task.reminder_config_json = json.dumps(reminder_config, ensure_ascii=False)
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
        self.rebuild_reminders(task_id)
        return self.get_task(task_id)

    def create_recurring_tasks(
        self,
        task_input: TaskInput,
        recurrence: RecurrenceInput,
        subtasks: list[SubtaskInput] | None = None,
    ) -> list[Task]:
        title = task_input.title.strip()
        if not title:
            raise ValueError("タスク名を入力してください。")
        if recurrence.end_date < recurrence.start_date:
            raise ValueError("繰り返しの終了日は開始日以降にしてください。")
        weekdays = tuple(sorted(set(int(value) for value in recurrence.weekdays)))
        if not weekdays or any(value < 0 or value > 6 for value in weekdays):
            raise ValueError("繰り返す曜日を1つ以上選択してください。")
        dates: list[date] = []
        current = recurrence.start_date
        while current <= recurrence.end_date:
            if current.weekday() in weekdays and (
                recurrence.include_holidays or not jpholiday.is_holiday(current)
            ):
                dates.append(current)
            current += timedelta(days=1)
        if not dates:
            raise ValueError("指定した期間に作成対象の日付がありません。")
        if len(dates) > self.MAX_RECURRING_TASKS:
            raise ValueError(f"繰り返しタスクは{self.MAX_RECURRING_TASKS}件以内にしてください。")

        progress_percent = self._validate_progress_percent(task_input.progress_percent)
        retention_days = self._validate_retention_days(task_input.retention_days)
        reminder_mode = self._validate_reminder_mode(task_input.reminder_mode)
        reminder_config = (
            self.validate_reminder_config(task_input.reminder_config)
            if reminder_mode == "custom"
            else {}
        )
        category_id = task_input.category_id or self.default_category().id
        with self.database.session() as session:
            group = RecurrenceGroup(
                name=title,
                start_date=datetime.combine(recurrence.start_date, time.min),
                end_date=datetime.combine(recurrence.end_date, time.min),
                weekdays_json=json.dumps(weekdays),
                include_holidays=recurrence.include_holidays,
            )
            session.add(group)
            session.flush()
            task_ids: list[str] = []
            for target_date in dates:
                due_at, due_has_time = self._to_due_at(target_date, task_input.due_time)
                task = Task(
                    title=title,
                    memo=task_input.memo.strip(),
                    progress_note=task_input.progress_note.strip(),
                    progress_percent=progress_percent,
                    status=task_input.status.value,
                    priority=int(task_input.priority),
                    due_at=due_at,
                    due_has_time=due_has_time,
                    planned_for_date=task_input.planned_for_date,
                    category_id=category_id,
                    recurrence_group_id=group.id,
                    retention_days=retention_days,
                    reminder_mode=reminder_mode,
                    reminder_config_json=json.dumps(reminder_config, ensure_ascii=False),
                )
                session.add(task)
                session.flush()
                for position, subtask_input in enumerate(subtasks or []):
                    subtask_title = subtask_input.title.strip()
                    if subtask_title:
                        session.add(
                            Subtask(
                                task_id=task.id,
                                title=subtask_title,
                                completed=subtask_input.completed,
                                position=position,
                            )
                        )
                session.add(
                    TaskHistory(
                        task_id=task.id,
                        action="created_from_recurrence",
                        after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                    )
                )
                task_ids.append(task.id)
            session.commit()
        for task_id in task_ids:
            self.rebuild_reminders(task_id)
        return [task for task_id in task_ids if (task := self.get_task(task_id)) is not None]

    def apply_recurrence_changes(
        self,
        source_task_id: str,
        subtasks: list[SubtaskInput] | None = None,
    ) -> list[Task]:
        source = self.get_task(source_task_id)
        if source is None:
            raise LookupError("タスクが見つかりません。")
        if source.recurrence_group_id is None:
            return [source]
        with self.database.session() as session:
            siblings = list(
                session.scalars(
                    select(Task).where(
                        Task.recurrence_group_id == source.recurrence_group_id,
                        Task.id != source.id,
                        Task.deleted_at.is_(None),
                        Task.status.in_([status.value for status in ACTIVE_STATUSES]),
                    )
                )
            )
            sibling_ids: list[str] = []
            for sibling in siblings:
                before = self._snapshot(sibling)
                sibling.title = source.title
                sibling.memo = source.memo
                sibling.priority = source.priority
                sibling.category_id = source.category_id
                sibling.retention_days = source.retention_days
                sibling.reminder_mode = source.reminder_mode
                sibling.reminder_config_json = source.reminder_config_json
                if sibling.due_at and source.due_at:
                    sibling.due_at = datetime.combine(
                        sibling.due_at.date(), source.due_at.time()
                    )
                    sibling.due_has_time = source.due_has_time
                sibling.updated_at = local_now()
                sibling.version += 1
                session.add(
                    TaskHistory(
                        task_id=sibling.id,
                        action="updated_from_recurrence",
                        before_json=json.dumps(before, ensure_ascii=False),
                        after_json=json.dumps(self._snapshot(sibling), ensure_ascii=False),
                    )
                )
                sibling_ids.append(sibling.id)
            session.commit()
        if subtasks is not None:
            for sibling_id in sibling_ids:
                copied = [
                    SubtaskInput(item.title, item.completed)
                    for item in subtasks
                ]
                self.replace_subtasks(sibling_id, copied)
        for sibling_id in sibling_ids:
            self.rebuild_reminders(sibling_id)
        return [
            task
            for task_id in [source_task_id, *sibling_ids]
            if (task := self.get_task(task_id)) is not None
        ]

    def replace_subtasks(self, task_id: str, inputs: list[SubtaskInput]) -> list[Subtask]:
        normalized: list[SubtaskInput] = []
        for item in inputs:
            title = item.title.strip()
            if not title:
                continue
            if len(title) > 300:
                raise ValueError("サブタスク名は300文字以内で入力してください。")
            normalized.append(SubtaskInput(title, item.completed, item.subtask_id))
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("タスクが見つかりません。")
            existing = {
                subtask.id: subtask
                for subtask in session.scalars(
                    select(Subtask).where(Subtask.task_id == task_id)
                )
            }
            retained_ids: set[str] = set()
            for position, item in enumerate(normalized):
                subtask = existing.get(item.subtask_id or "")
                if subtask is None:
                    subtask = Subtask(task_id=task_id)
                    session.add(subtask)
                subtask.title = item.title
                subtask.completed = item.completed
                subtask.status = (
                    TaskStatus.COMPLETED.value if item.completed else TaskStatus.TODO.value
                )
                subtask.position = position
                subtask.updated_at = local_now()
                session.flush()
                retained_ids.add(subtask.id)
            for subtask_id, subtask in existing.items():
                if subtask_id not in retained_ids:
                    session.delete(subtask)
            session.commit()
        task = self.get_task(task_id)
        return list(task.subtasks) if task else []

    def set_subtask_completed(self, subtask_id: str, completed: bool) -> Subtask:
        with self.database.session() as session:
            subtask = session.get(Subtask, subtask_id)
            if subtask is None:
                raise LookupError("サブタスクが見つかりません。")
            subtask.completed = bool(completed)
            subtask.status = (
                TaskStatus.COMPLETED.value if completed else TaskStatus.TODO.value
            )
            subtask.updated_at = local_now()
            session.commit()
            session.refresh(subtask)
            return subtask

    def set_planned_for_today(self, task_id: str, enabled: bool) -> Task:
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
                status=task.status_enum,
                priority=task.priority_enum,
                due_date=task.due_at.date() if task.due_at else None,
                due_time=(
                    task.due_at.time()
                    if task.due_at is not None and task.due_has_time
                    else None
                ),
                planned_for_date=local_now().date() if enabled else None,
                category_id=task.category_id,
                retention_days=task.retention_days,
                reminder_mode=task.reminder_mode,
                reminder_config=self._reminder_json(task),
            ),
        )

    def add_attachment(self, task_id: str, source: str | Path) -> Attachment:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise ValueError("添付するファイルが見つかりません。")
        size = source_path.stat().st_size
        if size > self.MAX_ATTACHMENT_BYTES:
            raise ValueError("添付ファイルは50MB以内にしてください。")
        stored_name = f"{uuid.uuid4()}{source_path.suffix}"
        destination = self.attachments_dir / stored_name
        shutil.copy2(source_path, destination)
        try:
            with self.database.session() as session:
                if session.get(Task, task_id) is None:
                    raise LookupError("タスクが見つかりません。")
                attachment = Attachment(
                    task_id=task_id,
                    original_name=source_path.name[:500],
                    stored_name=stored_name,
                    size_bytes=size,
                )
                session.add(attachment)
                session.commit()
                session.refresh(attachment)
                return attachment
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def remove_attachment(self, attachment_id: str) -> None:
        with self.database.session() as session:
            attachment = session.get(Attachment, attachment_id)
            if attachment is None:
                raise LookupError("添付ファイルが見つかりません。")
            path = self.attachments_dir / attachment.stored_name
            session.delete(attachment)
            session.commit()
        path.unlink(missing_ok=True)

    def attachment_path(self, attachment: Attachment | str) -> Path:
        if isinstance(attachment, str):
            with self.database.session() as session:
                stored = session.get(Attachment, attachment)
                if stored is None:
                    raise LookupError("添付ファイルが見つかりません。")
                stored_name = stored.stored_name
        else:
            stored_name = attachment.stored_name
        return self.attachments_dir / stored_name

    @staticmethod
    def _reminder_json(task: Task) -> dict[str, Any]:
        try:
            value = json.loads(task.reminder_config_json or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def reminder_config_for_task(self, task: Task) -> dict[str, Any] | None:
        if task.reminder_mode == "off":
            return None
        if task.reminder_mode == "custom":
            return self.validate_reminder_config(self._reminder_json(task))
        return self.default_reminder_config(task.priority_enum)

    def reminder_schedule(self, task: Task, now: datetime | None = None) -> list[datetime]:
        if task.due_at is None or task.deleted_at is not None:
            return []
        if task.status_enum not in ACTIVE_STATUSES:
            return []
        config = self.reminder_config_for_task(task)
        if config is None:
            return []
        due = task.due_at.replace(second=0, microsecond=0)
        current_time = (now or local_now()).replace(second=0, microsecond=0)
        if task.due_has_time:
            start = due - timedelta(minutes=config["start_minutes"])
        else:
            start = datetime.combine(due.date(), time(15, 0))

        candidates: set[datetime] = set()

        def add_series(series_start: datetime, interval_minutes: int) -> None:
            if interval_minutes <= 0:
                candidates.add(series_start)
                return
            candidate = series_start
            while candidate <= due and len(candidates) <= 5000:
                candidates.add(candidate)
                candidate += timedelta(minutes=interval_minutes)

        add_series(start, config["interval_minutes"])
        if config["final_window_minutes"] and config["final_interval_minutes"]:
            add_series(
                max(
                    start,
                    due - timedelta(minutes=config["final_window_minutes"]),
                ),
                config["final_interval_minutes"],
            )
        if config["previous_day_17"]:
            candidates.add(datetime.combine(due.date() - timedelta(days=1), time(17, 0)))
        candidates.add(due)

        work_start = config["work_start_hour"]
        work_end = config["work_end_hour"]
        return sorted(
            candidate
            for candidate in candidates
            if candidate >= current_time
            and candidate <= due
            and (
                candidate == due
                or work_start <= candidate.hour <= work_end
            )
        )

    def rebuild_reminders(
        self,
        task_id: str,
        now: datetime | None = None,
        preserve_snoozed: bool = False,
    ) -> int:
        task = self.get_task(task_id)
        with self.database.session() as session:
            pending_events = delete(ReminderEvent).where(
                ReminderEvent.task_id == task_id,
                ReminderEvent.status == "pending",
            )
            if preserve_snoozed:
                pending_events = pending_events.where(ReminderEvent.action.is_(None))
            session.execute(pending_events)
            if task is None:
                session.commit()
                return 0
            schedule = self.reminder_schedule(task, now)
            for scheduled_at in schedule:
                session.add(ReminderEvent(task_id=task_id, scheduled_at=scheduled_at))
            session.commit()
            return len(schedule)

    def rebuild_all_reminders(self, now: datetime | None = None) -> int:
        tasks = self.list_active_tasks()
        return sum(
            self.rebuild_reminders(task.id, now, preserve_snoozed=True)
            for task in tasks
        )

    def claim_due_reminders(self, now: datetime | None = None) -> list[ReminderDelivery]:
        current_time = (now or local_now()).replace(microsecond=0)
        with self.database.session() as session:
            events = list(
                session.scalars(
                    select(ReminderEvent)
                    .join(Task, Task.id == ReminderEvent.task_id)
                    .options(selectinload(ReminderEvent.task))
                    .where(
                        ReminderEvent.status == "pending",
                        ReminderEvent.scheduled_at <= current_time,
                        Task.deleted_at.is_(None),
                        Task.status.in_([status.value for status in ACTIVE_STATUSES]),
                    )
                    .order_by(ReminderEvent.scheduled_at)
                )
            )
            deliveries = [
                ReminderDelivery(
                    event_id=event.id,
                    task_id=event.task_id,
                    title=event.task.title,
                    due_at=event.task.due_at,
                    priority=event.task.priority_enum,
                )
                for event in events
            ]
            for event in events:
                event.status = "delivered"
                event.delivered_at = current_time
            session.commit()
            return deliveries

    def snooze_task(self, task_id: str, minutes: int) -> ReminderEvent:
        if minutes < 1 or minutes > 60 * 24 * 7:
            raise ValueError("再通知は1分～7日後で設定してください。")
        task = self.get_task(task_id)
        if task is None or task.deleted_at is not None or task.status_enum not in ACTIVE_STATUSES:
            raise ValueError("このタスクは再通知できません。")
        with self.database.session() as session:
            event = ReminderEvent(
                task_id=task_id,
                scheduled_at=local_now() + timedelta(minutes=minutes),
                action=f"snoozed_{minutes}",
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

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
                planned_for_date=task.planned_for_date,
                category_id=task.category_id,
                retention_days=task.retention_days,
                reminder_mode=task.reminder_mode,
                reminder_config=self._reminder_json(task),
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
                planned_for_date=task.planned_for_date,
                category_id=task.category_id,
                retention_days=task.retention_days,
                reminder_mode=task.reminder_mode,
                reminder_config=self._reminder_json(task),
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
            session.execute(
                delete(ReminderEvent).where(
                    ReminderEvent.task_id == task_id,
                    ReminderEvent.status == "pending",
                )
            )
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
        self.rebuild_reminders(task_id)
        return self.get_task(task_id)

    def permanently_delete_task(self, task_id: str) -> None:
        with self.database.session() as session:
            task = session.scalar(self._task_query().where(Task.id == task_id))
            if task is None:
                raise LookupError("タスクが見つかりません。")
            if task.deleted_at is None:
                raise ValueError("完全削除はゴミ箱内のタスクだけ実行できます。")
            attachment_paths = [
                self.attachments_dir / attachment.stored_name
                for attachment in task.attachments
            ]
            session.delete(task)
            session.commit()
        for path in attachment_paths:
            path.unlink(missing_ok=True)

    def archive_expired_completed_tasks(self) -> int:
        now = local_now()
        archived = 0
        with self.database.session() as session:
            tasks = list(
                session.scalars(
                    self._task_query().where(
                        Task.deleted_at.is_(None),
                        Task.status.in_(
                            (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value)
                        ),
                        Task.retention_days.is_not(None),
                    )
                )
            )
            for task in tasks:
                terminal_at = task.completed_at or task.cancelled_at
                if terminal_at is None or task.retention_days is None:
                    continue
                if terminal_at + timedelta(days=task.retention_days) > now:
                    continue
                task.deleted_at = now
                task.purge_at = now + timedelta(days=self.TRASH_RETENTION_DAYS)
                task.updated_at = now
                task.version += 1
                session.add(
                    TaskHistory(
                        task_id=task.id,
                        action="retention_expired",
                        after_json=json.dumps(self._snapshot(task), ensure_ascii=False),
                    )
                )
                session.execute(
                    delete(ReminderEvent).where(
                        ReminderEvent.task_id == task.id,
                        ReminderEvent.status == "pending",
                    )
                )
                archived += 1
            session.commit()
        return archived

    def purge_expired_tasks(self) -> int:
        now = local_now()
        attachment_paths: list[Path] = []
        with self.database.session() as session:
            tasks = list(
                session.scalars(
                    self._task_query().where(
                        Task.deleted_at.is_not(None),
                        Task.purge_at.is_not(None),
                        Task.purge_at <= now,
                    )
                )
            )
            for task in tasks:
                attachment_paths.extend(
                    self.attachments_dir / attachment.stored_name
                    for attachment in task.attachments
                )
                session.delete(task)
            session.commit()
        for path in attachment_paths:
            path.unlink(missing_ok=True)
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
            "planned_for_date": (
                task.planned_for_date.isoformat() if task.planned_for_date else None
            ),
            "category_id": task.category_id,
            "recurrence_group_id": task.recurrence_group_id,
            "retention_days": task.retention_days,
            "reminder_mode": task.reminder_mode,
            "reminder_config": TaskService._reminder_json(task),
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
