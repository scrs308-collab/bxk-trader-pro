"""Operator-only certification access check. Never places or changes orders."""
import json
import os

import requests

from staging_reconciliation_reader import CERT, CertificationOrderReader


def preflight(environ=None, session=None):
    env = os.environ if environ is None else environ
    if (env.get("BXK_PREVIEW_MODE", "").lower() != "true"
            or env.get("BXK_LIVE_TRADING_ENABLED", "").lower() != "false"):
        raise ValueError("Certification checks require preview mode and live trading disabled")
    if env.get("TASTYTRADE_CERT_BASE_URL") != CERT:
        raise ValueError("Certification destination must match the fixed sandbox host")
    names = ("ACCOUNT_NUMBER", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
    config = {key: env.get("TASTYTRADE_CERT_" + key, "").strip() for key in names}
    if not all(config.values()):
        raise ValueError("Dedicated certification configuration is incomplete")
    transport = session or requests.Session()
    headers = {"User-Agent": "bxk-certification/1.0", "Accept": "application/json"}
    # Validate the account before transmitting credentials. No production fallback.
    reader = CertificationOrderReader(config["ACCOUNT_NUMBER"], "certification-operator", lambda: headers,
                                      session=transport)
    try:
        auth = transport.post(CERT + "/oauth/token", headers=headers,
                              json={"grant_type": "refresh_token", "scope": "read",
                                    "client_id": config["CLIENT_ID"],
                                    "client_secret": config["CLIENT_SECRET"],
                                    "refresh_token": config["REFRESH_TOKEN"]},
                              timeout=15, allow_redirects=False)
        if auth.status_code != 200:
            raise ValueError("Certification authentication failed")
        token = auth.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Certification authentication failed")
        headers["Authorization"] = "Bearer " + token
        response = transport.get(CERT + "/customers/me/accounts", headers=headers,
                                 timeout=15, allow_redirects=False)
        if response.status_code != 200:
            raise ValueError("Certification account verification failed")
        accounts = response.json()["data"]["items"]
        if not any(item.get("account", {}).get("account-number") == config["ACCOUNT_NUMBER"]
                   for item in accounts):
            raise ValueError("Certification account ownership mismatch")
        _, history_complete = reader._pages("", {})
        _, today_complete = reader.today()
        return {"environment": "certification", "authenticated": True, "account_verified": True,
                "history_pagination_complete": history_complete,
                "today_pagination_complete": today_complete, "submitted": False}
    except Exception:
        # Provider bodies and exception messages may contain secrets or account data.
        raise RuntimeError("Certification access check failed; inspect provider status securely") from None


if __name__ == "__main__":
    try:
        print(json.dumps(preflight(), sort_keys=True))
    except (ValueError, RuntimeError) as error:
        print(json.dumps({"ok": False, "detail": str(error), "submitted": False}))
        raise SystemExit(1)
