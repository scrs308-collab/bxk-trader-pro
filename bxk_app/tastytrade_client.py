from tastytrade import Session

from bxk_app.config import (
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)


class TastytradeClient:
    def __init__(self):
        self.session = None
        self.last_error = None

    def connect(self):
        try:
            if not TASTYTRADE_CLIENT_SECRET:
                raise ValueError("Missing TASTYTRADE_CLIENT_SECRET")

            if not TASTYTRADE_REFRESH_TOKEN:
                raise ValueError("Missing TASTYTRADE_REFRESH_TOKEN")

            self.session = Session(
                TASTYTRADE_CLIENT_SECRET,
                TASTYTRADE_REFRESH_TOKEN,
            )

            self.last_error = None
            return True

        except Exception as e:
            self.session = None
            self.last_error = str(e)
            return False

    def connected(self):
        return self.session is not None

    def get_status(self):
        return {
            "connected": self.connected(),
            "last_error": self.last_error,
        }


tastytrade_client = TastytradeClient()