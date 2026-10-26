"""Staging-only durable order-intent ledger. Does not submit broker orders.

The unique idempotency key is a rehearsal safeguard. Live trading additionally
requires broker-side reconciliation of unknown outcomes and a real order lifecycle.
"""
import sqlite3
import time
from fastapi import HTTPException
from staging_confirmation import _connect, _fingerprint, _hash


def reserve_intent(order, idempotency_key):
    if not isinstance(idempotency_key, str) or not 16 <= len(idempotency_key) <= 128:
        raise HTTPException(400, "Invalid idempotency key")
    fingerprint = _fingerprint(order)
    key_hash = _hash(idempotency_key)
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS staging_order_intents (
            key_hash TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            status TEXT NOT NULL, created_at INTEGER NOT NULL
        )""")
        existing = conn.execute("SELECT fingerprint,status FROM staging_order_intents WHERE key_hash=?", (key_hash,)).fetchone()
        if existing:
            conn.rollback()
            if existing[0] != fingerprint:
                raise HTTPException(409, "Idempotency key reused for a different order")
            raise HTTPException(409, "Duplicate order intent rejected; no order submitted")
        conn.execute("INSERT INTO staging_order_intents (key_hash,fingerprint,status,created_at) VALUES (?,?,?,?)",
                     (key_hash, fingerprint, "SIMULATED_NO_SUBMISSION", int(time.time())))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise HTTPException(503, "Durable order-intent ledger unavailable") from None
    finally:
        conn.close()
    return {"recorded": True, "status": "SIMULATED_NO_SUBMISSION",
            "submitted": False, "live_trading_enabled": False}
