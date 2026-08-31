from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app.db_models.overnight_alert_state import (
    OvernightAlertState,
)
from bxk_app.services.position_alert_service import (
    classify_position_threat,
    process_position_threat,
)


def make_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    OvernightAlertState.__table__.create(
        engine
    )

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def position(
    *,
    spx=6050,
    short_put=6000,
    short_call=6100,
):
    return {
        "expiration": "2026-09-01",
        "spx_price": spx,
        "sell_put": short_put,
        "sell_call": short_call,
        "put_distance":
            spx - short_put,
        "call_distance":
            short_call - spx,
    }


def test_safe_position_is_green():
    risk = classify_position_threat(
        position()
    )

    assert risk["state"] == "GREEN"


def test_first_orange_state_sends_warning():
    factory = make_factory()
    sent = []

    result = process_position_threat(
        position(spx=6018),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 1
    assert "DAYTIME WARNING" in sent[0]
    assert "PUT short: 6000" in sent[0]


def test_orange_to_red_escalation_sends():
    factory = make_factory()
    sent = []

    process_position_threat(
        position(spx=6018),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_position_threat(
        position(spx=6008),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 2
    assert "DAYTIME DEFEND" in sent[-1]


def test_direct_green_to_red_sends():
    factory = make_factory()
    sent = []

    process_position_threat(
        position(spx=6050),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_position_threat(
        position(spx=6007),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 1
    assert "DAYTIME DEFEND" in sent[0]


def test_same_red_state_does_not_repeat():
    factory = make_factory()
    sent = []

    process_position_threat(
        position(spx=6007),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_position_threat(
        position(spx=6006),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["alert_sent"] is False
    assert len(sent) == 1


def test_green_rearms_future_warning():
    factory = make_factory()
    sent = []

    process_position_threat(
        position(spx=6018),
        session_factory=factory,
        send_func=sent.append,
    )

    process_position_threat(
        position(spx=6050),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_position_threat(
        position(spx=6017),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 2


def test_short_strike_breach_is_critical():
    factory = make_factory()
    sent = []

    result = process_position_threat(
        position(spx=5998),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 1
    assert "DAYTIME CRITICAL" in sent[0]
    assert "SHORT STRIKE BREACHED" in sent[0]


def test_call_side_threat_is_identified():
    factory = make_factory()
    sent = []

    result = process_position_threat(
        position(spx=6087),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert result["side"] == "CALL"
    assert "CALL short: 6100" in sent[0]
from pathlib import Path


def test_daytime_alert_monitor_is_started_by_app():
    source = Path(
        "bxk_app/main.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "run_daytime_alert_monitor()"
        in source
    )

    assert (
        'name="bxk-daytime-sms-alerts"'
        in source
    )

    assert (
        "daytime_alert_task.cancel()"
        in source
    )

    assert (
        "await daytime_alert_task"
        in source
    )
