"""add_langgraph_thread_id_to_trips

Revision ID: b2c3d4e5f6a7
Revises: 4075fc028452
Create Date: 2026-06-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "4075fc028452"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column("langgraph_thread_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trips", "langgraph_thread_id")
