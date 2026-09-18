from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid

import pytest

from bxk_app.db_models.sms_consent import (
    SmsConsent,
)
from bxk_app.db_models.user import User, UserRole
from bxk_app.services.sms_consent_service import (
    SMS_CONSENT_VERSION,
    has_active_sms_consent,
    get_user_sms_subscription,
    list_active_sms_subscriptions,
    normalize_sms_phone,
    provision_sms_phone,
    record_user_sms_consent,
    revoke_user_sms_consent,
    record_sms_consent,
)


def make_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    SmsConsent.__table__.create(
        engine
    )

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def make_user_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    User.__table__.create(engine)
    SmsConsent.__table__.create(engine)

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def test_us_phone_is_normalized_to_e164():
    assert (
        normalize_sms_phone(
            "(252) 318-7111"
        )
        == "+12523187111"
    )


def test_invalid_phone_is_rejected():
    with pytest.raises(
        ValueError,
        match="valid mobile number",
    ):
        normalize_sms_phone(
            "123"
        )


def test_consent_is_persisted():
    factory = make_factory()

    result = record_sms_consent(
        "(252) 318-7111",
        session_factory=factory,
    )

    assert result["phone"] == "***7111"

    assert (
        result["consent_version"]
        == SMS_CONSENT_VERSION
    )

    assert has_active_sms_consent(
        "+12523187111",
        session_factory=factory,
    ) is True

    with factory() as session:
        record = session.get(
            SmsConsent,
            "+12523187111",
        )

        assert record is not None
        assert record.is_active is True

        assert (
            record.consent_version
            == SMS_CONSENT_VERSION
        )

        assert (
            "Reply STOP to opt out"
            in record.consent_text
        )


def test_user_phone_is_pending_until_user_consents():
    factory = make_user_factory()
    user_id = uuid.uuid4()

    with factory() as session:
        session.add(
            User(
                id=user_id,
                username="kdixon",
                email="kdixon@example.com",
                password_hash="hash",
                role=UserRole.BETA,
                is_active=True,
            )
        )
        session.commit()

    pending = provision_sms_phone(
        "KDIXON",
        "5553271020",
        session_factory=factory,
    )

    assert pending == {
        "username": "kdixon",
        "phone": "***1020",
        "enabled": False,
    }

    status = get_user_sms_subscription(
        user_id,
        session_factory=factory,
    )

    assert status["phone_configured"] is True
    assert status["consent_active"] is False
    assert status["enabled"] is False
    assert list_active_sms_subscriptions(
        session_factory=factory
    ) == []

    record_user_sms_consent(
        user_id,
        session_factory=factory,
    )

    status = get_user_sms_subscription(
        user_id,
        session_factory=factory,
    )

    assert status["consent_active"] is True
    assert status["enabled"] is True

    subscriptions = list_active_sms_subscriptions(
        session_factory=factory
    )

    assert len(subscriptions) == 1
    assert (
        subscriptions[0]["user_context"]
        ["username"]
        == "kdixon"
    )
    assert (
        subscriptions[0]["phone_e164"]
        == "+15553271020"
    )

    revoke_user_sms_consent(
        user_id,
        session_factory=factory,
    )

    assert get_user_sms_subscription(
        user_id,
        session_factory=factory,
    )["enabled"] is False
