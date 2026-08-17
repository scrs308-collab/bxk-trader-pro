import base64
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


ENV_PATH = Path(".env")

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000

_ENV_KEY_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*="
)


def _read_env_values():
    if not ENV_PATH.exists():
        return {}

    values = dotenv_values(ENV_PATH)

    return {
        str(key): "" if value is None else str(value)
        for key, value in values.items()
    }


def _value(values, key, default=""):
    if key in values:
        return str(values.get(key) or "")

    return str(os.getenv(key, default) or "")


def _configured(value):
    return bool(str(value or "").strip())


def _mask_account(account_number):
    value = str(account_number or "").strip()

    if not value:
        return ""

    if len(value) <= 4:
        return "****"

    return f"*****{value[-4:]}"


def _env_encode(value):
    value = str(value)

    if not value:
        return ""

    if re.fullmatch(
        r"[A-Za-z0-9_./:@+\-]+",
        value,
    ):
        return value

    escaped = (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )

    return f'"{escaped}"'


def _write_env_updates(updates):
    existing_lines = []

    if ENV_PATH.exists():
        existing_lines = ENV_PATH.read_text(
            encoding="utf-8",
        ).splitlines()

    seen = set()
    output = []

    for line in existing_lines:
        match = _ENV_KEY_PATTERN.match(line)

        if not match:
            output.append(line)
            continue

        key = match.group(1)

        if key not in updates:
            output.append(line)
            continue

        output.append(
            f"{key}={_env_encode(updates[key])}"
        )
        seen.add(key)

    missing = [
        key
        for key in updates
        if key not in seen
    ]

    if missing:
        if output and output[-1].strip():
            output.append("")

        for key in missing:
            output.append(
                f"{key}={_env_encode(updates[key])}"
            )

    text = "\n".join(output).rstrip() + "\n"

    temp_path = ENV_PATH.with_name(
        f"{ENV_PATH.name}.tmp"
    )

    temp_path.write_text(
        text,
        encoding="utf-8",
    )

    temp_path.replace(ENV_PATH)


def hash_app_password(password):
    password = str(password)

    if len(password) < 8:
        raise ValueError(
            "BXK application password must be "
            "at least 8 characters."
        )

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )

    encoded_salt = base64.urlsafe_b64encode(
        salt,
    ).decode("ascii")

    encoded_digest = base64.urlsafe_b64encode(
        digest,
    ).decode("ascii")

    return (
        f"pbkdf2_{PBKDF2_ALGORITHM}"
        f"${PBKDF2_ITERATIONS}"
        f"${encoded_salt}"
        f"${encoded_digest}"
    )


def verify_app_password(password, stored_hash):
    try:
        (
            algorithm,
            iterations_text,
            encoded_salt,
            encoded_digest,
        ) = str(stored_hash).split("$", 3)

        if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
            return False

        iterations = int(iterations_text)

        salt = base64.urlsafe_b64decode(
            encoded_salt.encode("ascii")
        )

        expected = base64.urlsafe_b64decode(
            encoded_digest.encode("ascii")
        )

        actual = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            str(password).encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(
            actual,
            expected,
        )

    except (
        ValueError,
        TypeError,
        base64.binascii.Error,
    ):
        return False


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _format_number(value):
    number = float(value)

    if number.is_integer():
        return str(int(number))

    return (
        f"{number:.4f}"
        .rstrip("0")
        .rstrip(".")
    )


def get_system_settings():
    values = _read_env_values()

    client_id = _value(
        values,
        "TASTYTRADE_CLIENT_ID",
    )

    client_secret = _value(
        values,
        "TASTYTRADE_CLIENT_SECRET",
    )

    refresh_token = _value(
        values,
        "TASTYTRADE_REFRESH_TOKEN",
    )

    broker_username = _value(
        values,
        "TASTYTRADE_USERNAME",
    )

    broker_password = _value(
        values,
        "TASTYTRADE_PASSWORD",
    )

    account_number = _value(
        values,
        "TASTYTRADE_ACCOUNT_NUMBER",
    )

    base_url = _value(
        values,
        "TASTYTRADE_BASE_URL",
        "https://api.tastyworks.com",
    )

    app_username = _value(
        values,
        "BXK_APP_USERNAME",
    )

    app_password_hash = _value(
        values,
        "BXK_APP_PASSWORD_HASH",
    )

    live_value = _value(
        values,
        "BXK_LIVE_TRADING_ENABLED",
        "false",
    )

    live_enabled = (
        live_value.strip().lower()
        in {"1", "true", "yes", "on"}
    )

    return {
        "app_access": {
            "username": app_username,
            "password_configured": _configured(
                app_password_hash
            ),
        },
        "tastytrade": {
            "authentication_mode": (
                "OAUTH_REFRESH_TOKEN"
            ),
            "client_id_configured": _configured(
                client_id
            ),
            "client_secret_configured": (
                _configured(client_secret)
            ),
            "refresh_token_configured": (
                _configured(refresh_token)
            ),
            "username_configured": _configured(
                broker_username
            ),
            "password_configured": _configured(
                broker_password
            ),
            "legacy_username_password_used": False,
            "account_number_masked": (
                _mask_account(account_number)
            ),
            "account_configured": _configured(
                account_number
            ),
            "base_url": base_url,
        },
        "risk": {
            "max_order_risk": _safe_float(
                _value(
                    values,
                    "BXK_MAX_ORDER_RISK",
                    "7500",
                ),
                7500,
            ),
            "min_order_credit": _safe_float(
                _value(
                    values,
                    "BXK_MIN_ORDER_CREDIT",
                    "1.00",
                ),
                1.00,
            ),
            "min_remaining_buying_power": (
                _safe_float(
                    _value(
                        values,
                        "BXK_MIN_REMAINING_BUYING_POWER",
                        "15000",
                    ),
                    15000,
                )
            ),
        },
        "live_trading_enabled": live_enabled,
        "restart_required": False,
    }


