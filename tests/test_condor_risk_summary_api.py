from pathlib import Path

import bxk_app.services.market_service as market_service


def test_today_condor_summary_without_data(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    monkeypatch.setattr(
        market_service.market_data,
        "market_status",
        lambda: "CLOSED",
    )

    result = (
        market_service
        .get_today_condor_risk_summary()
    )

    assert result["partial_session"] is False
    assert result["market_status"] == "CLOSED"

    summary = result["summary"]

    assert summary["available"] is False
    assert summary["status"] == "NO_DATA"


def test_today_condor_summary_marks_live_as_partial(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    monkeypatch.setattr(
        market_service.market_data,
        "market_status",
        lambda: "LIVE",
    )

    result = (
        market_service
        .get_today_condor_risk_summary()
    )

    assert result["partial_session"] is True
    assert result["market_status"] == "LIVE"


def test_today_condor_summary_uses_expected_path(
    monkeypatch,
    tmp_path,
):
    captured = {}

    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    monkeypatch.setattr(
        market_service.market_data,
        "market_status",
        lambda: "CLOSED",
    )

    def fake_summary(path):
        captured["path"] = Path(path)

        return {
            "available": True,
            "status": "AVAILABLE",
        }

    monkeypatch.setattr(
        market_service,
        "summarize_condor_risk_day",
        fake_summary,
    )

    result = (
        market_service
        .get_today_condor_risk_summary()
    )

    assert result["summary"]["available"] is True

    assert (
        captured["path"].parent
        == tmp_path
    )

    assert (
        captured["path"].suffix
        == ".csv"
    )
