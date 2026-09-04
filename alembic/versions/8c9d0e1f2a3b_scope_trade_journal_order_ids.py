"""scope trade journal order ids per user

Revision ID: 8c9d0e1f2a3b
Revises: 4a61f0c9d2b8
"""

from alembic import op
import sqlalchemy as sa


revision = "8c9d0e1f2a3b"
down_revision = "4a61f0c9d2b8"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        "ix_trade_journals_broker_order_id",
        table_name="trade_journals",
    )

    op.drop_index(
        "ix_trade_journals_closing_broker_order_id",
        table_name="trade_journals",
    )

    op.create_index(
        "ix_trade_journals_broker_order_id",
        "trade_journals",
        ["broker_order_id"],
        unique=False,
    )

    op.create_index(
        "ix_trade_journals_closing_broker_order_id",
        "trade_journals",
        ["closing_broker_order_id"],
        unique=False,
    )

    op.create_index(
        "uq_trade_journals_user_broker_order_id",
        "trade_journals",
        ["user_id", "broker_order_id"],
        unique=True,
        postgresql_where=sa.text(
            "user_id IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "user_id IS NOT NULL"
        ),
    )

    op.create_index(
        "uq_trade_journals_legacy_broker_order_id",
        "trade_journals",
        ["broker_order_id"],
        unique=True,
        postgresql_where=sa.text(
            "user_id IS NULL"
        ),
        sqlite_where=sa.text(
            "user_id IS NULL"
        ),
    )

    op.create_index(
        "uq_trade_journals_user_closing_order_id",
        "trade_journals",
        ["user_id", "closing_broker_order_id"],
        unique=True,
        postgresql_where=sa.text(
            "user_id IS NOT NULL "
            "AND closing_broker_order_id IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "user_id IS NOT NULL "
            "AND closing_broker_order_id IS NOT NULL"
        ),
    )

    op.create_index(
        "uq_trade_journals_legacy_closing_order_id",
        "trade_journals",
        ["closing_broker_order_id"],
        unique=True,
        postgresql_where=sa.text(
            "user_id IS NULL "
            "AND closing_broker_order_id IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "user_id IS NULL "
            "AND closing_broker_order_id IS NOT NULL"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_trade_journals_legacy_closing_order_id",
        table_name="trade_journals",
    )
    op.drop_index(
        "uq_trade_journals_user_closing_order_id",
        table_name="trade_journals",
    )
    op.drop_index(
        "uq_trade_journals_legacy_broker_order_id",
        table_name="trade_journals",
    )
    op.drop_index(
        "uq_trade_journals_user_broker_order_id",
        table_name="trade_journals",
    )

    op.drop_index(
        "ix_trade_journals_closing_broker_order_id",
        table_name="trade_journals",
    )
    op.drop_index(
        "ix_trade_journals_broker_order_id",
        table_name="trade_journals",
    )

    op.create_index(
        "ix_trade_journals_broker_order_id",
        "trade_journals",
        ["broker_order_id"],
        unique=True,
    )

    op.create_index(
        "ix_trade_journals_closing_broker_order_id",
        "trade_journals",
        ["closing_broker_order_id"],
        unique=True,
    )
