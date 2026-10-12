"""Observation-only copies of explicitly confirmed stopped-out trades."""
import uuid

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from bxk_app.database import Base


class StopAudit(Base):
    __tablename__ = "stop_audits"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("trade_journals.id"), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    broker_name: Mapped[str] = mapped_column(String(32), nullable=False)
    account_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="TRACKING", index=True)
    attribution: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_CONFIRMED_STOP")
    underlying: Mapped[str] = mapped_column(String(16), nullable=False)
    expiration: Mapped[object] = mapped_column(Date, nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    tracking_started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    original_trade: Mapped[dict] = mapped_column(JSON, nullable=False)
    actual_gross_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    actual_net_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    entry_costs: Mapped[float] = mapped_column(Float, nullable=False)
    actual_exit_costs: Mapped[float] = mapped_column(Float, nullable=False)
    hypothetical_exit_costs: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="USER_ESTIMATE")
    latest_hypothetical_net_pnl: Mapped[float | None] = mapped_column(Float)
    latest_conservative_net_pnl: Mapped[float | None] = mapped_column(Float)
    best_hypothetical_net_pnl: Mapped[float | None] = mapped_column(Float)
    worst_hypothetical_net_pnl: Mapped[float | None] = mapped_column(Float)
    first_breakeven_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    first_profit_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    valid_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempted_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    last_reason: Mapped[str | None] = mapped_column(String(64))
    max_observation_gap_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settlement_status: Mapped[str] = mapped_column(String(40), nullable=False, default="NOT_DUE")
    expiration_hypothetical_net_pnl: Mapped[float | None] = mapped_column(Float)


class StopAuditSample(Base):
    __tablename__ = "stop_audit_samples"
    __table_args__ = (UniqueConstraint("audit_id", "minute_bucket", name="uq_stop_audit_sample_minute"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("stop_audits.id"), nullable=False, index=True)
    minute_bucket: Mapped[int] = mapped_column(Integer, nullable=False)
    attempted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNAVAILABLE")
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    quote_start_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    quote_end_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    midpoint_debit: Mapped[float | None] = mapped_column(Float)
    conservative_debit: Mapped[float | None] = mapped_column(Float)
    hypothetical_net_pnl: Mapped[float | None] = mapped_column(Float)
    conservative_net_pnl: Mapped[float | None] = mapped_column(Float)
    quote_evidence: Mapped[list | None] = mapped_column(JSON)
