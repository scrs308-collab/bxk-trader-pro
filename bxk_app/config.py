import os
from dotenv import load_dotenv

load_dotenv()

# ===============================
# Schwab API
# ===============================

SCHWAB_CLIENT_ID = os.getenv("SCHWAB_CLIENT_ID")
SCHWAB_CLIENT_SECRET = os.getenv("SCHWAB_CLIENT_SECRET")
SCHWAB_REDIRECT_URI = os.getenv("SCHWAB_REDIRECT_URI")
SCHWAB_TOKEN_FILE = os.getenv("SCHWAB_TOKEN_FILE")

# ===============================
# Trading Settings
# ===============================

MAX_WING_WIDTH = 25
TARGET_DELTA = 0.15

TRADE_SCORE = 70
CAUTION_SCORE = 55

STOP_MULTIPLIER = 2.0
TARGET_PERCENT = 70