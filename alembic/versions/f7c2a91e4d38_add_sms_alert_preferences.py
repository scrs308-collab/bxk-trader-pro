"""add sms alert preferences and delivery history

Revision ID: f7c2a91e4d38
Revises: c5f8a12d6e31
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "f7c2a91e4d38"
down_revision = "c5f8a12d6e31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "sms_alert_mode",
            sa.String(length=32),
            nullable=False,
            server_default="AFTER_HOURS",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "sms_snoozed_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "sms_alert_deliveries",
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
            "kind",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_sms_alert_deliveries_user_id",
        "sms_alert_deliveries",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_sms_alert_deliveries_sent_at",
        "sms_alert_deliveries",
        ["sent_at"],
        unique=False,
    )

    op.create_index(
        "ix_sms_alert_deliveries_user_kind_sent",
        "sms_alert_deliveries",
        ["user_id", "kind", "sent_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_sms_alert_deliveries_user_kind_sent",
        table_name="sms_alert_deliveries",
    )
    op.drop_index(
        "ix_sms_alert_deliveries_sent_at",
        table_name="sms_alert_deliveries",
    )
    op.drop_index(
        "ix_sms_alert_deliveries_user_id",
        table_name="sms_alert_deliveries",
    )
    op.drop_table("sms_alert_deliveries")
    op.drop_column("users", "sms_snoozed_until")
    op.drop_column("users", "sms_alert_mode")
