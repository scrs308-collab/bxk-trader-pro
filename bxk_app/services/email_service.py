import json
import os
import urllib.error
import urllib.request


RESEND_API_URL = (
    "https://api.resend.com/emails"
)


def _resend_api_key():
    # Preferred dedicated variable.
    key = str(
        os.getenv(
            "BXK_RESEND_API_KEY",
            "",
        )
    ).strip()

    if key:
        return key

    # Backward-compatible with the SMTP
    # configuration already stored in Railway.
    return str(
        os.getenv(
            "BXK_SMTP_PASSWORD",
            "",
        )
    ).strip()


def send_temporary_password_email(
    recipient: str,
    temporary_password: str,
    *,
    expires_minutes: int = 15,
):
    api_key = _resend_api_key()

    from_address = str(
        os.getenv(
            "BXK_SMTP_FROM",
            "security@bxktraderpro.com",
        )
    ).strip()

    recipient = str(
        recipient or ""
    ).strip()

    if not api_key:
        raise RuntimeError(
            "Resend API key is not configured."
        )

    if not from_address:
        raise RuntimeError(
            "BXK sender address is not configured."
        )

    if not recipient:
        raise RuntimeError(
            "BXK recipient address is missing."
        )

    text = (
        "A password reset was requested for "
        "BXK Trader Pro.\n\n"
        f"Temporary password: "
        f"{temporary_password}\n\n"
        f"This password expires in "
        f"{expires_minutes} minutes and "
        "can be used only once.\n\n"
        "After signing in, change your "
        "permanent password under System > "
        "Application Access.\n\n"
        "If you did not request this reset, "
        "you may ignore this email."
    )

    payload = {
        "from": (
            "BXK Trader Pro Security "
            f"<{from_address}>"
        ),
        "to": [recipient],
        "subject": (
            "BXK Trader Pro temporary password"
        ),
        "text": text,
    }

    request = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(
            payload
        ).encode("utf-8"),
        headers={
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json",
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
                    "Resend API rejected "
                    f"email with HTTP {status}."
                )

            return True

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "Resend API rejected the "
            f"email with HTTP {exc.code}."
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Unable to reach the "
            "Resend HTTPS API."
        ) from exc
