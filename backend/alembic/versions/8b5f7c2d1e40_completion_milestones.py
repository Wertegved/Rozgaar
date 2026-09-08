"""Add completion milestone metadata and worker states.

Revision ID: 8b5f7c2d1e40
Revises: 7a4e6a1f2c90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8b5f7c2d1e40"
down_revision: Union[str, None] = "7a4e6a1f2c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    evidence_type = postgresql.ENUM("WORKER_COMPLETION", "CONSUMER_COMPLETION", name="evidence_type")
    evidence_type.create(op.get_bind(), checkfirst=True)
    op.add_column("completion_evidence", sa.Column("agreement_id", sa.Uuid(), nullable=True))
    op.add_column("completion_evidence", sa.Column("uploader_role", sa.String(length=20), nullable=True))
    op.add_column("completion_evidence", sa.Column("evidence_type", evidence_type, nullable=True))
    op.create_foreign_key("fk_completion_evidence_agreement", "completion_evidence", "agreements", ["agreement_id"], ["id"], ondelete="RESTRICT")
    op.execute("UPDATE completion_evidence SET uploader_role = 'WORKER', evidence_type = 'WORKER_COMPLETION' WHERE uploader_role IS NULL")
    op.alter_column("completion_evidence", "uploader_role", nullable=False)
    op.alter_column("completion_evidence", "evidence_type", nullable=False)
    op.create_unique_constraint("uq_completion_evidence_submitter_type", "completion_evidence", ["job_id", "agreement_id", "uploaded_by", "evidence_type"])
    op.create_table(
        "completion_worker_states",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("worker_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["worker_id"], ["worker_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "agreement_id", name="uq_completion_worker_state_agreement"),
    )
    op.create_index("ix_completion_worker_states_job_id", "completion_worker_states", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_completion_worker_states_job_id", table_name="completion_worker_states")
    op.drop_table("completion_worker_states")
    op.drop_constraint("uq_completion_evidence_submitter_type", "completion_evidence", type_="unique")
    op.drop_constraint("fk_completion_evidence_agreement", "completion_evidence", type_="foreignkey")
    op.drop_column("completion_evidence", "evidence_type")
    op.drop_column("completion_evidence", "uploader_role")
    op.drop_column("completion_evidence", "agreement_id")
    postgresql.ENUM("WORKER_COMPLETION", "CONSUMER_COMPLETION", name="evidence_type").drop(op.get_bind(), checkfirst=True)