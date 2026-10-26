from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import staging_confirmation as confirmation
from staging_reconciliation import Ledger, Snapshot
from staging_reconciliation_rehearsal import FixtureReader, fixture_match, fixture_order
from staging_owner_review import OwnerReview, register_guarded_test_proof


class OwnerReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for context in (patch.dict(os.environ, {"BXK_PREVIEW_MODE": "true", "BXK_LIVE_TRADING_ENABLED": "false"}),
                        patch.object(confirmation, "DB", Path(self.tmp.name)/"review.sqlite3"),
                        patch.object(confirmation.os.path, "ismount", return_value=True)):
            context.start();self.addCleanup(context.stop)
        self.now = 1800000000
        self.ledger = Ledger(clock=lambda: self.now, jitter=lambda: 0, max_reads=1)
        self.scope = "simulation:cert:fixture-account"
        self.intent = self.ledger.create(self.scope, "original-owner-review-key", fixture_order())
        self.ledger.mark_unknown(self.intent, self.ledger.begin_attempt(self.intent))
        self.ledger.reconcile(self.intent, FixtureReader(Snapshot(self.scope, [], True)))
        self.worker = SimpleNamespace(reader=SimpleNamespace(scope=self.scope, read=Mock(return_value=Snapshot(self.scope, [], True))),
                                      lock=threading.Lock(), blocked_until=0)
        self.service = OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now)
        self.note = "Reviewed the independent test proof and fresh broker records."

    def proof(self):
        register_guarded_test_proof(self.ledger, self.scope, self.intent, "trusted-operator",
                                   "guarded-certification-harness-20261026", {"id": self.intent, "known_no_submission_test": True})

    def resolve(self, evidence, decision="CLOSE_WITHOUT_SUBMISSION"):
        return self.service.resolve(self.intent, evidence["review_id"], decision, self.note, True, "owner-from-session")

    def test_empty_search_alone_never_releases_scope(self):
        evidence = self.service.refresh(self.intent)
        self.assertEqual(evidence["allowed_decisions"], ["KEEP_BLOCKED"])
        with self.assertRaises(HTTPException) as caught:
            self.resolve(evidence)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.ledger.get(self.intent)["state"], "MANUAL_REVIEW")

    def test_proof_and_fresh_read_close_once_without_reusing_attempt_or_key(self):
        self.proof()
        before = self.ledger.get(self.intent)
        evidence = self.service.refresh(self.intent)
        self.assertIn("CLOSE_WITHOUT_SUBMISSION", evidence["allowed_decisions"])
        result = self.resolve(evidence)
        self.assertEqual(result["state"], "RESOLVED_NO_SUBMISSION")
        self.assertFalse(result["submitted"])
        self.assertTrue(result["fresh_confirmation_required"])
        after = self.ledger.get(self.intent)
        for key in ("attempt", "correlation", "fingerprint", "key_hash"):
            self.assertEqual(before[key], after[key])
        for action in (lambda: self.ledger.begin_attempt(self.intent),
                       lambda: self.ledger.create(self.scope, "original-owner-review-key", fixture_order()),
                       lambda: self.resolve(evidence)):
            with self.assertRaises(HTTPException) as caught:
                action()
            self.assertEqual(caught.exception.status_code, 409)
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM confirmations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_owner_resolutions").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM rehearsal_reconciliation WHERE scope=? AND state IN ('SUBMITTING','UNKNOWN','MANUAL_REVIEW')", (self.scope,)).fetchone()[0], 0)
        # A distinct simulated intent is a new READY record, never the old attempt.
        new_intent = self.ledger.create(self.scope, "fresh-simulation-review-key", fixture_order())
        self.assertEqual(self.ledger.get(new_intent)["state"], "READY")
        self.assertIsNone(self.ledger.get(new_intent)["attempt"])

    def test_keep_blocked_records_owner_and_requires_new_review(self):
        evidence = self.service.refresh(self.intent)
        self.resolve(evidence, "KEEP_BLOCKED")
        detail = self.service.detail(self.intent)
        self.assertEqual(detail["receipt"]["state"], "MANUAL_REVIEW")
        self.assertEqual(detail["resolutions"][0]["actor"], "owner-from-session")
        self.assertEqual(detail["resolutions"][0]["note"], self.note)
        with self.assertRaises(HTTPException):
            self.resolve(evidence, "KEEP_BLOCKED")

    def test_expired_or_other_intent_evidence_cannot_resolve(self):
        self.proof()
        evidence = self.service.refresh(self.intent)
        self.now += 301
        with self.assertRaises(HTTPException):
            self.resolve(evidence)
        self.now -= 301
        other = self.ledger.create("simulation:cert:another-account", "another-owner-review-key", fixture_order())
        with self.assertRaises(HTTPException):
            self.service.resolve(other, evidence["review_id"], "CLOSE_WITHOUT_SUBMISSION", self.note, True, "owner")

    def test_changed_row_invalidates_review_and_identity_bound_proof(self):
        self.proof()
        evidence = self.service.refresh(self.intent)
        with self.ledger.db(True) as db:
            db.execute("UPDATE rehearsal_reconciliation SET version=version+1 WHERE id=?", (self.intent,))
        with self.assertRaises(HTTPException):
            self.resolve(evidence)
        with self.ledger.db(True) as db:
            db.execute("UPDATE rehearsal_reconciliation SET attempt='changed-attempt' WHERE id=?", (self.intent,))
        self.assertIsNone(self.service.detail(self.intent)["no_submission_proof"])
        self.assertNotIn("CLOSE_WITHOUT_SUBMISSION", self.service.refresh(self.intent)["allowed_decisions"])

    def test_incomplete_or_conflicting_evidence_never_releases_even_with_proof(self):
        self.proof()
        row = self.ledger.get(self.intent)
        for snapshot in (Snapshot(self.scope, [], False),
                         Snapshot(self.scope, [fixture_match(row), fixture_match(row, broker_id="999")], True)):
            self.worker.reader.read.return_value = snapshot
            self.assertEqual(self.service.refresh(self.intent)["allowed_decisions"], ["KEEP_BLOCKED"])

    def test_verified_partial_broker_match_binds_and_preserves_exposure(self):
        row = self.ledger.get(self.intent)
        self.worker.reader.read.return_value = Snapshot(self.scope, [fixture_match(row, "Partially Filled", "1")], True)
        evidence = self.service.refresh(self.intent)
        self.assertEqual(evidence["allowed_decisions"], ["KEEP_BLOCKED", "BIND_BROKER_ORDER"])
        result = self.resolve(evidence, "BIND_BROKER_ORDER")
        self.assertEqual(result["state"], "ACKNOWLEDGED")
        self.assertEqual(self.ledger.get(self.intent)["filled"], "1")
        with self.assertRaises(HTTPException):
            self.ledger.begin_attempt(self.intent)

    def test_new_conflicting_read_supersedes_old_complete_evidence(self):
        self.proof()
        old = self.service.refresh(self.intent)
        row = self.ledger.get(self.intent)
        self.worker.reader.read.return_value = Snapshot(self.scope, [fixture_match(row), fixture_match(row, broker_id="999")], True)
        newest = self.service.refresh(self.intent)
        self.assertEqual(newest["allowed_decisions"], ["KEEP_BLOCKED"])
        self.service = OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now)
        with self.assertRaises(HTTPException) as caught:
            self.resolve(old)
        self.assertEqual(caught.exception.status_code, 409)
        self.resolve(newest, "KEEP_BLOCKED")
        self.assertEqual(self.ledger.get(self.intent)["state"], "MANUAL_REVIEW")

    def test_failed_refresh_invalidates_old_evidence_before_broker_io(self):
        self.proof()
        old = self.service.refresh(self.intent)
        def read(_):
            with self.assertRaises(HTTPException) as stale:
                self.resolve(old)
            self.assertEqual(stale.exception.status_code, 409)
            raise RuntimeError("injected timeout")
        self.worker.reader.read.side_effect = read
        with self.assertRaises(HTTPException) as failed:
            self.service.refresh(self.intent)
        self.assertEqual(failed.exception.status_code, 503)
        self.service = OwnerReview(self.worker, ledger=self.ledger, clock=lambda: self.now)
        with self.assertRaises(HTTPException):
            self.resolve(old)
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_owner_resolutions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_review_evidence").fetchone()[0], 1)
        self.assertEqual(self.ledger.get(self.intent)["state"], "MANUAL_REVIEW")

    def test_wrong_payload_match_or_scope_is_not_bindable(self):
        row = self.ledger.get(self.intent)
        item = fixture_match(row)
        item["price"] = "2.80"
        self.worker.reader.read.return_value = Snapshot(self.scope, [item], True)
        self.assertEqual(self.service.refresh(self.intent)["allowed_decisions"], ["KEEP_BLOCKED"])
        self.worker.reader.read.return_value = Snapshot("simulation:wrong", [], True)
        with self.assertRaises(HTTPException):
            self.service.refresh(self.intent)

    def test_refresh_failure_or_backoff_leaves_state_and_lease_intact(self):
        self.worker.blocked_until = self.now+60
        with self.assertRaises(HTTPException):
            self.service.refresh(self.intent)
        self.worker.reader.read.assert_not_called()
        self.worker.blocked_until = 0
        self.worker.reader.read.side_effect = RuntimeError("provider-secret")
        with self.assertRaises(HTTPException) as caught:
            self.service.refresh(self.intent)
        self.assertNotIn("provider-secret", caught.exception.detail)
        self.assertFalse(self.worker.lock.locked())
        self.assertEqual(self.ledger.get(self.intent)["state"], "MANUAL_REVIEW")

    def test_row_changed_during_broker_read_cannot_record_stale_evidence(self):
        def read(_):
            with self.ledger.db(True) as db:
                db.execute("UPDATE rehearsal_reconciliation SET version=version+1 WHERE id=?", (self.intent,))
            return Snapshot(self.scope, [], True)
        self.worker.reader.read.side_effect = read
        with self.assertRaises(HTTPException):
            self.service.refresh(self.intent)
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_review_evidence").fetchone()[0], 0)

    def test_explicit_acknowledgement_and_note_required(self):
        self.proof()
        evidence = self.service.refresh(self.intent)
        for note, ack in (("short", True), (self.note, False), (self.note, "true")):
            with self.assertRaises(HTTPException):
                self.service.resolve(self.intent, evidence["review_id"], "CLOSE_WITHOUT_SUBMISSION", note, ack, "owner")

    def test_concurrent_owner_decisions_commit_exactly_one_audit(self):
        self.proof()
        evidence = self.service.refresh(self.intent)
        def decide(_):
            try:
                self.resolve(evidence)
                return 200
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide, range(2))), [200, 409])
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_owner_resolutions").fetchone()[0], 1)

    def test_audit_write_failure_rolls_back_state_change(self):
        self.proof()
        evidence = self.service.refresh(self.intent)
        with self.ledger.db() as db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON certification_owner_resolutions BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(HTTPException):
            self.resolve(evidence)
        self.assertEqual(self.ledger.get(self.intent)["state"], "MANUAL_REVIEW")
        with self.ledger.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM certification_owner_resolutions").fetchone()[0], 0)

    def test_resolution_api_requires_same_origin_and_server_owner_identity(self):
        from starlette.requests import Request
        from staging_preview import OwnerResolution, owner_review_resolve
        evidence = self.service.refresh(self.intent)
        payload = OwnerResolution(review_id=evidence["review_id"], decision="KEEP_BLOCKED", note=self.note, acknowledged=True)
        def request(origin):
            return Request({"type": "http", "method": "POST", "scheme": "https", "path": "/review",
                            "server": ("stage.example", 443), "query_string": b"",
                            "headers": [(b"host", b"stage.example"), (b"origin", origin.encode())]})
        with patch.dict(os.environ, {"BXK_PUBLIC_APP_URL": "https://stage.example", "BXK_APP_USERNAME": "configured-owner"}), \
             patch("staging_preview.owner_review_service", return_value=self.service):
            for origin in ("", "https://evil.example", "https://stage.example.evil.example"):
                with self.assertRaises(HTTPException) as caught:
                    owner_review_resolve(self.intent, payload, request(origin))
                self.assertEqual(caught.exception.status_code, 403)
            owner_review_resolve(self.intent, payload, request("https://stage.example"))
        self.assertEqual(self.service.detail(self.intent)["resolutions"][0]["actor"], "configured-owner")

    def test_resolution_payload_does_not_coerce_text_acknowledgement(self):
        from pydantic import ValidationError
        from staging_preview import OwnerResolution
        with self.assertRaises(ValidationError):
            OwnerResolution(review_id="x"*36, decision="KEEP_BLOCKED", note=self.note, acknowledged="true")


if __name__ == "__main__":
    unittest.main()
