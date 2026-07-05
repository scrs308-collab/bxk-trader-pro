from tastytrade import Session
from tastytrade.account import Account

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

    def get_accounts(self):
        if not self.session:
            if not self.connect():
                return []

        try:
            accounts = Account.get_accounts(self.session)

            return [
                {
                    "account_number": acct.account_number,
                    "nickname": getattr(acct, "nickname", ""),
                }
                for acct in accounts
            ]

        except Exception as e:
            self.last_error = str(e)
            return []

    def connected(self):
        return self.session is not None

    def get_status(self):
        return {
            "connected": self.connected(),
            "last_error": self.last_error,
        }


tastytrade_client = TastytradeClient()