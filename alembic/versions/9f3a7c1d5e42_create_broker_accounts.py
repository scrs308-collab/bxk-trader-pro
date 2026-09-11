"""create broker accounts

Revision ID: 9f3a7c1d5e42
Revises: 8c9d0e1f2a3b
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "9f3a7c1d5e42"
down_revision = "8c9d0e1f2a3b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_accounts",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "broker_connection_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "account_number",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "broker_account_key",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "nickname",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "account_type",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
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
            ["broker_connection_id"],
            ["broker_connections.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_connection_id",
            "account_number",
            name=(
                "uq_broker_accounts_"
                "connection_account"
            ),
        ),
    )

    op.create_index(
        "ix_broker_accounts_broker_connection_id",
        "broker_accounts",
        ["broker_connection_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_broker_accounts_broker_connection_id",
        table_name="broker_accounts",
    )

    op.drop_table(
        "broker_accounts"
    )
