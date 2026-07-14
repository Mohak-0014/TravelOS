"""add_flight_origin_to_trips

Revision ID: c493f27a3172
Revises: c7d8e9f0a1b2
Create Date: 2026-07-14 00:58:57.089072

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c493f27a3172"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add trips.flight_origin (departure airport IATA) for flight budgeting.

    Note: autogenerate also proposed an unrelated outbox_events.id type flip
    (VARCHAR(36) vs UUID) — a cosmetic model/DB drift, intentionally excluded.
    """
    op.add_column("trips", sa.Column("flight_origin", sa.String(length=3), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("trips", "flight_origin")
