"""add trade journal closure fields

Revision ID: 0c3e7a9f1b24
Revises: f6a1c9d82b47
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0c3e7a9f1b24"
down_revision = "f6a1c9d82b47"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "trade_journals",
        sa.Column(
            "closing_broker_order_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "trade_journals",
        sa.Column(
            "close_snapshot",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_trade_journals_closing_broker_order_id",
        "trade_journals",
        ["closing_broker_order_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_trade_journals_closing_broker_order_id",
        table_name="trade_journals",
    )

    op.drop_column(
        "trade_journals",
        "close_snapshot",
    )

    op.drop_column(
        "trade_journals",
        "closing_broker_order_id",
    )
