"""Offline failure-injection tests. Never uses a broker or production database."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import staging_confirmation as confirmation
from staging_reconciliation import Ledger, Snapshot, canonical
from staging_reconciliation_rehearsal import fixture_order, fixture_match, FixtureReader, run, receipt
from staging_reconciliation_reader import CertificationOrderReader


class ReconciliationTests(unittest.TestCase):
    def test_complete_empty_certification_collections_never_release_unknown(self):
        session = Mock()
        reader = CertificationOrderReader("CERT0001", "test-user", lambda: {}, session=session)
        history = Mock(status_code=200)
        history.json.return_value = {"data": {"items": []}, "pagination": {"page-offset": 0, "total-pages": 0}}
        today = Mock(status_code=200)
        today.json.return_value = {"context": "/accounts/CERT0001/orders/live", "data": {"items": []}}
        session.get.side_effect = [history, today]
        intent = self.ledger.create(reader.scope, "certification-empty-history-key", fixture_order())
        attempt = self.ledger.begin_attempt(intent)
        self.ledger.mark_unknown(intent, attempt)
        self.assertEqual(self.ledger.reconcile(intent, reader)["state"], "UNKNOWN")
        with self.assertRaises(HTTPException) as duplicate:
            self.ledger.begin_attempt(intent)
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as replacement:
            self.ledger.create(reader.scope, "different-certification-intent-key", fixture_order())
        self.assertEqual(replacement.exception.status_code, 409)
        session.post.assert_not_called()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"reconciliation.sqlite3"
        for helper in [patch.object(confirmation, "DB", self.path),
                       patch.object(confirmation.os.path, "ismount", return_value=True),
                       patch.dict(os.environ, {"BXK_PREVIEW_MODE": "true", "BXK_LIVE_TRADING_ENABLED": "false"})]:
            helper.start()
            self.addCleanup(helper.stop)
        self.now = 1800000000
        self.ledger = Ledger(clock=lambda: self.now, jitter=lambda: 0, max_reads=3)
        self.scope = "simulation:test-user:cert-account"
        self.key = "stable-rehearsal-order-key-0001"
        self.intent = self.ledger.create(self.scope, self.key, fixture_order())

    def unknown(self):
        attempt = self.ledger.begin_attempt(self.intent)
        self.ledger.mark_unknown(self.intent, attempt)
        return self.ledger.get(self.intent)

    def observe(self, row, items, complete=True):
        return self.ledger.reconcile(row["id"], FixtureReader(Snapshot(row["scope"], items, complete)))

    def assert_blocked(self):
        with self.assertRaises(HTTPException) as caught:
            self.ledger.begin_attempt(self.intent)
        self.assertEqual(caught.exception.status_code, 409)

    def test_one_of_eight_workers_can_reserve_attempt(self):
        def attempt(_):
            try:
                return self.ledger.begin_attempt(self.intent)
            except HTTPException as exc:
                return exc.status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(results.count(409), 7)
        self.assertEqual(receipt(self.intent)["attempt_count"], 1)

    def test_timeout_and_empty_search_never_allow_retry_or_replacement(self):
        row = self.unknown()
        result = self.observe(row, [])
        self.assertEqual(result["state"], "UNKNOWN")
        self.assert_blocked()
        with self.assertRaises(HTTPException):
            self.ledger.create(self.scope, "new-browser-confirmation-key", fixture_order())
        # Scope isolation permits a separate simulated account.
        self.ledger.create("simulation:another-account", self.key, fixture_order())

    def test_lost_response_and_restart_find_broker_order(self):
        self.ledger.begin_attempt(self.intent)  # crash after fake broker accepted
        self.assertEqual(self.ledger.recover_inflight(), 1)
        row = self.ledger.get(self.intent)
        self.assertEqual(row["state"], "UNKNOWN")
        found = self.observe(row, [fixture_match(row)])
        self.assertEqual(found["state"], "ACKNOWLEDGED")
        self.assertEqual(found["broker_id"], "12345")
        self.assert_blocked()

    def test_restart_in_separate_process_retains_attempt_and_key(self):
        before = self.unknown()
        env = dict(os.environ, BXK_STAGING_CONFIRMATION_DB=str(self.path))
        script = '''
import json,sys
from unittest.mock import patch
from staging_reconciliation import Ledger
from fastapi import HTTPException
with patch("staging_confirmation.os.path.ismount", return_value=True):
    ledger=Ledger()
    ledger.recover_inflight()
    row=ledger.get(sys.argv[1])
    try:
        ledger.begin_attempt(sys.argv[1])
        code=200
    except HTTPException as exc:
        code=exc.status_code
    print(json.dumps({"attempt":row["attempt"],"correlation":row["correlation"],"code":code}))
'''
        result = subprocess.run([sys.executable, "-c", script, self.intent], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data, {"attempt": before["attempt"], "correlation": before["correlation"], "code": 409})

    def test_partial_fill_does_not_release_intent_and_fill_is_monotonic(self):
        row = self.unknown()
        partial = self.observe(row, [fixture_match(row, "Partially Filled", "1")])
        self.assertEqual((partial["state"], partial["filled"]), ("ACKNOWLEDGED", "1"))
        self.assert_blocked()
        self.now += 10
        stale = self.observe(partial, [fixture_match(row, "Live", "0")])
        self.assertEqual(stale["filled"], "1")
        self.now += 10
        final = self.observe(stale, [fixture_match(row, "Filled", "2")])
        self.assertEqual(final["state"], "TERMINAL")
        with self.assertRaises(HTTPException):
            self.observe(final, [fixture_match(row)])

    def test_cancelled_partial_order_retains_executed_exposure(self):
        row = self.unknown()
        partial = self.observe(row, [fixture_match(row, "Partially Filled", "1")])
        self.now += 10
        result = self.observe(partial, [fixture_match(row, "Cancelled", "1")])
        self.assertEqual((result["state"], result["filled"]), ("TERMINAL", "1"))
        self.assert_blocked()

    def test_terminal_rejection_never_permits_same_attempt_retry(self):
        row = self.unknown()
        result = self.observe(row, [fixture_match(row, "Rejected")])
        self.assertEqual(result["state"], "TERMINAL")
        self.assert_blocked()

    def test_multiple_matches_or_payload_conflict_require_manual_review(self):
        row = self.unknown()
        result = self.observe(row, [fixture_match(row), fixture_match(row, broker_id="999")])
        self.assertEqual(result["state"], "MANUAL_REVIEW")
        self.assert_blocked()

    def test_wrong_scope_requires_manual_review(self):
        row = self.unknown()
        result = self.ledger.reconcile(self.intent, FixtureReader(Snapshot("simulation:wrong-account", [], True)))
        self.assertEqual(result["state"], "MANUAL_REVIEW")

    def test_broker_payload_mutation_requires_manual_review(self):
        row = self.unknown()
        item = fixture_match(row)
        item["price"] = "2.80"
        self.assertEqual(self.observe(row, [item])["state"], "MANUAL_REVIEW")

    def test_incomplete_history_never_acknowledges_even_one_match(self):
        row = self.unknown()
        self.assertEqual(self.observe(row, [fixture_match(row)], False)["state"], "UNKNOWN")

    def test_duplicate_pages_of_same_order_are_deduplicated(self):
        row = self.unknown()
        self.assertEqual(self.observe(row, [fixture_match(row), fixture_match(row)])["state"], "ACKNOWLEDGED")

    def test_missing_correlation_does_not_match_similar_order(self):
        row = self.unknown()
        item = fixture_match(row)
        item.pop("external-identifier")
        self.assertEqual(self.observe(row, [item])["state"], "UNKNOWN")

    def test_backoff_and_recovery_limit(self):
        row = self.unknown()
        first = self.observe(row, [])
        self.assertEqual(first["next_read"], self.now+2)
        with self.assertRaises(HTTPException):
            self.observe(row, [])
        for _ in range(2):
            self.now += 20
            first = self.observe(row, [])
        self.assertEqual(first["state"], "MANUAL_REVIEW")

    def test_read_error_retains_block_and_redacts_provider_error(self):
        row = self.unknown()
        reader = Mock()
        reader.read.side_effect = TimeoutError("secret account access-token")
        result = self.ledger.reconcile(self.intent, reader)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["reason"], "READ_UNAVAILABLE")
        self.assertNotIn("secret", json.dumps(result))

    def test_reader_has_no_write_lock_and_stale_worker_cannot_overwrite(self):
        row = self.unknown()
        def read(_):
            self.now += 61
            other = Ledger(clock=lambda: self.now, jitter=lambda: 0)
            other.reconcile(self.intent, FixtureReader(Snapshot(row["scope"], [fixture_match(row, "Filled", "2")], True)))
            return Snapshot(row["scope"], [], True)
        reader = Mock()
        reader.read.side_effect = read
        with self.assertRaises(HTTPException) as caught:
            self.ledger.reconcile(self.intent, reader)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.ledger.get(self.intent)["state"], "TERMINAL")

    def test_failed_result_commit_preserves_uncertainty_and_recovers(self):
        row = self.unknown()
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute("CREATE TRIGGER fail_result BEFORE UPDATE ON rehearsal_reconciliation WHEN NEW.state='ACKNOWLEDGED' BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
        with self.assertRaises(HTTPException) as caught:
            self.observe(row, [fixture_match(row)])
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(self.ledger.get(self.intent)["state"], "UNKNOWN")
        self.assert_blocked()
        with closing(sqlite3.connect(self.path, isolation_level=None)) as db:
            db.execute("DROP TRIGGER fail_result")
        self.ledger.recover_inflight()
        self.assertEqual(self.observe(row, [fixture_match(row)])["state"], "ACKNOWLEDGED")

    def test_changed_key_payload_and_decimal_precision(self):
        changed = fixture_order()
        changed["price"] = "2.8"
        with self.assertRaises(HTTPException):
            self.ledger.create(self.scope, self.key, changed)
        reversed_order = fixture_order()
        reversed_order["legs"].reverse()
        self.assertEqual(canonical(reversed_order), canonical(fixture_order()))
        for invalid in ("NaN", "Infinity", "2.901"):
            changed["price"] = invalid
            with self.assertRaises(ValueError):
                canonical(changed)

    def test_live_flags_or_missing_volume_block_reconciliation(self):
        with patch.dict(os.environ, {"BXK_LIVE_TRADING_ENABLED": "true"}):
            with self.assertRaises(HTTPException):
                Ledger()
        with patch.object(confirmation.os.path, "ismount", return_value=False):
            with self.assertRaises(HTTPException) as caught:
                self.ledger.get(self.intent)
            self.assertEqual(caught.exception.status_code, 503)

    def test_owner_rehearsal_and_restart_receipt(self):
        report = run()
        self.assertTrue(report["all_passed"])
        pending = report["restart_receipt"]
        self.assertEqual(pending["state"], "SUBMITTING")
        self.ledger.recover_inflight()
        recovered = receipt(pending["id"])
        self.assertEqual(recovered["state"], "UNKNOWN")
        self.assertEqual(recovered["attempt_count"], 1)
        self.assertTrue(recovered["retry_blocked"])
        self.assertEqual(recovered["attempt"], pending["attempt"])

    @unittest.skipIf(os.getenv("BXK_SKIP_ASGI_SOCKET_TESTS") == "true", "Local sandbox blocks Windows asyncio socket pairs; run in Linux CI")
    def test_http_startup_recovers_and_rejects_duplicate_attempt(self):
        from fastapi.testclient import TestClient
        import staging_preview
        before = self.ledger.begin_attempt(self.intent)
        with patch.object(staging_preview, "_configured", return_value=True), \
             patch.object(staging_preview, "_authorized", return_value=True), \
             TestClient(staging_preview.app) as client:
            response = client.get("/api/workbench/reconciliation-rehearsal/"+self.intent)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["state"], "UNKNOWN")
            self.assertEqual(response.json()["attempt"], before)
            self.assertEqual(client.post("/api/workbench/reconciliation-rehearsal/"+self.intent+"/attempt").status_code, 409)
            self.assertEqual(client.post("/api/order-submit").status_code, 503)

    @unittest.skipIf(os.getenv("BXK_SKIP_ASGI_SOCKET_TESTS") == "true", "Local sandbox blocks Windows asyncio socket pairs; run in Linux CI")
    def test_reconciliation_routes_require_authentication(self):
        from fastapi.testclient import TestClient
        import staging_preview
        with patch.object(staging_preview, "_configured", return_value=True), \
             patch.object(staging_preview, "_authorized", return_value=False), \
             TestClient(staging_preview.app) as client:
            self.assertEqual(client.post("/api/workbench/reconciliation-rehearsal").status_code, 401)
            self.assertEqual(client.get("/api/workbench/reconciliation-rehearsal/"+self.intent).status_code, 401)
            self.assertEqual(client.post("/api/workbench/reconciliation-rehearsal/"+self.intent+"/attempt").status_code, 401)
            self.assertEqual(client.get("/api/workbench/reconciliation-status").status_code, 401)
            self.assertEqual(client.get("/api/workbench/owner-review/"+self.intent).status_code, 401)
            self.assertEqual(client.post("/api/workbench/owner-review/"+self.intent+"/refresh").status_code, 401)
            self.assertEqual(client.post("/api/workbench/owner-review/"+self.intent+"/resolve", json={}).status_code, 401)


class CertificationReaderTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.reader = CertificationOrderReader("CERT0001", "test-user", lambda: {"Authorization": "Bearer fixture"}, session=self.session, clock=lambda: 1800000100)
        self.row = {"scope": self.reader.scope, "attempt_at": 1800000000, "correlation": "fixture-correlation", "broker_id": None}
        self.item = {**fixture_order(), "id": "12345", "account-number": "CERT0001",
                     "external-identifier": "fixture-correlation", "status": "Live"}
        for leg in self.item["legs"]:
            leg["remaining-quantity"] = "2"
            leg["fills"] = []

    def page(self, items, page=0, total=1):
        response = Mock(status_code=200)
        response.json.return_value = {"data": {"items": items}, "pagination": {"page-offset": page, "total-pages": total}}
        return response

    def test_pagination_history_and_today_use_only_certification_gets(self):
        self.session.get.side_effect = [self.page([], 0, 2), self.page([self.item], 1, 2), self.page([]), self.page([])]
        result = self.reader.read(self.row)
        self.assertTrue(result.complete)
        self.assertEqual(result.items[0]["filled-quantity"], "0")
        self.assertEqual(self.session.get.call_count, 4)
        for call in self.session.get.call_args_list:
            self.assertTrue(call.args[0].startswith("https://api.cert.tastyworks.com/accounts/CERT0001/orders"))
            self.assertFalse(call.kwargs["allow_redirects"])
        self.session.post.assert_not_called()
        self.assertIn("start-at", self.session.get.call_args_list[0].kwargs["params"])

    def test_repeated_page_is_incomplete(self):
        self.session.get.side_effect = [self.page([self.item], 0, 3), self.page([self.item], 1, 3), self.page([]), self.page([])]
        self.assertFalse(self.reader.read(self.row).complete)

    def test_history_window_crosses_midnight_and_preserves_terminal_orders(self):
        from datetime import datetime, timezone
        self.row["attempt_at"] = datetime(2026, 10, 25, 23, 59, tzinfo=timezone.utc).timestamp()
        self.reader.clock = lambda: datetime(2026, 10, 26, 0, 2, tzinfo=timezone.utc).timestamp()
        self.item["status"] = "Cancelled"
        self.session.get.side_effect = [self.page([self.item]), self.collection([])]
        result = self.reader.read(self.row)
        self.assertTrue(result.complete)
        params = self.session.get.call_args_list[0].kwargs["params"]
        self.assertTrue(params["start-at"].startswith("2026-10-25"))
        self.assertTrue(params["end-at"].startswith("2026-10-26"))

    def collection(self, items):
        response = Mock(status_code=200)
        response.json.return_value = {"context": "/accounts/CERT0001/orders/live", "data": {"items": items}}
        return response

    def test_unpaginated_today_empty_and_nonempty_collections(self):
        for items in ([], [self.item]):
            self.session.get.side_effect = [self.page([]), self.collection(items)]
            result = self.reader.read(self.row)
            self.assertTrue(result.complete)
            self.assertEqual(len(result.items), len(items))
            self.assertEqual(self.session.get.call_args.kwargs["params"], {})

    def test_unpaginated_history_is_still_incomplete(self):
        history = self.collection([])
        history.json.return_value["context"] = "/accounts/CERT0001/orders"
        self.session.get.side_effect = [history, self.collection([])]
        self.assertFalse(self.reader.read(self.row).complete)

    def test_unpaginated_today_rejects_ambiguous_or_malformed_envelopes(self):
        original = self.collection([]).json.return_value
        invalid = [None, {}, {**original, "context": "/accounts/OTHER/orders/live"},
                   {**original, "next": "more"}, {**original, "data": {"items": [], "has-more": True}},
                   {**original, "data": {"items": None}},
                   {**original, "data": {"items": [None]}},
                   {**original, "data": {"items": [{"id": "1", "account-number": "OTHER"}]}}]
        for body in invalid:
            with self.subTest(body=body):
                response = Mock(status_code=200)
                response.json.return_value = body
                self.session.get.side_effect = [response]
                self.assertFalse(self.reader.today()[1])

    def test_explicit_broken_pagination_does_not_use_collection_fallback(self):
        broken = self.collection([])
        broken.json.return_value["pagination"] = {}
        self.session.get.side_effect = [broken, broken]
        self.assertFalse(self.reader.today()[1])

    def test_unpaginated_today_with_paginated_history_finds_terminal_match(self):
        self.item["status"] = "Cancelled"
        self.session.get.side_effect = [self.page([]), self.collection([self.item])]
        result = self.reader.read(self.row)
        self.assertTrue(result.complete)
        self.assertEqual(result.items[0]["status"], "Cancelled")

    def test_imbalanced_fill_or_wrong_account_is_not_a_valid_match(self):
        item = deepcopy(self.item)
        item["legs"][0]["remaining-quantity"] = "1"
        self.assertIsNone(self.reader._normalise(item)["filled-quantity"])
        item["account-number"] = "WRONG0001"
        self.assertEqual(self.reader._normalise(item)["scope"], "INVALID_ACCOUNT")

    def test_cancelled_remaining_quantity_does_not_invent_fills(self):
        self.item["status"] = "Cancelled"
        for leg in self.item["legs"]:
            leg["remaining-quantity"] = "0"
        self.assertEqual(self.reader._normalise(self.item)["filled-quantity"], "0")
        for leg in self.item["legs"]:
            leg["fills"] = [{"quantity": "1"}]
        self.assertEqual(self.reader._normalise(self.item)["filled-quantity"], "1")

    def test_provider_errors_and_scope_mismatch_never_mutate_broker(self):
        for code in (401, 403, 429, 500):
            self.session.get.return_value = Mock(status_code=code)
            with self.assertRaises(RuntimeError):
                self.reader.read(self.row)
        self.session.get.reset_mock()
        self.row["scope"] = "simulation:wrong"
        with self.assertRaises(ValueError):
            self.reader.read(self.row)
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
