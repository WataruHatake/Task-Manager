from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from dandori.infrastructure.config import AppPaths
from dandori.infrastructure.database import Database
from dandori.infrastructure.hotkeys import GlobalHotkeyService
from dandori.infrastructure.single_instance import SingleInstanceCoordinator
from dandori.services.task_service import TaskService
from dandori.ui.edge_windows import EdgeAddWindow, EdgeTaskWindow
from dandori.ui.main_window import MainWindow
from dandori.ui.theme import apply_theme, load_bundled_fonts


def make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#101310"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#86BC25"))
    painter.drawRoundedRect(14, 14, 36, 36, 9, 9)
    painter.setPen(QColor("#101310"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(23)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
    painter.end()
    return QIcon(pixmap)


class DandoriRuntime:
    def __init__(
        self,
        application: QApplication,
        paths: AppPaths,
        single_instance: SingleInstanceCoordinator,
    ) -> None:
        self.application = application
        load_bundled_fonts()
        self.paths = paths
        self.paths.ensure_directories()
        self.database = Database(paths.database_file)
        self.database.initialize()
        self.task_service = TaskService(self.database)
        self.single_instance = single_instance
        self.main_window = MainWindow(self.task_service)
        self.edge_tasks = EdgeTaskWindow(self.task_service)
        self.edge_add = EdgeAddWindow(self.task_service)
        self.tray_icon: QSystemTrayIcon | None = None

        icon = make_app_icon()
        self.application.setWindowIcon(icon)
        self.main_window.setWindowIcon(icon)
        self.edge_tasks.setWindowIcon(icon)
        self.edge_add.setWindowIcon(icon)

        self.main_window.edge_tasks_requested.connect(self.show_edge_tasks)
        self.main_window.edge_add_requested.connect(self.show_edge_add)
        self.main_window.theme_requested.connect(self.apply_theme)
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
        self.hotkeys.registration_failed.connect(self._show_hotkey_warning)
        self.hotkeys.start()

    def _setup_tray(self, icon: QIcon) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.application.setQuitOnLastWindowClosed(True)
            return
        self.tray_icon = QSystemTrayIcon(icon, self.application)
        self.tray_icon.setToolTip("DANDORI")
        menu = QMenu()
        menu.addAction("全表示", self.show_main)
        menu.addAction("タスク追加", self.show_edge_add)
        menu.addAction("タスク表示", self.show_edge_tasks)
        menu.addSeparator()
        menu.addAction("完全終了", self.quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()
        self.main_window.hide_to_tray = True

    def apply_theme(self, theme: str) -> None:
        apply_theme(self.application, theme)

    def show_main(self) -> None:
        self.edge_tasks.hide()
        self.edge_add.hide()
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

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_edge_tasks()

    def _show_hotkey_warning(self, shortcut: str) -> None:
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                "DANDORI",
                f"{shortcut} を登録できませんでした。他のアプリで使用されている可能性があります。",
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )

    def quit(self) -> None:
        self.main_window.hide_to_tray = False
        self.hotkeys.stop()
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
        QMessageBox.critical(None, "DANDORIを起動できません", str(error))
        return 1
    apply_theme(application, "dark")
    runtime.handle_command(start_mode)
    return application.exec()
