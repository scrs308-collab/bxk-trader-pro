from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app.db_models.overnight_alert_state import (
    OvernightAlertState,
)
from bxk_app.services.overnight_alert_service import (
    ALERT_SCOPE,
    process_overnight_risk,
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


def payload(
    state,
    *,
    available=True,
    active=True,
):
    return {
        "available": available,
        "state": state,
        "recommendation": (
            "MONITOR"
            if state != "GREEN"
            else "HOLD"
        ),
        "reason_code":
            f"TEST_{state}",
        "position_count": (
            1 if available else 0
        ),
        "session": {
            "overnight_monitoring_active":
                active,
        },
        "positions": [
            {
                "position": {
                    "sell_put": 6000,
                    "sell_call": 6100,
                },
                "risk": {
                    "state": state,
                    "threatened_side":
                        "PUT",
                },
            }
        ],
    }


def read_state(factory):
    with factory() as session:
        return session.get(
            OvernightAlertState,
            ALERT_SCOPE,
        )


def test_first_state_becomes_baseline():
    factory = make_factory()
    sent = []

    result = process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "BASELINE"
    assert sent == []
    assert read_state(factory).state == "GREEN"


def test_same_state_is_not_repeated():
    factory = make_factory()
    sent = []

    process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "UNCHANGED"
    assert sent == []


def test_worsening_states_send_alerts():
    factory = make_factory()
    sent = []

    for state in [
        "GREEN",
        "YELLOW",
        "ORANGE",
        "RED",
    ]:
        process_overnight_risk(
            payload(state),
            session_factory=factory,
            send_func=sent.append,
        )

    assert len(sent) == 3

    assert "GREEN -> YELLOW" in sent[0]
    assert "YELLOW -> ORANGE" in sent[1]
    assert "ORANGE -> RED" in sent[2]


def test_intermediate_recovery_does_not_text():
    factory = make_factory()
    sent = []

    process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    process_overnight_risk(
        payload("RED"),
        session_factory=factory,
        send_func=sent.append,
    )

    sent.clear()

    result = process_overnight_risk(
        payload("ORANGE"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert (
        result["action"]
        == "STATE_UPDATED"
    )

    assert sent == []


def test_return_to_green_sends_recovery():
    factory = make_factory()
    sent = []

    process_overnight_risk(
        payload("YELLOW"),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 1
    assert (
        "BXK OVERNIGHT RECOVERY"
        in sent[0]
    )


def test_inactive_monitoring_resets_baseline():
    factory = make_factory()
    sent = []

    process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    result = process_overnight_risk(
        payload(
            "YELLOW",
            active=False,
        ),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "IDLE"
    assert read_state(factory).state is None

    sent.clear()

    result = process_overnight_risk(
        payload("RED"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "BASELINE"
    assert sent == []


def test_failed_sms_is_retried():
    factory = make_factory()

    process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=lambda message: None,
    )

    def fail(message):
        raise RuntimeError(
            "simulated SMS failure"
        )

    try:
        process_overnight_risk(
            payload("YELLOW"),
            session_factory=factory,
            send_func=fail,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Expected SMS failure."
        )

    assert read_state(factory).state == "GREEN"

    sent = []

    result = process_overnight_risk(
        payload("YELLOW"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert len(sent) == 1


def test_temporary_unavailable_preserves_baseline_and_next_worsening_alerts():
    factory = make_factory()
    sent = []

    process_overnight_risk(
        payload("GREEN"),
        session_factory=factory,
        send_func=sent.append,
    )

    unavailable = payload(
        None,
        available=False,
        active=True,
    )
    unavailable["reason_code"] = (
        "OVERNIGHT_REFERENCE_UNAVAILABLE"
    )

    result = process_overnight_risk(
        unavailable,
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "UNAVAILABLE"
    assert read_state(factory).state == "GREEN"
    assert sent == []

    result = process_overnight_risk(
        payload("YELLOW"),
        session_factory=factory,
        send_func=sent.append,
    )

    assert result["action"] == "ALERTED"
    assert read_state(factory).state == "YELLOW"
    assert len(sent) == 1
    assert "GREEN -> YELLOW" in sent[0]
