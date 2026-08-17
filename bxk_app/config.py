import os
from dotenv import load_dotenv


load_dotenv(override=True)


# ===============================
# Schwab API
# ===============================

SCHWAB_CLIENT_ID = os.getenv("SCHWAB_CLIENT_ID", "")
SCHWAB_CLIENT_SECRET = os.getenv("SCHWAB_CLIENT_SECRET", "")
SCHWAB_REDIRECT_URI = os.getenv("SCHWAB_REDIRECT_URI", "")
SCHWAB_TOKEN_FILE = os.getenv("SCHWAB_TOKEN_FILE", "schwab_tokens.json")


# ===============================
# Tastytrade API
# ===============================
TASTYTRADE_CLIENT_ID = os.getenv("TASTYTRADE_CLIENT_ID", "")
TASTYTRADE_CLIENT_SECRET = os.getenv("TASTYTRADE_CLIENT_SECRET", "")
TASTYTRADE_REFRESH_TOKEN = os.getenv("TASTYTRADE_REFRESH_TOKEN", "")
TASTYTRADE_ACCOUNT_NUMBER = os.getenv(
    "TASTYTRADE_ACCOUNT_NUMBER",
    "",
).strip()
TASTYTRADE_BASE_URL = os.getenv(
    "TASTYTRADE_BASE_URL",
    "https://api.tastyworks.com",
).strip()

TASTYTRADE_USERNAME = os.getenv(
    "TASTYTRADE_USERNAME",
    "",
).strip()

TASTYTRADE_PASSWORD = os.getenv(
    "TASTYTRADE_PASSWORD",
    "",
)

# ===============================
# BXK Application Access
# ===============================

BXK_APP_USERNAME = os.getenv(
    "BXK_APP_USERNAME",
    "",
).strip()

BXK_APP_PASSWORD_HASH = os.getenv(
    "BXK_APP_PASSWORD_HASH",
    "",
)


# ===============================
# BXK Authentication
# ===============================

BXK_AUTH_ENABLED = (
    os.getenv(
        "BXK_AUTH_ENABLED",
        "false",
    )
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

BXK_SESSION_SECRET = os.getenv(
    "BXK_SESSION_SECRET",
    "",
)

BXK_SESSION_TTL_SECONDS = int(
    os.getenv(
        "BXK_SESSION_TTL_SECONDS",
        "43200",
    )
)

if BXK_SESSION_TTL_SECONDS <= 0:
    raise ValueError(
        "BXK_SESSION_TTL_SECONDS must "
        "be greater than zero."
    )

BXK_AUTH_COOKIE_SECURE = (
    os.getenv(
        "BXK_AUTH_COOKIE_SECURE",
        "false",
    )
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

if (
    BXK_AUTH_ENABLED
    and len(BXK_SESSION_SECRET) < 32
):
    raise ValueError(
        "BXK_SESSION_SECRET must be at least "
        "32 characters when authentication "
        "is enabled."
    )


# ===============================
# Trading Settings
# ===============================

MAX_WING_WIDTH = 25
TARGET_DELTA = 0.15

TRADE_SCORE = 70
CAUTION_SCORE = 55

STOP_MULTIPLIER = 2.0
TARGET_PERCENT = 70


# ===============================
# Live Trading Safety
# ===============================

BXK_MIN_ORDER_CREDIT = float(
    os.getenv(
        "BXK_MIN_ORDER_CREDIT",
        "1.00",
    )
)

if BXK_MIN_ORDER_CREDIT <= 0:
    raise ValueError(
        "BXK_MIN_ORDER_CREDIT must be greater than zero."
    )

BXK_MIN_REMAINING_BUYING_POWER = float(
    os.getenv(
        "BXK_MIN_REMAINING_BUYING_POWER",
        "15000",
    )
)

if BXK_MIN_REMAINING_BUYING_POWER < 0:
    raise ValueError(
        "BXK_MIN_REMAINING_BUYING_POWER cannot be negative."
    )

BXK_MAX_ORDER_RISK = float(
    os.getenv(
        "BXK_MAX_ORDER_RISK",
        "7500",
    )
)

if BXK_MAX_ORDER_RISK <= 0:
    raise ValueError(
        "BXK_MAX_ORDER_RISK must be greater than zero."
    )

BXK_LIVE_TRADING_ENABLED = (
    os.getenv(
        "BXK_LIVE_TRADING_ENABLED",
        "false",
    )
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

# ===============================
# Execution Audit
# ===============================

BXK_ORDER_AUDIT_FILE = os.getenv(
    "BXK_ORDER_AUDIT_FILE",
    "logs/order-audit.jsonl",
).strip()

if not BXK_ORDER_AUDIT_FILE:
    raise ValueError(
        "BXK_ORDER_AUDIT_FILE cannot be empty."
    )
