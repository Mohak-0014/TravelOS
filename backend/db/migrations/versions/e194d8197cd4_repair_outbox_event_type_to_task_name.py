"""repair_outbox_event_type_to_task_name

Repairs schema drift on outbox_events: the original c7d8e9f0a1b2 migration was
edited in place at some point — renaming "event_type" to "task_name", adding
"last_error", and changing "id" from VARCHAR(36) to UUID. Databases migrated
before that edit still carry the old shape, which breaks drain_outbox twice
over (UndefinedColumnError on task_name/last_error, then
"operator does not exist: character varying = uuid" on the id comparison under
asyncpg). Databases created after the edit are already correct. Both states
sit at the same Alembic revision, so this revision reconciles conditionally
and is a no-op where the table already matches c7d8e9f0a1b2's current
definition.

Revision ID: e194d8197cd4
Revises: e92e137fb79d
Create Date: 2026-07-15 12:41:22.225931

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e194d8197cd4"
down_revision: Union[str, Sequence[str], None] = "e92e137fb79d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _outbox_columns() -> dict[str, dict]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"]: col for col in inspector.get_columns("outbox_events")}


def upgrade() -> None:
    cols = _outbox_columns()
    if "event_type" in cols and "task_name" not in cols:
        op.alter_column("outbox_events", "event_type", new_column_name="task_name")
    if "last_error" not in cols:
        op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True))
    if "id" in cols and not isinstance(cols["id"]["type"], sa.UUID):
        op.alter_column(
            "outbox_events",
            "id",
            type_=sa.UUID(as_uuid=False),
            postgresql_using="id::uuid",
        )


def downgrade() -> None:
    # Only reverse changes this revision could have performed. A database that
    # was already correct on upgrade must stay untouched on downgrade too —
    # which is impossible to distinguish afterwards, so downgrade restores the
    # pre-edit column name/type only where clearly reversible and keeps
    # last_error (dropping a possibly pre-existing column would lose data).
    cols = _outbox_columns()
    if "task_name" in cols and "event_type" not in cols:
        op.alter_column("outbox_events", "task_name", new_column_name="event_type")
    if "id" in cols and isinstance(cols["id"]["type"], sa.UUID):
        op.alter_column(
            "outbox_events",
            "id",
            type_=sa.String(36),
            postgresql_using="id::text",
        )
