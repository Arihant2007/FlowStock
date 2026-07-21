"""Add admin user management columns

Revision ID: c3f1a2b9d4e5
Revises: 384d91871300
Create Date: 2026-07-21 17:44:00.000000

Adds:
  users.is_locked              — admin-imposed lock flag
  users.must_change_password   — force password change on next login
  users.password_changed_at    — UTC timestamp of last password change
  users.last_login_at          — UTC timestamp of last successful login
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1a2b9d4e5"
down_revision: Union[str, None] = "384d91871300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_locked",
                sa.Boolean(),
                nullable=False,
                server_default="0",
                comment="Admin-imposed lock. True = account is locked regardless of locked_until.",
            )
        )
        batch_op.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default="0",
                comment="When True, user must set a new password before accessing the application.",
            )
        )
        batch_op.add_column(
            sa.Column(
                "password_changed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="UTC timestamp of the last successful password change or admin reset.",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_login_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="UTC timestamp of the last successful login.",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("password_changed_at")
        batch_op.drop_column("must_change_password")
        batch_op.drop_column("is_locked")
