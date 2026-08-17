import csv
from datetime import date, timedelta

import bxk_app.services.market_service as market_service


FIELDS = [
    "timestamp",
    "session_phase",
    "minutes_since_open",
    "expected_pace_pct",
    "pressure_ratio",
    "pace_delta_pct",
    "spx",
    "vix",
    "vix1d",
    "expected_move",
    "session_open",
    "day_high",
    "day_low",
    "session_range",
    "upside_excursion",
    "downside_excursion",
    "max_directional_excursion",
    "directional_consumed_pct",
    "range_band_consumed_pct",
    "current_displacement",
    "current_displacement_pct",
    "overnight_gap",
    "overnight_gap_pct",
    "expected_move_source",
    "market_status",
    "signal_ready",
]


def write_day(path, *, implied, move, pressure):
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=FIELDS,
        )

        writer.writeheader()

        row = {
            field: ""
            for field in FIELDS
        }

        row.update({
            "timestamp":
                f"{path.stem}T10:00:00",
            "minutes_since_open": 30,
            "spx": 7800,
            "expected_move": implied,
            "session_range": move,
            "max_directional_excursion": move,
            "directional_consumed_pct":
                (move / implied) * 100,
            "expected_pace_pct": 27.7,
            "pressure_ratio": pressure,
        })

        writer.writerow(row)


def test_recent_summary_without_history(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    result = (
        market_service
        .get_recent_condor_risk_summaries()
    )

    assert result == {
        "status": "NO_DATA",
        "count": 0,
        "limit": 10,
        "summaries": [],
    }


def test_recent_summary_excludes_today(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    today = date.today()

    yesterday = (
        today - timedelta(days=1)
    ).isoformat()

    write_day(
        tmp_path /
        f"{yesterday}.csv",
        implied=50,
        move=40,
        pressure=1.2,
    )

    # This deliberately violent current-day file must
    # never enter completed historical summaries.
    write_day(
        tmp_path /
        f"{today.isoformat()}.csv",
        implied=50,
        move=110,
        pressure=2.5,
    )

    result = (
        market_service
        .get_recent_condor_risk_summaries()
    )

    assert result["status"] == "AVAILABLE"
    assert result["count"] == 1

    assert (
        result["summaries"][0]["date"]
        == yesterday
    )

    assert (
        result["summaries"][0]
        ["max_directional_excursion"]
        == 40.0
    )


def test_recent_summary_respects_limit(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    today = date.today()

    for offset in range(1, 6):
        trading_date = (
            today -
            timedelta(days=offset)
        ).isoformat()

        write_day(
            tmp_path /
            f"{trading_date}.csv",
            implied=50,
            move=30 + offset,
            pressure=1.0 + (
                offset / 10
            ),
        )

    result = (
        market_service
        .get_recent_condor_risk_summaries(
            limit=3
        )
    )

    assert result["count"] == 3
    assert result["limit"] == 3
    assert len(result["summaries"]) == 3


def test_recent_summary_caps_limit(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        market_service,
        "DEFAULT_LOG_DIR",
        tmp_path,
    )

    result = (
        market_service
        .get_recent_condor_risk_summaries(
            limit=500
        )
    )

    assert result["limit"] == 30
