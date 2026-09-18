"""add user sms subscriptions

Revision ID: d3f7a91c6b24
Revises: c2e8a4f71b36
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "d3f7a91c6b24"
down_revision = "c2e8a4f71b36"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "sms_phone_e164",
            sa.String(length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "sms_alerts_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_unique_constraint(
        "uq_users_sms_phone_e164",
        "users",
        ["sms_phone_e164"],
    )

    op.add_column(
        "sms_consents",
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sms_consents_user_id",
        "sms_consents",
        ["user_id"],
    )
    op.create_foreign_key(
        "fk_sms_consents_user_id_users",
        "sms_consents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_sms_consents_user_id_users",
        "sms_consents",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_sms_consents_user_id",
        table_name="sms_consents",
    )
    op.drop_column("sms_consents", "user_id")

    op.drop_constraint(
        "uq_users_sms_phone_e164",
        "users",
        type_="unique",
    )
    op.drop_column("users", "sms_alerts_enabled")
    op.drop_column("users", "sms_phone_e164")
