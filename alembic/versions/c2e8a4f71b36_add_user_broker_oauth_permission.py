"""add user broker oauth permission

Revision ID: c2e8a4f71b36
Revises: b7e4c2d9f6a1
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa


revision = "c2e8a4f71b36"
down_revision = "b7e4c2d9f6a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "broker_oauth_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Initial controlled beta rollout requested for
    # kdixon. Username matching is case-insensitive.
    op.execute(
        sa.text(
            "UPDATE users "
            "SET broker_oauth_enabled = true "
            "WHERE lower(username) = 'kdixon'"
        )
    )


def downgrade():
    op.drop_column(
        "users",
        "broker_oauth_enabled",
    )
