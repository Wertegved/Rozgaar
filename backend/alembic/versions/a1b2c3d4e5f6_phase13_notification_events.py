"""Add missing Phase 13 notification event types.

Revision ID: a1b2c3d4e5f6
Revises: 9c6d8e3f1a20
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c6d8e3f1a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in (
        "APPLICATION_WITHDRAWN",
        "COUNTER_OFFER_ACCEPTED",
        "COUNTER_OFFER_REJECTED",
    ):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass
