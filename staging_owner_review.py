"""Owner review of certification outcomes. No order mutation transport."""
import hashlib
import json
import re
import time
import uuid

from fastapi import HTTPException

from staging_reconciliation import Ledger, Snapshot, _json

REVIEW_TTL = 300
DECISIONS = {"KEEP_BLOCKED", "BIND_BROKER_ORDER", "CLOSE_WITHOUT_SUBMISSION"}


def identity_hash(row):
    fields = {key: row[key] for key in ("id", "scope", "attempt", "correlation", "fingerprint")}
    return hashlib.sha256(_json(fields).encode()).hexdigest()


def register_guarded_test_proof(ledger, scope, intent, actor, reference, receipt):
    """Trusted operator entry point only; deliberately has no HTTP counterpart.

    The operator attests to a guarded certification harness that performed no order
    POST. Broker absence is never used to manufacture this proof automatically.
    """
    if (not actor or not re.fullmatch(r"[A-Za-z0-9:/._ -]{16,240}", reference)
            or receipt != {"id": intent, "known_no_submission_test": True}):
        raise HTTPException(400, "Guarded test evidence is incomplete")
    with ledger.db(True) as db:
        row = ledger._row(db, intent)
        if row["scope"] != scope or not scope.startswith("simulation:cert:"):
            raise HTTPException(404, "Certification receipt not found")
        if row["state"] != "MANUAL_REVIEW" or row["broker_id"] or row["filled"] != "0" or not row["attempt"]:
            raise HTTPException(409, "Receipt cannot accept a no-submission proof")
        if db.execute("SELECT 1 FROM certification_no_submission_proofs WHERE intent_id=?", (intent,)).fetchone():
            raise HTTPException(409, "Proof already registered")
        db.execute("INSERT INTO certification_no_submission_proofs VALUES(?,?,?,?,?,?)",
                   (intent, identity_hash(row), "GUARDED_CERTIFICATION_TEST", reference, actor, int(ledger.clock())))
        ledger._event(db, intent, row["state"], "NO_SUBMISSION_TEST_PROOF_REGISTERED", row["version"])


class OwnerReview:
    def __init__(self, worker, ledger=None, clock=time.time):
        if worker.reader is None:
            raise HTTPException(503, "Certification connection is unavailable")
        self.worker, self.clock = worker, clock
        self.ledger = ledger or Ledger(clock=clock)
        self.scope = worker.reader.scope

    def _check(self, row):
        if row["scope"] != self.scope:
            raise HTTPException(404, "Certification receipt not found")

    def _proof(self, db, row):
        proof = db.execute("SELECT * FROM certification_no_submission_proofs WHERE intent_id=?", (row["id"],)).fetchone()
        return dict(proof) if proof and proof["identity_hash"] == identity_hash(row) else None

    def _options(self, row, snapshot, proof):
        result = ["KEEP_BLOCKED"]
        state, reason, *_ = self.ledger._decide(row, snapshot)
        if snapshot.complete is True and reason == "BROKER_ORDER_MATCHED" and state in {"ACKNOWLEDGED", "TERMINAL"}:
            result.append("BIND_BROKER_ORDER")
        if (snapshot.complete is True and not snapshot.items and proof
                and not row["broker_id"] and row["filled"] == "0"):
            result.append("CLOSE_WITHOUT_SUBMISSION")
        return result

    def detail(self, intent):
        with self.ledger.db() as db:
            row = self.ledger._row(db, intent)
            self._check(row)
            events = db.execute("SELECT state,reason,version,occurred_at FROM rehearsal_reconciliation_events WHERE intent_id=? ORDER BY sequence DESC LIMIT 100", (intent,)).fetchall()
            decisions = db.execute("SELECT id,review_id,actor,decision,note,previous_state,new_state,proof_reference,created_at FROM certification_owner_resolutions WHERE intent_id=? ORDER BY created_at DESC LIMIT 20", (intent,)).fetchall()
            evidence = db.execute("SELECT id,snapshot,version,created_at,expires_at FROM certification_review_evidence WHERE intent_id=? ORDER BY created_at DESC LIMIT 10", (intent,)).fetchall()
            proof = self._proof(db, row)
        summaries = []
        for record in evidence:
            snapshot = json.loads(record["snapshot"])
            summaries.append({"id": record["id"], "version": record["version"],
                              "created_at": record["created_at"], "expires_at": record["expires_at"],
                              "complete": snapshot["complete"],
                              "candidates": [{key: item.get(key) for key in ("id", "status", "filled-quantity")} for item in snapshot["items"]]})
        return {"environment": "certification", "submission_enabled": False,
                "receipt": {key: row[key] for key in ("id", "state", "reason", "version", "broker_id", "broker_status", "filled", "created_at")},
                "order": json.loads(row["request"]), "events": [dict(item) for item in events],
                "resolutions": [dict(item) for item in decisions], "evidence": summaries,
                "no_submission_proof": {key: proof[key] for key in ("source", "reference", "actor", "created_at")} if proof else None,
                "fresh_confirmation_required": True}

    def refresh(self, intent):
        row = self.ledger.get(intent)
        self._check(row)
        if row["state"] != "MANUAL_REVIEW":
            raise HTTPException(409, "Only an owner-review receipt can be refreshed")
        if not self.worker.lock.acquire(blocking=False):
            raise HTTPException(409, "A broker check is already running")
        try:
            with self.ledger.db() as db:
                cooldown = db.execute("SELECT blocked_until FROM certification_worker_state WHERE scope=?", (self.scope,)).fetchone()
            if max(self.worker.blocked_until, cooldown["blocked_until"] if cooldown else 0) > self.clock():
                raise HTTPException(409, "Broker backoff is active; try after it ends")
            try:
                snapshot = self.worker.reader.read(row)
            except Exception:
                raise HTTPException(503, "Broker evidence is unavailable; receipt remains blocked") from None
            if not isinstance(snapshot, Snapshot) or snapshot.scope != self.scope or not isinstance(snapshot.items, list) or len(snapshot.items) > 100 or not all(isinstance(item, dict) for item in snapshot.items):
                raise HTTPException(409, "Broker evidence scope mismatch")
            # Persist normalized evidence, never credentials or raw provider bodies.
            safe_items = [{key: item[key] for key in ("id", "scope", "external-identifier", "status", "filled-quantity", "legs", "price", "order-type", "time-in-force", "price-effect") if key in item}
                          for item in snapshot.items]
            snapshot = Snapshot(snapshot.scope, safe_items, snapshot.complete is True)
            review_id, now = str(uuid.uuid4()), int(self.clock())
            with self.ledger.db(True) as db:
                current = self.ledger._row(db, intent)
                if current["version"] != row["version"] or current["state"] != "MANUAL_REVIEW":
                    raise HTTPException(409, "Receipt changed; refresh evidence again")
                db.execute("INSERT INTO certification_review_evidence VALUES(?,?,?,?,?,?,?)",
                           (review_id, intent, self.scope, row["version"], _json({"scope": snapshot.scope, "items": snapshot.items, "complete": snapshot.complete}), now, now+REVIEW_TTL))
                self.ledger._event(db, intent, row["state"], "OWNER_BROKER_EVIDENCE_REFRESHED", row["version"])
                options = self._options(row, snapshot, self._proof(db, row))
            return {"review_id": review_id, "version": row["version"], "expires_at": now+REVIEW_TTL,
                    "complete": snapshot.complete, "candidate_count": len(snapshot.items),
                    "allowed_decisions": options, "submission_enabled": False}
        finally:
            self.worker.lock.release()

    def resolve(self, intent, review_id, decision, note, acknowledged, actor):
        if (decision not in DECISIONS or acknowledged is not True or not actor
                or not isinstance(note, str) or not 20 <= len(note.strip()) <= 500):
            raise HTTPException(400, "Explicit acknowledgement and a review note are required")
        with self.ledger.db(True) as db:
            row = self.ledger._row(db, intent)
            self._check(row)
            evidence = db.execute("SELECT * FROM certification_review_evidence WHERE id=? AND intent_id=? AND scope=?", (review_id, intent, self.scope)).fetchone()
            if (row["state"] != "MANUAL_REVIEW" or not evidence
                    or evidence["expires_at"] <= self.clock() or evidence["version"] != row["version"]
                    or db.execute("SELECT 1 FROM certification_owner_resolutions WHERE review_id=?", (review_id,)).fetchone()):
                raise HTTPException(409, "Review is stale, used or unavailable; refresh broker evidence")
            raw = json.loads(evidence["snapshot"])
            snapshot = Snapshot(raw["scope"], raw["items"], raw["complete"])
            proof = self._proof(db, row)
            if decision not in self._options(row, snapshot, proof):
                raise HTTPException(409, "Evidence does not support releasing this receipt")
            state, reason, broker_id, status, filled = row["state"], "OWNER_KEPT_BLOCKED", row["broker_id"], row["broker_status"], row["filled"]
            if decision == "BIND_BROKER_ORDER":
                state, _, broker_id, status, filled = self.ledger._decide(row, snapshot)
                reason = "OWNER_BOUND_VERIFIED_BROKER_ORDER"
            elif decision == "CLOSE_WITHOUT_SUBMISSION":
                state, reason = "RESOLVED_NO_SUBMISSION", "OWNER_CONFIRMED_NO_SUBMISSION"
            resolution_id, now = str(uuid.uuid4()), int(self.clock())
            db.execute("INSERT INTO certification_owner_resolutions VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (resolution_id, review_id, intent, actor, decision, note.strip(), row["state"], state,
                        proof["reference"] if decision == "CLOSE_WITHOUT_SUBMISSION" else None, now))
            changed = db.execute("UPDATE rehearsal_reconciliation SET state=?,reason=?,broker_id=?,broker_status=?,filled=?,version=version+1,next_read=0 WHERE id=? AND version=?",
                                 (state, reason, broker_id, status, filled, intent, row["version"]))
            if changed.rowcount != 1:
                raise HTTPException(409, "Receipt changed during owner review")
            self.ledger._event(db, intent, state, reason, row["version"]+1)
        return {"resolution_id": resolution_id, "state": state, "submitted": False,
                "fresh_confirmation_required": True, "original_attempt_retry_allowed": False}
