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

        summary = []

        for pos in positions:
            symbol = pos.get("symbol", "")
            underlying = pos.get("underlying-symbol", "")
            quantity = pos.get("quantity", "0")
            direction = pos.get("quantity-direction", "")
            close_price = pos.get("close-price", "0")
            average_open_price = pos.get("average-open-price", "0")
            instrument_type = pos.get("instrument-type", "")

            summary.append({
                "symbol": symbol,
                "underlying": underlying,
                "instrument_type": instrument_type,
                "quantity": quantity,
                "direction": direction,
                "average_open_price": average_open_price,
                "close_price": close_price,
                "cost_effect": pos.get("cost-effect", ""),
                "expires_at": pos.get("expires-at", ""),
                "multiplier": pos.get("multiplier", "100.0"),
            })

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
        headers = self.headers()

        if not headers:
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

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return None

            data = response.json()
            items = data.get("data", {}).get("items", [])

            if not items:
                self.last_error = f"No index quote returned for {symbol}"
                return None

            return items[0]

        except Exception as e:
            self.last_error = str(e)
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

    def get_option_quotes(self, symbols: list[str]):
        headers = self.headers()

        if not headers:
            return []

        if not symbols:
            return []

        try:
            response = requests.get(
                f"{TASTYTRADE_BASE_URL}/market-data/by-type",
                headers=headers,
                params={
                    "option": ",".join(symbols),
                },
                timeout=20,
            )

            if response.status_code != 200:
                self.last_error = f"{response.status_code}: {response.text}"
                return []

            return response.json().get("data", {}).get("items", [])

        except Exception as e:
            self.last_error = str(e)
            return []

    def get_status(self):
        return {
            "connected": self.access_token is not None,
            "last_error": self.last_error,
        }

tastytrade_api = TastytradeAPI()