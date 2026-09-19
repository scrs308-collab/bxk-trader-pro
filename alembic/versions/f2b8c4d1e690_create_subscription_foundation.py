"""create subscription foundation

Revision ID: f2b8c4d1e690
Revises: d3f7a91c6b24
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "f2b8c4d1e690"
down_revision = "d3f7a91c6b24"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_subscriptions",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "provider_customer_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "provider_subscription_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "provider_price_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "trial_ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "grace_period_ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "manual_access_granted",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "manual_access_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_customer_id",
        ),
        sa.UniqueConstraint(
            "provider_subscription_id",
        ),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_user_subscriptions_user_id",
        "user_subscriptions",
        ["user_id"],
    )

    op.create_table(
        "billing_webhook_events",
        sa.Column(
            "provider_event_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "payload_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "provider_event_id"
        ),
    )


def downgrade():
    op.drop_table(
        "billing_webhook_events"
    )
    op.drop_index(
        "ix_user_subscriptions_user_id",
        table_name="user_subscriptions",
    )
    op.drop_table(
        "user_subscriptions"
    )
