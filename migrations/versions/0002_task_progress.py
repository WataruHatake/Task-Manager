"""Add current progress details to tasks.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _task_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("tasks")}


def upgrade() -> None:
    columns = _task_columns()
    with op.batch_alter_table("tasks") as batch:
        if "progress_note" not in columns:
            batch.add_column(
                sa.Column(
                    "progress_note",
                    sa.Text(),
                    nullable=False,
                    server_default="",
                )
            )
        if "progress_percent" not in columns:
            batch.add_column(
                sa.Column(
                    "progress_percent",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )


def downgrade() -> None:
    columns = _task_columns()
    with op.batch_alter_table("tasks") as batch:
        if "progress_percent" in columns:
            batch.drop_column("progress_percent")
        if "progress_note" in columns:
            batch.drop_column("progress_note")
