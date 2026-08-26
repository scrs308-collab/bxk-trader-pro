from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from bxk_app.db_models.sms_consent import (
    SmsConsent,
)
from bxk_app.services.sms_consent_service import (
    SMS_CONSENT_VERSION,
    has_active_sms_consent,
    normalize_sms_phone,
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
