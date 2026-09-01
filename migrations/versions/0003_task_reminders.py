"""Add per-task reminder settings.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _task_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("tasks")}


def upgrade() -> None:
    columns = _task_columns()
    with op.batch_alter_table("tasks") as batch:
        if "reminder_mode" not in columns:
            batch.add_column(
                sa.Column(
                    "reminder_mode",
                    sa.String(length=20),
                    nullable=False,
                    server_default="priority",
                )
            )
        if "reminder_config_json" not in columns:
            batch.add_column(
                sa.Column(
                    "reminder_config_json",
                    sa.Text(),
                    nullable=False,
                    server_default="{}",
                )
            )


def downgrade() -> None:
    columns = _task_columns()
    with op.batch_alter_table("tasks") as batch:
        if "reminder_config_json" in columns:
            batch.drop_column("reminder_config_json")
        if "reminder_mode" in columns:
            batch.drop_column("reminder_mode")
