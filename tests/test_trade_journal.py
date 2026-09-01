import uuid

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import (
    sessionmaker,
)
from sqlalchemy.pool import (
    StaticPool,
)

import bxk_app.services.trade_journal_service as service
from bxk_app.db_models.trade_journal import (
    TradeJournal,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)


def make_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    User.__table__.create(
        engine
    )

    TradeJournal.__table__.create(
        engine
    )

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def sample_order():
    return {
        "strategy":
            "SPX Iron Condor",
        "symbol": "SPX",
        "quantity": 2,
        "limit_price": 2.75,
        "expiration":
            "2026-09-02",
        "dte": 1,
        "wing_width": 25,
        "max_profit": 550,
        "max_risk": 4450,
        "legs": [
            {
                "action": "SELL",
                "option_type": "PUT",
                "strike": 6500,
                "symbol": "PUT-SHORT",
            },
            {
                "action": "BUY",
                "option_type": "PUT",
                "strike": 6475,
                "symbol": "PUT-LONG",
            },
            {
                "action": "SELL",
                "option_type": "CALL",
                "strike": 6650,
                "symbol": "CALL-SHORT",
            },
            {
                "action": "BUY",
                "option_type": "CALL",
                "strike": 6675,
                "symbol": "CALL-LONG",
            },
        ],
    }


def create_user(factory):
    user_id = uuid.uuid4()

    with factory() as session:
        session.add(
            User(
                id=user_id,
                username="owner",
                email=
                    "owner@example.com",
                password_hash="hash",
                role=UserRole.OWNER,
                is_active=True,
                must_change_password=False,
            )
        )

        session.commit()

    return user_id


def test_submission_creates_journal(
    monkeypatch,
):
    factory = make_factory()
    user_id = create_user(factory)

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    result = (
        service.record_submitted_trade(
            user_context={
                "user_id":
                    str(user_id),
            },
            broker_order_id=
                "ORDER-100",
            broker_status="FILLED",
            order=sample_order(),
            trade={
                "stability_score": 82,
                "expected_move": 71.5,
            },
            broker_order={
                "received-at":
                    "2026-09-01T14:35:00Z",
            },
            reconciliation={
                "filled_quantity": "2",
                "average_fill_price":
                    "2.68",
                "updated_at":
                    "2026-09-01T14:35:01Z",
            },
            session_factory=factory,
        )
    )

    assert result["recorded"] is True
    assert result["created"] is True
    assert result["status"] == "OPEN"

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            )
        ).scalar_one()

        assert journal.user_id == user_id
        assert (
            journal.broker_order_id
            == "ORDER-100"
        )
        assert journal.short_put == 6500
        assert journal.long_put == 6475
        assert journal.short_call == 6650
        assert journal.long_call == 6675
        assert (
            journal.submitted_credit
            == 2.75
        )
        assert (
            journal.entry_fill_credit
            == 2.68
        )
        assert journal.quantity == 2

        assert (
            journal.entry_snapshot[
                "trade"
            ][
                "stability_score"
            ]
            == 82
        )


def test_same_broker_order_is_idempotent(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    first = (
        service.record_submitted_trade(
            broker_order_id=
                "ORDER-200",
            broker_status=
                "RECEIVED",
            order=sample_order(),
            reconciliation={},
            session_factory=factory,
        )
    )

    second = (
        service.record_submitted_trade(
            broker_order_id=
                "ORDER-200",
            broker_status=
                "FILLED",
            order=sample_order(),
            reconciliation={
                "filled_quantity": 2,
                "average_fill_price":
                    2.70,
            },
            session_factory=factory,
        )
    )

    assert first["created"] is True
    assert second["created"] is False
    assert second["status"] == "OPEN"

    with factory() as session:
        journals = session.execute(
            select(
                TradeJournal
            )
        ).scalars().all()

        assert len(journals) == 1

        assert (
            journals[0].
            entry_fill_credit
            == 2.70
        )


def test_database_disabled_skips_cleanly(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: False,
    )

    result = (
        service.record_submitted_trade(
            broker_order_id=
                "ORDER-300",
            order=sample_order(),
        )
    )

    assert result == {
        "recorded": False,
        "reason":
            "DATABASE_NOT_CONFIGURED",
    }


def test_order_route_contains_journal_hook():
    from pathlib import Path

    source = Path(
        "bxk_app/routes/order.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "record_submitted_trade"
        in source
    )

    assert (
        "broker_order_id=order_id"
        in source
    )

    assert (
        "reconciliation=reconciliation"
        in source
    )

    assert (
        "user_context: dict = Depends"
        in source
    )
