import os
import smtplib
import ssl
from email.message import EmailMessage


def send_temporary_password_email(
    recipient: str,
    temporary_password: str,
    *,
    expires_minutes: int = 15,
):
    host = str(
        os.getenv("BXK_SMTP_HOST", "")
    ).strip()

    port = int(
        os.getenv("BXK_SMTP_PORT", "587")
    )

    username = str(
        os.getenv("BXK_SMTP_USERNAME", "")
    ).strip()

    password = str(
        os.getenv("BXK_SMTP_PASSWORD", "")
    )

    from_address = str(
        os.getenv(
            "BXK_SMTP_FROM",
            username,
        )
    ).strip()

    mode = str(
        os.getenv(
            "BXK_SMTP_MODE",
            "starttls",
        )
    ).strip().lower()

    if not host or not from_address:
        raise RuntimeError(
            "BXK outbound email is not configured."
        )

    message = EmailMessage()
    message["Subject"] = (
        "BXK Trader Pro temporary password"
    )
    message["From"] = from_address
    message["To"] = recipient

    message.set_content(
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

    context = ssl.create_default_context()

    if mode == "ssl":
        with smtplib.SMTP_SSL(
            host,
            port,
            context=context,
            timeout=15,
        ) as client:
            if username:
                client.login(
                    username,
                    password,
                )
            client.send_message(message)

        return True

    with smtplib.SMTP(
        host,
        port,
        timeout=15,
    ) as client:
        if mode == "starttls":
            client.starttls(
                context=context
            )

        if username:
            client.login(
                username,
                password,
            )

        client.send_message(message)

    return True
