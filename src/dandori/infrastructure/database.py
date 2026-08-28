from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from dandori.infrastructure.migration import upgrade_database
from dandori.infrastructure.models import Category


class Database:
    def __init__(self, database_file: Path) -> None:
        database_file.parent.mkdir(parents=True, exist_ok=True)
        self.database_file = database_file
        self.engine = create_engine(
            f"sqlite:///{database_file.as_posix()}",
            connect_args={"timeout": 5},
        )
        self._configure_sqlite(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    def initialize(self) -> None:
        with self.engine.begin() as connection:
            upgrade_database(connection)
        with self.session() as session:
            existing = session.scalar(select(Category).where(Category.name == "未分類"))
            if existing is None:
                session.add(Category(name="未分類", color="#8E8E93"))
                session.commit()
            elif existing.color.upper() == "#86BC25":
                existing.color = "#8E8E93"
                session.commit()

    def session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()
