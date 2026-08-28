from __future__ import annotations

from enum import Enum, IntEnum


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return {
            self.TODO: "未着手",
            self.IN_PROGRESS: "進行中",
            self.ON_HOLD: "保留",
            self.COMPLETED: "完了",
            self.CANCELLED: "取り消し",
        }[self]

    @classmethod
    def from_label(cls, label: str) -> TaskStatus:
        for status in cls:
            if status.label == label:
                return status
        raise ValueError(f"未知の状態です: {label}")


class Priority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

    @property
    def label(self) -> str:
        return {
            self.LOW: "低",
            self.NORMAL: "通常",
            self.HIGH: "高",
            self.URGENT: "最優先",
            self.CRITICAL: "超最優先",
        }[self]

    @classmethod
    def from_label(cls, label: str) -> Priority:
        for priority in cls:
            if priority.label == label:
                return priority
        raise ValueError(f"未知の重要度です: {label}")


ACTIVE_STATUSES = (
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.ON_HOLD,
)
