"""baseline (empty)

Revision ID: 0001
Revises:
Create Date: 2026-10-24

Additive only (expand/contract, AGENTS.md section 5): the previous image must keep running.
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
