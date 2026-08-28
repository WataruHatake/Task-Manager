from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def upgrade_database(connection: Connection) -> None:
    root = project_root()
    configuration = Config(str(root / "alembic.ini"))
    configuration.set_main_option("script_location", str(root / "migrations"))
    configuration.attributes["connection"] = connection
    command.upgrade(configuration, "head")
