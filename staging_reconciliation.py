"""Durable reconciliation rehearsal. No submission transport or live-order path.

Independent tables: existing confirmation/intent records cannot become attempts.
Only injected read-only readers are used, outside SQLite transactions.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import uuid

from fastapi import HTTPException
from staging_confirmation import _connect

TERMINAL = {"Filled", "Cancelled", "Expired", "Rejected"}
ACTIVE = {"Received", "Routed", "In Flight", "Live", "Partially Filled",
          "Cancel Requested", "Replace Requested", "Contingent", "Queued"}
UNCERTAIN = {"SUBMITTING", "UNKNOWN", "MANUAL_REVIEW"}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _number(value, integer=False):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or (integer and number != number.to_integral_value()):
            raise ValueError()
        return format(number.normalize(), "f")
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid order number") from None


def canonical(order):
    """Order-independent legs, decimal money and complete order terms."""
    legs = [{"symbol": x["symbol"], "action": x["action"],
             "instrument-type": x["instrument-type"], "quantity": _number(x["quantity"], True)}
            for x in order["legs"]]
    if len(legs) != 4 or len({x["symbol"] for x in legs}) != 4:
        raise ValueError("Four distinct legs required")
    if any(not isinstance(x["symbol"], str) or not x["symbol"].startswith("SPXW  ")
           or x["instrument-type"] != "Equity Option" or x["quantity"] == "0"
           or x["action"] not in {"Buy to Open", "Sell to Open"} for x in legs):
        raise ValueError("Invalid rehearsal leg")
    if len({x["quantity"] for x in legs}) != 1:
        raise ValueError("Equal leg quantities required")
    price = _number(order["price"])
    if Decimal(price) <= 0 or Decimal(price) != Decimal(price).quantize(Decimal(".01")):
        raise ValueError("Positive cent-precision price required")
    if order["order-type"] != "Limit" or order["time-in-force"] != "Day" or order["price-effect"] != "Credit":
        raise ValueError("Only Day limit-credit rehearsals supported")
    return {"legs": sorted(legs, key=lambda x: x["symbol"]), "price": price,
            "order-type": "Limit", "time-in-force": "Day", "price-effect": "Credit"}


@dataclass(frozen=True)
class Snapshot:
    scope: str
    items: list
    complete: bool


class Ledger:
    def __init__(self, clock=time.time, jitter=lambda: secrets.randbelow(4), max_reads=6):
        if os.getenv("BXK_PREVIEW_MODE", "").lower() != "true" or os.getenv("BXK_LIVE_TRADING_ENABLED", "").lower() != "false":
            raise HTTPException(403, "Reconciliation rehearsal requires live trading disabled")
        self.clock, self.jitter, self.max_reads = clock, jitter, max_reads

    @contextmanager
    def db(self, write=False):
        db = _connect()
        db.row_factory = sqlite3.Row
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS rehearsal_reconciliation (
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, key_hash TEXT NOT NULL,
                request TEXT NOT NULL, fingerprint TEXT NOT NULL,
                correlation TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0, attempt TEXT,
                attempt_at INTEGER, lease TEXT, lease_until INTEGER NOT NULL DEFAULT 0,
                reads INTEGER NOT NULL DEFAULT 0, next_read INTEGER NOT NULL DEFAULT 0,
                broker_id TEXT, broker_status TEXT, filled TEXT NOT NULL DEFAULT '0',
                reason TEXT NOT NULL, created_at INTEGER NOT NULL,
                UNIQUE(scope,key_hash))""")
            db.execute("""CREATE TABLE IF NOT EXISTS rehearsal_reconciliation_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, intent_id TEXT NOT NULL,
                state TEXT NOT NULL, reason TEXT NOT NULL, version INTEGER NOT NULL,
                occurred_at INTEGER NOT NULL)""")
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except sqlite3.Error:
            db.rollback()
            raise HTTPException(503, "Durable reconciliation storage unavailable") from None
        finally:
            db.close()

    def _row(self, db, intent):
        row = db.execute("SELECT * FROM rehearsal_reconciliation WHERE id=?", (intent,)).fetchone()
        if row is None:
            raise HTTPException(404, "Rehearsal intent not found")
        return dict(row)

    def _event(self, db, intent, state, reason, version):
        db.execute("INSERT INTO rehearsal_reconciliation_events(intent_id,state,reason,version,occurred_at) VALUES(?,?,?,?,?)",
                   (intent, state, reason, version, int(self.clock())))

    def create(self, scope, key, order):
        if not isinstance(scope, str) or not scope.startswith("simulation:") or len(scope) > 200:
            raise HTTPException(400, "Simulation-scoped account identity required")
        if not isinstance(key, str) or not 16 <= len(key) <= 128:
            raise HTTPException(400, "Invalid rehearsal idempotency key")
        request = _json(canonical(order))
        intent, correlation = str(uuid.uuid4()), str(uuid.uuid4())
        with self.db(True) as db:
            if db.execute("SELECT 1 FROM rehearsal_reconciliation WHERE scope=? AND key_hash=?", (scope, _hash(key))).fetchone():
                raise HTTPException(409, "Duplicate or mutated rehearsal key rejected")
            if db.execute("SELECT 1 FROM rehearsal_reconciliation WHERE scope=? AND state IN ('SUBMITTING','UNKNOWN','MANUAL_REVIEW')", (scope,)).fetchone():
                raise HTTPException(409, "Uncertain account outcome blocks replacement intents")
            db.execute("INSERT INTO rehearsal_reconciliation(id,scope,key_hash,request,fingerprint,correlation,state,reason,created_at) VALUES(?,?,?,?,?,?,'READY','SIMULATION_CREATED',?)",
                       (intent, scope, _hash(key), request, _hash(request), correlation, int(self.clock())))
            self._event(db, intent, "READY", "SIMULATION_CREATED", 0)
        return intent

    def get(self, intent):
        with self.db() as db:
            return self._row(db, intent)

    def begin_attempt(self, intent):
        """Record a synthetic attempt before a fake broker action; sends nothing."""
        with self.db(True) as db:
            row = self._row(db, intent)
            if row["state"] != "READY":
                raise HTTPException(409, "Attempt already reserved; submission retry blocked")
            if db.execute("SELECT 1 FROM rehearsal_reconciliation WHERE scope=? AND id<>? AND state IN ('SUBMITTING','UNKNOWN','MANUAL_REVIEW')", (row["scope"], intent)).fetchone():
                raise HTTPException(409, "Another unresolved attempt blocks this account")
            attempt = str(uuid.uuid4())
            db.execute("UPDATE rehearsal_reconciliation SET state='SUBMITTING',attempt=?,attempt_at=?,version=version+1,reason='SIMULATED_ATTEMPT_RESERVED' WHERE id=?", (attempt, int(self.clock()), intent))
            self._event(db, intent, "SUBMITTING", "SIMULATED_ATTEMPT_RESERVED", row["version"]+1)
        return attempt

    def recover_inflight(self):
        """Run on startup; interrupted attempts may only be reconciled by reads."""
        with self.db(True) as db:
            rows = db.execute("SELECT * FROM rehearsal_reconciliation WHERE state='SUBMITTING' OR lease IS NOT NULL").fetchall()
            for row in rows:
                state = "UNKNOWN" if row["state"] == "SUBMITTING" else row["state"]
                db.execute("UPDATE rehearsal_reconciliation SET state=?,lease=NULL,lease_until=0,next_read=0,reason='RESTART_RECOVERY',version=version+1 WHERE id=?", (state, row["id"]))
                self._event(db, row["id"], state, "RESTART_RECOVERY", row["version"]+1)
        return len(rows)

    def mark_unknown(self, intent, attempt):
        with self.db(True) as db:
            row = self._row(db, intent)
            if row["state"] != "SUBMITTING" or row["attempt"] != attempt:
                raise HTTPException(409, "Stale attempt result rejected")
            db.execute("UPDATE rehearsal_reconciliation SET state='UNKNOWN',reason='UNCERTAIN_RESPONSE',version=version+1 WHERE id=?", (intent,))
            self._event(db, intent, "UNKNOWN", "UNCERTAIN_RESPONSE", row["version"]+1)

    def reconcile(self, intent, reader):
        now, lease = int(self.clock()), str(uuid.uuid4())
        with self.db(True) as db:
            row = self._row(db, intent)
            if row["state"] not in {"UNKNOWN", "ACKNOWLEDGED"}:
                raise HTTPException(409, "State does not permit reconciliation")
            if row["next_read"] > now or row["lease_until"] > now:
                raise HTTPException(409, "Reconciliation already running or awaiting backoff")
            version = row["version"]+1
            db.execute("UPDATE rehearsal_reconciliation SET lease=?,lease_until=?,version=? WHERE id=?", (lease, now+60, version, intent))
        # No SQLite lock is held across provider I/O. Errors never authorize a POST.
        try:
            snapshot = reader.read(row)
            state, reason, broker_id, status, filled = self._decide(row, snapshot)
        except Exception:
            state, reason, broker_id, status, filled = row["state"], "READ_UNAVAILABLE", row["broker_id"], row["broker_status"], row["filled"]
        reads = row["reads"]+1
        if state == "UNKNOWN" and reads >= self.max_reads:
            state, reason = "MANUAL_REVIEW", "RECOVERY_READ_LIMIT"
        # Backoff applies to reads only. There is no mutation transport to retry.
        due = int(self.clock()) + min(300, 2**min(reads, 8)) + self.jitter()
        with self.db(True) as db:
            changed = db.execute("UPDATE rehearsal_reconciliation SET state=?,reason=?,broker_id=?,broker_status=?,filled=?,reads=?,next_read=?,lease=NULL,lease_until=0,version=version+1 WHERE id=? AND version=? AND lease=?",
                                 (state, reason, broker_id, status, filled, reads, due, intent, version, lease))
            if changed.rowcount != 1:
                raise HTTPException(409, "Stale reconciliation result rejected")
            self._event(db, intent, state, reason, version+1)
        return self.get(intent)

    def _decide(self, row, snapshot):
        old = (row["state"], "INCOMPLETE_HISTORY", row["broker_id"], row["broker_status"], row["filled"])
        manual = ("MANUAL_REVIEW", "CONFLICTING_BROKER_EVIDENCE", *old[2:])
        if not isinstance(snapshot, Snapshot) or snapshot.scope != row["scope"]:
            return manual
        if snapshot.complete is not True:
            return old
        matches = {}
        for item in snapshot.items:
            if item.get("external-identifier") != row["correlation"]:
                if row["broker_id"] and str(item.get("id")) == row["broker_id"]:
                    return manual
                continue
            broker_id = str(item.get("id") or "")
            try:
                valid = item.get("scope") == row["scope"] and _hash(_json(canonical(item))) == row["fingerprint"]
                status = item["status"]
                filled = _number(item.get("filled-quantity"), True)
                quantity = Decimal(json.loads(row["request"])["legs"][0]["quantity"])
                valid = valid and status in TERMINAL | ACTIVE and Decimal(filled) <= quantity
                valid = valid and (status != "Filled" or Decimal(filled) == quantity)
                valid = valid and (status != "Partially Filled" or 0 < Decimal(filled) < quantity)
            except (KeyError, ValueError, TypeError, InvalidOperation):
                valid = False
            if not valid or not re.fullmatch(r"[0-9]{1,32}", broker_id) or (row["broker_id"] and broker_id != row["broker_id"]):
                return manual
            evidence = (status, filled)
            if broker_id in matches and matches[broker_id] != evidence:
                return manual
            matches[broker_id] = evidence
        if len(matches) > 1:
            return manual
        if not matches:
            return row["state"], "NO_MATCH_YET", *old[2:]
        broker_id, (status, filled) = next(iter(matches.items()))
        if Decimal(filled) < Decimal(row["filled"]):
            return row["state"], "STALE_FILL_IGNORED", *old[2:]
        state = "TERMINAL" if status in TERMINAL else "ACKNOWLEDGED"
        return state, "BROKER_ORDER_MATCHED", broker_id, status, filled
