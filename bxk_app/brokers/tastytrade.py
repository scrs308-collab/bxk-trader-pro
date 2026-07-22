import time
from typing import Any

import requests

from bxk_app.brokers.base import BrokerBase
from bxk_app.config import (
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)


TASTYTRADE_BASE_URL = "https://api.tastyworks.com"

# Tastytrade access tokens normally last about 15 minutes.
# Refresh slightly early so requests do not fail at the boundary.
ACCESS_TOKEN_REFRESH_SECONDS = 13 * 60


class TastytradeBroker(BrokerBase):
    def __init__(self):
        self.access_token: str | None = None
        self.token_created_at: float = 0.0
        self.last_error: str | None = None
        self.session = requests.Session()

    # ---------------------------------------------------------
    # Authentication
    # ---------------------------------------------------------

    def authenticate(self, force: bool = False) -> bool:
        """
        Retrieve a fresh OAuth access token.

        When force=False, reuse the current token until it is close
        to expiring. When force=True, always request a new token.
        """

        token_age = time.time() - self.token_created_at

        if (
            not force
            and self.access_token
            and token_age < ACCESS_TOKEN_REFRESH_SECONDS
        ):
            return True

        try:
            response = self.session.post(
                f"{TASTYTRADE_BASE_URL}/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": TASTYTRADE_REFRESH_TOKEN,
                    "client_secret": TASTYTRADE_CLIENT_SECRET,
                },
                timeout=15,
            )

            if response.status_code not in (200, 201):
                self.access_token = None
                self.token_created_at = 0.0
                self.last_error = (
                    f"Authentication failed "
                    f"({response.status_code}): "
                    f"{response.text}"
                )
                return False

            payload = response.json()

            self.access_token = (
                payload.get("access_token")
                or payload.get("access-token")
                or payload.get("data", {}).get("access_token")
                or payload.get("data", {}).get("access-token")
            )

            if not self.access_token:
                self.token_created_at = 0.0
                self.last_error = (
                    "Authentication response did not contain "
                    f"an access token: {payload}"
                )
                return False

            self.token_created_at = time.time()
            self.last_error = None
            return True

        except requests.RequestException as exc:
            self.access_token = None
            self.token_created_at = 0.0
            self.last_error = f"Authentication request failed: {exc}"
            return False

        except (TypeError, ValueError) as exc:
            self.access_token = None
            self.token_created_at = 0.0
            self.last_error = f"Invalid authentication response: {exc}"
            return False

    def headers(self) -> dict[str, str] | None:
        """
        Return valid authorization headers.

        authenticate() automatically refreshes an aging token.
        """

        if not self.authenticate():
            return None

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ---------------------------------------------------------
    # Shared request helper
    # ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> requests.Response | None:
        """
        Send an authenticated API request.

        If Tastytrade returns 401, refresh the access token and retry
        exactly once.
        """

        headers = self.headers()

        if not headers:
            return None

        url = f"{TASTYTRADE_BASE_URL}{path}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=15,
            )

            if response.status_code == 401:
                if not self.authenticate(force=True):
                    return None

                refreshed_headers = self.headers()

                if not refreshed_headers:
                    return None

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=refreshed_headers,
                    params=params,
                    timeout=15,
                )

            if response.status_code < 200 or response.status_code >= 300:
                self.last_error = (
                    f"{method.upper()} {path} failed "
                    f"({response.status_code}): "
                    f"{response.text}"
                )
                return None

            self.last_error = None
            return response

        except requests.RequestException as exc:
            self.last_error = (
                f"{method.upper()} {path} request failed: {exc}"
            )
            return None

    @staticmethod
    def _items_from_response(
        response: requests.Response | None,
    ) -> list[dict]:
        if response is None:
            return []

        try:
            payload = response.json()
        except (TypeError, ValueError):
            return []

        return payload.get("data", {}).get("items", [])

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def get_status(self):
        token_age = (
            round(time.time() - self.token_created_at, 1)
            if self.access_token
            else None
        )

        return {
            "connected": self.access_token is not None,
            "token_age_seconds": token_age,
            "last_error": self.last_error,
        }

    # ---------------------------------------------------------
    # Accounts
    # ---------------------------------------------------------

    def get_accounts(self):
        response = self._request(
            "GET",
            "/customers/me/accounts",
        )

        return self._items_from_response(response)

    def get_first_account_number(self):
        accounts = self.get_accounts()

        if not accounts:
            self.last_error = (
                self.last_error
                or "No Tastytrade accounts were returned"
            )
            return None

        account = accounts[0].get("account", {})
        account_number = account.get("account-number")

        if not account_number:
            self.last_error = (
                "First account did not contain an account number"
            )

        return account_number

    # ---------------------------------------------------------
    # Balances
    # ---------------------------------------------------------

    def get_balances(self, account_number=None):
        if account_number is None:
            account_number = self.get_first_account_number()

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return None

        response = self._request(
            "GET",
            f"/accounts/{account_number}/balances",
        )

        if response is None:
            return None

        try:
            return response.json().get("data", {})
        except (TypeError, ValueError) as exc:
            self.last_error = (
                f"Invalid balances response: {exc}"
            )
            return None

    # ---------------------------------------------------------
    # Positions
    # ---------------------------------------------------------

    def get_positions(self, account_number=None):
        if account_number is None:
            account_number = self.get_first_account_number()

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return []

        response = self._request(
            "GET",
            f"/accounts/{account_number}/positions",
        )

        return self._items_from_response(response)

    def get_position_summary(self):
        positions = self.get_positions()
        summary = []

        for position in positions:
            summary.append(
                {
                    "symbol": position.get("symbol", ""),
                    "underlying": position.get(
                        "underlying-symbol",
                        "",
                    ),
                    "instrument_type": position.get(
                        "instrument-type",
                        "",
                    ),
                    "quantity": position.get(
                        "quantity",
                        "0",
                    ),
                    "direction": position.get(
                        "quantity-direction",
                        "",
                    ),
                    "average_open_price": position.get(
                        "average-open-price",
                        "0",
                    ),
                    "close_price": position.get(
                        "close-price",
                        "0",
                    ),
                    "cost_effect": position.get(
                        "cost-effect",
                        "",
                    ),
                    "expires_at": position.get(
                        "expires-at",
                        "",
                    ),
                    "multiplier": position.get(
                        "multiplier",
                        "100.0",
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
            except (TypeError, ValueError):
                return 0.0

        return {
            "number": balances.get("account-number"),
            "net_liquidation": money(
                balances.get("net-liquidating-value")
            ),
            "cash": money(
                balances.get("cash-balance")
            ),
            "buying_power": money(
                balances.get("equity-buying-power")
            ),
            "derivative_buying_power": money(
                balances.get("derivative-buying-power")
            ),
            "maintenance": money(
                balances.get("maintenance-requirement")
            ),
            "margin_equity": money(
                balances.get("margin-equity")
            ),
            "open_positions": len(positions),
        }

    # ---------------------------------------------------------
    # Quotes
    # ---------------------------------------------------------

    def get_market_data_by_type(
        self,
        instrument_type: str,
        symbols: list[str],
    ) -> list[dict]:
        """
        Retrieve market data for one or more symbols of a given type.

        Tastytrade expects a comma-separated symbol list.
        """

        clean_symbols = [
            str(symbol).strip().upper().replace("$", "")
            for symbol in symbols
            if symbol
        ]

        if not clean_symbols:
            self.last_error = (
                "No symbols supplied for market-data request"
            )
            return []

        response = self._request(
            "GET",
            "/market-data/by-type",
            params={
                instrument_type: ",".join(clean_symbols),
            },
        )

        items = self._items_from_response(response)

        if not items and self.last_error is None:
            self.last_error = (
                "No market data returned for "
                f"{instrument_type}: "
                f"{','.join(clean_symbols)}"
            )

        return items

    def get_equity_quote(self, symbol: str):
        items = self.get_market_data_by_type(
            "equity",
            [symbol],
        )

        return items[0] if items else None

    def get_index_quote(self, symbol: str):
        response = self._request(
            "GET",
            "/market-data/by-type",
            params={"index": symbol},
        )

        if response is None:
            print(
                "INDEX QUOTE FAILED:",
                symbol,
                self.last_error,
            )
            return None
        
        items = self._items_from_response(response)

        return items[0] if items else None

    def get_quotes(
        self,
        *,
        equities: list[str] | None = None,
        indexes: list[str] | None = None,
    ) -> dict[str, dict]:
        """
        Retrieve several market quotes with fewer API calls.
        """

        result: dict[str, dict] = {}

        if equities:
            for item in self.get_market_data_by_type(
                "equity",
                equities,
            ):
                symbol = (
                    item.get("symbol")
                    or item.get("instrument-symbol")
                )

                if symbol:
                    result[str(symbol).upper()] = item

        if indexes:
            for item in self.get_market_data_by_type(
                "index",
                indexes,
            ):
                symbol = (
                    item.get("symbol")
                    or item.get("instrument-symbol")
                )

                if symbol:
                    result[
                        str(symbol)
                        .upper()
                        .replace("$", "")
                    ] = item

        return result

    def get_quote(self, symbol: str):
        clean_symbol = (
            symbol.strip()
            .upper()
            .replace("$", "")
        )

        index_symbols = {
            "SPX",
            "VIX",
            "VIX1D",
        }

        if clean_symbol in index_symbols:
            return self.get_index_quote(clean_symbol)

        return self.get_equity_quote(clean_symbol)


broker = TastytradeBroker()