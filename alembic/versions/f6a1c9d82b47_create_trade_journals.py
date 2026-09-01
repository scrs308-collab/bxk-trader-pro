"""create trade journals

Revision ID: f6a1c9d82b47
Revises: e4c7a912b6d3
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a1c9d82b47"
down_revision = "e4c7a912b6d3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trade_journals",

        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),

        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=True,
        ),

        sa.Column(
            "broker_order_id",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),

        sa.Column(
            "broker_status",
            sa.String(length=64),
            nullable=True,
        ),

        sa.Column(
            "strategy",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "underlying",
            sa.String(length=16),
            nullable=True,
        ),

        sa.Column(
            "expiration",
            sa.Date(),
            nullable=True,
        ),

        sa.Column(
            "dte",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=True,
        ),

        sa.Column(
            "wing_width",
            sa.Float(),
            nullable=True,
        ),

        sa.Column("short_put", sa.Float(), nullable=True),
        sa.Column("long_put", sa.Float(), nullable=True),
        sa.Column("short_call", sa.Float(), nullable=True),
        sa.Column("long_call", sa.Float(), nullable=True),

        sa.Column(
            "submitted_credit",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "entry_fill_credit",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "max_profit",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "max_risk",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "best_open_pnl",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "worst_open_pnl",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "min_short_cushion",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "worst_threat_state",
            sa.String(length=32),
            nullable=True,
        ),

        sa.Column(
            "first_orange_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "first_red_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "first_critical_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "exit_debit",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "realized_pnl",
            sa.Float(),
            nullable=True,
        ),

        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "outcome",
            sa.String(length=32),
            nullable=True,
        ),

        sa.Column(
            "exit_reason",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "entry_snapshot",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_trade_journals_broker_order_id",
        "trade_journals",
        ["broker_order_id"],
        unique=True,
    )

    op.create_index(
        "ix_trade_journals_user_id",
        "trade_journals",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_trade_journals_status",
        "trade_journals",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_trade_journals_submitted_at",
        "trade_journals",
        ["submitted_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_trade_journals_submitted_at",
        table_name="trade_journals",
    )

    op.drop_index(
        "ix_trade_journals_status",
        table_name="trade_journals",
    )

    op.drop_index(
        "ix_trade_journals_user_id",
        table_name="trade_journals",
    )

    op.drop_index(
        "ix_trade_journals_broker_order_id",
        table_name="trade_journals",
    )

    op.drop_table(
        "trade_journals"
    )
