"""Separate-process persistence and transaction-failure tests; no broker calls.

The mount shim is confined to the child test process. These tests exercise SQLite
on a temporary local directory, not a Railway volume or an actual host restart.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
from contextlib import closing
import json, sys
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
import staging_confirmation as confirmation
import staging_order_ledger as ledger
command, token = sys.argv[1:3]
order = SimpleNamespace(legs=[SimpleNamespace(symbol="SPXW  261026P07550000", action="Sell to Open")], quantity=1, limit_price=2.9)
with patch.object(confirmation.os.path, "ismount", return_value=True):
    try:
        if command == "issue":
            result = confirmation.issue(order, {"all_checks_pass": True, "server_quote_verified": True})
        elif command == "receipt":
            result = confirmation.receipt(order, token)
        elif command == "consume":
            result = confirmation.consume(order, token)
        else:
            result = ledger.reserve_intent(order, token)
        print(json.dumps({"status": 200, "result": result}))
    except HTTPException as exc:
        print(json.dumps({"status": exc.status_code, "detail": exc.detail}))
'''


class RestartSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "confirmations.sqlite3"

    def child(self, command, token="unused"):
        env = dict(os.environ, BXK_STAGING_CONFIRMATION_DB=str(self.db))
        result = subprocess.run([sys.executable, "-c", CHILD, command, token],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_confirmation_replay_in_new_process_retains_exactly_one_intent(self):
        issued = self.child("issue")
        token = issued["result"]["confirmation_token"]
        self.assertEqual(self.child("consume", token)["status"], 200)
        before = self.child("receipt", token)["result"]
        self.assertTrue(before["durable_intent_verified"])
        self.assertEqual(self.child("consume", token)["status"], 409)
        self.assertEqual(self.child("receipt", token)["result"], before)
        with closing(sqlite3.connect(self.db, isolation_level=None)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM confirmations WHERE consumed_at IS NOT NULL").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT status FROM staging_order_intents").fetchall(), [("SIMULATED_NO_SUBMISSION",)])

    def test_intent_replay_in_new_process_retains_exactly_one_record(self):
        key = "restart-rehearsal-intent-0001"
        self.assertEqual(self.child("reserve", key)["status"], 200)
        replay = self.child("reserve", key)
        self.assertEqual(replay["status"], 409)
        self.assertIn("Duplicate", replay["detail"])
        with closing(sqlite3.connect(self.db, isolation_level=None)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM staging_order_intents").fetchone()[0], 1)

    def test_failed_intent_insert_rolls_back_token_consumption(self):
        token = self.child("issue")["result"]["confirmation_token"]
        with closing(sqlite3.connect(self.db, isolation_level=None)) as db:
            db.execute("CREATE TABLE staging_order_intents (key_hash TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL)")
            db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON staging_order_intents BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.assertEqual(self.child("consume", token)["status"], 503)
        with closing(sqlite3.connect(self.db, isolation_level=None)) as db:
            self.assertIsNone(db.execute("SELECT consumed_at FROM confirmations").fetchone()[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM staging_order_intents").fetchone()[0], 0)
            db.execute("DROP TRIGGER fail_insert")
        self.assertEqual(self.child("consume", token)["status"], 200)

    def test_unconsumed_token_is_not_a_durable_intent_receipt(self):
        token = self.child("issue")["result"]["confirmation_token"]
        self.assertEqual(self.child("reserve", "another-simulated-intent-key")["status"], 200)
        result = self.child("receipt", token)
        self.assertEqual(result["status"], 200)
        self.assertFalse(result["result"]["durable_intent_verified"])


if __name__ == "__main__":
    unittest.main()
