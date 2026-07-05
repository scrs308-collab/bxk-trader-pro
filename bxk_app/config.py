import os
from dotenv import load_dotenv


load_dotenv()


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
TASTYTRADE_BASE_URL = os.getenv("TASTYTRADE_BASE_URL", "https://api.tastytrade.com")

# ===============================
# Trading Settings
# ===============================

MAX_WING_WIDTH = 25
TARGET_DELTA = 0.15

TRADE_SCORE = 70
CAUTION_SCORE = 55

STOP_MULTIPLIER = 2.0
TARGET_PERCENT = 70