from datetime import timezone

from bxk_app.services import (
    overnight_risk_service as service,
)


def _carry_risk():
    return {
        "available": True,
        "state": "RED",
        "decision": "DO_NOT_CARRY",
        "threatened_side": "CALL",
        "short_cushion": 27.04,
        "one_day_expected_move": 78.98,
        "expected_move_source": "VIX",
        "cushion_to_1d_em_ratio": 0.342,
    }


def test_linked_position_records_close_snapshot(
    monkeypatch,
):
    captured = {}

    def fake_record(**kwargs):
        captured.update(kwargs)

        return {
            "recorded": True,
            "changed": True,
            "reason_code":
                "CARRY_SNAPSHOT_RECORDED",
        }

    monkeypatch.setattr(
        service,
        "record_overnight_carry_snapshot",
        fake_record,
    )

    result = service._record_carry_learning(
        position={
            "broker_linked": True,
            "broker_order_id": "501237249",
        },
        carry_risk=_carry_risk(),
        baseline={
            "trading_date": "2026-09-01",
            "captured_at":
                "2026-09-01T15:59:47-04:00",
        },
        baseline_source="STORED",
        session={
            "monitoring_state": "GTH",
        },
        vix1d=0.0,
        vix=16.34,
    )

    assert result["recorded"] is True

    assert (
        captured["broker_order_id"]
        == "501237249"
    )

    assert (
        captured["evaluated_at"].astimezone(
            timezone.utc
        ).isoformat()
        == "2026-09-01T19:59:47+00:00"
    )

    assert captured["vix1d"] == 0.0
    assert captured["vix"] == 16.34
    assert captured["held_overnight"] is True

    snapshot = captured["carry_risk"]

    assert (
        snapshot["baseline_trading_date"]
        == "2026-09-01"
    )
    assert (
        snapshot["baseline_source"]
        == "STORED"
    )


def test_unlinked_position_not_recorded(
    monkeypatch,
):
    called = False

    def fake_record(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        service,
        "record_overnight_carry_snapshot",
        fake_record,
    )

    result = service._record_carry_learning(
        position={
            "broker_linked": False,
        },
        carry_risk=_carry_risk(),
        baseline={
            "trading_date": "2026-09-01",
            "captured_at":
                "2026-09-01T15:59:47-04:00",
        },
        baseline_source="STORED",
        session={
            "monitoring_state": "GTH",
        },
        vix1d=0.0,
        vix=16.34,
    )

    assert called is False
    assert result["recorded"] is False
    assert (
        result["reason_code"]
        == "POSITION_NOT_BROKER_LINKED"
    )


def test_nonstored_baseline_not_recorded(
    monkeypatch,
):
    called = False

    def fake_record(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        service,
        "record_overnight_carry_snapshot",
        fake_record,
    )

    result = service._record_carry_learning(
        position={
            "broker_linked": True,
            "broker_order_id": "ORDER-1",
        },
        carry_risk=_carry_risk(),
        baseline={
            "captured_at":
                "2026-09-01T15:59:47-04:00",
        },
        baseline_source="FALLBACK",
        session={
            "monitoring_state": "GTH",
        },
        vix1d=0.0,
        vix=16.34,
    )

    assert called is False
    assert result["recorded"] is False
    assert (
        result["reason_code"]
        == "STORED_BASELINE_REQUIRED"
    )
