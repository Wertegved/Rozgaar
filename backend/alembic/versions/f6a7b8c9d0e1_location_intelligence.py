"""Add privacy-safe coordinates for location intelligence."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("worker_profiles", sa.Column("working_latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("worker_profiles", sa.Column("working_longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("jobs", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("jobs", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.create_index("ix_worker_profiles_working_coordinates", "worker_profiles", ["working_latitude", "working_longitude"])
    op.create_index("ix_jobs_coordinates", "jobs", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_jobs_coordinates", table_name="jobs")
    op.drop_index("ix_worker_profiles_working_coordinates", table_name="worker_profiles")
    op.drop_column("jobs", "longitude")
    op.drop_column("jobs", "latitude")
    op.drop_column("worker_profiles", "working_longitude")
    op.drop_column("worker_profiles", "working_latitude")