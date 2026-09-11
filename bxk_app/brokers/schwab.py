import requests

from bxk_app.brokers.base import BrokerBase


class SchwabBroker(BrokerBase):
    """
    Read-only Charles Schwab Trader API adapter.

    OAuth token acquisition/refresh and live order execution
    are intentionally outside this initial implementation.
    """

    broker_name = "schwab"

    capabilities = frozenset({
        "accounts",
        "balances",
        "positions",
    })

    DEFAULT_BASE_URL = (
        "https://api.schwabapi.com"
    )

    def __init__(
        self,
        *,
        access_token=None,
        account_number=None,
        base_url=None,
        session=None,
    ):
        self.access_token = str(
            access_token or ""
        ).strip()

        self.account_number = str(
            account_number or ""
        ).strip()

        self.base_url = str(
            base_url
            or self.DEFAULT_BASE_URL
        ).rstrip("/")

        self.session = (
            session
            or requests.Session()
        )

        self.last_error = None
        self._authenticated = False
        self._accounts_cache = None

    def _headers(self):
        return {
            "Accept": "application/json",
            "Authorization": (
                f"Bearer {self.access_token}"
            ),
        }

    def _request(
        self,
        method,
        path,
        *,
        params=None,
    ):
        if not self.access_token:
            self.last_error = (
                "Schwab access token is unavailable."
            )
            return None

        url = (
            f"{self.base_url}"
            f"{path}"
        )

        try:
            response = self.session.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            self.last_error = (
                "Schwab request failed: "
                f"{exc}"
            )
            return None

        if not (
            200
            <= response.status_code
            < 300
        ):
            self.last_error = (
                "Schwab API request failed "
                f"with HTTP {response.status_code}."
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            self.last_error = (
                "Schwab returned invalid JSON."
            )
            return None

        self.last_error = None

        return payload

    def authenticate(self, force=False):
        if not self.access_token:
            self.last_error = (
                "Schwab access token is unavailable."
            )
            self._authenticated = False
            return False

        accounts = self.get_accounts(
            force=force
        )

        self._authenticated = bool(
            accounts
        )

        return self._authenticated

    def get_status(self):
        return {
            "broker": self.broker_name,
            "connected": bool(
                self._authenticated
            ),
            "token_configured": bool(
                self.access_token
            ),
            "account_number": (
                self.account_number
                or None
            ),
            "last_error": self.last_error,
        }

    def get_accounts(self, force=False):
        if (
            self._accounts_cache is not None
            and not force
        ):
            return list(
                self._accounts_cache
            )

        payload = self._request(
            "GET",
            (
                "/trader/v1/accounts/"
                "accountNumbers"
            ),
        )

        if payload is None:
            return []

        if not isinstance(payload, list):
            self.last_error = (
                "Schwab account response "
                "was not a list."
            )
            return []

        accounts = []

        for item in payload:
            if not isinstance(item, dict):
                continue

            account_number = str(
                item.get("accountNumber")
                or ""
            ).strip()

            account_key = str(
                item.get("hashValue")
                or ""
            ).strip()

            if (
                not account_number
                or not account_key
            ):
                continue

            accounts.append({
                "account_number":
                    account_number,
                "broker_account_key":
                    account_key,
            })

        if not accounts:
            self.last_error = (
                "Schwab returned no "
                "authorized accounts."
            )
            return []

        self._accounts_cache = accounts
        self.last_error = None

        return list(accounts)

    def _resolve_account(
        self,
        account_number=None,
    ):
        accounts = self.get_accounts()

        if not accounts:
            return None

        target = str(
            account_number
            or self.account_number
            or ""
        ).strip()

        if not target:
            if len(accounts) == 1:
                return accounts[0]

            self.last_error = (
                "Multiple Schwab accounts "
                "are authorized; select a "
                "default account."
            )
            return None

        for account in accounts:
            if (
                account["account_number"]
                == target
            ):
                return account

        self.last_error = (
            "Selected Schwab account is "
            "not authorized."
        )

        return None

    def get_default_account_number(self):
        account = self._resolve_account()

        if account is None:
            return None

        return account[
            "account_number"
        ]

    def get_balances(
        self,
        account_number=None,
    ):
        account = self._resolve_account(
            account_number
        )

        if account is None:
            return {}

        account_key = account[
            "broker_account_key"
        ]

        payload = self._request(
            "GET",
            (
                "/trader/v1/accounts/"
                f"{account_key}"
            ),
        )

        if not isinstance(payload, dict):
            return {}

        securities_account = (
            payload.get(
                "securitiesAccount"
            )
            or {}
        )

        balances = (
            securities_account.get(
                "currentBalances"
            )
            or {}
        )

        if not isinstance(
            balances,
            dict,
        ):
            self.last_error = (
                "Schwab balance response "
                "was invalid."
            )
            return {}

        return balances

    def get_positions(
        self,
        account_number=None,
    ):
        account = self._resolve_account(
            account_number
        )

        if account is None:
            return []

        account_key = account[
            "broker_account_key"
        ]

        payload = self._request(
            "GET",
            (
                "/trader/v1/accounts/"
                f"{account_key}"
            ),
            params={
                "fields": "positions",
            },
        )

        if not isinstance(payload, dict):
            return []

        securities_account = (
            payload.get(
                "securitiesAccount"
            )
            or {}
        )

        positions = (
            securities_account.get(
                "positions"
            )
            or []
        )

        if not isinstance(
            positions,
            list,
        ):
            self.last_error = (
                "Schwab position response "
                "was invalid."
            )
            return []

        return positions

    def get_quote(self, symbol: str):
        raise NotImplementedError(
            "Schwab market data is handled "
            "by the market-data provider layer"
        )
