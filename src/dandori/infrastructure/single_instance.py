from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

VALID_COMMANDS = {"full", "tasks", "add", "tray"}


class SingleInstanceCoordinator(QObject):
    command_received = Signal(str)

    def __init__(self, data_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        identity = str(data_dir.resolve()).casefold().encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()[:16]
        self.server_name = f"dandori-{digest}"
        self.server: QLocalServer | None = None
        self._clients: set[QLocalSocket] = set()

    def notify_existing(self, command: str, timeout_ms: int = 700) -> bool:
        if command not in VALID_COMMANDS:
            raise ValueError(f"Unknown DANDORI command: {command}")
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(timeout_ms):
            socket.abort()
            return False
        if socket.write(command.encode("utf-8")) < 0:
            socket.abort()
            return False
        socket.flush()
        sent = socket.bytesToWrite() == 0 or socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return sent

    def start(self) -> bool:
        QLocalServer.removeServer(self.server_name)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        return self.server.listen(self.server_name)

    def stop(self) -> None:
        for socket in tuple(self._clients):
            socket.abort()
            socket.deleteLater()
        self._clients.clear()
        if self.server is not None:
            self.server.close()
            self.server.deleteLater()
            self.server = None
        QLocalServer.removeServer(self.server_name)

    def _accept_connections(self) -> None:
        if self.server is None:
            return
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            self._clients.add(socket)
            socket.readyRead.connect(lambda current=socket: self._read_command(current))
            socket.disconnected.connect(lambda current=socket: self._discard_client(current))
            if socket.bytesAvailable():
                self._read_command(socket)

    def _read_command(self, socket: QLocalSocket) -> None:
        command = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
        if command in VALID_COMMANDS:
            self.command_received.emit(command)
        socket.disconnectFromServer()

    def _discard_client(self, socket: QLocalSocket) -> None:
        self._clients.discard(socket)
        socket.deleteLater()
