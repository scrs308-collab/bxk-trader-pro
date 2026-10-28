"""Read-only certification recovery worker. OAuth is its only POST operation."""
import asyncio
import os
import threading
import time

import requests
from fastapi import HTTPException

from staging_reconciliation import Ledger
from staging_reconciliation_reader import CERT, BrokerReadError, CertificationOrderReader, retry_seconds


class ObservedReader(CertificationOrderReader):
    def __init__(self, worker, *args, **kwargs):
        self.worker = worker
        super().__init__(*args, **kwargs)

    def read(self, row):
        try:
            snapshot = super().read(row)
        except BrokerReadError as error:
            self.worker.provider_failure(error)
            raise
        except Exception:
            # Network, OAuth decoding and collection-shape failures must also
            # throttle owner refreshes, which do not pass through worker.tick.
            error = BrokerReadError()
            self.worker.provider_failure(error)
            raise error from None
        if snapshot.complete is True:
            self.worker.provider_success()
        return snapshot


class CertificationWorker:
    def __init__(self, session=None, clock=time.time):
        self.session = session or requests.Session()
        self.clock = clock
        self.lock = threading.Lock()
        self.token, self.token_until = None, 0
        self.blocked_until, self.failures = 0, 0
        self.failure_events = 0
        self.last_check, self.last_error = None, None
        self.reader = None
        self.enabled = os.getenv("BXK_CERT_RECONCILIATION_ENABLED", "").lower() == "true"
        try:
            self.config = {key: os.environ["TASTYTRADE_CERT_"+key].strip()
                           for key in ("ACCOUNT_NUMBER", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")}
            if not all(self.config.values()) or os.getenv("TASTYTRADE_CERT_BASE_URL") != CERT:
                raise ValueError()
            if os.getenv("BXK_PREVIEW_MODE", "").lower() != "true" or os.getenv("BXK_LIVE_TRADING_ENABLED", "").lower() != "false":
                raise ValueError()
            self.reader = ObservedReader(self, self.config["ACCOUNT_NUMBER"], "certification-operator",
                                         self.headers, session=self.session, clock=clock)
        except (KeyError, ValueError):
            self.last_error = "CERTIFICATION_CONFIGURATION_UNAVAILABLE"

    def provider_failure(self, error):
        if error.status_code == 401:
            self.token, self.token_until = None, 0
        # Cool down the whole account, not only the current intent. No tight
        # retry loop for bare 429s or repeated authentication failures.
        self.last_error = ("BROKER_RATE_LIMITED" if error.status_code == 429 else
                           "BROKER_AUTH_UNAVAILABLE" if error.status_code in (401, 403) else "BROKER_READ_UNAVAILABLE")
        with Ledger(clock=self.clock).db(True) as db:
            previous = db.execute("SELECT failures FROM certification_provider_failures WHERE scope=?", (self.reader.scope,)).fetchone()
            failures = min(5, (previous["failures"] if previous else 0)+1)
            delay = max(error.retry_after, min(300, 30 * 2**(failures-1)))
            blocked_until = int(self.clock())+delay
            db.execute("INSERT INTO certification_provider_failures VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET failures=excluded.failures", (self.reader.scope, failures))
            db.execute("INSERT INTO certification_worker_state(scope,blocked_until,last_error) VALUES(?,?,?) ON CONFLICT(scope) DO UPDATE SET blocked_until=MAX(blocked_until,excluded.blocked_until),last_error=excluded.last_error",
                       (self.reader.scope, blocked_until, self.last_error))
        self.failures, self.blocked_until = failures, blocked_until
        self.failure_events += 1

    def provider_success(self):
        with Ledger(clock=self.clock).db(True) as db:
            db.execute("DELETE FROM certification_worker_state WHERE scope=?", (self.reader.scope,))
            db.execute("DELETE FROM certification_provider_failures WHERE scope=?", (self.reader.scope,))
        self.failures, self.blocked_until, self.last_error = 0, 0, None

    def headers(self):
        headers = {"User-Agent": "bxk-certification-worker/1.0", "Accept": "application/json"}
        if not self.token or self.token_until <= self.clock():
            response = self.session.post(CERT+"/oauth/token", headers=headers,
                                         json={"grant_type": "refresh_token", "scope": "read",
                                               "client_id": self.config["CLIENT_ID"],
                                               "client_secret": self.config["CLIENT_SECRET"],
                                               "refresh_token": self.config["REFRESH_TOKEN"]},
                                         timeout=15, allow_redirects=False)
            if response.status_code != 200:
                raise BrokerReadError(response.status_code, retry_seconds(response.headers.get("Retry-After"), self.clock()))
            body = response.json()
            token, ttl = body.get("access_token"), body.get("expires_in")
            if not isinstance(token, str) or not token or type(ttl) is not int or ttl <= 30:
                raise BrokerReadError()
            candidate = {**headers, "Authorization": "Bearer "+token}
            response = self.session.get(CERT+"/customers/me/accounts", headers=candidate,
                                        timeout=15, allow_redirects=False)
            if response.status_code != 200:
                raise BrokerReadError(response.status_code, retry_seconds(response.headers.get("Retry-After"), self.clock()))
            items = response.json()["data"]["items"]
            if not any(item.get("account", {}).get("account-number") == self.config["ACCOUNT_NUMBER"] for item in items):
                raise BrokerReadError(403)
            self.token, self.token_until = token, self.clock()+min(ttl, 900)-30
        return {**headers, "Authorization": "Bearer "+self.token}

    def tick(self):
        if not self.enabled or self.reader is None or self.blocked_until > self.clock():
            return
        if not self.lock.acquire(blocking=False):
            return
        try:
            ledger = Ledger(clock=self.clock)
            with ledger.db() as db:
                cooldown = db.execute("SELECT blocked_until,last_error FROM certification_worker_state WHERE scope=?", (self.reader.scope,)).fetchone()
                if cooldown and cooldown["blocked_until"] > self.clock():
                    self.blocked_until, self.last_error = cooldown["blocked_until"], cooldown["last_error"]
                    return
                row = db.execute("SELECT id FROM rehearsal_reconciliation WHERE scope=? AND state IN ('UNKNOWN','ACKNOWLEDGED') AND next_read<=? AND lease_until<=? ORDER BY next_read,created_at LIMIT 1",
                                 (self.reader.scope, int(self.clock()), int(self.clock()))).fetchone()
            if row is None:
                return
            previous_failures = self.failure_events
            result = ledger.reconcile(row["id"], self.reader)
            self.last_check = int(self.clock())
            if self.failure_events == previous_failures:
                if result["reason"] == "READ_UNAVAILABLE":
                    self.provider_failure(BrokerReadError())
        except HTTPException as error:
            if error.status_code != 409:
                self.last_error = "DURABLE_STORAGE_UNAVAILABLE"
        except Exception:
            self.last_error = "CERTIFICATION_CHECK_UNAVAILABLE"
            self.blocked_until = int(self.clock())+30
        finally:
            self.lock.release()

    def status(self):
        result = {"environment": "certification", "enabled": self.enabled,
                  "configured": self.reader is not None, "last_check": self.last_check,
                  "last_error": self.last_error, "backoff_until": self.blocked_until,
                  "submission_enabled": False, "items": [], "counts": {}}
        if self.reader is None:
            return result
        with Ledger().db() as db:
            cooldown = db.execute("SELECT blocked_until,last_error FROM certification_worker_state WHERE scope=?", (self.reader.scope,)).fetchone()
            rows = db.execute("SELECT id,state,reason,broker_status,filled,reads,next_read,created_at FROM rehearsal_reconciliation WHERE scope=? ORDER BY created_at DESC,id LIMIT 50", (self.reader.scope,)).fetchall()
            counts = db.execute("SELECT state,COUNT(*) AS n FROM rehearsal_reconciliation WHERE scope=? GROUP BY state", (self.reader.scope,)).fetchall()
        result["items"] = [dict(row) for row in rows]
        result["counts"] = {row["state"]: row["n"] for row in counts}
        if cooldown and cooldown["blocked_until"] > self.clock():
            result["backoff_until"], result["last_error"] = cooldown["blocked_until"], cooldown["last_error"]
        result["account_blocked"] = any(result["counts"].get(state, 0) for state in ("SUBMITTING", "UNKNOWN", "MANUAL_REVIEW"))
        return result


async def run_worker(worker, stop):
    while not stop.is_set():
        await asyncio.to_thread(worker.tick)
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass
