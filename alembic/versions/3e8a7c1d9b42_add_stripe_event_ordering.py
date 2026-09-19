"""add Stripe event ordering fields

Revision ID: 3e8a7c1d9b42
Revises: f2b8c4d1e690
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "3e8a7c1d9b42"
down_revision = "f2b8c4d1e690"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_subscriptions",
        sa.Column(
            "provider_event_created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_subscriptions",
        sa.Column(
            "provider_event_id",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "user_subscriptions",
        "provider_event_id",
    )
    op.drop_column(
        "user_subscriptions",
        "provider_event_created_at",
    )
