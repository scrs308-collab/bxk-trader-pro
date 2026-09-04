import time
from typing import Any

import requests

from bxk_app.brokers.base import BrokerBase
from bxk_app.config import (
    BXK_LIVE_TRADING_ENABLED,
    TASTYTRADE_ACCOUNT_NUMBER,
    TASTYTRADE_BASE_URL,
    TASTYTRADE_CLIENT_SECRET,
    TASTYTRADE_REFRESH_TOKEN,
)




# Tastytrade access tokens normally last about 15 minutes.
# Refresh slightly early so requests do not fail at the boundary.
ACCESS_TOKEN_REFRESH_SECONDS = 13 * 60


class TastytradeBroker(BrokerBase):
    def __init__(
        self,
        *,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        account_number: str | None = None,
        base_url: str | None = None,
        live_trading_enabled: bool | None = None,
    ):
        self.client_secret = (
            None
            if client_secret is None
            else str(client_secret).strip()
        )

        self.refresh_token = (
            None
            if refresh_token is None
            else str(refresh_token).strip()
        )

        self.account_number = (
            None
            if account_number is None
            else str(account_number).strip()
        )

        self.base_url = (
            None
            if base_url is None
            else str(base_url).strip()
        )

        # Existing global OWNER broker preserves its
        # historical behavior. Per-user broker instances
        # can additionally disable live execution.
        self.live_trading_enabled = (
            True
            if live_trading_enabled is None
            else bool(live_trading_enabled)
        )

        self.access_token: str | None = None
        self.token_created_at: float = 0.0
        self.last_error: str | None = None
        self.session = requests.Session()

    def _resolved_client_secret(self) -> str:
        if self.client_secret is not None:
            return self.client_secret

        return str(
            TASTYTRADE_CLIENT_SECRET or ""
        ).strip()

    def _resolved_refresh_token(self) -> str:
        if self.refresh_token is not None:
            return self.refresh_token

        return str(
            TASTYTRADE_REFRESH_TOKEN or ""
        ).strip()

    def _resolved_account_number(self) -> str:
        if self.account_number is not None:
            return self.account_number

        return str(
            TASTYTRADE_ACCOUNT_NUMBER or ""
        ).strip()

    def _resolved_base_url(self) -> str:
        if self.base_url is not None:
            return self.base_url

        return str(
            TASTYTRADE_BASE_URL or ""
        ).strip()

    def reset_authentication(self):
        """
        Clear cached OAuth state after broker settings change.

        The next broker request will authenticate using the
        current runtime configuration.
        """
        self.access_token = None
        self.token_created_at = 0.0
        self.last_error = None

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
                f"{self._resolved_base_url()}/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._resolved_refresh_token(),
                    "client_secret": self._resolved_client_secret(),
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
        json_body: dict[str, Any] | None = None,
    ) -> requests.Response | None:
        """
        Send an authenticated API request.

        If Tastytrade returns 401, refresh the access token and retry
        exactly once.
        """

        headers = self.headers()

        if not headers:
            return None

        url = f"{self._resolved_base_url()}{path}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
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
                    json=json_body,
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
        target_account = (
            self._resolved_account_number()
        )

        if not target_account:
            self.last_error = (
                "TASTYTRADE_ACCOUNT_NUMBER is not configured."
            )
            return None

        accounts = self.get_accounts()

        if not accounts:
            self.last_error = (
                self.last_error
                or "No Tastytrade accounts were returned"
            )
            return None

        for item in accounts:
            account = (
                (item or {}).get("account") or {}
            )

            account_number = str(
                account.get("account-number") or ""
            ).strip()

            if account_number == target_account:
                self.last_error = None
                return account_number

        self.last_error = (
            "Configured Tastytrade account was not returned."
        )
        return None

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
    # Live Orders
    # ---------------------------------------------------------

    def get_order(
        self,
        order_id,
        account_number=None,
    ):
        """Fetch one order directly from Tastytrade."""

        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return None

        clean_order_id = str(order_id or "").strip()

        if (
            not clean_order_id
            or not all(
                character.isalnum()
                or character == "-"
                for character in clean_order_id
            )
        ):
            self.last_error = "Order ID is invalid."
            return None

        response = self._request(
            "GET",
            (
                f"/accounts/{account_number}"
                f"/orders/{clean_order_id}"
            ),
        )

        if response is None:
            return None

        try:
            payload = response.json()
            order = (payload.get("data") or {}).get(
                "order"
            )
        except (AttributeError, TypeError, ValueError) as exc:
            self.last_error = (
                "Invalid Tastytrade order response: "
                f"{exc}"
            )
            return None

        if not isinstance(order, dict):
            self.last_error = (
                "Tastytrade did not return order data."
            )
            return None

        self.last_error = None
        return order



    def get_transactions(
        self,
        account_number=None,
        *,
        start_date=None,
        end_date=None,
        instrument_type=None,
    ):
        """
        Read account transaction history.

        Used for broker-confirmed SPX expiration and
        cash-settlement reconciliation.
        """

        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return []

        page_offset = 0
        per_page = 250
        transactions = []

        while True:
            params = {
                "per-page": per_page,
                "page-offset": page_offset,
                "sort": "Desc",
            }

            if start_date:
                params["start-date"] = str(
                    start_date
                )

            if end_date:
                params["end-date"] = str(
                    end_date
                )

            if instrument_type:
                params["instrument-type"] = str(
                    instrument_type
                )

            response = self._request(
                "GET",
                (
                    f"/accounts/{account_number}"
                    "/transactions"
                ),
                params=params,
            )

            if response is None:
                return []

            try:
                payload = response.json()

                data = (
                    payload.get("data")
                    or {}
                )

                items = (
                    data.get("items")
                    or []
                )

                pagination = (
                    payload.get("pagination")
                    or data.get("pagination")
                    or {}
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ) as exc:
                self.last_error = (
                    "Invalid Tastytrade transaction "
                    f"response: {exc}"
                )
                return []

            if not isinstance(
                items,
                list,
            ):
                self.last_error = (
                    "Invalid Tastytrade transaction "
                    "items collection."
                )
                return []

            transactions.extend(
                items
            )

            raw_total_pages = (
                pagination.get(
                    "total-pages"
                )
            )

            if raw_total_pages is None:
                total_pages = (
                    1
                    if items
                    else 0
                )

            else:
                try:
                    total_pages = int(
                        raw_total_pages
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    self.last_error = (
                        "Invalid Tastytrade transaction "
                        "pagination."
                    )
                    return []

            if total_pages == 0:
                break

            if (
                total_pages < 0
                or total_pages > 100
            ):
                self.last_error = (
                    "Unsafe Tastytrade transaction "
                    "pagination range."
                )
                return []

            page_offset += 1

            if (
                page_offset
                >= total_pages
            ):
                break

        self.last_error = None

        return transactions

    def get_orders(
        self,
        account_number=None,
        *,
        start_date=None,
        end_date=None,
        statuses=None,
        underlying_symbol=None,
    ):
        """
        Search account order history.

        Read-only broker operation used for trade
        journal reconciliation.
        """

        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return []

        page_offset = 0
        per_page = 100
        orders = []

        while True:
            params = {
                "per-page": per_page,
                "page-offset": page_offset,
                "sort": "Desc",
            }

            if start_date:
                params["start-date"] = str(
                    start_date
                )

            if end_date:
                params["end-date"] = str(
                    end_date
                )

            if underlying_symbol:
                params["underlying-symbol"] = str(
                    underlying_symbol
                ).strip().upper()

            if statuses:
                if isinstance(
                    statuses,
                    (list, tuple, set),
                ):
                    clean_statuses = [
                        str(value).strip()
                        for value in statuses
                        if str(value).strip()
                    ]
                else:
                    clean_statuses = [
                        str(statuses).strip()
                    ]

                if clean_statuses:
                    params["status[]"] = (
                        clean_statuses
                    )

            response = self._request(
                "GET",
                (
                    f"/accounts/{account_number}"
                    "/orders"
                ),
                params=params,
            )

            if response is None:
                return []

            try:
                payload = response.json()
                data = (
                    payload.get("data")
                    or {}
                )

                items = (
                    data.get("items")
                    or []
                )

                pagination = (
                    payload.get("pagination")
                    or {}
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
            ) as exc:
                self.last_error = (
                    "Invalid Tastytrade order-history "
                    f"response: {exc}"
                )
                return []

            if not isinstance(
                items,
                list,
            ):
                self.last_error = (
                    "Invalid Tastytrade order-history "
                    "items collection."
                )
                return []

            orders.extend(
                items
            )

            try:
                total_pages = int(
                    pagination.get(
                        "total-pages",
                        1,
                    )
                    or 1
                )

            except (
                TypeError,
                ValueError,
            ):
                self.last_error = (
                    "Invalid Tastytrade order-history "
                    "pagination."
                )
                return []

            # A valid empty search may return
            # total-pages == 0.
            if total_pages == 0:
                self.last_error = None
                break

            if (
                total_pages < 0
                or total_pages > 100
            ):
                self.last_error = (
                    "Unsafe Tastytrade order-history "
                    "pagination range."
                )
                return []

            page_offset += 1

            if (
                page_offset
                >= total_pages
            ):
                break

        self.last_error = None

        return orders

    def get_live_orders(
        self,
        account_number=None,
    ):
        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No account number available"
            )
            return []

        orders = []
        page_offset = 0
        per_page = 100

        while True:
            response = self._request(
                "GET",
                (
                    f"/accounts/{account_number}"
                    "/orders/live"
                ),
                params={
                    "per-page": per_page,
                    "page-offset": page_offset,
                },
            )

            if response is None:
                return []

            try:
                payload = response.json()
                data = payload.get("data") or {}
                items = data.get("items") or []
                pagination = (
                    payload.get("pagination") or {}
                )
            except (AttributeError, TypeError, ValueError) as exc:
                self.last_error = (
                    "Invalid Tastytrade live-orders "
                    f"response: {exc}"
                )
                return []

            if not isinstance(items, list):
                self.last_error = (
                    "Invalid Tastytrade live-orders "
                    "items collection."
                )
                return []

            orders.extend(items)

            try:
                total_pages = int(
                    pagination.get(
                        "total-pages",
                        1,
                    )
                    or 1
                )
            except (TypeError, ValueError):
                self.last_error = (
                    "Invalid Tastytrade live-orders "
                    "pagination."
                )
                return []

            if total_pages < 1 or total_pages > 100:
                self.last_error = (
                    "Unsafe Tastytrade live-orders "
                    "pagination range."
                )
                return []

            page_offset += 1

            if page_offset >= total_pages:
                break

        self.last_error = None
        return orders
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

    def get_future_instruments(
        self,
        product_code: str,
    ) -> list[dict]:
        """
        Retrieve futures contracts for one product code.

        Observation/data retrieval only.
        """

        code = str(
            product_code or ""
        ).strip().upper()

        if not code:
            self.last_error = (
                "Future product code is required."
            )
            return []

        response = self._request(
            "GET",
            "/instruments/futures",
            params={
                "product-code": code,
            },
        )

        return self._items_from_response(
            response
        )

    def get_active_future(
        self,
        product_code: str,
    ) -> dict | None:
        """
        Return Tastytrade's currently active-month
        futures contract for a product.
        """

        contracts = self.get_future_instruments(
            product_code
        )

        for contract in contracts:
            if (
                contract.get("active") is True
                and
                contract.get(
                    "active-month"
                ) is True
            ):
                return contract

        self.last_error = (
            "No active-month future found for "
            f"{str(product_code).upper()}."
        )

        return None

    def get_future_quote(
        self,
        symbol: str,
    ) -> dict | None:
        """
        Retrieve one futures market-data quote.
        """

        clean_symbol = str(
            symbol or ""
        ).strip()

        if not clean_symbol:
            self.last_error = (
                "Future symbol is required."
            )
            return None

        items = self.get_market_data_by_type(
            "future",
            [clean_symbol],
        )

        return items[0] if items else None

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


    # ---------------------------------------------------------
    # BXK / Tastytrade Order Preflight
    # ---------------------------------------------------------

    @staticmethod
    def _tasty_open_action(action: str) -> str:
        action = str(action or "").strip().upper()

        mapping = {
            "BUY": "Buy to Open",
            "SELL": "Sell to Open",
        }

        if action not in mapping:
            raise ValueError(
                f"Unsupported BXK order action: {action}"
            )

        return mapping[action]

    def build_dry_run_payload(
        self,
        order: dict,
    ) -> dict:
        """
        Translate a validated BXK opening order into
        a Tastytrade dry-run order payload.

        This method cannot submit a live order.
        """

        if not order:
            raise ValueError(
                "No BXK order supplied."
            )

        quantity = int(
            order.get("quantity") or 0
        )

        if quantity <= 0:
            raise ValueError(
                "Order quantity must be greater than zero."
            )

        try:
            price = float(
                order.get("limit_price")
            )
        except (TypeError, ValueError):
            price = 0.0

        if price <= 0:
            raise ValueError(
                "Limit credit must be greater than zero."
            )

        bxk_legs = order.get("legs") or []

        if not bxk_legs:
            raise ValueError(
                "Order does not contain option legs."
            )

        tasty_legs = []

        for leg in bxk_legs:
            symbol = str(
                leg.get("symbol") or ""
            ).strip()

            if not symbol:
                raise ValueError(
                    "Option leg is missing its symbol."
                )

            tasty_legs.append({
                "instrument-type": "Equity Option",
                "symbol": symbol,
                "quantity": quantity,
                "action": self._tasty_open_action(
                    leg.get("action")
                ),
            })

        return {
            "time-in-force": "Day",
            "order-type": "Limit",
            "price": f"{price:.2f}",
            "price-effect": "Credit",
            "legs": tasty_legs,
        }

    def dry_run_order(
        self,
        order: dict,
        account_number=None,
    ):
        """
        Send a BXK order to Tastytrade's dry-run endpoint.

        SAFETY:
        This cannot submit a live order.
        """

        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No Tastytrade account available."
            )
            return None

        try:
            payload = self.build_dry_run_payload(
                order
            )
        except (TypeError, ValueError) as exc:
            self.last_error = str(exc)
            return None

        response = self._request(
            "POST",
            (
                f"/accounts/{account_number}"
                "/orders/dry-run"
            ),
            json_body=payload,
        )

        if response is None:
            return None

        try:
            broker_response = response.json()
        except (TypeError, ValueError) as exc:
            self.last_error = (
                "Invalid Tastytrade dry-run response: "
                f"{exc}"
            )
            return None

        self.last_error = None

        return {
            "payload": payload,
            "broker_response": broker_response,
        }

    def submit_live_order(
        self,
        order: dict,
        account_number=None,
    ):
        """
        Submit a validated BXK opening order to Tastytrade.

        SAFETY:
        Live submission is blocked unless
        BXK_LIVE_TRADING_ENABLED is explicitly enabled.
        """

        if (
            not BXK_LIVE_TRADING_ENABLED
            or not self.live_trading_enabled
        ):
            self.last_error = (
                "BXK live trading is disabled."
            )
            return None

        if account_number is None:
            account_number = (
                self.get_first_account_number()
            )

        if not account_number:
            self.last_error = (
                self.last_error
                or "No Tastytrade account available."
            )
            return None

        try:
            payload = self.build_dry_run_payload(
                order
            )
        except (TypeError, ValueError) as exc:
            self.last_error = str(exc)
            return None

        response = self._request(
            "POST",
            (
                f"/accounts/{account_number}"
                "/orders"
            ),
            json_body=payload,
        )

        if response is None:
            return None

        try:
            broker_response = response.json()
        except (TypeError, ValueError) as exc:
            self.last_error = (
                "Invalid Tastytrade live-order response: "
                f"{exc}"
            )
            return None

        self.last_error = None

        return {
            "payload": payload,
            "broker_response": broker_response,
        }

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
