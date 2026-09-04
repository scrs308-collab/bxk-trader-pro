"""create execution audits

Revision ID: 4a61f0c9d2b8
Revises: 7b2c6e5f9a11
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "4a61f0c9d2b8"
down_revision = "7b2c6e5f9a11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_audits",
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
            "event",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "reason_code",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "review_reference",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "account_masked",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "broker_status",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "order_snapshot",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id"
        ),
    )

    op.create_index(
        op.f(
            "ix_execution_audits_user_id"
        ),
        "execution_audits",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_broker"
        ),
        "execution_audits",
        ["broker"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_event"
        ),
        "execution_audits",
        ["event"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_status"
        ),
        "execution_audits",
        ["status"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_review_reference"
        ),
        "execution_audits",
        ["review_reference"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_order_id"
        ),
        "execution_audits",
        ["order_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_execution_audits_created_at"
        ),
        "execution_audits",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f(
            "ix_execution_audits_created_at"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_order_id"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_review_reference"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_status"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_event"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_broker"
        ),
        table_name="execution_audits",
    )

    op.drop_index(
        op.f(
            "ix_execution_audits_user_id"
        ),
        table_name="execution_audits",
    )

    op.drop_table(
        "execution_audits"
    )
