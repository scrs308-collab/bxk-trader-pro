from pathlib import Path
import uuid
from datetime import datetime, timezone

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


def _utc(value):
    """
    SQLite drops timezone metadata from DateTime
    columns during these in-memory tests.
    Normalize before comparing timestamps.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _journal_for(
    factory,
    broker_order_id,
):
    with factory() as session:
        return session.execute(
            select(
                TradeJournal
            ).where(
                TradeJournal.broker_order_id
                == broker_order_id
            )
        ).scalar_one()


def test_live_observation_tracks_extremes(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-400",
        broker_status="RECEIVED",
        order=sample_order(),
        reconciliation={},
        session_factory=factory,
    )

    t1 = datetime(
        2026,
        9,
        2,
        14,
        0,
        tzinfo=timezone.utc,
    )

    t2 = datetime(
        2026,
        9,
        2,
        17,
        0,
        tzinfo=timezone.utc,
    )

    service.observe_open_position(
        {
            "broker_order_id":
                "ORDER-400",
            "broker_linked": True,
            "pnl": 125,
            "pnl_is_estimate": False,
            "spx_price": 6575,
            "put_distance": 75,
            "call_distance": 75,
            "sell_put": 6500,
            "sell_call": 6650,
        },
        observed_at=t1,
        session_factory=factory,
    )

    service.observe_open_position(
        {
            "broker_order_id":
                "ORDER-400",
            "broker_linked": True,
            "pnl": -350,
            "pnl_is_estimate": False,
            "spx_price": 6642,
            "put_distance": 142,
            "call_distance": 8,
            "sell_put": 6500,
            "sell_call": 6650,
        },
        observed_at=t2,
        session_factory=factory,
    )

    journal = _journal_for(
        factory,
        "ORDER-400",
    )

    assert journal.status == "OPEN"
    assert journal.best_open_pnl == 125
    assert journal.worst_open_pnl == -350
    assert journal.min_short_cushion == 8
    assert (
        journal.worst_threat_state
        == "RED"
    )
    assert _utc(journal.first_orange_at) == t2
    assert _utc(journal.first_red_at) == t2
    assert journal.first_critical_at is None


def test_critical_first_observation_sets_thresholds(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-401",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    observed = datetime(
        2026,
        9,
        2,
        18,
        0,
        tzinfo=timezone.utc,
    )

    result = service.observe_open_position(
        {
            "broker_order_id":
                "ORDER-401",
            "broker_linked": True,
            "pnl": -900,
            "pnl_is_estimate": False,
            "spx_price": 6653,
            "put_distance": 153,
            "call_distance": -3,
            "sell_put": 6500,
            "sell_call": 6650,
        },
        observed_at=observed,
        session_factory=factory,
    )

    assert (
        result["worst_threat_state"]
        == "CRITICAL"
    )

    journal = _journal_for(
        factory,
        "ORDER-401",
    )

    assert journal.min_short_cushion == -3
    assert _utc(journal.first_orange_at) == observed
    assert _utc(journal.first_red_at) == observed
    assert _utc(journal.first_critical_at) == observed


def test_estimated_pnl_is_not_learning_data(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-402",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    result = service.observe_open_position(
        {
            "broker_order_id":
                "ORDER-402",
            "broker_linked": True,
            "pnl": -1850,
            "pnl_is_estimate": True,
            "spx_price": 6635,
            "put_distance": 135,
            "call_distance": 15,
            "sell_put": 6500,
            "sell_call": 6650,
        },
        session_factory=factory,
    )

    journal = _journal_for(
        factory,
        "ORDER-402",
    )

    assert result["pnl_recorded"] is False
    assert journal.best_open_pnl is None
    assert journal.worst_open_pnl is None
    assert journal.min_short_cushion == 15
    assert (
        journal.worst_threat_state
        == "ORANGE"
    )


def test_repeated_observation_is_idempotent(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-403",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    position = {
        "broker_order_id":
            "ORDER-403",
        "broker_linked": True,
        "pnl": 100,
        "pnl_is_estimate": False,
        "spx_price": 6575,
        "put_distance": 75,
        "call_distance": 75,
        "sell_put": 6500,
        "sell_call": 6650,
    }

    first = service.observe_open_position(
        position,
        session_factory=factory,
    )

    second = service.observe_open_position(
        position,
        session_factory=factory,
    )

    assert first["changed"] is True
    assert second["changed"] is False


def test_shared_classifier_and_position_hook():
    alert_source = Path(
        "bxk_app/services/"
        "position_alert_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    position_source = Path(
        "bxk_app/services/"
        "position_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from bxk_app.services."
        "position_threat_service import"
        in alert_source
    )

    assert (
        "def classify_position_threat("
        not in alert_source
    )

    assert (
        "observe_linked_positions("
        in position_source
    )

def test_records_overnight_carry_snapshot(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-CARRY-1",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    evaluated = datetime(
        2026,
        9,
        1,
        19,
        59,
        50,
        tzinfo=timezone.utc,
    )

    result = (
        service.record_overnight_carry_snapshot(
            broker_order_id="ORDER-CARRY-1",
            carry_risk={
                "available": True,
                "state": "RED",
                "decision": "DO_NOT_CARRY",
                "threatened_side": "CALL",
                "short_cushion": 27.04,
                "one_day_expected_move": 78.98,
                "expected_move_source": "VIX",
                "cushion_to_1d_em_ratio": 0.342,
            },
            evaluated_at=evaluated,
            vix1d=0.0,
            vix=16.34,
            held_overnight=True,
            session_factory=factory,
        )
    )

    assert result["recorded"] is True
    assert result["changed"] is True

    journal = _journal_for(
        factory,
        "ORDER-CARRY-1",
    )

    assert (
        _utc(journal.carry_evaluated_at)
        == evaluated
    )
    assert journal.carry_state == "RED"
    assert (
        journal.carry_decision
        == "DO_NOT_CARRY"
    )
    assert (
        journal.carry_threatened_side
        == "CALL"
    )
    assert journal.carry_short_cushion == 27.04
    assert journal.carry_expected_move == 78.98
    assert (
        journal.carry_expected_move_source
        == "VIX"
    )
    assert journal.carry_cushion_ratio == 0.342
    assert journal.carry_vix1d == 0.0
    assert journal.carry_vix == 16.34
    assert journal.held_overnight is True
    assert (
        journal.carry_snapshot["state"]
        == "RED"
    )


def test_carry_snapshot_is_write_once(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-CARRY-2",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    first = {
        "available": True,
        "state": "RED",
        "decision": "DO_NOT_CARRY",
        "threatened_side": "CALL",
        "short_cushion": 25,
        "one_day_expected_move": 80,
        "expected_move_source": "VIX",
        "cushion_to_1d_em_ratio": 0.312,
    }

    second = {
        "available": True,
        "state": "GREEN",
        "decision": "CARRY_WITH_MONITORING",
        "threatened_side": "PUT",
        "short_cushion": 100,
        "one_day_expected_move": 70,
        "expected_move_source": "VIX1D",
        "cushion_to_1d_em_ratio": 1.429,
    }

    service.record_overnight_carry_snapshot(
        broker_order_id="ORDER-CARRY-2",
        carry_risk=first,
        vix=16,
        session_factory=factory,
    )

    result = (
        service.record_overnight_carry_snapshot(
            broker_order_id="ORDER-CARRY-2",
            carry_risk=second,
            vix1d=12,
            session_factory=factory,
        )
    )

    assert result["recorded"] is True
    assert result["changed"] is False

    journal = _journal_for(
        factory,
        "ORDER-CARRY-2",
    )

    assert journal.carry_state == "RED"
    assert journal.carry_short_cushion == 25
    assert journal.carry_cushion_ratio == 0.312
    assert journal.carry_vix == 16
    assert journal.carry_vix1d is None


def test_unavailable_carry_risk_not_recorded(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-CARRY-3",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    result = (
        service.record_overnight_carry_snapshot(
            broker_order_id="ORDER-CARRY-3",
            carry_risk={
                "available": False,
                "reason_code":
                    "CARRY_RISK_INPUT_UNAVAILABLE",
            },
            session_factory=factory,
        )
    )

    assert result["recorded"] is False
    assert result["changed"] is False

    journal = _journal_for(
        factory,
        "ORDER-CARRY-3",
    )

    assert journal.carry_evaluated_at is None
    assert journal.carry_state is None

def test_records_next_open_outcome(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )
    service.record_submitted_trade(
        broker_order_id="ORDER-NEXT-1",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    service.record_overnight_carry_snapshot(
        broker_order_id="ORDER-NEXT-1",
        carry_risk={
            "available": True,
            "state": "RED",
            "decision": "DO_NOT_CARRY",
            "threatened_side": "CALL",
            "short_cushion": 75,
            "one_day_expected_move": 80,
            "expected_move_source": "VIX",
            "cushion_to_1d_em_ratio": 0.938,
            "spx_close": 6575,
            "baseline_trading_date":
                "2026-09-01",
        },
        held_overnight=True,
        session_factory=factory,
    )

    evaluated = datetime(
        2026,
        9,
        2,
        13,
        31,
        tzinfo=timezone.utc,
    )

    result = service.record_next_open_outcomes(
        spx_open=6660,
        trading_date="2026-09-02",
        evaluated_at=evaluated,
        session_factory=factory,
    )

    assert result["updated"] == 1

    journal = _journal_for(
        factory,
        "ORDER-NEXT-1",
    )

    assert (
        _utc(journal.next_open_evaluated_at)
        == evaluated
    )
    assert journal.next_open_spx == 6660
    assert journal.next_open_gap_points == 85
    assert (
        journal.next_open_short_breached
        is True
    )


def test_next_open_nonbreach_recorded(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )
    service.record_submitted_trade(
        broker_order_id="ORDER-NEXT-2",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    service.record_overnight_carry_snapshot(
        broker_order_id="ORDER-NEXT-2",
        carry_risk={
            "available": True,
            "state": "GREEN",
            "decision":
                "CARRY_WITH_MONITORING",
            "threatened_side": "PUT",
            "short_cushion": 75,
            "one_day_expected_move": 60,
            "expected_move_source": "VIX1D",
            "cushion_to_1d_em_ratio": 1.25,
            "spx_close": 6575,
            "baseline_trading_date":
                "2026-09-01",
        },
        held_overnight=True,
        session_factory=factory,
    )

    result = service.record_next_open_outcomes(
        spx_open=6600,
        trading_date="2026-09-02",
        session_factory=factory,
    )

    assert result["updated"] == 1

    journal = _journal_for(
        factory,
        "ORDER-NEXT-2",
    )

    assert journal.next_open_gap_points == 25
    assert (
        journal.next_open_short_breached
        is False
    )


def test_same_day_is_not_next_open(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-NEXT-3",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    service.record_overnight_carry_snapshot(
        broker_order_id="ORDER-NEXT-3",
        carry_risk={
            "available": True,
            "state": "RED",
            "decision": "DO_NOT_CARRY",
            "threatened_side": "CALL",
            "short_cushion": 25,
            "one_day_expected_move": 80,
            "expected_move_source": "VIX",
            "cushion_to_1d_em_ratio": 0.312,
            "spx_close": 6575,
            "baseline_trading_date":
                "2026-09-01",
        },
        held_overnight=True,
        session_factory=factory,
    )

    result = service.record_next_open_outcomes(
        spx_open=6580,
        trading_date="2026-09-01",
        session_factory=factory,
    )

    assert result["updated"] == 0

    journal = _journal_for(
        factory,
        "ORDER-NEXT-3",
    )

    assert journal.next_open_spx is None
    assert (
        journal.next_open_short_breached
        is None
    )

def test_trade_row_includes_overnight_learning():
    class FakeJournal:
        def __getattr__(self, name):
            return None

    journal = FakeJournal()

    journal.id = "ROW-OVERNIGHT-1"

    journal.carry_state = "RED"
    journal.carry_decision = "DO_NOT_CARRY"
    journal.carry_threatened_side = "CALL"
    journal.carry_short_cushion = 27.04
    journal.carry_expected_move = 78.98
    journal.carry_expected_move_source = "VIX"
    journal.carry_cushion_ratio = 0.342
    journal.carry_vix1d = 0.0
    journal.carry_vix = 16.34
    journal.held_overnight = True

    journal.next_open_spx = 7650.0
    journal.next_open_gap_points = -22.96
    journal.next_open_short_breached = False

    row = service._journal_trade_row(
        journal
    )

    assert row["carry_state"] == "RED"
    assert (
        row["carry_decision"]
        == "DO_NOT_CARRY"
    )
    assert (
        row["carry_threatened_side"]
        == "CALL"
    )
    assert row["carry_short_cushion"] == 27.04
    assert row["carry_expected_move"] == 78.98
    assert (
        row["carry_expected_move_source"]
        == "VIX"
    )
    assert row["carry_cushion_ratio"] == 0.342
    assert row["carry_vix1d"] == 0.0
    assert row["carry_vix"] == 16.34
    assert row["held_overnight"] is True

    assert row["next_open_spx"] == 7650.0
    assert row["next_open_gap_points"] == -22.96
    assert (
        row["next_open_short_breached"]
        is False
    )

def test_trade_report_can_include_open_rows(
    monkeypatch,
):
    factory = make_factory()

    monkeypatch.setattr(
        service,
        "database_configured",
        lambda: True,
    )

    service.record_submitted_trade(
        broker_order_id="ORDER-REPORT-OPEN",
        broker_status="FILLED",
        order=sample_order(),
        reconciliation={
            "average_fill_price": 2.70,
        },
        session_factory=factory,
    )

    default_result = (
        service.get_trade_journal_trades(
            limit=100,
            session_factory=factory,
        )
    )

    assert (
        default_result["include_open"]
        is False
    )

    assert not any(
        row["broker_order_id"]
        == "ORDER-REPORT-OPEN"
        for row in default_result["trades"]
    )

    open_result = (
        service.get_trade_journal_trades(
            limit=100,
            include_open=True,
            session_factory=factory,
        )
    )

    assert (
        open_result["include_open"]
        is True
    )

    row = next(
        row
        for row in open_result["trades"]
        if row["broker_order_id"]
        == "ORDER-REPORT-OPEN"
    )

    assert row["status"] in {
        "SUBMITTED",
        "OPEN",
    }
