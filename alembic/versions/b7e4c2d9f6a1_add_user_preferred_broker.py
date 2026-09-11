"""add user preferred broker

Revision ID: b7e4c2d9f6a1
Revises: a4d2e6f819c0
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e4c2d9f6a1"
down_revision = "a4d2e6f819c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "preferred_broker",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "users",
        "preferred_broker",
    )
