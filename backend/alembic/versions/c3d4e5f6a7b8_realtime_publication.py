"""Enable the minimal existing tables in Supabase Realtime publication.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "jobs",
    "applications",
    "agreements",
    "worker_availability",
    "payments",
    "completions",
    "completion_worker_states",
    "reviews",
    "complaints",
    "disputes",
    "notifications",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') "
            f"AND NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = '{table}') "
            f"THEN ALTER PUBLICATION supabase_realtime ADD TABLE {table}; END IF; END $$;"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') "
            f"AND EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = '{table}') "
            f"THEN ALTER PUBLICATION supabase_realtime DROP TABLE {table}; END IF; END $$;"
        )