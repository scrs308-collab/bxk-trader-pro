"""Regression tests for staging confirmation replay, expiry, and order mutation.

Uses a temporary SQLite path with a mount-check shim; never calls a broker.
"""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException


class ConfirmationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with patch.dict(os.environ, {"BXK_STAGING_CONFIRMATION_DB": str(Path(self.tmp.name) / "test.sqlite3")}):
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

    def test_failed_checks_never_issue_token(self):
        with self.assertRaises(HTTPException):
            self.module.issue(self.order, {"all_checks_pass": False, "server_quote_verified": True})


if __name__ == "__main__":
    unittest.main()
