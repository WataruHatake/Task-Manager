from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dandori.domain.enums import Priority, TaskStatus


def new_id() -> str:
    return str(uuid.uuid4())


def local_now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#8E8E93")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=local_now, onupdate=local_now
    )

    tasks: Mapped[list[Task]] = relationship(back_populates="category")


class RecurrenceGroup(Base):
    __tablename__ = "recurrence_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    weekdays_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    include_holidays: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)

    tasks: Mapped[list[Task]] = relationship(back_populates="recurrence_group")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_active_due", "deleted_at", "status", "due_at"),
        Index("ix_tasks_category", "category_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=TaskStatus.TODO.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=int(Priority.NORMAL))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_has_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    recurrence_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("recurrence_groups.id"), nullable=True
    )
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=365)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=local_now, onupdate=local_now
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    category: Mapped[Category] = relationship(back_populates="tasks")
    recurrence_group: Mapped[RecurrenceGroup | None] = relationship(back_populates="tasks")
    subtasks: Mapped[list[Subtask]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(secondary="task_tags", back_populates="tasks")
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    history: Mapped[list[TaskHistory]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def status_enum(self) -> TaskStatus:
        return TaskStatus(self.status)

    @property
    def priority_enum(self) -> Priority:
        return Priority(self.priority)


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=TaskStatus.TODO.value)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=int(Priority.NORMAL))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=local_now, onupdate=local_now
    )

    task: Mapped[Task] = relationship(back_populates="subtasks")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)

    tasks: Mapped[list[Task]] = relationship(secondary="task_tags", back_populates="tags")


class TaskTag(Base):
    __tablename__ = "task_tags"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)

    task: Mapped[Task] = relationship(back_populates="attachments")


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)

    task: Mapped[Task] = relationship(back_populates="history")


class ReminderProfile(Base):
    __tablename__ = "reminder_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=local_now, onupdate=local_now
    )

    rules: Mapped[list[ReminderRule]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ReminderRule(Base):
    __tablename__ = "reminder_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("reminder_profiles.id"), nullable=False, index=True
    )
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile: Mapped[ReminderProfile] = relationship(back_populates="rules")


class ReminderEvent(Base):
    __tablename__ = "reminder_events"
    __table_args__ = (Index("ix_reminder_events_due", "status", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=local_now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=local_now, onupdate=local_now
    )
