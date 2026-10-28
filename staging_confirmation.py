"""Durable, staging-only confirmation rehearsal ledger. No order submission."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from fastapi import HTTPException

DB = Path(os.getenv("BXK_STAGING_CONFIRMATION_DB", "/data/confirmations.sqlite3"))
TTL = 30


def _connect():
    # Fail closed if persistent Railway volume is absent.
    if not DB.parent.is_dir() or not os.path.ismount(str(DB.parent)):
        raise HTTPException(503, "Persistent confirmation volume is not mounted")
    conn = None
    try:
        conn = sqlite3.connect(str(DB), timeout=10, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        # A successful receipt must follow a durable commit, including WAL sync.
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS confirmations (
            token_hash TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            consumed_at INTEGER,
            created_at INTEGER NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS confirmation_expiry ON confirmations(expires_at)")
        return conn
    except sqlite3.Error:
        if conn is not None:
            conn.close()
        raise HTTPException(503, "Durable confirmation ledger unavailable") from None


def _fingerprint(order):
    canonical = {"legs": [{"symbol": x.symbol, "action": x.action} for x in order.legs],
                 "quantity": order.quantity, "limit_price": round(order.limit_price, 2)}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue(order, broker_result):
    if broker_result.get("all_checks_pass") is not True or broker_result.get("server_quote_verified") is not True:
        raise HTTPException(409, "Fresh broker checks must pass before confirmation")
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Retain consumed records for auditing; prune only expired unconsumed records.
        conn.execute("DELETE FROM confirmations WHERE consumed_at IS NULL AND expires_at < ?", (now-86400,))
        conn.execute("INSERT INTO confirmations (token_hash,fingerprint,expires_at,created_at) VALUES (?,?,?,?)",
                     (_hash(token), _fingerprint(order), now+TTL, now))
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise HTTPException(503, "Could not persist confirmation") from None
    finally:
        conn.close()
    return {"confirmation_token": token, "expires_in_seconds": TTL,
            "simulation_only": True, "order_submission_enabled": False}


def consume(order, token):
    now = int(time.time())
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT fingerprint,expires_at,consumed_at FROM confirmations WHERE token_hash=?",
                           (_hash(token),)).fetchone()
        if row is None or row[2] is not None or now >= row[1]:
            conn.rollback()
            raise HTTPException(409, "Confirmation already used, expired, or invalid")
        # Consume before checking fingerprint, so a changed order cannot retry the token.
        updated = conn.execute("UPDATE confirmations SET consumed_at=? WHERE token_hash=? AND consumed_at IS NULL",
                               (now, _hash(token)))
        if updated.rowcount != 1:
            conn.rollback()
            raise HTTPException(409, "Confirmation already consumed")
        # Record a simulated order intent in the SAME transaction as token consumption.
        # This is not a live broker order, and no broker submission method is called.
        conn.execute("""CREATE TABLE IF NOT EXISTS staging_order_intents (
            key_hash TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            status TEXT NOT NULL, created_at INTEGER NOT NULL
        )""")
        if not hmac.compare_digest(row[0], _fingerprint(order)):
            conn.commit()
            raise HTTPException(409, "Order details changed; confirmation consumed")
        inserted = conn.execute(
            "INSERT INTO staging_order_intents (key_hash,fingerprint,status,created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(key_hash) DO NOTHING",
            (_hash(token), row[0], "SIMULATED_NO_SUBMISSION", now)
        )
        if inserted.rowcount != 1:
            conn.commit()
            raise HTTPException(409, "Duplicate simulated order intent; no order submitted")
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise HTTPException(503, "Durable confirmation ledger unavailable") from None
    finally:
        conn.close()
    return {"acknowledged": True, "simulation_only": True, "submitted": False,
            "order_intent_status": "SIMULATED_NO_SUBMISSION",
            "message": "Confirmation and simulated order intent committed atomically; no broker order sent."}


def receipt(order, token):
    """Read persisted evidence; expiry alone is not proof of replay protection."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT c.fingerprint,c.consumed_at,i.fingerprint,i.status,i.created_at "
            "FROM confirmations c LEFT JOIN staging_order_intents i ON i.key_hash=c.token_hash "
            "WHERE c.token_hash=?", (_hash(token),)
        ).fetchone()
        if row is None or not hmac.compare_digest(row[0], _fingerprint(order)):
            raise HTTPException(404, "Simulation receipt not found")
        return {"simulation_only": True, "submitted": False, "receipt_id": _hash(token),
                "consumed_at": row[1], "intent_created_at": row[4],
                "order_intent_status": row[3],
                "durable_intent_verified": row[1] is not None and row[2] == row[0]
                and row[3] == "SIMULATED_NO_SUBMISSION"}
    except sqlite3.Error:
        raise HTTPException(503, "Durable simulation receipt unavailable") from None
    finally:
        conn.close()
