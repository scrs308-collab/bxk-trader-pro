import csv
from datetime import datetime
from types import SimpleNamespace

from bxk_app.services.condor_stability_logger import (
    log_condor_stability,
)


def build_market_data(
    *,
    signal_ready=True,
    market_status="LIVE",
    expected_move_source="VIX1D",
):
    return SimpleNamespace(
        spx=7800.0,
        vix=15.0,
        vix1d=16.0,
        expected_move=50.0,
        condor_stability={
            "available": True,
            "signal_ready": signal_ready,
            "state": "OBSERVING",
            "reason_code":
                "STABILITY_METRICS_AVAILABLE",
            "expected_move_source":
                expected_move_source,
            "market_status": market_status,
            "implied_move": 50.0,
            "session_open": 7780.0,
            "day_high": 7810.0,
            "day_low": 7770.0,
            "session_range": 40.0,
            "upside_excursion": 30.0,
            "downside_excursion": 10.0,
            "max_directional_excursion": 30.0,
            "directional_consumed_pct": 60.0,
            "range_band_consumed_pct": 40.0,
            "current_displacement": 20.0,
            "current_displacement_pct": 40.0,
            "overnight_gap": 5.0,
            "overnight_gap_pct": 10.0,
            "range_expansion_pressure": {
                "available": True,
                "state": "OBSERVING",
                "expected_pace_pct": 27.7,
                "pressure_ratio": 2.17,
                "pace_delta_pct": 32.3,
            },
            "stability_score": {
                "available": True,
                "state": "OBSERVING",
                "score": 61.4,
                "total_penalty": 38.6,
            },
        },
    )


def read_rows(path):
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def test_logger_writes_valid_live_observation(
    tmp_path,
):
    market = build_market_data()

    result = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            17,
            9,
            45,
            12,
        ),
        log_dir=tmp_path,
    )

    assert result["logged"] is True
    assert result["reason"] == "LOGGED"

    path = (
        tmp_path /
        "2026-08-17.csv"
    )

    rows = read_rows(path)

    assert len(rows) == 1
    assert rows[0]["session_phase"] == "OPENING"
    assert rows[0]["minutes_since_open"] == "15"
    assert rows[0]["expected_pace_pct"] == "27.7"
    assert rows[0]["pressure_ratio"] == "2.17"
    assert rows[0]["pace_delta_pct"] == "32.3"
    assert rows[0]["stability_score"] == "61.4"
    assert rows[0]["stability_total_penalty"] == "38.6"
    assert rows[0]["spx"] == "7800.0"
    assert rows[0]["vix1d"] == "16.0"
    assert (
        rows[0]["directional_consumed_pct"]
        == "60.0"
    )
    assert (
        rows[0]["expected_move_source"]
        == "VIX1D"
    )


def test_logger_skips_duplicate_minute(
    tmp_path,
):
    market = build_market_data()

    first = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            17,
            9,
            45,
            12,
        ),
        log_dir=tmp_path,
    )

    second = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            17,
            9,
            45,
            55,
        ),
        log_dir=tmp_path,
    )

    assert first["logged"] is True
    assert second["logged"] is False
    assert (
        second["reason"]
        == "MINUTE_ALREADY_LOGGED"
    )

    rows = read_rows(
        tmp_path /
        "2026-08-17.csv"
    )

    assert len(rows) == 1


def test_logger_writes_next_minute(
    tmp_path,
):
    market = build_market_data()

    log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            17,
            9,
            45,
            12,
        ),
        log_dir=tmp_path,
    )

    result = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            17,
            9,
            46,
            2,
        ),
        log_dir=tmp_path,
    )

    assert result["logged"] is True

    rows = read_rows(
        tmp_path /
        "2026-08-17.csv"
    )

    assert len(rows) == 2


def test_logger_skips_when_signal_not_ready(
    tmp_path,
):
    market = build_market_data(
        signal_ready=False,
        market_status="CLOSED",
        expected_move_source="VIX",
    )

    result = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            16,
            20,
            30,
            0,
        ),
        log_dir=tmp_path,
    )

    assert result["logged"] is False
    assert result["reason"] == "SIGNAL_NOT_READY"

    assert not (
        tmp_path /
        "2026-08-16.csv"
    ).exists()


def test_logger_rejects_weekend_even_if_signal_claims_live(
    tmp_path,
):
    market = build_market_data(
        signal_ready=True,
        market_status="LIVE",
        expected_move_source="VIX1D",
    )

    result = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            16,
            10,
            0,
            0,
        ),
        log_dir=tmp_path,
    )

    assert result["logged"] is False
    assert result["reason"] == "MARKET_NOT_LIVE"

    assert not (
        tmp_path /
        "2026-08-16.csv"
    ).exists()


def test_logger_accepts_vix_fallback(
    tmp_path,
):
    market = build_market_data(
        signal_ready=True,
        market_status="LIVE",
        expected_move_source="VIX",
    )

    result = log_condor_stability(
        market,
        now=datetime(
            2026,
            8,
            20,
            10,
            30,
            0,
        ),
        log_dir=tmp_path,
    )

    assert result["logged"] is True

    path = (
        tmp_path
        / "2026-08-20.csv"
    )

    rows = list(
        csv.DictReader(
            path.open(
                newline="",
                encoding="utf-8",
            )
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["expected_move_source"]
        == "VIX"
    )
