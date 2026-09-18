import re
import uuid
import json
import os
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
from bxk_app.db_models.user import User, UserRole
from sqlalchemy import select


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
    user_id: str | uuid.UUID | None = None,
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

    parsed_user_id = None

    if user_id not in (None, ""):
        try:
            parsed_user_id = (
                user_id
                if isinstance(user_id, uuid.UUID)
                else uuid.UUID(str(user_id))
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid user ID."
            ) from exc

    with factory() as session:
        user = None

        if parsed_user_id is not None:
            user = session.get(
                User,
                parsed_user_id,
            )

            if user is None or not user.is_active:
                raise ValueError(
                    "Active user account not found."
                )

            assigned_user = session.scalar(
                select(User).where(
                    User.sms_phone_e164
                    == normalized,
                    User.id != parsed_user_id,
                )
            )

            if assigned_user is not None:
                raise ValueError(
                    "This mobile number is already "
                    "assigned to another BXK account."
                )

        consent = session.get(
            SmsConsent,
            normalized,
        )

        if consent is None:
            consent = SmsConsent(
                phone_e164=normalized,
                user_id=parsed_user_id,
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
            if (
                parsed_user_id is not None
                and consent.user_id is not None
                and consent.user_id
                != parsed_user_id
            ):
                raise ValueError(
                    "This mobile number is already "
                    "assigned to another BXK account."
                )

            if parsed_user_id is not None:
                consent.user_id = parsed_user_id

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

        if user is not None:
            old_phone = str(
                user.sms_phone_e164 or ""
            ).strip()

            if old_phone and old_phone != normalized:
                old_consent = session.get(
                    SmsConsent,
                    old_phone,
                )

                if old_consent is not None:
                    old_consent.is_active = False
                    old_consent.revoked_at = now

            user.sms_phone_e164 = normalized
            user.sms_alerts_enabled = True

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


def record_user_sms_consent(
    user_id: str | uuid.UUID,
    phone_number: str | None = None,
    *,
    session_factory=None,
):
    factory = (
        session_factory
        or get_session_factory()
    )

    parsed_user_id = (
        user_id
        if isinstance(user_id, uuid.UUID)
        else uuid.UUID(str(user_id))
    )

    selected_phone = str(
        phone_number or ""
    ).strip()

    if not selected_phone:
        with factory() as session:
            user = session.get(
                User,
                parsed_user_id,
            )

            if user is None or not user.is_active:
                raise ValueError(
                    "Active user account not found."
                )

            selected_phone = str(
                user.sms_phone_e164 or ""
            ).strip()

    if not selected_phone:
        raise ValueError(
            "Mobile phone number is required."
        )

    return record_sms_consent(
        selected_phone,
        user_id=parsed_user_id,
        session_factory=factory,
    )


def provision_sms_phone(
    username: str,
    phone_number: str,
    *,
    session_factory=None,
):
    """Assign a pending phone without recording consent."""
    normalized = normalize_sms_phone(
        phone_number
    )

    username_value = str(
        username or ""
    ).strip()

    if not username_value:
        raise ValueError("Username is required.")

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        user = session.scalar(
            select(User).where(
                User.username.ilike(
                    username_value
                )
            )
        )

        if user is None:
            raise LookupError("User not found.")

        existing = session.scalar(
            select(User).where(
                User.sms_phone_e164
                == normalized,
                User.id != user.id,
            )
        )

        if existing is not None:
            raise ValueError(
                "This mobile number is already "
                "assigned to another BXK account."
            )

        user.sms_phone_e164 = normalized
        user.sms_alerts_enabled = False
        session.commit()

        return {
            "username": user.username,
            "phone": mask_sms_phone(normalized),
            "enabled": False,
        }


def provision_sms_phones_from_environment(
    *,
    session_factory=None,
) -> list[dict]:
    """
    Apply one-time pending phone assignments supplied
    by an operator. Assignments never enable alerts or
    create consent records.
    """
    raw = str(
        os.getenv(
            "BXK_SMS_PENDING_ASSIGNMENTS",
            "",
        )
        or ""
    ).strip()

    if not raw:
        return []

    try:
        assignments = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "BXK_SMS_PENDING_ASSIGNMENTS must be "
            "a JSON object."
        ) from exc

    if not isinstance(assignments, dict):
        raise RuntimeError(
            "BXK_SMS_PENDING_ASSIGNMENTS must be "
            "a JSON object."
        )

    results = []

    for username, phone_number in assignments.items():
        results.append(
            provision_sms_phone(
                username,
                phone_number,
                session_factory=session_factory,
            )
        )

    return results


def get_user_sms_subscription(
    user_id: str | uuid.UUID,
    *,
    session_factory=None,
):
    parsed_user_id = (
        user_id
        if isinstance(user_id, uuid.UUID)
        else uuid.UUID(str(user_id))
    )

    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        user = session.get(User, parsed_user_id)

        if user is None:
            raise LookupError("User not found.")

        phone = str(
            user.sms_phone_e164 or ""
        ).strip()

        consent_active = False

        if phone:
            consent = session.get(
                SmsConsent,
                phone,
            )
            consent_active = bool(
                consent
                and consent.user_id == user.id
                and consent.is_active
                and consent.revoked_at is None
            )

        return {
            "phone": (
                mask_sms_phone(phone)
                if phone
                else None
            ),
            "phone_configured": bool(phone),
            "consent_active": consent_active,
            "enabled": bool(
                user.sms_alerts_enabled
                and consent_active
            ),
        }


def revoke_user_sms_consent(
    user_id: str | uuid.UUID,
    *,
    session_factory=None,
):
    parsed_user_id = (
        user_id
        if isinstance(user_id, uuid.UUID)
        else uuid.UUID(str(user_id))
    )

    factory = (
        session_factory
        or get_session_factory()
    )

    now = datetime.now(timezone.utc)

    with factory() as session:
        user = session.get(User, parsed_user_id)

        if user is None:
            raise LookupError("User not found.")

        phone = str(
            user.sms_phone_e164 or ""
        ).strip()

        if phone:
            consent = session.get(
                SmsConsent,
                phone,
            )

            if consent is not None:
                consent.is_active = False
                consent.revoked_at = now

        user.sms_alerts_enabled = False
        session.commit()

        return {
            "phone": (
                mask_sms_phone(phone)
                if phone
                else None
            ),
            "enabled": False,
        }


def list_active_sms_subscriptions(
    *,
    session_factory=None,
    include_owner: bool = False,
) -> list[dict]:
    factory = (
        session_factory
        or get_session_factory()
    )

    with factory() as session:
        statement = (
            select(User, SmsConsent)
            .join(
                SmsConsent,
                SmsConsent.phone_e164
                == User.sms_phone_e164,
            )
            .where(
                User.is_active.is_(True),
                User.sms_alerts_enabled.is_(True),
                SmsConsent.is_active.is_(True),
                SmsConsent.revoked_at.is_(None),
                SmsConsent.user_id == User.id,
            )
        )

        rows = session.execute(statement).all()
        results = []

        for user, consent in rows:
            role = (
                user.role.value
                if isinstance(user.role, UserRole)
                else str(user.role)
            )

            if (
                not include_owner
                and role.upper()
                == UserRole.OWNER.value
            ):
                continue

            results.append(
                {
                    "user_context": {
                        "user_id": str(user.id),
                        "username": user.username,
                        "role": role,
                        "broker_oauth_enabled": bool(
                            user.broker_oauth_enabled
                        ),
                        "auth_source": "DATABASE",
                    },
                    "phone_e164":
                        consent.phone_e164,
                }
            )

        return results


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
