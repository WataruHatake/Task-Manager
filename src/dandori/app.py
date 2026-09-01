from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from dandori.infrastructure.config import AppPaths
from dandori.infrastructure.database import Database
from dandori.infrastructure.hotkeys import GlobalHotkeyService
from dandori.infrastructure.single_instance import SingleInstanceCoordinator
from dandori.services.task_service import TaskService
from dandori.ui.edge_windows import EdgeAddWindow, EdgeTaskWindow
from dandori.ui.main_window import MainWindow
from dandori.ui.theme import (
    apply_theme,
    get_palette,
    load_bundled_fonts,
    normalize_appearance,
    theme_accent_colors,
)
from dandori.ui.theme_dialog import ThemeDialog


def make_app_icon(accent: str, foreground: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(accent))
    painter.drawRoundedRect(10, 10, 44, 44, 12, 12)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(foreground), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(21, 32, 29, 40)
    painter.drawLine(29, 40, 44, 23)
    painter.end()
    return QIcon(pixmap)


class DandoriRuntime(QObject):
    def __init__(
        self,
        application: QApplication,
        paths: AppPaths,
        single_instance: SingleInstanceCoordinator,
    ) -> None:
        super().__init__(application)
        self.application = application
        load_bundled_fonts()
        self.paths = paths
        self.paths.ensure_directories()
        self.database = Database(paths.database_file)
        self.database.initialize()
        self.task_service = TaskService(self.database)
        self.task_service.archive_expired_completed_tasks()
        self.task_service.purge_expired_tasks()
        self.task_service.rebuild_all_reminders()
        self.single_instance = single_instance
        theme_setting = self.task_service.get_setting("theme", {})
        if not isinstance(theme_setting, dict):
            theme_setting = {}
        self.palette_key = get_palette(str(theme_setting.get("palette", "default"))).key
        self.appearance = normalize_appearance(str(theme_setting.get("appearance", "dark")))
        apply_theme(self.application, self.palette_key, self.appearance)
        self.main_window = MainWindow(self.task_service)
        self.edge_tasks = EdgeTaskWindow(self.task_service)
        self.edge_add = EdgeAddWindow(self.task_service)
        self.tray_icon: QSystemTrayIcon | None = None
        self.tray_add_action: QAction | None = None
        self.last_reminder_task_id: str | None = None
        self.snooze_actions: list[QAction] = []
        self.complete_reminder_action: QAction | None = None

        icon = self._update_icons()

        self.main_window.edge_tasks_requested.connect(self.show_edge_tasks)
        self.main_window.edge_add_requested.connect(self.show_edge_add)
        self.main_window.theme_requested.connect(self.show_theme_settings)
        self.main_window.hidden_to_tray.connect(self._show_tray_hint)
        self.edge_tasks.tasks_changed.connect(self.main_window.refresh)
        self.edge_tasks.open_main_requested.connect(self.show_main)
        self.edge_tasks.open_add_requested.connect(self.show_edge_add)
        self.edge_add.task_created.connect(self._task_created)
        self.edge_add.open_main_requested.connect(self.show_main)
        self.edge_add.open_tasks_requested.connect(self.show_edge_tasks)
        self._setup_tray(icon)
        self.hotkeys = GlobalHotkeyService(self.application)
        self.hotkeys.add_requested.connect(self.toggle_edge_add)
        self.hotkeys.tasks_requested.connect(self.toggle_edge_tasks)
        self.hotkeys.fallback_registered.connect(self._show_hotkey_fallback)
        self.hotkeys.registration_failed.connect(self._show_hotkey_warning)
        self.hotkeys.start()
        self.single_instance.command_received.connect(self.handle_command)
        self.trash_purge_timer = QTimer(self)
        self.trash_purge_timer.setInterval(60 * 60 * 1000)
        self.trash_purge_timer.timeout.connect(self._purge_expired_trash)
        self.trash_purge_timer.start()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30 * 1000)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start()
        self._check_reminders()

    def _update_icons(self) -> QIcon:
        accent, foreground = theme_accent_colors(self.palette_key, self.appearance)
        icon = make_app_icon(accent, foreground)
        self.application.setWindowIcon(icon)
        self.main_window.setWindowIcon(icon)
        self.edge_tasks.setWindowIcon(icon)
        self.edge_add.setWindowIcon(icon)
        if self.tray_icon is not None:
            self.tray_icon.setIcon(icon)
        return icon

    def _setup_tray(self, icon: QIcon) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.application.setQuitOnLastWindowClosed(True)
            return
        self.tray_icon = QSystemTrayIcon(icon, self.application)
        self.tray_icon.setToolTip("タスク管理")
        menu = QMenu()
        menu.addAction("全表示", self.show_main)
        self.tray_add_action = menu.addAction(
            "タスク追加    Ctrl+Alt+N", self.show_edge_add
        )
        menu.addAction("タスク表示    Ctrl+Alt+T", self.show_edge_tasks)
        menu.addAction("カラーテーマ", self.show_theme_settings)
        notification_menu = menu.addMenu("通知表示時間")
        timeout_group = QActionGroup(notification_menu)
        timeout_group.setExclusive(True)
        current_timeout = int(
            self.task_service.get_setting("notification_timeout_seconds", 15)
        )
        for seconds, label in ((5, "5秒"), (15, "15秒"), (30, "30秒"), (60, "60秒")):
            action = notification_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(seconds == current_timeout)
            action.triggered.connect(
                lambda _checked=False, value=seconds: self.task_service.set_setting(
                    "notification_timeout_seconds", value
                )
            )
            timeout_group.addAction(action)
        menu.addSeparator()
        snooze_10 = menu.addAction("最後の通知を10分後に再通知")
        snooze_10.triggered.connect(lambda: self._snooze_last_reminder(10))
        snooze_60 = menu.addAction("最後の通知を1時間後に再通知")
        snooze_60.triggered.connect(lambda: self._snooze_last_reminder(60))
        self.snooze_actions = [snooze_10, snooze_60]
        self.complete_reminder_action = menu.addAction("最後に通知したタスクを完了")
        self.complete_reminder_action.triggered.connect(self._complete_last_reminder)
        for action in (*self.snooze_actions, self.complete_reminder_action):
            action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("完全終了", self.quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.messageClicked.connect(self._notification_clicked)
        self.tray_icon.show()
        self.main_window.hide_to_tray = True

    def show_theme_settings(self) -> None:
        parent = self.main_window
        if self.edge_tasks.isVisible():
            parent = self.edge_tasks
        elif self.edge_add.isVisible():
            parent = self.edge_add
        dialog = ThemeDialog(self.palette_key, self.appearance, parent)
        dialog.theme_selected.connect(self._apply_theme_selection)
        dialog.exec()

    def _apply_theme_selection(self, palette_key: str, appearance: str) -> None:
        self.palette_key = get_palette(palette_key).key
        self.appearance = normalize_appearance(appearance)
        self.task_service.set_setting(
            "theme", {"palette": self.palette_key, "appearance": self.appearance}
        )
        apply_theme(self.application, self.palette_key, self.appearance)
        self._update_icons()

    def show_main(self, task_id: str | None = None) -> None:
        self.edge_tasks.hide()
        self.edge_add.hide()
        if task_id:
            self.main_window.show_task(task_id)
        else:
            self.main_window.refresh()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def show_edge_tasks(self) -> None:
        self.edge_add.hide()
        self.edge_tasks.show_at_screen_edge()

    def show_edge_add(self) -> None:
        self.edge_tasks.hide()
        self.edge_add.show_at_screen_edge()

    def toggle_edge_tasks(self) -> None:
        if self.edge_tasks.isVisible():
            self.edge_tasks.hide()
        else:
            self.show_edge_tasks()

    def toggle_edge_add(self) -> None:
        if self.edge_add.isVisible():
            self.edge_add.hide()
        else:
            self.show_edge_add()

    @Slot(str)
    def handle_command(self, command: str) -> None:
        if command == "full":
            self.show_main()
        elif command == "tasks":
            self.show_edge_tasks()
        elif command == "add":
            self.show_edge_add()

    def _task_created(self, task_id: str) -> None:
        self.main_window.refresh(task_id)
        self.edge_tasks.refresh()

    def _purge_expired_trash(self) -> None:
        changed = self.task_service.archive_expired_completed_tasks()
        changed += self.task_service.purge_expired_tasks()
        if changed:
            self.main_window.refresh()
            self.edge_tasks.refresh()

    def _check_reminders(self) -> None:
        if self.tray_icon is None:
            return
        for reminder in self.task_service.claim_due_reminders():
            self.last_reminder_task_id = reminder.task_id
            for action in (*self.snooze_actions, self.complete_reminder_action):
                action.setEnabled(True)
            due_text = (
                reminder.due_at.strftime("%Y/%m/%d %H:%M")
                if reminder.due_at
                else "期限なし"
            )
            timeout = int(
                self.task_service.get_setting("notification_timeout_seconds", 15)
            )
            self.tray_icon.showMessage(
                f"{reminder.priority.label} · タスクの期限が近づいています",
                f"{reminder.title}\n期限 {due_text}\nクリックすると詳細を開きます。",
                QSystemTrayIcon.MessageIcon.Information,
                timeout * 1000,
            )

    def _notification_clicked(self) -> None:
        if self.last_reminder_task_id:
            self.show_main(self.last_reminder_task_id)

    def _snooze_last_reminder(self, minutes: int) -> None:
        if not self.last_reminder_task_id:
            return
        try:
            self.task_service.snooze_task(self.last_reminder_task_id, minutes)
        except ValueError as error:
            QMessageBox.warning(None, "再通知できません", str(error))

    def _complete_last_reminder(self) -> None:
        if not self.last_reminder_task_id:
            return
        try:
            self.task_service.complete_task(self.last_reminder_task_id)
        except (ValueError, LookupError):
            return
        self.main_window.refresh()
        self.edge_tasks.refresh()
        self.last_reminder_task_id = None
        for action in (*self.snooze_actions, self.complete_reminder_action):
            action.setEnabled(False)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_main()

    @Slot(str, str)
    def _show_hotkey_fallback(self, unavailable: str, fallback: str) -> None:
        if self.tray_add_action is not None:
            self.tray_add_action.setText(
                f"タスク追加    {fallback.replace(' ', '')}"
            )
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                "タスク追加のショートカットを変更しました",
                f"{unavailable} は他のアプリが使用しています。代わりに {fallback} を使用できます。",
                QSystemTrayIcon.MessageIcon.Information,
                7000,
            )

    @Slot(str)
    def _show_hotkey_warning(self, shortcut: str) -> None:
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                "タスク管理",
                f"{shortcut} を登録できませんでした。他のアプリで使用されている可能性があります。",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    def _show_tray_hint(self) -> None:
        if self.tray_icon is None or self.task_service.get_setting(
            "tray_hint_shown", False
        ):
            return
        self.tray_icon.showMessage(
            "通知領域で実行中",
            "画面を閉じてもタスク管理は終了していません。チェックアイコンから再表示できます。",
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )
        self.task_service.set_setting("tray_hint_shown", True)

    def quit(self) -> None:
        self.main_window.hide_to_tray = False
        self.hotkeys.stop()
        self.reminder_timer.stop()
        self.trash_purge_timer.stop()
        self.single_instance.stop()
        self.tray_icon.hide() if self.tray_icon else None
        self.database.dispose()
        self.application.quit()


def run(application: QApplication, data_dir: Path, start_mode: str = "full") -> int:
    paths = AppPaths.from_data_dir(data_dir)
    single_instance = SingleInstanceCoordinator(paths.data_dir, application)
    if single_instance.notify_existing(start_mode):
        return 0
    single_instance.start()
    try:
        runtime = DandoriRuntime(application, paths, single_instance)
    except (OSError, RuntimeError) as error:
        single_instance.stop()
        QMessageBox.critical(None, "起動できません", str(error))
        return 1
    runtime.handle_command(start_mode)
    return application.exec()
