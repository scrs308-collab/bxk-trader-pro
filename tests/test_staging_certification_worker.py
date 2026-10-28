import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests
from fastapi import HTTPException

import staging_confirmation as confirmation
from staging_certification_worker import CertificationWorker
from staging_reconciliation import Ledger
from staging_reconciliation_rehearsal import fixture_order
from staging_owner_review import OwnerReview


class CertificationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1800000000
        self.env = {"BXK_PREVIEW_MODE": "true", "BXK_LIVE_TRADING_ENABLED": "false",
                    "BXK_CERT_RECONCILIATION_ENABLED": "true",
                    "TASTYTRADE_CERT_BASE_URL": "https://api.cert.tastyworks.com",
                    "TASTYTRADE_CERT_ACCOUNT_NUMBER": "CERT0001",
                    "TASTYTRADE_CERT_CLIENT_ID": "fixture-id",
                    "TASTYTRADE_CERT_CLIENT_SECRET": "fixture-secret",
                    "TASTYTRADE_CERT_REFRESH_TOKEN": "fixture-refresh"}
        for context in (patch.dict(os.environ, self.env),
                        patch.object(confirmation, "DB", Path(self.tmp.name)/"worker.sqlite3"),
                        patch.object(confirmation.os.path, "ismount", return_value=True)):
            context.start()
            self.addCleanup(context.stop)
        self.session = Mock()
        self.worker = CertificationWorker(session=self.session, clock=lambda: self.now)
        self.ledger = Ledger(clock=lambda: self.now, jitter=lambda: 0)

    def unknown(self, scope=None):
        intent = self.ledger.create(scope or self.worker.reader.scope, "worker-intent-key-0001", fixture_order())
        self.ledger.mark_unknown(intent, self.ledger.begin_attempt(intent))
        return intent

    def reply(self, body=None, status=200, headers=None):
        response = Mock(status_code=status, headers=headers or {})
        response.json.return_value = body
        return response

    def empty(self):
        return [self.reply({"data": {"items": []}, "pagination": {"page-offset": 0, "total-pages": 0}}),
                self.reply({"context": "/accounts/CERT0001/orders/live", "data": {"items": []}})]

    def cached_token(self):
        self.worker.token, self.worker.token_until = "fixture-access", self.now+500

    def test_disabled_bad_host_or_live_flags_never_contact_provider(self):
        self.unknown()
        for key, value in [("BXK_CERT_RECONCILIATION_ENABLED", "false"),
                           ("TASTYTRADE_CERT_BASE_URL", "https://api.tastyworks.com"),
                           ("BXK_LIVE_TRADING_ENABLED", "true")]:
            with patch.dict(os.environ, {key: value}):
                CertificationWorker(session=self.session).tick()
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_synthetic_rehearsals_are_never_polled(self):
        self.unknown("simulation:synthetic-fixture")
        self.worker.tick()
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_empty_match_stays_unknown_and_next_tick_obeys_durable_backoff(self):
        intent = self.unknown()
        self.cached_token()
        self.session.get.side_effect = self.empty()
        self.worker.tick()
        self.assertEqual(self.ledger.get(intent)["state"], "UNKNOWN")
        self.worker.tick()
        self.assertEqual(self.session.get.call_count, 2)
        status = self.worker.status()
        self.assertTrue(status["account_blocked"])
        self.assertEqual(status["items"][0]["reason"], "NO_MATCH_YET")
        self.assertNotIn("fixture-access", json.dumps(status))
        self.assertNotIn("fixture-secret", json.dumps(status))

    def test_rate_limit_retry_after_survives_new_worker_and_delays_account(self):
        intent = self.unknown()
        self.cached_token()
        self.session.get.return_value = self.reply(status=429, headers={"Retry-After": "120"})
        self.worker.tick()
        row = self.ledger.get(intent)
        self.assertEqual((row["state"], row["reason"]), ("UNKNOWN", "BROKER_RATE_LIMITED"))
        self.assertGreaterEqual(row["next_read"], self.now+120)
        self.now += 60
        restarted = CertificationWorker(session=self.session, clock=lambda: self.now)
        restarted.tick()
        self.assertEqual(self.session.get.call_count, 1)
        self.session.post.assert_not_called()
        self.assertEqual(restarted.status()["backoff_until"], 1800000120)

    def test_unauthorized_clears_token_then_refreshes_after_cooldown(self):
        intent = self.unknown()
        self.cached_token()
        self.session.get.return_value = self.reply(status=401)
        self.worker.tick()
        self.assertIsNone(self.worker.token)
        self.assertEqual(self.ledger.get(intent)["reason"], "BROKER_AUTH_UNAVAILABLE")
        self.worker.tick()
        self.assertEqual(self.session.get.call_count, 1)
        self.now += 40
        self.session.post.return_value = self.reply({"access_token": "new-fixture-token", "expires_in": 900})
        self.session.get.side_effect = [self.reply({"data": {"items": [{"account": {"account-number": "CERT0001"}}]}}), *self.empty()]
        self.worker.tick()
        self.assertEqual(self.session.post.call_count, 1)
        self.assertEqual(self.session.post.call_args.args[0], "https://api.cert.tastyworks.com/oauth/token")
        self.assertEqual(self.session.post.call_args.kwargs["json"]["scope"], "read")
        self.assertEqual(self.ledger.get(intent)["state"], "UNKNOWN")
        self.assertIsNone(self.worker.last_error)

    def test_new_token_requires_account_ownership_before_order_reads(self):
        self.unknown()
        self.session.post.return_value = self.reply({"access_token": "fixture-token", "expires_in": 900})
        self.session.get.return_value = self.reply({"data": {"items": []}})
        self.worker.tick()
        self.assertEqual(self.session.get.call_count, 1)
        self.assertTrue(self.session.get.call_args.args[0].endswith("/customers/me/accounts"))
        self.assertIsNone(self.worker.token)
        self.assertEqual(self.worker.last_error, "BROKER_AUTH_UNAVAILABLE")

    def test_expired_cached_token_refreshes_and_is_reused(self):
        self.unknown()
        self.worker.token, self.worker.token_until = "expired-fixture", self.now-1
        self.session.post.return_value = self.reply({"access_token": "fresh-fixture", "expires_in": 900})
        self.session.get.side_effect = [self.reply({"data": {"items": [{"account": {"account-number": "CERT0001"}}]}}), *self.empty(), *self.empty()]
        self.worker.tick()
        self.now += 10
        self.worker.tick()
        self.assertEqual(self.session.post.call_count, 1)
        self.assertEqual(self.worker.token, "fresh-fixture")

    def test_storage_failure_never_contacts_provider(self):
        self.unknown()
        with patch.object(confirmation.os.path, "ismount", return_value=False):
            self.worker.tick()
        self.assertEqual(self.worker.last_error, "DURABLE_STORAGE_UNAVAILABLE")
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_owner_network_and_malformed_reads_persist_account_backoff(self):
        intent = self.unknown()
        with self.ledger.db(True) as db:
            db.execute("UPDATE rehearsal_reconciliation SET state='MANUAL_REVIEW' WHERE id=?", (intent,))
        for index, failure in enumerate((requests.Timeout("private provider detail"), KeyError("private response field"))):
            self.cached_token()
            self.session.get.side_effect = failure
            review = OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now)
            with self.assertRaises(HTTPException) as caught:
                review.refresh(intent)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertNotIn("private", str(caught.exception.detail))
            calls = self.session.get.call_count
            self.assertEqual(self.worker.failures, index+1)
            restarted = CertificationWorker(session=self.session, clock=lambda: self.now)
            with self.assertRaises(HTTPException) as blocked:
                OwnerReview(restarted, ledger=self.ledger, clock=lambda: self.now).refresh(intent)
            self.assertEqual(blocked.exception.status_code, 409)
            self.assertEqual(self.session.get.call_count, calls)
            delay = 30 * 2**index
            self.assertEqual(restarted.status()["backoff_until"], self.now+delay)
            self.assertEqual(self.ledger.get(intent)["state"], "MANUAL_REVIEW")
            with self.ledger.db() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_review_evidence").fetchone()[0], 0)
            self.now += delay+1
            self.worker = restarted
        self.session.post.assert_not_called()

    def test_failure_escalation_survives_restarts_and_complete_read_resets(self):
        intent = self.unknown()
        with self.ledger.db(True) as db:
            db.execute("UPDATE rehearsal_reconciliation SET state='MANUAL_REVIEW' WHERE id=?", (intent,))
        for delay in (30, 60, 120, 240, 300, 300):
            self.worker = CertificationWorker(session=self.session, clock=lambda: self.now)
            self.cached_token()
            self.session.get.side_effect = requests.Timeout()
            with self.assertRaises(HTTPException):
                OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now).refresh(intent)
            self.assertEqual(self.worker.status()["backoff_until"], self.now+delay)
            self.now += delay+1
        # Incomplete broker collections cannot reset consecutive failure history.
        self.session.get.side_effect = [self.reply({"data": {"items": []}}), self.empty()[1]]
        review = OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now)
        self.assertFalse(review.refresh(intent)["complete"])
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT failures FROM certification_provider_failures").fetchone()[0], 5)
        self.session.get.side_effect = self.empty()
        self.assertTrue(review.refresh(intent)["complete"])
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_provider_failures").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_worker_state").fetchone()[0], 0)
        self.session.get.side_effect = requests.Timeout()
        with self.assertRaises(HTTPException):
            review.refresh(intent)
        self.assertEqual(self.worker.status()["backoff_until"], self.now+30)
        self.session.post.assert_not_called()

    def test_terminal_and_manual_review_attempts_are_not_polled(self):
        intent = self.unknown()
        for state in ("TERMINAL", "MANUAL_REVIEW"):
            with self.ledger.db(True) as db:
                db.execute("UPDATE rehearsal_reconciliation SET state=? WHERE id=?", (state, intent))
            self.worker.tick()
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
