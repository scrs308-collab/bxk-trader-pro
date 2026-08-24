import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from bxk_app import config
from bxk_app.database import (
    database_configured,
    get_session_factory,
)
from bxk_app.db_models.user import User
from bxk_app.services.system_settings_service import (
    hash_app_password,
    verify_app_password,
)


SESSION_COOKIE_NAME = "bxk_session"
SESSION_VERSION = 1
DATABASE_SESSION_VERSION = 2

_TEMP_PASSWORD_LOCK = threading.Lock()
_TEMP_PASSWORD = {
    "username": None,
    "password_hash": None,
    "expires_at": 0.0,
}


def clear_temporary_password():
    with _TEMP_PASSWORD_LOCK:
        _TEMP_PASSWORD.update(
            {
                "username": None,
                "password_hash": None,
                "expires_at": 0.0,
            }
        )


def issue_temporary_password(
    username: str,
    *,
    ttl_seconds: int = 900,
    now: float | None = None,
):
    configured_username = str(
        config.BXK_APP_USERNAME or ""
    ).strip()

    supplied_username = str(
        username or ""
    ).strip()

    if (
        not configured_username
        or not hmac.compare_digest(
            supplied_username.encode("utf-8"),
            configured_username.encode("utf-8"),
        )
    ):
        return None

    alphabet = (
        "ABCDEFGHJKLMNPQRSTUVWXYZ"
        "abcdefghijkmnopqrstuvwxyz"
        "23456789"
    )

    temporary_password = "".join(
        secrets.choice(alphabet)
        for _ in range(16)
    )

    issued_at = (
        time.time()
        if now is None
        else float(now)
    )

    with _TEMP_PASSWORD_LOCK:
        _TEMP_PASSWORD.update(
            {
                "username": configured_username,
                "password_hash":
                    hash_app_password(
                        temporary_password
                    ),
                "expires_at":
                    issued_at + int(ttl_seconds),
            }
        )

    return temporary_password


def _verify_temporary_password(
    username: str,
    password: str,
    *,
    now: float | None = None,
) -> bool:
    current_time = (
        time.time()
        if now is None
        else float(now)
    )

    with _TEMP_PASSWORD_LOCK:
        stored_username = str(
            _TEMP_PASSWORD.get("username") or ""
        )
        stored_hash = str(
            _TEMP_PASSWORD.get(
                "password_hash"
            ) or ""
        )
        expires_at = float(
            _TEMP_PASSWORD.get(
                "expires_at"
            ) or 0.0
        )

        if (
            not stored_username
            or not stored_hash
            or expires_at <= current_time
        ):
            if expires_at and expires_at <= current_time:
                _TEMP_PASSWORD.update(
                    {
                        "username": None,
                        "password_hash": None,
                        "expires_at": 0.0,
                    }
                )
            return False

        username_valid = hmac.compare_digest(
            str(username or "").encode("utf-8"),
            stored_username.encode("utf-8"),
        )

        password_valid = verify_app_password(
            str(password or ""),
            stored_hash,
        )

        if not (
            username_valid
            and password_valid
        ):
            return False

        # One-time credential: consume immediately.
        _TEMP_PASSWORD.update(
            {
                "username": None,
                "password_hash": None,
                "expires_at": 0.0,
            }
        )

        return True


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



