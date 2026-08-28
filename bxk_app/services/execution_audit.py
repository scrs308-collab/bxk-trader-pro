import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from bxk_app.config import BXK_ORDER_AUDIT_FILE


_AUDIT_LOCK = threading.Lock()
_MAX_AUDIT_READ_BYTES = 5_000_000
_MAX_SUBMITTED_ORDERS = 100


def _masked_account(account):
    if account is None:
        return None

    account_text = str(account).strip()

    if not account_text:
        return None

    if len(account_text) < 4:
        return "***"

    return f"***{account_text[-4:]}"


def _review_reference(review_id):
    if review_id is None:
        return None

    clean_review_id = str(review_id).strip()

    if not clean_review_id:
        return None

    return clean_review_id[:12]


def _safe_leg(leg):
    if not isinstance(leg, dict):
        return {}

    allowed_fields = (
        "action",
        "symbol",
        "quantity",
        "instrument_type",
        "instrument-type",
    )

    return {
        field: leg.get(field)
        for field in allowed_fields
        if leg.get(field) is not None
    }


def _safe_order(order):
    if not isinstance(order, dict):
        return None

    allowed_fields = (
        "strategy",
        "symbol",
        "quantity",
        "limit_price",
        "credit",
        "max_profit",
        "max_risk",
        "buying_power",
        "expiration",
        "dte",
        "wing_width",
    )

    safe_order = {
        field: order.get(field)
        for field in allowed_fields
        if order.get(field) is not None
    }

    legs = order.get("legs")

    if isinstance(legs, list):
        safe_order["legs"] = [
            _safe_leg(leg)
            for leg in legs
        ]

    return safe_order


def write_order_audit(
    event,
    *,
    status=None,
    reason_code=None,
    review_id=None,
    account=None,
    order_id=None,
    broker_status=None,
    order=None,
):
    clean_event = str(event or "").strip().upper()

    if not clean_event:
        raise ValueError(
            "Audit event is required."
        )

    record = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "event": clean_event,
        "status": status,
        "reason_code": reason_code,
        "review_reference":
            _review_reference(review_id),
        "account": _masked_account(account),
        "order_id": order_id,
        "broker_status": broker_status,
        "order": _safe_order(order),
    }

    record = {
        key: value
        for key, value in record.items()
        if value is not None
    }

    audit_path = Path(
        BXK_ORDER_AUDIT_FILE
    )

    audit_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
    )

    with _AUDIT_LOCK:
        with audit_path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as audit_file:
            audit_file.write(serialized + "\n")
            audit_file.flush()
            os.fsync(audit_file.fileno())

    return record


def read_recent_submitted_orders(
    limit: int = _MAX_SUBMITTED_ORDERS,
) -> list[dict]:
    """Read recent confirmed submissions for position linking."""

    try:
        clean_limit = max(
            1,
            min(int(limit), _MAX_SUBMITTED_ORDERS),
        )
    except (TypeError, ValueError):
        clean_limit = _MAX_SUBMITTED_ORDERS

    audit_path = Path(BXK_ORDER_AUDIT_FILE)

    if not audit_path.is_file():
        return []

    try:
        if audit_path.stat().st_size > _MAX_AUDIT_READ_BYTES:
            return []

        with _AUDIT_LOCK:
            lines = audit_path.read_text(
                encoding="utf-8",
            ).splitlines()
    except OSError:
        return []

    submitted = []
    seen_order_ids = set()

    for line in reversed(lines):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue

        if record.get("event") != "SUBMITTED":
            continue

        order_id = str(
            record.get("order_id") or ""
        ).strip()
        order = record.get("order")

        if (
            not order_id
            or order_id in seen_order_ids
            or not isinstance(order, dict)
        ):
            continue

        legs = order.get("legs")

        if not isinstance(legs, list) or not legs:
            continue

        seen_order_ids.add(order_id)
        submitted.append(record)

        if len(submitted) >= clean_limit:
            break

    return submitted
