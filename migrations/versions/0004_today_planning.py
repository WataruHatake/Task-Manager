"""Add a separate date for the Today work list.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _task_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("tasks")}


def upgrade() -> None:
    if "planned_for_date" not in _task_columns():
        with op.batch_alter_table("tasks") as batch:
            batch.add_column(sa.Column("planned_for_date", sa.Date(), nullable=True))


def downgrade() -> None:
    if "planned_for_date" in _task_columns():
        with op.batch_alter_table("tasks") as batch:
            batch.drop_column("planned_for_date")
