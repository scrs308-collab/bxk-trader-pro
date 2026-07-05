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

            self.access_token = data.get("access_token") or data.get("data", {}).get("access-token")

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

    def get_status(self):
        return {
            "connected": self.access_token is not None,
            "last_error": self.last_error,
        }


tastytrade_api = TastytradeAPI()