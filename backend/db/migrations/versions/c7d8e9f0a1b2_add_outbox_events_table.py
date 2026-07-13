"""add_outbox_events_table

Revision ID: c7d8e9f0a1b2
Revises: f3f5215ec0b8
Create Date: 2026-06-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "f3f5215ec0b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create outbox_events table for reliable Celery task dispatch."""
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_outbox_status_created",
        "outbox_events",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Drop outbox_events table."""
    op.drop_index("idx_outbox_status_created", table_name="outbox_events")
    op.drop_table("outbox_events")
