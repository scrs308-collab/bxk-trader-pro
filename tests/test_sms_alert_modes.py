import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app.db_models.user import User, UserRole
from bxk_app.db_models.sms_alert_delivery import (
    SmsAlertDelivery,
)
from bxk_app.services.sms_alert_modes import (
    AFTER_HOURS,
    AFTER_HOURS_CRITICAL,
    ALL,
    OFF,
    daytime_delivery_decision,
    get_preferences,
    normalize_mode,
    record_delivery,
    set_mode,
    set_snooze,
)


def make_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    User.__table__.create(engine)
    SmsAlertDelivery.__table__.create(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    user_id = uuid.uuid4()

    with factory() as session:
        session.add(
            User(
                id=user_id,
                username="sms-test",
                email="sms-test@example.com",
                password_hash="test",
                role=UserRole.BETA,
                is_active=True,
            )
        )
        session.commit()

    return factory, user_id


def test_mode_defaults_and_validation():
    assert normalize_mode(None) == AFTER_HOURS
    assert normalize_mode("all") == ALL
    assert normalize_mode("off") == OFF


def test_set_mode_updates_daytime_policy():
    factory, user_id = make_factory()

    result = set_mode(
        user_id,
        AFTER_HOURS_CRITICAL,
        session_factory=factory,
    )

    assert result["alert_mode"] == AFTER_HOURS_CRITICAL
    assert result["daytime_enabled"] is True
    assert result["overnight_enabled"] is True

    result = set_mode(
        user_id,
        OFF,
        session_factory=factory,
    )

    assert result["daytime_enabled"] is False
    assert result["overnight_enabled"] is False


def test_snooze_and_resume():
    factory, user_id = make_factory()

    snoozed = set_snooze(
        user_id,
        "ONE_HOUR",
        session_factory=factory,
    )

    assert snoozed["snoozed"] is True
    assert snoozed["snoozed_until"] is not None

    resumed = set_snooze(
        user_id,
        "RESUME",
        session_factory=factory,
    )

    assert resumed["snoozed"] is False
    assert resumed["snoozed_until"] is None


def test_daytime_rate_limit_blocks_fourth_alert():
    factory, user_id = make_factory()

    set_mode(
        user_id,
        ALL,
        session_factory=factory,
    )

    for state in ["ORANGE", "RED", "ORANGE"]:
        assert daytime_delivery_decision(
            user_id,
            state,
            session_factory=factory,
        )["allowed"] is True

        record_delivery(
            user_id,
            "DAYTIME",
            state,
            session_factory=factory,
        )

    decision = daytime_delivery_decision(
        user_id,
        "RED",
        session_factory=factory,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "RATE_LIMITED"


def test_critical_can_break_through_rate_limit_once():
    factory, user_id = make_factory()

    set_mode(
        user_id,
        ALL,
        session_factory=factory,
    )

    for state in ["ORANGE", "RED", "ORANGE"]:
        record_delivery(
            user_id,
            "DAYTIME",
            state,
            session_factory=factory,
        )

    decision = daytime_delivery_decision(
        user_id,
        "CRITICAL",
        session_factory=factory,
    )

    assert decision["allowed"] is True
    assert decision["reason"] == "CRITICAL_BREAKTHROUGH"

    record_delivery(
        user_id,
        "DAYTIME",
        "CRITICAL",
        session_factory=factory,
    )

    second = daytime_delivery_decision(
        user_id,
        "CRITICAL",
        session_factory=factory,
    )

    assert second["allowed"] is False
    assert second["reason"] == "RATE_LIMITED"
