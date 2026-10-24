"""setup wizard and admin login

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24

Additive only (expand/contract, AGENTS.md section 5): the previous image must keep running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("admin_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_admin_sessions_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("totp_confirmed_at", app.db.types.UTCDateTime(), nullable=True))
        batch_op.add_column(sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("failed_logins", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("locked_until", app.db.types.UTCDateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_logins")
        batch_op.drop_column("totp_last_step")
        batch_op.drop_column("totp_confirmed_at")

    # Dropping the table drops its indexes (MariaDB refuses to drop an FK index first).
    op.drop_table("admin_sessions")
    op.drop_table("system_settings")
