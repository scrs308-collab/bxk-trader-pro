"""Regression tests for staging confirmation replay, expiry, and order mutation.

Uses a temporary SQLite path with a mount-check shim; never calls a broker.
"""
import importlib
import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException


class ConfirmationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "test.sqlite3"
        self.env_patch = patch.dict(os.environ, {"BXK_STAGING_CONFIRMATION_DB": str(self.db_path)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        import staging_confirmation
        self.module = importlib.reload(staging_confirmation)
        self.mount = patch.object(self.module.os.path, "ismount", return_value=True)
        self.mount.start()
        self.addCleanup(self.mount.stop)
        self.order = SimpleNamespace(
            legs=[SimpleNamespace(symbol=f"SPXW  261026{kind}{strike:08d}", action=action)
                  for kind, strike, action in [
                      ("P", 7550000, "Sell to Open"), ("P", 7540000, "Buy to Open"),
                      ("C", 7690000, "Sell to Open"), ("C", 7700000, "Buy to Open")]],
            quantity=1, limit_price=2.90)
        self.result = {"all_checks_pass": True, "server_quote_verified": True}

    def test_single_use_survives_module_reload(self):
        token = self.module.issue(self.order, self.result)["confirmation_token"]
        self.assertTrue(self.module.consume(self.order, token)["acknowledged"])
        self.module = importlib.reload(self.module)
        with self.assertRaises(HTTPException) as caught:
            self.module.consume(self.order, token)
        self.assertEqual(caught.exception.status_code, 409)

    def test_confirmation_atomically_records_simulated_intent(self):
        token = self.module.issue(self.order, self.result)["confirmation_token"]
        result = self.module.consume(self.order, token)
        self.assertEqual(result["order_intent_status"], "SIMULATED_NO_SUBMISSION")
        self.assertFalse(result["submitted"])
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT status FROM staging_order_intents WHERE key_hash=?",
                (self.module._hash(token),)
            ).fetchone()
        self.assertEqual(row, ("SIMULATED_NO_SUBMISSION",))
        with self.assertRaises(HTTPException):
            self.module.consume(self.order, token)

    def test_expired_token_rejected(self):
        token = self.module.issue(self.order, self.result)["confirmation_token"]
        with patch.object(self.module.time, "time", return_value=10**12):
            with self.assertRaises(HTTPException) as caught:
                self.module.consume(self.order, token)
        self.assertEqual(caught.exception.status_code, 409)

    def test_changed_order_consumes_token(self):
        token = self.module.issue(self.order, self.result)["confirmation_token"]
        changed = SimpleNamespace(legs=self.order.legs, quantity=1, limit_price=2.85)
        with self.assertRaises(HTTPException) as caught:
            self.module.consume(changed, token)
        self.assertEqual(caught.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            self.module.consume(self.order, token)

    def test_concurrent_consumers_only_one_succeeds(self):
        token = self.module.issue(self.order, self.result)["confirmation_token"]
        def consume_once(_):
            try:
                return self.module.consume(self.order, token)["acknowledged"]
            except HTTPException as exc:
                return exc.status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(consume_once, range(8)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(409), 7)

    def test_missing_volume_fails_closed(self):
        with patch.object(self.module.os.path, "ismount", return_value=False):
            with self.assertRaises(HTTPException) as caught:
                self.module.issue(self.order, self.result)
        self.assertEqual(caught.exception.status_code, 503)

    def test_order_intent_idempotency_survives_reload(self):
        import staging_order_ledger
        ledger = importlib.reload(staging_order_ledger)
        key = "rehearsal-idempotency-key-0001"
        first = ledger.reserve_intent(self.order, key)
        self.assertEqual(first["status"], "SIMULATED_NO_SUBMISSION")
        self.assertFalse(first["submitted"])
        ledger = importlib.reload(ledger)
        with self.assertRaises(HTTPException) as caught:
            ledger.reserve_intent(self.order, key)
        self.assertEqual(caught.exception.status_code, 409)

    def test_order_intent_key_cannot_change_order(self):
        import staging_order_ledger
        ledger = importlib.reload(staging_order_ledger)
        key = "rehearsal-idempotency-key-0002"
        ledger.reserve_intent(self.order, key)
        changed = SimpleNamespace(legs=self.order.legs, quantity=1, limit_price=2.80)
        with self.assertRaises(HTTPException) as caught:
            ledger.reserve_intent(changed, key)
        self.assertEqual(caught.exception.status_code, 409)

    def test_failed_checks_never_issue_token(self):
        with self.assertRaises(HTTPException):
            self.module.issue(self.order, {"all_checks_pass": False, "server_quote_verified": True})


if __name__ == "__main__":
    unittest.main()
