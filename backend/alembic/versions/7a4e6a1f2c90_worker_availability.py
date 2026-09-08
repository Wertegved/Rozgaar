"""Add explicit worker availability windows.

Revision ID: 7a4e6a1f2c90
Revises: 45badac89889
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7a4e6a1f2c90"
down_revision: Union[str, None] = "45badac89889"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    availability_status = postgresql.ENUM(
        "AVAILABLE", "UNAVAILABLE", name="availability_status", create_type=False
    )
    availability_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "worker_availability",
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("available_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", availability_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="ck_worker_availability_time_order"),
        sa.ForeignKeyConstraint(["worker_id"], ["worker_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_worker_availability_worker_date",
        "worker_availability",
        ["worker_id", "available_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_worker_availability_worker_date", table_name="worker_availability")
    op.drop_table("worker_availability")
    postgresql.ENUM("AVAILABLE", "UNAVAILABLE", name="availability_status").drop(
        op.get_bind(), checkfirst=True
    )