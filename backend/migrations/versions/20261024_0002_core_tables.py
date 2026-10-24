"""core tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24

Additive only (expand/contract, AGENTS.md section 5): the previous image must keep running.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_device_id", sa.Uuid(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_log_at"), ["at"], unique=False)

    op.create_table(
        "conflict_log",
        sa.Column("at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("table_name", sa.String(length=60), nullable=False),
        sa.Column("row_id", sa.Uuid(), nullable=False),
        sa.Column("field_group", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("losing_user_id", sa.Uuid(), nullable=True),
        sa.Column("losing_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("losing_values", sa.JSON(), nullable=False),
        sa.Column("winning_user_id", sa.Uuid(), nullable=True),
        sa.Column("winning_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("winning_values", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("conflict_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_conflict_log_at"), ["at"], unique=False)

    op.create_table(
        "job_log",
        sa.Column("job", sa.String(length=60), nullable=False),
        sa.Column("started_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("finished_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("job_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_job_log_job"), ["job"], unique=False)

    rev_counter = op.create_table(
        "rev_counter",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(rev_counter, [{"id": 1, "value": 0}])
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "users",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rev", sa.BigInteger(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("deleted_at", app.db.types.UTCDateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_rev"), ["rev"], unique=True)

    op.create_table(
        "devices",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("app_version", sa.Integer(), nullable=True),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column("fcm_token_updated_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("last_sync_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("device_status", sa.JSON(), nullable=True),
        sa.Column("locked_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("locked_reason", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_devices_user_id"), ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("message_key", sa.String(length=100), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("todo_id", sa.Uuid(), nullable=True),
        sa.Column("show_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rev", sa.BigInteger(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("deleted_at", app.db.types.UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_notifications_rev"), ["rev"], unique=True)
        batch_op.create_index(batch_op.f("ix_notifications_user_id"), ["user_id"], unique=False)

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quiet_hours", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("mode_until", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("mode_schedule", sa.JSON(), nullable=False),
        sa.Column("theme", sa.String(length=10), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rev", sa.BigInteger(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("deleted_at", app.db.types.UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    with op.batch_alter_table("user_settings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_settings_rev"), ["rev"], unique=True)

    op.create_table(
        "alarm_firings",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("planned_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("fired_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("alarm_type", sa.String(length=20), nullable=False),
        sa.Column("idle", sa.Boolean(), nullable=False),
        sa.Column("network", sa.Boolean(), nullable=False),
        sa.Column("sync_result", sa.String(length=20), nullable=False),
        sa.Column("sync_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("alarm_firings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alarm_firings_device_id"), ["device_id"], unique=False)

    op.create_table(
        "deliveries",
        sa.Column("display_key", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("planned_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("shown_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("opened_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("acked_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_key", "device_id"),
    )
    with op.batch_alter_table("deliveries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deliveries_device_id"), ["device_id"], unique=False)

    op.create_table(
        "device_tokens",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("first_used_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("revoked_at", app.db.types.UTCDateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", app.db.types.UTCDateTime(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id"],
            ["device_tokens.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("device_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_device_tokens_device_id"), ["device_id"], unique=False)


def downgrade() -> None:
    # Dropping a table drops its indexes; MariaDB refuses to drop an index a foreign key needs.
