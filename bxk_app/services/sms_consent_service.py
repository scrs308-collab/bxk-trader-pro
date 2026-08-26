import re
from datetime import (
    datetime,
    timezone,
)

from bxk_app.database import (
    get_session_factory,
)
from bxk_app.db_models.sms_consent import (
    SmsConsent,
)


SMS_CONSENT_VERSION = "2026-08-26-v1"

SMS_CONSENT_SOURCE = "PUBLIC_WEB_FORM"

SMS_CONSENT_DISCLOSURE = (
    "By checking this box, I agree to receive "
    "recurring transactional SMS alerts from "
    "BXK Trader Pro regarding monitored trading "
    "positions, overnight risk changes, and "
    "recovery notifications. Message frequency "
    "varies. Message and data rates may apply. "
    "Reply STOP to opt out and HELP for help. "
    "SMS consent is optional and is not required "
    "to use BXK Trader Pro. Privacy Policy: "
    "https://app.bxktraderpro.com/privacy "
    "Terms & Conditions: "
    "https://app.bxktraderpro.com/terms"
)


def normalize_sms_phone(
    value: str,
) -> str:
    raw = str(
        value or ""
    ).strip()

    if not raw:
        raise ValueError(
            "Mobile phone number is required."
        )

    has_plus = raw.startswith("+")

    digits = re.sub(
        r"\D",
        "",
        raw,
    )

    if (
        not has_plus
        and len(digits) == 10
    ):
        digits = "1" + digits

    if (
        not has_plus
        and len(digits) == 11
        and digits.startswith("1")
    ):
        has_plus = True

    if has_plus:
        normalized = "+" + digits
    elif (
        len(digits) == 11
        and digits.startswith("1")
    ):
        normalized = "+" + digits
    else:
        raise ValueError(
            "Enter a valid mobile number."
        )

    if not re.fullmatch(
        r"\+[1-9]\d{7,14}",
        normalized,
    ):
        raise ValueError(
            "Enter a valid mobile number."
        )

    return normalized


def mask_sms_phone(
    phone_e164: str,
) -> str:
    normalized = normalize_sms_phone(
        phone_e164
    )

    return (
        "***"
        + normalized[-4:]
    )


def record_sms_consent(
    phone_number: str,
    *,
    session_factory=None,
):
    normalized = normalize_sms_phone(
        phone_number
    )

    factory = (
        session_factory
        or get_session_factory()
    )

    now = datetime.now(
        timezone.utc
    )

    with factory() as session:
        consent = session.get(
            SmsConsent,
            normalized,
        )

        if consent is None:
            consent = SmsConsent(
                phone_e164=normalized,
                is_active=True,
                consent_version=
                    SMS_CONSENT_VERSION,
                consent_text=
                    SMS_CONSENT_DISCLOSURE,
                consent_source=
                    SMS_CONSENT_SOURCE,
                consented_at=now,
                revoked_at=None,
            )

            session.add(
                consent
            )

        else:
            consent.is_active = True
            consent.consent_version = (
                SMS_CONSENT_VERSION
            )
            consent.consent_text = (
                SMS_CONSENT_DISCLOSURE
            )
            consent.consent_source = (
                SMS_CONSENT_SOURCE
            )
            consent.consented_at = now
            consent.revoked_at = None

        session.commit()

    return {
        "phone":
            mask_sms_phone(
                normalized
            ),
        "consent_version":
            SMS_CONSENT_VERSION,
        "consented_at":
            now.isoformat(),
    }


def has_active_sms_consent(
    phone_number: str,
    *,
    session_factory=None,
) -> bool:
    normalized = normalize_sms_phone(
        phone_number
    )

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        consent = session.get(
            SmsConsent,
            normalized,
        )

        return bool(
            consent
            and consent.is_active
            and consent.revoked_at is None
        )
