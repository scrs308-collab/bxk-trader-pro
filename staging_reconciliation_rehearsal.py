"""Owner-only synthetic scenarios on durable storage. No broker/network access."""
import json
import uuid

from fastapi import HTTPException
from staging_reconciliation import Ledger, Snapshot


def fixture_order(quantity=2):
    return {"order-type": "Limit", "time-in-force": "Day", "price-effect": "Credit", "price": "2.90",
            "legs": [{"symbol": f"SPXW  261026{kind}{strike:08d}", "action": action,
                      "instrument-type": "Equity Option", "quantity": quantity}
                     for kind, strike, action in [
                         ("P", 7550000, "Sell to Open"), ("P", 7540000, "Buy to Open"),
                         ("C", 7690000, "Sell to Open"), ("C", 7700000, "Buy to Open")]]}


def fixture_match(row, status="Live", filled="0", broker_id="12345"):
    return {**json.loads(row["request"]), "scope": row["scope"], "id": broker_id,
            "external-identifier": row["correlation"], "status": status, "filled-quantity": filled}


class FixtureReader:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def read(self, row):
        return self.snapshot


def receipt(intent):
    ledger = Ledger()
    row = ledger.get(intent)
    with ledger.db() as db:
        attempts = db.execute("SELECT COUNT(*) FROM rehearsal_reconciliation_events WHERE intent_id=? AND reason='SIMULATED_ATTEMPT_RESERVED'", (intent,)).fetchone()[0]
    return {k: row[k] for k in ("id", "correlation", "fingerprint", "attempt", "state", "reason")} | {
        "synthetic_data": True, "submitted": False, "submission_enabled": False,
        "attempt_count": attempts, "retry_blocked": row["state"] != "READY"}


def run():
    ledger, run_id, checks = Ledger(), str(uuid.uuid4()), []
    for name, status, filled, expected in [
        ("timeout_no_match", None, "0", "UNKNOWN"),
        ("response_lost_broker_found", "Live", "0", "ACKNOWLEDGED"),
        ("partial_fill", "Partially Filled", "1", "ACKNOWLEDGED"),
        ("filled", "Filled", "2", "TERMINAL"),
        ("rejected", "Rejected", "0", "TERMINAL"),
        ("conflicting_orders", "Live", "0", "MANUAL_REVIEW"),
    ]:
        intent = ledger.create("simulation:"+run_id+":"+name, run_id+":"+name, fixture_order())
        attempt = ledger.begin_attempt(intent)
        ledger.mark_unknown(intent, attempt)
        row = ledger.get(intent)
        items = [fixture_match(row, status, filled)] if status else []
        if name == "conflicting_orders":
            items.append(fixture_match(row, broker_id="67890"))
        result = ledger.reconcile(intent, FixtureReader(Snapshot(row["scope"], items, True)))
        blocked = False
        try:
            ledger.begin_attempt(intent)
        except HTTPException as exc:
            blocked = exc.status_code == 409
        checks.append({"scenario": name, "state": result["state"], "passed": result["state"] == expected and blocked,
                       "retry_blocked": blocked})
    # Intentionally unfinished synthetic attempt: real app startup must recover it.
    pending = ledger.create("simulation:"+run_id+":restart", run_id+":restart", fixture_order())
    ledger.begin_attempt(pending)
    return {"synthetic_data": True, "submitted": False, "submission_enabled": False,
            "all_passed": all(x["passed"] for x in checks), "checks": checks,
            "restart_receipt": receipt(pending)}