def update_system_settings(payload):
    if (
        "BXK_LIVE_TRADING_ENABLED" in payload
        or "live_trading_enabled" in payload
    ):
        raise ValueError(
            "Live trading cannot be changed "
            "through system settings."
        )

    updates = {}

    def optional_text(
        field_name,
        env_key,
    ):
        if field_name not in payload:
            return

        raw = payload.get(field_name)

        if raw is None:
            return

        value = str(raw).strip()

        # Blank input deliberately means:
        # preserve existing value.
        if not value:
            return

        updates[env_key] = value

    optional_text(
        "app_username",
        "BXK_APP_USERNAME",
    )

    if "app_password" in payload:
        password = str(
            payload.get("app_password") or ""
        )

        if password:
            updates[
                "BXK_APP_PASSWORD_HASH"
            ] = hash_app_password(password)

    optional_text(
        "tastytrade_client_id",
        "TASTYTRADE_CLIENT_ID",
    )

    optional_text(
        "tastytrade_client_secret",
        "TASTYTRADE_CLIENT_SECRET",
    )

    optional_text(
        "tastytrade_refresh_token",
        "TASTYTRADE_REFRESH_TOKEN",
    )

    optional_text(
        "tastytrade_username",
        "TASTYTRADE_USERNAME",
    )

    optional_text(
        "tastytrade_password",
        "TASTYTRADE_PASSWORD",
    )

    optional_text(
        "tastytrade_account_number",
        "TASTYTRADE_ACCOUNT_NUMBER",
    )

    if "tastytrade_base_url" in payload:
        raw_url = str(
            payload.get(
                "tastytrade_base_url",
            )
            or ""
        ).strip()

        if raw_url:
            parsed = urlparse(raw_url)

            if (
                parsed.scheme.lower() != "https"
                or not parsed.netloc
            ):
                raise ValueError(
                    "Tastytrade base URL must "
                    "be a valid HTTPS URL."
                )

            updates[
                "TASTYTRADE_BASE_URL"
            ] = raw_url.rstrip("/")

    if "max_order_risk" in payload:
        value = float(
            payload["max_order_risk"]
        )

        if value <= 0:
            raise ValueError(
                "Maximum order risk must be "
                "greater than zero."
            )

        updates[
            "BXK_MAX_ORDER_RISK"
        ] = _format_number(value)

    if "min_order_credit" in payload:
        value = float(
            payload["min_order_credit"]
        )

        if value <= 0:
            raise ValueError(
                "Minimum order credit must be "
                "greater than zero."
            )

        updates[
            "BXK_MIN_ORDER_CREDIT"
        ] = _format_number(value)

    if (
        "min_remaining_buying_power"
        in payload
    ):
        value = float(
            payload[
                "min_remaining_buying_power"
            ]
        )

        if value < 0:
            raise ValueError(
                "Minimum remaining buying power "
                "cannot be negative."
            )

        updates[
            "BXK_MIN_REMAINING_BUYING_POWER"
        ] = _format_number(value)

    if not updates:
        response = get_system_settings()
        response.update(
            {
                "saved": False,
                "restart_required": False,
                "changed_fields": [],
                "message": (
                    "No settings were changed."
                ),
            }
        )
        return response

    _write_env_updates(updates)

    response = get_system_settings()

    response.update(
        {
            "saved": True,
            "restart_required": True,
            "changed_fields": sorted(
                updates.keys()
            ),
            "message": (
                "Settings saved. Restart BXK "
                "Trader Pro to activate the "
                "updated runtime configuration."
            ),
        }
    )

    return response
