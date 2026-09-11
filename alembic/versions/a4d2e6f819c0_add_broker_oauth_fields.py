"""add broker oauth fields

Revision ID: a4d2e6f819c0
Revises: 9f3a7c1d5e42
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "a4d2e6f819c0"
down_revision = "9f3a7c1d5e42"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "broker_connections"
    ) as batch_op:
        batch_op.alter_column(
            "client_secret_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )

        batch_op.alter_column(
            "refresh_token_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )

        batch_op.add_column(
            sa.Column(
                "access_token_encrypted",
                sa.Text(),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "access_token_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "refresh_token_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "oauth_state_hash",
                sa.String(length=64),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "oauth_state_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    op.create_index(
        "ix_broker_connections_oauth_state_hash",
        "broker_connections",
        ["oauth_state_hash"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_broker_connections_oauth_state_hash",
        table_name="broker_connections",
    )

    with op.batch_alter_table(
        "broker_connections"
    ) as batch_op:
        batch_op.drop_column(
            "oauth_state_expires_at"
        )

        batch_op.drop_column(
            "oauth_state_hash"
        )

        batch_op.drop_column(
            "refresh_token_expires_at"
        )

        batch_op.drop_column(
            "access_token_expires_at"
        )

        batch_op.drop_column(
            "access_token_encrypted"
        )

        batch_op.alter_column(
            "refresh_token_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )

        batch_op.alter_column(
            "client_secret_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
