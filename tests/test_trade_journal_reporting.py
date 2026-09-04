from datetime import (
    datetime,
    timezone,
)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

import bxk_app.routes.trade_journal as route_module
import bxk_app.services.trade_journal_service as service

from bxk_app.db_models.trade_journal import (
    TradeJournal,
)

from tests.test_trade_journal import (
    make_factory,
    sample_order,
)


def _terminal_trade(
    factory,
    monkeypatch,
    *,
    order_id,
    pnl,
    day,
    outcome,
    exit_reason,
    threat="GREEN",
    cushion=30.0,
):
    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id=
            order_id,
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "filled_quantity": 1,
            "average_fill_price":
                2.50,
            "updated_at":
                "2026-09-01T15:00:00Z",
        },
        session_factory=factory,
    )

    with factory() as session:
        journal = session.execute(
            select(
                TradeJournal
            ).where(
                TradeJournal.broker_order_id
                == order_id
            )
        ).scalar_one()

        journal.status = (
            "EXPIRED"
            if exit_reason
            in {
                "EXPIRED_WORTHLESS",
                "SPX_CASH_SETTLEMENT",
            }
            else "CLOSED"
        )

        journal.realized_pnl = pnl
        journal.outcome = outcome
        journal.exit_reason = exit_reason
        journal.worst_threat_state = threat
        journal.min_short_cushion = cushion

        journal.closed_at = datetime(
            2026,
            9,
            day,
            20,
            0,
            tzinfo=timezone.utc,
        )

        session.commit()


def test_trade_journal_summary_metrics(
    monkeypatch,
):
    factory = make_factory()

    _terminal_trade(
        factory,
        monkeypatch,
        order_id="REPORT-1",
        pnl=200.0,
        day=1,
        outcome="WIN",
        exit_reason=
            "BROKER_CLOSE_ORDER",
        threat="GREEN",
        cushion=30,
    )

    _terminal_trade(
        factory,
        monkeypatch,
        order_id="REPORT-2",
        pnl=100.0,
        day=2,
        outcome="WIN",
        exit_reason=
            "BROKER_CLOSE_ORDER",
        threat="ORANGE",
        cushion=20,
    )

    _terminal_trade(
        factory,
        monkeypatch,
        order_id="REPORT-3",
        pnl=-50.0,
        day=3,
        outcome="LOSS",
        exit_reason=
            "SPX_CASH_SETTLEMENT",
        threat="CRITICAL",
        cushion=-5,
    )

    _terminal_trade(
        factory,
        monkeypatch,
        order_id="REPORT-4",
        pnl=0.0,
        day=4,
        outcome="SCRATCH",
        exit_reason=
            "EXPIRED_WORTHLESS",
        threat="RED",
        cushion=15,
    )

    summary = (
        service.
        get_trade_journal_summary(
            user_context={},
            session_factory=factory,
        )
    )

    assert summary["available"] is True
    assert summary["total_trades"] == 4
    assert summary["wins"] == 2
    assert summary["losses"] == 1
    assert summary["scratches"] == 1
    assert summary["win_rate"] == 50.0

    assert (
        summary["total_realized_pnl"]
        == 250.0
    )

    assert summary["average_pnl"] == 62.5

    assert (
        summary["average_winner"]
        == 150.0
    )

    assert (
        summary["average_loser"]
        == -50.0
    )

    assert summary["profit_factor"] == 6.0

    assert (
        summary["best_trade"][
            "realized_pnl"
        ]
        == 200.0
    )

    assert (
        summary["worst_trade"][
            "realized_pnl"
        ]
        == -50.0
    )

    assert (
        summary["threat_counts"]
        == {
            "orange": 3,
            "red": 2,
            "critical": 1,
        }
    )

    assert (
        summary["exit_reasons"][
            "broker_close"
        ]
        == 2
    )

    assert (
        summary["exit_reasons"][
            "expired_worthless"
        ]
        == 1
    )

    assert (
        summary["exit_reasons"][
            "cash_settlement"
        ]
        == 1
    )


def test_recent_trades_are_newest_first(
    monkeypatch,
):
    factory = make_factory()

    for index in range(
        1,
        4,
    ):
        _terminal_trade(
            factory,
            monkeypatch,
            order_id=
                f"RECENT-{index}",
            pnl=float(
                index * 10
            ),
            day=index,
            outcome="WIN",
            exit_reason=
                "BROKER_CLOSE_ORDER",
        )

    result = (
        service.
        get_trade_journal_trades(
            user_context={},
            limit=2,
            session_factory=factory,
        )
    )

    assert result["count"] == 2

    assert [
        trade["broker_order_id"]
        for trade
        in result["trades"]
    ] == [
        "RECENT-3",
        "RECENT-2",
    ]


