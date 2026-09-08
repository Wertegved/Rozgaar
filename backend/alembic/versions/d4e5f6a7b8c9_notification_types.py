"""Add the remaining controlled Phase 15 notification types.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in (
        "COUNTER_OFFER_CREATED",
        "AGREEMENT_ACTIVE",
        "PAYMENT_FAILED",
        "JOB_COMPLETED",
        "REVIEW_CREATED",
        "COMPLAINT_CREATED",
        "COMPLAINT_STATUS_CHANGED",
        "JOB_CREATED",
        "JOB_STATUS_CHANGED",
        "SCHEDULE_UPDATED",
    ):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass