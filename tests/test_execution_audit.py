import json

import pytest

import bxk_app.services.execution_audit as audit


def _read_records(path):
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def test_audit_masks_and_whitelists_data(
    monkeypatch,
    tmp_path,
):
    audit_file = (
        tmp_path / "order-audit.jsonl"
    )

    monkeypatch.setattr(
        audit,
        "BXK_ORDER_AUDIT_FILE",
        str(audit_file),
    )

    record = audit.write_order_audit(
        "broker_preflight_blocked",
        status="BLOCKED",
        reason_code=
            "BUYING_POWER_RESERVE",
        review_id=
            "review-abcdefghijklmnopqrstuvwxyz",
        account="5WI27178",
        order={
            "strategy": "SPX Iron Condor",
            "symbol": "SPX",
            "quantity": 1,
            "limit_price": 4.85,
            "max_risk": 2015.0,
            "buying_power": 2015.0,
            "client_secret":
                "DO-NOT-RECORD",
            "refresh_token":
                "DO-NOT-RECORD-EITHER",
            "legs": [
                {
                    "action":
                        "SELL_TO_OPEN",
                    "symbol":
                        "SPXW TEST OPTION",
                    "quantity": 1,
                    "access_token":
                        "HIDDEN",
                }
            ],
        },
    )

    records = _read_records(
        audit_file
    )

    assert len(records) == 1
    assert records[0] == record
    assert record["account"] == "***7178"
    assert (
        record["review_reference"]
        == "review-abcde"
    )
    assert (
        record["event"]
        == "BROKER_PREFLIGHT_BLOCKED"
    )

    serialized = audit_file.read_text(
        encoding="utf-8"
    )

    assert "DO-NOT-RECORD" not in serialized
    assert (
        "DO-NOT-RECORD-EITHER"
        not in serialized
    )
    assert "HIDDEN" not in serialized
    assert "5WI27178" not in serialized


def test_audit_appends_one_json_record_per_event(
    monkeypatch,
    tmp_path,
):
    audit_file = (
        tmp_path / "nested"
        / "order-audit.jsonl"
    )

    monkeypatch.setattr(
        audit,
        "BXK_ORDER_AUDIT_FILE",
        str(audit_file),
    )

    audit.write_order_audit(
        "preflight_passed",
        status=
            "BROKER_PREFLIGHT_PASSED",
    )

    audit.write_order_audit(
        "submission_blocked",
        status="BLOCKED",
        reason_code=
            "LIVE_TRADING_DISABLED",
    )

    records = _read_records(
        audit_file
    )

    assert len(records) == 2
    assert (
        records[0]["event"]
        == "PREFLIGHT_PASSED"
    )
    assert (
        records[1]["event"]
        == "SUBMISSION_BLOCKED"
    )


def test_audit_requires_event(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        audit,
        "BXK_ORDER_AUDIT_FILE",
        str(
            tmp_path
            / "order-audit.jsonl"
        ),
    )

    with pytest.raises(
        ValueError,
        match="Audit event is required",
    ):
        audit.write_order_audit("")
