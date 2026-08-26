import base64
import os
import urllib.error
import urllib.parse
import urllib.request


TWILIO_API_TEMPLATE = (
    "https://api.twilio.com/2010-04-01/"
    "Accounts/{account_sid}/Messages.json"
)


def _environment_value(name: str) -> str:
    return str(
        os.getenv(name, "")
    ).strip()


def send_sms(
    message: str,
    *,
    recipient: str | None = None,
):
    account_sid = _environment_value(
        "BXK_TWILIO_ACCOUNT_SID"
    )

    auth_token = _environment_value(
        "BXK_TWILIO_AUTH_TOKEN"
    )

    from_number = _environment_value(
        "BXK_TWILIO_FROM_NUMBER"
    )

    to_number = str(
        recipient
        or _environment_value(
            "BXK_ALERT_PHONE"
        )
    ).strip()

    body = str(
        message or ""
    ).strip()

    missing = []

    if not account_sid:
        missing.append(
            "BXK_TWILIO_ACCOUNT_SID"
        )

    if not auth_token:
        missing.append(
            "BXK_TWILIO_AUTH_TOKEN"
        )

    if not from_number:
        missing.append(
            "BXK_TWILIO_FROM_NUMBER"
        )

    if not to_number:
        missing.append(
            "BXK_ALERT_PHONE"
        )

    if missing:
        raise RuntimeError(
            "SMS configuration is incomplete: "
            + ", ".join(missing)
        )

    if not body:
        raise RuntimeError(
            "SMS message is empty."
        )

    url = TWILIO_API_TEMPLATE.format(
        account_sid=account_sid
    )

    payload = urllib.parse.urlencode(
        {
            "To": to_number,
            "From": from_number,
            "Body": body,
        }
    ).encode("utf-8")

    credentials = (
        f"{account_sid}:{auth_token}"
    ).encode("utf-8")

    authorization = (
        "Basic "
        + base64.b64encode(
            credentials
        ).decode("ascii")
    )

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization":
                authorization,
            "Content-Type":
                (
                    "application/"
                    "x-www-form-urlencoded"
                ),
            "User-Agent":
                "BXK-Trader-Pro/6.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            status = int(
                getattr(
                    response,
                    "status",
                    200,
                )
            )

            if not 200 <= status < 300:
                raise RuntimeError(
                    "Twilio rejected SMS "
                    f"with HTTP {status}."
                )

            return True

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "Twilio rejected SMS "
            f"with HTTP {exc.code}."
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Unable to reach Twilio "
            "SMS API."
        ) from exc



def send_bxk_sms(
    message: str,
    *,
    recipient: str | None = None,
):
    """
    Send a BXK-generated SMS only after
    verifying active recipient consent.

    The lower-level send_sms() function remains
    transport-only for diagnostics and isolated
    infrastructure tests.
    """
    from bxk_app.services.sms_consent_service import (
        has_active_sms_consent,
        normalize_sms_phone,
    )

    raw_recipient = str(
        recipient
        or _environment_value(
            "BXK_ALERT_PHONE"
        )
    ).strip()

    if not raw_recipient:
        raise RuntimeError(
            "SMS configuration is incomplete: "
            "BXK_ALERT_PHONE"
        )

    try:
        normalized = normalize_sms_phone(
            raw_recipient
        )
    except ValueError as exc:
        raise RuntimeError(
            "SMS recipient phone number "
            "is invalid."
        ) from exc

    try:
        consented = (
            has_active_sms_consent(
                normalized
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "SMS consent verification failed."
        ) from exc

    if not consented:
        raise RuntimeError(
            "SMS recipient has not provided "
            "active consent."
        )

    return send_sms(
        message,
        recipient=normalized,
    )
