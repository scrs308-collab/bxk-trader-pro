"""create broker connections

Revision ID: 7b2c6e5f9a11
Revises: 0aa83b95c713
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa


revision = "7b2c6e5f9a11"
down_revision = "0aa83b95c713"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_connections",
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
            "broker",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "client_secret_encrypted",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "refresh_token_encrypted",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "account_number",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "base_url",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "live_trading_enabled",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
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
        sa.UniqueConstraint(
            "user_id",
            "broker",
            name="uq_broker_connections_user_broker",
        ),
    )

    op.create_index(
        op.f(
            "ix_broker_connections_user_id"
        ),
        "broker_connections",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f(
            "ix_broker_connections_user_id"
        ),
        table_name="broker_connections",
    )

    op.drop_table(
        "broker_connections"
    )
