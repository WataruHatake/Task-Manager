from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from dandori.infrastructure.config import AppPaths
from dandori.infrastructure.database import Database
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
    def __init__(self, application: QApplication, paths: AppPaths) -> None:
        self.application = application
        load_bundled_fonts()
        self.paths = paths
        self.paths.ensure_directories()
        self.database = Database(paths.database_file)
        self.database.initialize()
        self.task_service = TaskService(self.database)
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
        self.edge_add.task_created.connect(self._task_created)
        self._setup_tray(icon)

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
        self.main_window.refresh()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def show_edge_tasks(self) -> None:
        self.edge_tasks.show_at_screen_edge()

    def show_edge_add(self) -> None:
        self.edge_add.show_at_screen_edge()

    def _task_created(self, task_id: str) -> None:
        self.main_window.refresh(task_id)
        self.edge_tasks.refresh()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_edge_tasks()

    def quit(self) -> None:
        self.main_window.hide_to_tray = False
        self.tray_icon.hide() if self.tray_icon else None
        self.database.dispose()
        self.application.quit()


def run(application: QApplication, data_dir: Path, start_in_tray: bool = False) -> int:
    paths = AppPaths.from_data_dir(data_dir)
    try:
        runtime = DandoriRuntime(application, paths)
    except (OSError, RuntimeError) as error:
        QMessageBox.critical(None, "DANDORIを起動できません", str(error))
        return 1
    apply_theme(application, "dark")
    if not start_in_tray:
        runtime.show_main()
    return application.exec()
