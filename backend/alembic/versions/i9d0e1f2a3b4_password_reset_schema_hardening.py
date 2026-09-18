"""Harden password reset token defaults and access controls."""
from typing import Sequence, Union

from alembic import op


revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE password_reset_tokens ALTER COLUMN created_at SET DEFAULT now()")
    op.execute("ALTER TABLE password_reset_tokens ALTER COLUMN updated_at SET DEFAULT now()")
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)")
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE password_reset_tokens ALTER COLUMN created_at DROP DEFAULT")
    op.execute("ALTER TABLE password_reset_tokens ALTER COLUMN updated_at DROP DEFAULT")
