"""pairing codes

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

Additive only (expand/contract, AGENTS.md section 5): the previous image must keep running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pairing_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("used_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("used_by_device_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_device_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    with op.batch_alter_table("pairing_codes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pairing_codes_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    # Dropping the table drops its indexes (MariaDB refuses to drop an FK index first).
    op.drop_table("pairing_codes")
