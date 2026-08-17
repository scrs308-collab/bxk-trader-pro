import base64
import hashlib
import hmac
import json
import secrets
import time

from bxk_app import config
from bxk_app.services.system_settings_service import (
    verify_app_password,
)


SESSION_COOKIE_NAME = "bxk_session"
SESSION_VERSION = 1


def _b64encode(data: bytes) -> str:
    return (
        base64.urlsafe_b64encode(data)
        .decode("ascii")
        .rstrip("=")
    )


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)

    return base64.urlsafe_b64decode(
        (value + padding).encode("ascii")
    )


def auth_configuration_status():
    username_configured = bool(
        str(config.BXK_APP_USERNAME or "").strip()
    )

    password_configured = bool(
        str(config.BXK_APP_PASSWORD_HASH or "").strip()
    )

    session_secret_configured = bool(
        str(config.BXK_SESSION_SECRET or "").strip()
    )

    configured = (
        username_configured
        and password_configured
        and session_secret_configured
    )

    return {
        "enabled": bool(
            config.BXK_AUTH_ENABLED
        ),
        "configured": configured,
        "username_configured": (
            username_configured
        ),
        "password_configured": (
            password_configured
        ),
        "session_secret_configured": (
            session_secret_configured
        ),
        "session_ttl_seconds": int(
            config.BXK_SESSION_TTL_SECONDS
        ),
    }


def verify_credentials(
    username: str,
    password: str,
) -> bool:
    configured_username = str(
        config.BXK_APP_USERNAME or ""
    )

    stored_hash = str(
        config.BXK_APP_PASSWORD_HASH or ""
    )

    supplied_username = str(
        username or ""
    )

    supplied_password = str(
        password or ""
    )

    if not configured_username or not stored_hash:
        return False

    # Always perform password verification when a
    # stored hash exists so wrong usernames do not
    # short-circuit the expensive password check.
    password_valid = verify_app_password(
        supplied_password,
        stored_hash,
    )

    username_valid = hmac.compare_digest(
        supplied_username.encode("utf-8"),
        configured_username.encode("utf-8"),
    )

    return bool(
        username_valid
        and password_valid
    )


def _sign_payload(
    encoded_payload: str,
    secret: str,
) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return _b64encode(digest)


def create_session_token(
    username: str,
    *,
    now: int | None = None,
) -> str:
    secret = str(
        config.BXK_SESSION_SECRET or ""
    ).strip()

    if not secret:
        raise ValueError(
            "BXK session secret is not configured."
        )

    issued_at = int(
        time.time()
        if now is None
        else now
    )

    expires_at = (
        issued_at
        + int(config.BXK_SESSION_TTL_SECONDS)
    )

    payload = {
        "v": SESSION_VERSION,
        "sub": str(username),
        "iat": issued_at,
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(12),
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    encoded_payload = _b64encode(
        payload_bytes
    )

    signature = _sign_payload(
        encoded_payload,
        secret,
    )

    return (
        f"{encoded_payload}.{signature}"
    )


def verify_session_token(
    token: str,
    *,
    now: int | None = None,
):
    secret = str(
        config.BXK_SESSION_SECRET or ""
    ).strip()

    if not secret:
        return None

    try:
        encoded_payload, supplied_signature = (
            str(token).split(".", 1)
        )

        expected_signature = _sign_payload(
            encoded_payload,
            secret,
        )

        if not hmac.compare_digest(
            supplied_signature,
            expected_signature,
        ):
            return None

        payload = json.loads(
            _b64decode(
                encoded_payload
            ).decode("utf-8")
        )

        if (
            payload.get("v")
            != SESSION_VERSION
        ):
            return None

        username = str(
            payload.get("sub") or ""
        )

        issued_at = int(
            payload.get("iat")
        )

        expires_at = int(
            payload.get("exp")
        )

        current_time = int(
            time.time()
            if now is None
            else now
        )

        if not username:
            return None

        if issued_at > current_time + 60:
            return None

        if expires_at <= current_time:
            return None

        if expires_at <= issued_at:
            return None

        configured_username = str(
            config.BXK_APP_USERNAME or ""
        )

        if not hmac.compare_digest(
            username.encode("utf-8"),
            configured_username.encode("utf-8"),
        ):
            return None

        return {
            "username": username,
            "issued_at": issued_at,
            "expires_at": expires_at,
        }

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        base64.binascii.Error,
    ):
        return None
