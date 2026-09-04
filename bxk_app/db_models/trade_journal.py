import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from bxk_app.database import Base


class TradeJournal(Base):
    __tablename__ = "trade_journals"

    __table_args__ = (
        Index(
            "uq_trade_journals_user_broker_order_id",
            "user_id",
            "broker_order_id",
            unique=True,
            postgresql_where=text(
                "user_id IS NOT NULL"
            ),
            sqlite_where=text(
                "user_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_trade_journals_legacy_broker_order_id",
            "broker_order_id",
            unique=True,
            postgresql_where=text(
                "user_id IS NULL"
            ),
            sqlite_where=text(
                "user_id IS NULL"
            ),
        ),
        Index(
            "uq_trade_journals_user_closing_order_id",
            "user_id",
            "closing_broker_order_id",
            unique=True,
            postgresql_where=text(
                "user_id IS NOT NULL "
                "AND closing_broker_order_id IS NOT NULL"
            ),
            sqlite_where=text(
                "user_id IS NOT NULL "
                "AND closing_broker_order_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_trade_journals_legacy_closing_order_id",
            "closing_broker_order_id",
            unique=True,
            postgresql_where=text(
                "user_id IS NULL "
                "AND closing_broker_order_id IS NOT NULL"
            ),
            sqlite_where=text(
                "user_id IS NULL "
                "AND closing_broker_order_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    broker_order_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SUBMITTED",
        index=True,
    )

    broker_status: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
    )

    strategy: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    underlying: Mapped[
        str | None
    ] = mapped_column(
        String(16),
        nullable=True,
    )

    expiration: Mapped[
        object | None
    ] = mapped_column(
        Date,
        nullable=True,
    )

    dte: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    quantity: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    wing_width: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    short_put: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    long_put: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    short_call: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    long_call: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    submitted_credit: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    entry_fill_credit: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    max_profit: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    max_risk: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    submitted_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    opened_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # These observation fields will be updated by
    # Position Monitor in the next journal phase.
    best_open_pnl: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    worst_open_pnl: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    min_short_cushion: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    worst_threat_state: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    # -------------------------------------------------
    # Overnight carry-risk learning snapshot.
    # -------------------------------------------------

    carry_evaluated_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    carry_state: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    carry_decision: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
    )

    carry_threatened_side: Mapped[
        str | None
    ] = mapped_column(
        String(16),
        nullable=True,
    )

    carry_short_cushion: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    carry_expected_move: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    carry_expected_move_source: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    carry_cushion_ratio: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    carry_vix1d: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    carry_vix: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    carry_snapshot: Mapped[
        dict | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    held_overnight: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    # -------------------------------------------------
    # Next regular-session open outcome.
    # -------------------------------------------------

    next_open_evaluated_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_open_spx: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    next_open_gap_points: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    next_open_short_breached: Mapped[
        bool | None
    ] = mapped_column(
        Boolean,
        nullable=True,
    )

    first_orange_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    first_red_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    first_critical_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    closing_broker_order_id: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    close_snapshot: Mapped[
        dict | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    exit_debit: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    realized_pnl: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    closed_at: Mapped[
        object | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    outcome: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    exit_reason: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    # Flexible frozen entry snapshot. This lets us
    # retain today's scoring/market fields even as
    # Trader Pro evolves.
    entry_snapshot: Mapped[
        dict | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
