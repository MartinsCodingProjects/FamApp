"""processed ops

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24

Additive only (expand/contract, AGENTS.md section 5): the previous image must keep running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_ops",
        sa.Column("op_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("processed_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.PrimaryKeyConstraint("op_id"),
    )
    with op.batch_alter_table("processed_ops", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_processed_ops_device_id"), ["device_id"], unique=False)


def downgrade() -> None:
    # Dropping the table drops its indexes (MariaDB refuses to drop an FK index first).
    op.drop_table("processed_ops")
