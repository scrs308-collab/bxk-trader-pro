from datetime import datetime
from zoneinfo import ZoneInfo

from bxk_app.services import (
    overnight_baseline_service,
)


ET = ZoneInfo("America/New_York")


ACTIVE_ES = {
    "symbol": "/ESU6",
    "active": True,
    "active-month": True,
}


ES_QUOTE = {
    "bid": "7728.75",
    "ask": "7729.00",
    "mark": "7729.00",
    "symbol": "/ESU6",
}


def et(
    hour,
    minute,
    second=0,
):
    return datetime(
        2026,
        8,
        20,
        hour,
        minute,
        second,
        tzinfo=ET,
    )


def configure_broker(
    monkeypatch,
):
    monkeypatch.setattr(
        overnight_baseline_service.broker,
        "get_active_future",
        lambda product_code: ACTIVE_ES,
    )

    monkeypatch.setattr(
        overnight_baseline_service.broker,
        "get_future_quote",
        lambda symbol: ES_QUOTE,
    )


def test_capture_inside_close_window(
    monkeypatch,
    tmp_path,
):
    configure_broker(
        monkeypatch
    )

    result = (
        overnight_baseline_service
        .maybe_capture_overnight_baseline(
            spx_price=7707.98,
            now=et(
                15,
                59,
                30,
            ),
            directory=tmp_path,
        )
    )

    assert result["captured"] is True

    assert (
        result["reason_code"]
        == "OVERNIGHT_BASELINE_CAPTURED"
    )

    assert (
        result["price_source"]
        == "MID"
    )

    assert (
        result["baseline"][
            "spx_close"
        ]
        == 7707.98
    )

    assert (
        result["baseline"][
            "es_anchor_price"
        ]
        == 7728.875
    )


def test_before_window_does_not_capture(
    monkeypatch,
    tmp_path,
):
    result = (
        overnight_baseline_service
        .maybe_capture_overnight_baseline(
            spx_price=7707.98,
            now=et(
                15,
                57,
                59,
            ),
            directory=tmp_path,
        )
    )

    assert result["captured"] is False

    assert (
        result["reason_code"]
        == "BASELINE_CAPTURE_WINDOW_INACTIVE"
    )


def test_at_4pm_does_not_capture(
    tmp_path,
):
    result = (
        overnight_baseline_service
        .maybe_capture_overnight_baseline(
            spx_price=7707.98,
            now=et(
                16,
                0,
                0,
            ),
            directory=tmp_path,
        )
    )

    assert result["captured"] is False


def test_missing_spx_fails_closed(
    tmp_path,
):
    result = (
        overnight_baseline_service
        .maybe_capture_overnight_baseline(
            spx_price=None,
            now=et(
                15,
                59,
            ),
            directory=tmp_path,
        )
    )

    assert result["captured"] is False

    assert (
        result["reason_code"]
        == "SPX_CAPTURE_PRICE_UNAVAILABLE"
    )


def test_missing_es_contract_fails_closed(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        overnight_baseline_service.broker,
        "get_active_future",
        lambda product_code: None,
    )

    result = (
        overnight_baseline_service
        .maybe_capture_overnight_baseline(
            spx_price=7707.98,
            now=et(
                15,
                59,
            ),
            directory=tmp_path,
        )
    )

    assert result["captured"] is False

    assert (
        result["reason_code"]
        == "ACTIVE_ES_CONTRACT_UNAVAILABLE"
    )


def test_second_capture_replaces_first(
    monkeypatch,
    tmp_path,
):
    configure_broker(
        monkeypatch
    )

    overnight_baseline_service \
        .maybe_capture_overnight_baseline(
            spx_price=7705.00,
            now=et(
                15,
                58,
                5,
            ),
            directory=tmp_path,
        )

    overnight_baseline_service \
        .maybe_capture_overnight_baseline(
            spx_price=7707.98,
            now=et(
                15,
                59,
                45,
            ),
            directory=tmp_path,
        )

    from bxk_app.overnight_baseline import (
        load_overnight_baseline,
    )

    saved = load_overnight_baseline(
        trading_date="2026-08-20",
        directory=tmp_path,
    )

    assert saved["spx_close"] == 7707.98

    assert (
        saved["captured_at"]
        == "2026-08-20T15:59:45-04:00"
    )
