from __future__ import annotations

import uuid

import pytest

from dandori.infrastructure.single_instance import SingleInstanceCoordinator


def test_single_instance_forwards_commands(qtbot, tmp_path):
    data_dir = tmp_path / str(uuid.uuid4())
    primary = SingleInstanceCoordinator(data_dir)
    secondary = SingleInstanceCoordinator(data_dir)
    commands: list[str] = []
    primary.command_received.connect(commands.append)

    if not primary.start():
        error = primary.server.errorString() if primary.server is not None else "unknown"
        pytest.skip(f"Local sockets are unavailable in this environment: {error}")
    try:
        assert secondary.notify_existing("add")
        qtbot.waitUntil(lambda: commands == ["add"], timeout=2000)
    finally:
        primary.stop()


def test_single_instance_rejects_unknown_command(tmp_path):
    coordinator = SingleInstanceCoordinator(tmp_path)

    with pytest.raises(ValueError, match="Unknown"):
        coordinator.notify_existing("unknown")
