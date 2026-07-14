"""add_budget_state_to_trips

Revision ID: e92e137fb79d
Revises: c493f27a3172
Create Date: 2026-07-14 10:37:38.685130

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e92e137fb79d"
down_revision: str | Sequence[str] | None = "c493f27a3172"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trips.budget_state — durable snapshot of the graph's budget summary.

    Note: autogenerate also proposed the same unrelated outbox_events.id type
    flip seen in c493f27a3172 (cosmetic model/DB drift) — excluded again.
    """
    op.add_column("trips", sa.Column("budget_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("trips", "budget_state")
