from __future__ import annotations

import os

import pytest

from dandori.infrastructure.database import Database
from dandori.services.task_service import TaskService

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def database(tmp_path):
    database = Database(tmp_path / "tasks.db")
    database.initialize()
    yield database
    database.dispose()


@pytest.fixture
def task_service(database):
    return TaskService(database)
