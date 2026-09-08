"""Add durable notification idempotency keys.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_notifications_recipient_event",
        "notifications",
        ["recipient_user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_recipient_event", table_name="notifications")
    op.drop_column("notifications", "idempotency_key")