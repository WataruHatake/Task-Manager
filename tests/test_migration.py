from __future__ import annotations

import sqlite3

from sqlalchemy import inspect, text

from dandori.infrastructure.database import Database


def test_existing_database_is_upgraded_with_progress_fields(tmp_path):
    database_file = tmp_path / "existing.db"
    connection = sqlite3.connect(database_file)
    connection.executescript(
        """
        CREATE TABLE alembic_version (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        );
        INSERT INTO alembic_version (version_num) VALUES ('0001');

        CREATE TABLE categories (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            name VARCHAR(80) NOT NULL UNIQUE,
            color VARCHAR(9) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        INSERT INTO categories VALUES (
            'category-1', '未分類', '#8E8E93',
            '2026-01-01 09:00:00', '2026-01-01 09:00:00'
        );

        CREATE TABLE tasks (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            title VARCHAR(300) NOT NULL,
            memo TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            priority INTEGER NOT NULL,
            due_at DATETIME,
            due_has_time BOOLEAN NOT NULL,
            category_id VARCHAR(36) NOT NULL,
            recurrence_group_id VARCHAR(36),
            retention_days INTEGER,
            completed_at DATETIME,
            cancelled_at DATETIME,
            deleted_at DATETIME,
            purge_at DATETIME,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            version INTEGER NOT NULL,
            FOREIGN KEY(category_id) REFERENCES categories (id)
        );
        INSERT INTO tasks VALUES (
            'task-1', '既存タスク', '既存メモ', 'todo', 3,
            NULL, 0, 'category-1', NULL, 365,
            NULL, NULL, NULL, NULL,
            '2026-01-01 09:00:00', '2026-01-01 09:00:00', 1
        );
        """
    )
    connection.commit()
    connection.close()

    database = Database(database_file)
    database.initialize()

    columns = {column["name"] for column in inspect(database.engine).get_columns("tasks")}
    with database.engine.connect() as migrated:
        row = migrated.execute(
            text(
                "SELECT progress_note, progress_percent "
                "FROM tasks WHERE id = 'task-1'"
            )
        ).one()
        reminder_values = migrated.execute(
            text(
                "SELECT reminder_mode, reminder_config_json "
                "FROM tasks WHERE id = 'task-1'"
            )
        ).one()
        planned_for_date = migrated.execute(
            text("SELECT planned_for_date FROM tasks WHERE id = 'task-1'")
        ).scalar_one_or_none()
        revision = migrated.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert {"progress_note", "progress_percent"} <= columns
    assert {"reminder_mode", "reminder_config_json"} <= columns
    assert "planned_for_date" in columns
    assert row == ("", 0)
    assert reminder_values == ("priority", "{}")
    assert planned_for_date is None
    assert revision == "0004"
    database.dispose()
