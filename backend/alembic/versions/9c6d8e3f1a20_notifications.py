"""Add in-app notifications.

Revision ID: 9c6d8e3f1a20
Revises: 8b5f7c2d1e40
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "9c6d8e3f1a20"
down_revision: Union[str, None] = "8b5f7c2d1e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_type = postgresql.ENUM(
        "APPLICATION_SUBMITTED", "APPLICATION_ACCEPTED", "APPLICATION_REJECTED",
        "COUNTER_OFFER_RECEIVED", "AGREEMENT_CREATED", "ADVANCE_PAYMENT_COMPLETED",
        "COMPLETION_CONFIRMED", "FINAL_PAYMENT_COMPLETED", "REVIEW_AVAILABLE",
        "COMPLAINT_RESPONSE", "DISPUTE_CREATED", "DISPUTE_STATUS_CHANGED",
        "DISPUTE_RESOLVED", "ACCOUNT_EVENT", name="notification_type", create_type=False,
    )
    notification_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "notifications",
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_entity_type", sa.String(length=80), nullable=True),
        sa.Column("related_entity_id", sa.Uuid(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_user_id", "created_at"], unique=False)
    op.create_index("ix_notifications_recipient_unread", "notifications", ["recipient_user_id", "is_read"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_table("notifications")
    postgresql.ENUM(name="notification_type").drop(op.get_bind(), checkfirst=True)