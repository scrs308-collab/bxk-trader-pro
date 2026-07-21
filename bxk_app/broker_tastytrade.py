from email.utils import quote
from turtle import pos
from urllib import response

from numpy import rint
import requests

from bxk_app.config import (
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)

TASTYTRADE_BASE_URL = "https://api.tastyworks.com"


class TastytradeAPI:
    def __init__(self):
        self.access_token = None
        self.last_error = None

    def authenticate(self):
        try:
            response = requests.post(
                f"{TASTYTRADE_BASE_URL}/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": TASTYTRADE_REFRESH_TOKEN,
                    "client_secret": TASTYTRADE_CLIENT_SECRET,
                },
                timeout=15,
            )

            if response.status_code not in (200, 201):
                self.last_error = f"{response.status_code}: {response.text}"
                return False

            data = response.json()

            self.access_token = (
                data.get("access_token")
                or data.get("data", {}).get("access-token")
            )

            if not self.access_token:
                self.last_error = f"No access token found: {data}"
                return False

            self.last_error = None
            return True

        except Exception as e:
            self.last_error = str(e)
            return False

    def headers(self):
        if not self.access_token:
            if not self.authenticate():
                return None

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_accounts(self):
        headers = self.headers()

        if not headers:
            return []

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/customers/me/accounts",
                headers=headers,
                timeout=15,
            )
           
            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return []

            data = response.json()
            return data.get("data", {}).get("items", [])

        except Exception as e:
            self.last_error = str(e)
            return []

    def get_first_account_number(self):
        accounts = self.get_accounts()

        if not accounts:
            return None

        return accounts[0]["account"]["account-number"]

    def get_balances(self, account_number=None):
        headers = self.headers()

        if not headers:
            return None

        if account_number is None:
            account_number = self.get_first_account_number()

        if not account_number:
            self.last_error = "No account number available"
            return None

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/accounts/{account_number}/balances",
                headers=headers,
                timeout=15,
            )

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return None

            return response.json().get("data", {})

        except Exception as e:
            self.last_error = str(e)
            return None
    def get_positions(self, account_number=None):
        headers = self.headers()

        if not headers:
            return []

        if account_number is None:
            account_number = self.get_first_account_number()

        if not account_number:
            self.last_error = "No account number available"
            return []

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/accounts/{account_number}/positions",
                headers=headers,
                timeout=15,
            )

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return []

            return response.json().get("data", {}).get("items", [])

        except Exception as e:
            self.last_error = str(e)
            return []
    
    def get_position_summary(self):
        positions = self.get_positions()

        if not positions:
            return []

        option_symbols = [
            pos.get("symbol")
            for pos in positions
            if pos.get("symbol")
        ]

        quotes = self.get_option_quotes(
            option_symbols
        )

        quote_map = {}

        for quote in quotes:
            symbol = (
                quote.get("eventSymbol")
                or quote.get("streamer-symbol")
                or quote.get("symbol")
            )

            if symbol:
                quote_map[symbol] = quote

        summary = []

        for pos in positions:
            quantity = abs(
                float(pos.get("quantity", 0))
            )

            multiplier = float(
                pos.get("multiplier", 100)
            )

            open_price = float(
                pos.get("average-open-price", 0)
            )

            option_symbol = pos.get("symbol")

            streamer_symbol = pos.get("streamer-symbol")

            quote = quote_map.get(
                option_symbol,
                {},
            )

            bid = float(
                quote.get(
                    "bid",
                    quote.get(
                        "bidPrice",
                        quote.get("bid-price", 0),
                    ),
                )
                or 0
            )

            ask = float(
                quote.get(
                    "ask",
                    quote.get(
                        "askPrice",
                        quote.get("ask-price", 0),
                    ),
                )
                or 0
            )

            mid = float(
                quote.get(
                    "mid",
                    quote.get(
                        "mark",
                        quote.get("dx-mark", 0),
                    ),
                )
                or 0
            )

            if bid > 0 and ask > 0:
                current_price = (
                    bid + ask
                ) / 2
                price_source = "live-mid"

            elif mid > 0:
                current_price = mid
                price_source = "live-mid"

            else:
                current_price = float(
                    pos.get("close-price", 0)
                )
                price_source = "close-price"

            direction = str(
                pos.get(
                    "quantity-direction",
                    "",
                )
            ).upper()

            if direction == "SHORT":
                pnl = (
                    open_price
                    - current_price
                ) * quantity * multiplier
            else:
                pnl = (
                    current_price
                    - open_price
                ) * quantity * multiplier

            position_cost = (
                open_price
                * quantity
                * multiplier
            )

            pnl_percent = (
                pnl / position_cost * 100
                if position_cost > 0
                else 0
            )

            summary.append(
                {
                    "symbol": pos.get(
                        "symbol",
                        "",
                    ),
                    "streamer_symbol": streamer_symbol,
                    "underlying": pos.get(
                        "underlying-symbol",
                        "",
                    ),
                    "instrument_type": pos.get(
                        "instrument-type",
                        "",
                    ),
                    "quantity": quantity,
                    "direction": direction,
                    "average_open_price": round(
                        open_price,
                        4,
                    ),
                    "current_price": round(
                        current_price,
                        4,
                    ),
                    "bid": round(bid, 4),
                    "ask": round(ask, 4),
                    "price_source": price_source,
                    "cost_effect": str(
                        pos.get(
                            "cost-effect",
                            "",
                        )
                    ).upper(),
                    "expires_at": pos.get(
                        "expires-at",
                        "",
                    ),
                    "multiplier": multiplier,
                    "pnl": round(pnl, 2),
                    "pnl_percent": round(
                        pnl_percent,
                        1,
                    ),
                }
            )

        return summary

    def get_account_summary(self):
        balances = self.get_balances()
        positions = self.get_position_summary()

        if not balances:
            return None

        def money(value):
            try:
                return round(float(value), 2)
            except Exception:
                return 0.0

        return {
            "number": balances.get("account-number"),
            "net_liquidation": money(balances.get("net-liquidating-value")),
            "cash": money(balances.get("cash-balance")),
            "buying_power": money(balances.get("equity-buying-power")),
            "derivative_buying_power": money(balances.get("derivative-buying-power")),
            "maintenance": money(balances.get("maintenance-requirement")),
            "margin_equity": money(balances.get("margin-equity")),
            "open_positions": len(positions),
        }

    def get_equity_quote(self, symbol: str):
        headers = self.headers()

        if not headers:
            return None

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/market-data/by-type",
                headers=headers,
                params={
                    "equity": symbol,
                },
                timeout=15,
            )

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return None

            data = response.json()
            items = data.get("data", {}).get("items", [])

            if not items:
                self.last_error = f"No quote returned for {symbol}"
                return None

            return items[0]

        except Exception as e:
            self.last_error = str(e)
            return None

    def get_index_quote(self, symbol: str):
        print(
            "RUNNING get_index_quote FROM:",
            __file__,
            "SYMBOL:",
            symbol,
        )

        headers = self.headers()

        if not headers:
            print(f"INDEX QUOTE {symbol}: no authentication headers")
            return None

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/market-data/by-type",
                headers=headers,
                params={
                    "index": symbol,
                },
                timeout=15,
            )

            print(
                f"INDEX QUOTE {symbol}:",
                response.status_code,
                response.url,
            )

            print(
                f"INDEX RESPONSE {symbol}:",
                response.text,
            )

            if response.status_code != 200:
                self.last_error = (
                    f"{response.status_code}: "
                    f"{response.text}"
                )
                return None

            data = response.json()
            items = (
                data.get("data", {})
                .get("items", [])
            )

            if not items:
                self.last_error = (
                    f"No index quote returned "
                    f"for {symbol}"
                )
                return None

            return items[0]

        except Exception as e:
            self.last_error = str(e)

            print(
                f"INDEX QUOTE ERROR {symbol}:",
                repr(e),
            )

            return None

    def get_quote(self, symbol: str):
        symbol = symbol.upper()

        if symbol in ["SPX", "$SPX", "VIX", "$VIX", "VIX1D", "$VIX1D"]:
            clean_symbol = symbol.replace("$", "")
            return self.get_index_quote(clean_symbol)

        return self.get_equity_quote(symbol)

    def get_nested_option_chain(self, symbol: str):
        headers = self.headers()

        if not headers:
            return None

        symbol = symbol.upper().replace("$", "")

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/option-chains/{symbol}/nested",
                headers=headers,
                timeout=20,
            )

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return None

            return response.json().get("data", {})

        except Exception as e:
            self.last_error = str(e)
            return None

    def get_spx_option_chain(self):
        return self.get_nested_option_chain("SPX")

    def get_option_quotes(
        self,
        symbols: list[str],
    ):
        headers = self.headers()

        if not headers:
            return []

        if not symbols:
            return []

        try:
            response = requests.get(
                (
                    f"{TASTYTRADE_BASE_URL}"
                    "/market-data/by-type"
                ),
                headers=headers,
                params={
                    "equity-option": ",".join(symbols),
                },
                timeout=20,
            )
            
            if response.status_code != 200:
                self.last_error = (
                    f"{response.status_code}: "
                    f"{response.text}"
                )
                return []

            return (
                response.json()
                .get("data", {})
                .get("items", [])
            )

        except Exception as e:
            self.last_error = str(e)
            return []

    def get_status(self):
        return {
            "connected": self.access_token is not None,
            "last_error": self.last_error,
        }

tastytrade_api = TastytradeAPI()