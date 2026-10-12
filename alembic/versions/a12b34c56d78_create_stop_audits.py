"""Create independent observational Stop Audit records.

Revision ID: a12b34c56d78
Revises: f7c2a91e4d38
"""
from alembic import op
import sqlalchemy as sa

revision = "a12b34c56d78"
down_revision = "f7c2a91e4d38"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stop_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("journal_id", sa.Uuid(), sa.ForeignKey("trade_journals.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("broker_name", sa.String(32), nullable=False),
        sa.Column("account_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attribution", sa.String(32), nullable=False),
        sa.Column("underlying", sa.String(16), nullable=False),
        sa.Column("expiration", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tracking_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_trade", sa.JSON(), nullable=False),
        *[sa.Column(name, sa.Float(), nullable=False) for name in (
            "actual_gross_pnl", "actual_net_pnl", "entry_costs", "actual_exit_costs", "hypothetical_exit_costs",
        )],
        sa.Column("cost_basis", sa.String(32), nullable=False),
        *[sa.Column(name, sa.Float()) for name in (
            "latest_hypothetical_net_pnl", "latest_conservative_net_pnl", "best_hypothetical_net_pnl", "worst_hypothetical_net_pnl", "expiration_hypothetical_net_pnl",
        )],
        *[sa.Column(name, sa.DateTime(timezone=True)) for name in (
            "first_breakeven_at", "first_profit_at", "last_attempt_at", "last_observed_at",
        )],
        *[sa.Column(name, sa.Integer(), nullable=False) for name in (
            "valid_samples", "attempted_samples", "max_observation_gap_seconds",
        )],
        sa.Column("last_reason", sa.String(64)),
        sa.Column("settlement_status", sa.String(40), nullable=False),
    )
    op.create_index("ix_stop_audits_user_id", "stop_audits", ["user_id"])
    op.create_index("ix_stop_audits_status", "stop_audits", ["status"])
    op.create_table(
        "stop_audit_samples",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("audit_id", sa.Uuid(), sa.ForeignKey("stop_audits.id"), nullable=False),
        sa.Column("minute_bucket", sa.Integer(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("quote_start_at", sa.DateTime(timezone=True)),
        sa.Column("quote_end_at", sa.DateTime(timezone=True)),
        *[sa.Column(name, sa.Float()) for name in (
            "midpoint_debit", "conservative_debit", "hypothetical_net_pnl", "conservative_net_pnl",
        )],
        sa.Column("quote_evidence", sa.JSON()),
        sa.UniqueConstraint("audit_id", "minute_bucket", name="uq_stop_audit_sample_minute"),
    )
    op.create_index("ix_stop_audit_samples_audit_id", "stop_audit_samples", ["audit_id"])


def downgrade():
    op.drop_table("stop_audit_samples")
    op.drop_table("stop_audits")
