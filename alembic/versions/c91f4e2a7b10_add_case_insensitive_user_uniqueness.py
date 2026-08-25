"""add case insensitive user uniqueness

Revision ID: c91f4e2a7b10
Revises: bb8d65457c1d
Create Date: 2026-08-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c91f4e2a7b10"
down_revision: Union[str, Sequence[str], None] = (
    "bb8d65457c1d"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )

    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_users_email_lower",
        table_name="users",
    )

    op.drop_index(
        "uq_users_username_lower",
        table_name="users",
    )