def test_trade_journal_api_routes(
    monkeypatch,
):
    monkeypatch.setattr(
        route_module,
        "get_trade_journal_summary",
        lambda **kwargs: {
            "available": True,
            "total_trades": 7,
        },
    )

    monkeypatch.setattr(
        route_module,
        "get_trade_journal_trades",
        lambda **kwargs: {
            "available": True,
            "count": 1,
            "trades": [
                {
                    "broker_order_id":
                        "API-1",
                }
            ],
        },
    )

    app = FastAPI()

    app.include_router(
        route_module.router,
    )

    app.dependency_overrides[
        route_module.
        get_authenticated_user
    ] = lambda: {
        "role": "OWNER",
    }

    client = TestClient(
        app
    )

    summary = client.get(
        "/api/trade-journal/summary"
    )

    assert summary.status_code == 200

    assert (
        summary.json()[
            "total_trades"
        ]
        == 7
    )

    trades = client.get(
        "/api/trade-journal/trades?limit=10"
    )

    assert trades.status_code == 200

    assert (
        trades.json()[
            "trades"
        ][0][
            "broker_order_id"
        ]
        == "API-1"
    )


def test_beta_reporting_excludes_legacy_rows(
    monkeypatch,
):
    import bxk_app.services.trade_journal_service as journal_service

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from bxk_app.database import Base
    from bxk_app.db_models import (
        TradeJournal,
        User,
        UserRole,
    )

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with factory() as session:
        beta_user = User(
            username="beta_journal",
            email="beta_journal@example.com",
            password_hash="unused",
            role=UserRole.BETA,
            is_active=True,
            must_change_password=False,
        )

        owner_user = User(
            username="owner_journal",
            email="owner_journal@example.com",
            password_hash="unused",
            role=UserRole.OWNER,
            is_active=True,
            must_change_password=False,
        )

        session.add_all([
            beta_user,
            owner_user,
        ])

        session.commit()
        session.refresh(beta_user)
        session.refresh(owner_user)

        session.add_all([
            TradeJournal(
                user_id=beta_user.id,
                broker_order_id="BETA-ONLY",
                status="SUBMITTED",
            ),
            TradeJournal(
                user_id=owner_user.id,
                broker_order_id="OWNER-ONLY",
                status="SUBMITTED",
            ),
            TradeJournal(
                user_id=None,
                broker_order_id="LEGACY-ONLY",
                status="SUBMITTED",
            ),
        ])

        session.commit()

        beta_id = str(beta_user.id)
        owner_id = str(owner_user.id)

    monkeypatch.setattr(
        journal_service,
        "database_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        journal_service,
        "get_session_factory",
        lambda: factory,
    )

    beta_rows = (
        journal_service
        ._journal_reporting_rows(
            user_context={
                "user_id": beta_id,
                "role": "BETA",
            }
        )
    )

    beta_ids = {
        row.broker_order_id
        for row in beta_rows
    }

    assert beta_ids == {
        "BETA-ONLY",
    }

    owner_rows = (
        journal_service
        ._journal_reporting_rows(
            user_context={
                "user_id": owner_id,
                "role": "OWNER",
            }
        )
    )

    owner_ids = {
        row.broker_order_id
        for row in owner_rows
    }

    assert owner_ids == {
        "OWNER-ONLY",
        "LEGACY-ONLY",
    }


def test_trade_journal_summary_and_trades_use_authenticated_user(
    monkeypatch,
):
    captured = {
        "summary": None,
        "trades": None,
    }

    monkeypatch.setattr(
        route_module,
        "get_trade_journal_summary",
        lambda **kwargs: (
            captured.__setitem__(
                "summary",
                kwargs["user_context"],
            )
            or {
                "available": True,
            }
        ),
    )

    monkeypatch.setattr(
        route_module,
        "get_trade_journal_trades",
        lambda **kwargs: (
            captured.__setitem__(
                "trades",
                kwargs["user_context"],
            )
            or {
                "available": True,
                "count": 0,
                "trades": [],
            }
        ),
    )

    app = FastAPI()

    app.include_router(
        route_module.router,
    )

    app.dependency_overrides[
        route_module.get_authenticated_user
    ] = lambda: {
        "user_id": "beta-user-id",
        "role": "BETA",
    }

    client = TestClient(app)

    summary = client.get(
        "/api/trade-journal/summary"
    )

    trades = client.get(
        "/api/trade-journal/trades"
    )

    assert summary.status_code == 200
    assert trades.status_code == 200

    assert (
        captured["summary"]["role"]
        == "BETA"
    )

    assert (
        captured["trades"]["role"]
        == "BETA"
    )
