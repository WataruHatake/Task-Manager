from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from dandori.domain.enums import Priority
from dandori.infrastructure.models import Attachment, Subtask, Task
from dandori.services.task_service import SubtaskInput, TaskService


class SubtaskRow(QWidget):
    def __init__(
        self,
        title: str = "",
        completed: bool = False,
        subtask_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.subtask_id = subtask_id
        self.completed = QCheckBox()
        self.completed.setChecked(completed)
        self.title = QLineEdit(title)
        self.title.setPlaceholderText("サブタスク")
        self.remove_button = QPushButton("×")
        self.remove_button.setObjectName("compactButton")
        self.remove_button.setToolTip("サブタスクを削除")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.completed)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.remove_button)

    def input_value(self) -> SubtaskInput:
        return SubtaskInput(
            title=self.title.text(),
            completed=self.completed.isChecked(),
            subtask_id=self.subtask_id,
        )


class SubtaskEditor(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("embeddedEditor")
        self.rows: list[SubtaskRow] = []
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(5)
        add_button = QPushButton("＋ サブタスク")
        add_button.clicked.connect(self.add_row)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(self.rows_layout)
        layout.addWidget(add_button)

    def add_row(
        self,
        title: str = "",
        completed: bool = False,
        subtask_id: str | None = None,
    ) -> SubtaskRow:
        row = SubtaskRow(title, completed, subtask_id, self)
        row.remove_button.clicked.connect(lambda: self.remove_row(row))
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        row.title.setFocus()
        return row

    def remove_row(self, row: SubtaskRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
            row.deleteLater()

    def set_subtasks(self, subtasks: list[Subtask]) -> None:
        for row in self.rows:
            row.deleteLater()
        self.rows.clear()
        for subtask in sorted(subtasks, key=lambda item: item.position):
            self.add_row(subtask.title, subtask.completed, subtask.id)

    def inputs(self) -> list[SubtaskInput]:
        return [row.input_value() for row in self.rows if row.title.text().strip()]

    def state(self) -> tuple[tuple[str | None, str, bool], ...]:
        return tuple(
            (item.subtask_id, item.title.strip(), item.completed)
            for item in self.inputs()
        )


class AttachmentEditor(QFrame):
    def __init__(self, task_service: TaskService, parent=None) -> None:
        super().__init__(parent)
        self.task_service = task_service
        self.task_id: str | None = None
        self.existing: list[Attachment] = []
        self.pending: list[Path] = []
        self.removed_ids: set[str] = set()
        self.setObjectName("embeddedEditor")
        self.items_layout = QVBoxLayout()
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)
        add_button = QPushButton("＋ ファイルを添付")
        add_button.clicked.connect(self._choose_files)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(self.items_layout)
        layout.addWidget(add_button)
        self._render()

    def set_task(self, task: Task | None) -> None:
        self.task_id = task.id if task else None
        self.existing = list(task.attachments) if task else []
        self.pending = []
        self.removed_ids = set()
        self._render()

    def _clear_items(self) -> None:
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render(self) -> None:
        self._clear_items()
        visible_existing = [
            item for item in self.existing if item.id not in self.removed_ids
        ]
        entries: list[tuple[str, Path, str | None]] = [
            (
                item.original_name,
                self.task_service.attachment_path(item),
                item.id,
            )
            for item in visible_existing
        ]
        entries.extend((path.name, path, None) for path in self.pending)
        if not entries:
            label = QLabel("添付ファイルなし")
            label.setObjectName("muted")
            self.items_layout.addWidget(label)
            return
        for name, path, attachment_id in entries:
            row = QWidget()
            name_label = QLabel(name)
            name_label.setWordWrap(True)
            open_button = QPushButton("開く")
            open_button.setObjectName("compactButton")
            open_button.clicked.connect(
                lambda _checked=False, target=path: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(target))
                )
            )
            remove_button = QPushButton("×")
            remove_button.setObjectName("compactButton")
            remove_button.clicked.connect(
                lambda _checked=False, existing_id=attachment_id, target=path: self._remove(
                    existing_id, target
                )
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            row_layout.addWidget(name_label, 1)
            row_layout.addWidget(open_button)
            row_layout.addWidget(remove_button)
            self.items_layout.addWidget(row)

    def _choose_files(self) -> None:
        names, _selected_filter = QFileDialog.getOpenFileNames(
            self, "添付ファイルを選択"
        )
        for name in names:
            path = Path(name)
            if path not in self.pending:
                self.pending.append(path)
        self._render()

    def _remove(self, attachment_id: str | None, path: Path) -> None:
        if attachment_id:
            self.removed_ids.add(attachment_id)
        elif path in self.pending:
            self.pending.remove(path)
        self._render()

    def apply(self, task_ids: list[str]) -> None:
        if self.task_id and self.task_id in task_ids:
            for attachment_id in self.removed_ids:
                self.task_service.remove_attachment(attachment_id)
        for task_id in task_ids:
            for path in self.pending:
                self.task_service.add_attachment(task_id, path)

    def state(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return (
            tuple(item.id for item in self.existing),
            tuple(sorted(self.removed_ids)),
            tuple(str(path) for path in self.pending),
        )


class DurationInput(QWidget):
    def __init__(
        self,
        maximum_minutes: int,
        suffix: str,
        zero_text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.maximum_minutes = maximum_minutes
        self.suffix = suffix
        self.zero_text = zero_text
        self._updating = False

        self.days = QSpinBox()
        self.hours = QSpinBox()
        self.minutes_part = QSpinBox()
        self.days.setRange(0, max(1, maximum_minutes // (24 * 60)))
        self.hours.setRange(0, 23)
        self.minutes_part.setRange(0, 59)
        for spin in (self.days, self.hours, self.minutes_part):
            spin.setMinimumWidth(36)
            spin.valueChanged.connect(self._value_changed)

        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(4)
        layout.setVerticalSpacing(2)
        for column, (label, spin) in enumerate(
            (("日", self.days), ("時間", self.hours), ("分", self.minutes_part))
        ):
            heading = QLabel(label)
            heading.setObjectName("muted")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(heading, 0, column)
            layout.addWidget(spin, 1, column)
            layout.setColumnStretch(column, 1)
        layout.addWidget(self.summary, 2, 0, 1, 3)
        self.set_minutes(0)

    def set_minutes(self, value: int) -> None:
        total = max(0, min(int(value), self.maximum_minutes))
        days, remaining = divmod(total, 24 * 60)
        hours, minutes = divmod(remaining, 60)
        self._updating = True
        self.days.setValue(days)
        self.hours.setValue(hours)
        self.minutes_part.setValue(minutes)
        self._updating = False
        self._update_summary()

    def minutes(self) -> int:
        return min(
            self.maximum_minutes,
            self.days.value() * 24 * 60
            + self.hours.value() * 60
            + self.minutes_part.value(),
        )

    def _value_changed(self) -> None:
        if self._updating:
            return
        raw_total = (
            self.days.value() * 24 * 60
            + self.hours.value() * 60
            + self.minutes_part.value()
        )
        if raw_total > self.maximum_minutes:
            self.set_minutes(self.maximum_minutes)
            return
        self._update_summary()

    def _update_summary(self) -> None:
        total = self.minutes()
        if total == 0:
            self.summary.setText(self.zero_text)
            return
        days, remaining = divmod(total, 24 * 60)
        hours, minutes = divmod(remaining, 60)
        parts = []
        if days:
            parts.append(f"{days}日")
        if hours:
            parts.append(f"{hours}時間")
        if minutes:
            parts.append(f"{minutes}分")
        self.summary.setText(f"{' '.join(parts)}{self.suffix}")


class ReminderControls(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("embeddedEditor")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("標準（重要度に連動）", "priority")
        self.mode_combo.addItem("個別設定", "custom")
        self.mode_combo.addItem("通知しない", "off")

        self.start_duration = DurationInput(43200, "前", "1分以上を指定")
        self.interval_duration = DurationInput(10080, "ごと", "1回のみ")
        self.final_window_duration = DurationInput(10080, "前から", "使用しない")
        self.final_interval_duration = DurationInput(1440, "ごと", "使用しない")
        self.previous_day = QCheckBox("前日の17時にも通知")
        self.work_start = self._spin(0, 23, " 時")
        self.work_end = self._spin(0, 23, " 時")

        self.custom_widget = QWidget()
        custom_layout = QVBoxLayout(self.custom_widget)
        custom_layout.setContentsMargins(0, 4, 0, 0)
        custom_layout.setSpacing(5)
        for label_text, widget in (
            ("通知開始", self.start_duration),
            ("通知間隔", self.interval_duration),
            ("期限直前", self.final_window_duration),
            ("直前間隔", self.final_interval_duration),
            ("通知開始時刻", self.work_start),
            ("通知終了時刻", self.work_end),
        ):
            field_label = QLabel(label_text)
            field_label.setObjectName("fieldLabel")
            custom_layout.addWidget(field_label)
            custom_layout.addWidget(widget)
        custom_layout.addWidget(self.previous_day)

        hint = QLabel(
            "日付だけの期限は当日15時から通知します。標準設定は重要度が高いほど通知間隔が短くなります。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.mode_combo)
        layout.addWidget(hint)
        layout.addWidget(self.custom_widget)
        self.mode_combo.currentIndexChanged.connect(self._sync_visibility)
        self.set_values("priority", {})

    @staticmethod
    def _spin(minimum: int, maximum: int, suffix: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        return spin

    def set_values(
        self,
        mode: str,
        config: dict[str, object] | None,
        priority: Priority = Priority.NORMAL,
    ) -> None:
        index = self.mode_combo.findData(mode)
        self.mode_combo.setCurrentIndex(max(0, index))
        values = TaskService.default_reminder_config(priority)
        values.update(config or {})
        self.start_duration.set_minutes(int(values["start_minutes"]))
        self.interval_duration.set_minutes(int(values["interval_minutes"]))
        self.final_window_duration.set_minutes(int(values["final_window_minutes"]))
        self.final_interval_duration.set_minutes(
            int(values["final_interval_minutes"])
        )
        self.previous_day.setChecked(bool(values["previous_day_17"]))
        self.work_start.setValue(int(values["work_start_hour"]))
        self.work_end.setValue(int(values["work_end_hour"]))
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        self.custom_widget.setVisible(self.mode() == "custom")

    def mode(self) -> str:
        return str(self.mode_combo.currentData())

    def config(self) -> dict[str, object]:
        return {
            "start_minutes": self.start_duration.minutes(),
            "interval_minutes": self.interval_duration.minutes(),
            "final_window_minutes": self.final_window_duration.minutes(),
            "final_interval_minutes": self.final_interval_duration.minutes(),
            "previous_day_17": self.previous_day.isChecked(),
            "work_start_hour": self.work_start.value(),
            "work_end_hour": self.work_end.value(),
        }

    def state(self) -> tuple[str, tuple[tuple[str, object], ...]]:
        return self.mode(), tuple(sorted(self.config().items()))


class RetentionControls(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.days = QSpinBox()
        self.days.setRange(1, 3650)
        self.days.setValue(365)
        self.days.setSuffix(" 日")
        self.unlimited = QCheckBox("無期限")
        self.unlimited.toggled.connect(lambda checked: self.days.setEnabled(not checked))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.days, 1)
        layout.addWidget(self.unlimited)

    def set_value(self, value: int | None) -> None:
        self.unlimited.setChecked(value is None)
        if value is not None:
            self.days.setValue(value)

    def value(self) -> int | None:
        return None if self.unlimited.isChecked() else self.days.value()

    def state(self) -> tuple[int, bool]:
        return self.days.value(), self.unlimited.isChecked()