def authenticate_database_credentials(
    username: str,
    password: str,
) -> dict:
    """
    Authenticate one PostgreSQL user.

    This function is intentionally independent of the
    current config-based login path during migration.
    """
    supplied_username = str(
        username or ""
    ).strip()

    supplied_password = str(
        password or ""
    )

    base_result = {
        "authenticated": False,
        "database_available": False,
        "reason": None,
        "user_id": None,
        "username": None,
        "role": None,
        "must_change_password": False,
    }

    if not database_configured():
        return {
            **base_result,
            "reason": "DATABASE_NOT_CONFIGURED",
        }

    if not supplied_username:
        return {
            **base_result,
            "database_available": True,
            "reason": "USER_NOT_FOUND",
        }

    try:
        session_factory = get_session_factory()

        with session_factory() as session:
            user = session.scalar(
                select(User).where(
                    func.lower(User.username)
                    == supplied_username.casefold()
                )
            )

            if user is None:
                return {
                    **base_result,
                    "database_available": True,
                    "reason": "USER_NOT_FOUND",
                }

            password_valid = verify_app_password(
                supplied_password,
                str(user.password_hash or ""),
            )

            if not password_valid:
                return {
                    **base_result,
                    "database_available": True,
                    "reason": "INVALID_PASSWORD",
                }

            if not user.is_active:
                return {
                    **base_result,
                    "database_available": True,
                    "reason": "USER_INACTIVE",
                }

            return {
                "authenticated": True,
                "database_available": True,
                "reason": "AUTHENTICATED",
                "user_id": str(user.id),
                "username": user.username,
                "role": user.role.value,
                "must_change_password": bool(
                    user.must_change_password
                ),
            }

    except (SQLAlchemyError, RuntimeError):
        return {
            **base_result,
            "reason": "DATABASE_UNAVAILABLE",
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

    if (
        username_valid
        and password_valid
    ):
        return True

    return _verify_temporary_password(
        supplied_username,
        supplied_password,
    )



def authenticate_credentials(
    username: str,
    password: str,
) -> dict:
    """
    Authenticate database users first while preserving
    the legacy OWNER credential as a migration fallback.
    """
    database_result = (
        authenticate_database_credentials(
            username,
            password,
        )
    )

    if database_result["authenticated"]:
        return {
            **database_result,
            "auth_source": "DATABASE",
        }

    # An explicitly disabled database user must never
    # fall through to legacy authentication.
    if database_result["reason"] == "USER_INACTIVE":
        return {
            **database_result,
            "auth_source": None,
        }

    # Temporary OWNER passwords still live in the
    # legacy auth path during this migration phase.
    if verify_credentials(
        username,
        password,
    ):
        return {
            "authenticated": True,
            "database_available":
                database_result[
                    "database_available"
                ],
            "reason": "AUTHENTICATED",
            "user_id": None,
            "username": str(
                config.BXK_APP_USERNAME or ""
            ),
            "role": "OWNER",
            "must_change_password": False,
            "auth_source": "CONFIG",
        }

    return {
        **database_result,
        "auth_source": None,
    }

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



def create_database_session_token(
    user_id: str,
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

    subject = str(user_id or "").strip()

    if not subject:
        raise ValueError(
            "Database user ID is required."
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
        "v": DATABASE_SESSION_VERSION,
        "sub": subject,
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

        version = int(
            payload.get("v")
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

        if issued_at > current_time + 60:
            return None

        if expires_at <= current_time:
            return None

        if expires_at <= issued_at:
            return None

        # Legacy config-based OWNER session.
        if version == SESSION_VERSION:
            username = str(
                payload.get("sub") or ""
            )

            if not username:
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
                "user_id": None,
                "username": username,
                "role": "OWNER",
                "must_change_password": False,
                "auth_source": "CONFIG",
                "issued_at": issued_at,
                "expires_at": expires_at,
            }

        # Database-backed multi-user session.
        if version == DATABASE_SESSION_VERSION:
            user_id = str(
                payload.get("sub") or ""
            ).strip()

            if not user_id:
                return None

            if not database_configured():
                return None

            user_uuid = uuid.UUID(user_id)

            session_factory = (
                get_session_factory()
            )

            with session_factory() as session:
                user = session.get(
                    User,
                    user_uuid,
                )

                if (
                    user is None
                    or not user.is_active
                ):
                    return None

                return {
                    "user_id": str(user.id),
                    "username": user.username,
                    "role": user.role.value,
                    "must_change_password": bool(
                        user.must_change_password
                    ),
                    "auth_source": "DATABASE",
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                }

        return None

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        base64.binascii.Error,
        SQLAlchemyError,
        RuntimeError,
    ):
        return None
