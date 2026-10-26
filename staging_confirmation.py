"""Server-owned, single-use confirmation rehearsal. Never submits live orders.

In-memory tokens are deliberately NOT a durable live-trading idempotency system.
This module is staging-only; a durable transactional store is required before live use.
"""
import hashlib
import hmac
import json
import secrets
import threading
import time
from fastapi import HTTPException

_lock = threading.Lock()
_pending = {}
_used = set()
TTL = 30


def _fingerprint(order):
    canonical = {"legs": [{"symbol": x.symbol, "action": x.action} for x in order.legs],
                 "quantity": order.quantity, "limit_price": round(order.limit_price, 2)}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def issue(order, broker_result):
    if broker_result.get("all_checks_pass") is not True or broker_result.get("server_quote_verified") is not True:
        raise HTTPException(409, "Fresh broker checks must pass before confirmation")
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        for key, value in list(_pending.items()):
            if value["expires"] < now:
                del _pending[key]
        _pending[token] = {"fingerprint": _fingerprint(order), "expires": now + TTL}
    return {"confirmation_token": token, "expires_in_seconds": TTL,
            "simulation_only": True, "order_submission_enabled": False}


def consume(order, token):
    now = time.monotonic()
    with _lock:
        if token in _used:
            raise HTTPException(409, "Confirmation already used")
        record = _pending.pop(token, None)
        if not record or now > record["expires"]:
            raise HTTPException(409, "Confirmation expired or invalid")
        # Mark consumed even on mismatch to prevent replay.
        _used.add(token)
        if not hmac.compare_digest(record["fingerprint"], _fingerprint(order)):
            raise HTTPException(409, "Order details changed; request a new confirmation")
    return {"acknowledged": True, "simulation_only": True, "submitted": False,
            "message": "Server consumed one-time confirmation. No order was sent."}
