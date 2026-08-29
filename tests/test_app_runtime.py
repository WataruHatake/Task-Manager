from __future__ import annotations

import ctypes
from types import SimpleNamespace

from PySide6.QtWidgets import QSystemTrayIcon

from dandori.app import DandoriRuntime
from dandori.infrastructure.config import AppPaths
from dandori.infrastructure.hotkeys import GlobalHotkeyService
from dandori.infrastructure.single_instance import SingleInstanceCoordinator


def test_runtime_routes_shortcut_and_tray_click_to_main(qtbot, qapp, tmp_path):
    paths = AppPaths.from_data_dir(tmp_path / "data")
    coordinator = SingleInstanceCoordinator(paths.data_dir, qapp)
    runtime = DandoriRuntime(qapp, paths, coordinator)
    qtbot.addWidget(runtime.main_window)
    qtbot.addWidget(runtime.edge_tasks)
    qtbot.addWidget(runtime.edge_add)

    runtime.show_edge_tasks()
    coordinator.command_received.emit("full")

    assert runtime.main_window.isVisible()
    assert not runtime.edge_tasks.isVisible()

    runtime.main_window.hide()
    runtime._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)

    assert runtime.main_window.isVisible()
    assert runtime.trash_purge_timer.isActive()
    runtime.trash_purge_timer.stop()
    runtime.hotkeys.stop()
    runtime.database.dispose()


def test_add_hotkey_uses_fallback_when_primary_is_unavailable(monkeypatch, qapp):
    class FakeUser32:
        def RegisterHotKey(self, _window, _hotkey_id, _modifiers, virtual_key):
            return virtual_key in (ord("A"), ord("T"))

        def GetMessageW(self, _message, _window, _minimum, _maximum):
            return 0

        def UnregisterHotKey(self, _window, _hotkey_id):
            return True

    fake_user32 = FakeUser32()
    fake_kernel32 = SimpleNamespace(GetCurrentThreadId=lambda: 123)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32, kernel32=fake_kernel32),
        raising=False,
    )
    service = GlobalHotkeyService(qapp)
    fallbacks: list[tuple[str, str]] = []
    service.fallback_registered.connect(
        lambda primary, fallback: fallbacks.append((primary, fallback))
    )

    service._message_loop()

    assert service._registered_count == 2
    assert fallbacks == [("Ctrl + Alt + N", "Ctrl + Alt + A")]
