from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal


class GlobalHotkeyService(QObject):
    add_requested = Signal()
    tasks_requested = Signal()
    registration_failed = Signal(str)

    HOTKEY_ADD_ID = 0xD101
    HOTKEY_TASKS_ID = 0xD102

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._registered_count = 0

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._thread is not None and self._thread.is_alive():
            return self._registered_count > 0
        self._ready.clear()
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)
        return self._registered_count > 0

    def stop(self) -> None:
        if sys.platform != "win32" or self._thread_id is None:
            return
        import ctypes

        ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._thread = None
        self._thread_id = None
        self._registered_count = 0

    def _message_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        modifiers = 0x0001 | 0x0002 | 0x4000  # ALT | CONTROL | NOREPEAT
        registrations = (
            (self.HOTKEY_ADD_ID, ord("N"), "Ctrl + Alt + N"),
            (self.HOTKEY_TASKS_ID, ord("T"), "Ctrl + Alt + T"),
        )
        registered_ids: list[int] = []
        for hotkey_id, virtual_key, label in registrations:
            if user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key):
                registered_ids.append(hotkey_id)
            else:
                self.registration_failed.emit(label)

        self._registered_count = len(registered_ids)
        self._ready.set()

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message != 0x0312:  # WM_HOTKEY
                continue
            if message.wParam == self.HOTKEY_ADD_ID:
                self.add_requested.emit()
            elif message.wParam == self.HOTKEY_TASKS_ID:
                self.tasks_requested.emit()

        for hotkey_id in registered_ids:
            user32.UnregisterHotKey(None, hotkey_id)
