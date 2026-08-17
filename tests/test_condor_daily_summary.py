import csv

from bxk_app.condor_daily_summary import (
    summarize_condor_risk_day,
)


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


def write_day(path, rows):
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

        for row in rows:
            base = {
                field: ""
                for field in FIELDS
            }

            base.update(row)
            writer.writerow(base)


def test_daily_summary(
    tmp_path,
):
    path = tmp_path / "2026-08-17.csv"

    write_day(
        path,
        [
            {
                "timestamp":
                    "2026-08-17T09:45:00",
                "minutes_since_open": 15,
                "spx": 7800,
                "expected_move": 50,
                "session_range": 15,
                "max_directional_excursion": 12,
                "directional_consumed_pct": 24,
                "expected_pace_pct": 19.6,
                "pressure_ratio": 1.22,
            },
            {
                "timestamp":
                    "2026-08-17T10:00:00",
                "minutes_since_open": 30,
                "spx": 7820,
                "expected_move": 48,
                "session_range": 30,
                "max_directional_excursion": 28,
                "directional_consumed_pct": 58,
                "expected_pace_pct": 27.7,
                "pressure_ratio": 2.09,
            },
            {
                "timestamp":
                    "2026-08-17T10:30:00",
                "minutes_since_open": 60,
                "spx": 7830,
                "expected_move": 45,
                "session_range": 42,
                "max_directional_excursion": 35,
                "directional_consumed_pct": 78,
                "expected_pace_pct": 39.2,
                "pressure_ratio": 1.99,
            },
            {
                "timestamp":
                    "2026-08-17T14:15:00",
                "minutes_since_open": 285,
                "spx": 7860,
                "expected_move": 30,
                "session_range": 74,
                "max_directional_excursion": 63,
                "directional_consumed_pct": 126,
                "expected_pace_pct": 85.5,
                "pressure_ratio": 1.47,
            },
        ],
    )

    result = summarize_condor_risk_day(
        path
    )

    assert result["available"] is True
    assert result["date"] == "2026-08-17"

    assert (
        result["opening_implied_move"]
        == 50.0
    )

    assert (
        result["final_session_range"]
        == 74.0
    )

    assert (
        result["max_directional_excursion"]
        == 63.0
    )

    assert (
        result["max_directional_consumed_pct"]
        == 126.0
    )

    assert result["expansion_ratio"] == 1.26

    assert (
        result["peak_pressure_ratio"]
        == 2.09
    )

    assert (
        result["peak_pressure_minute"]
        == 30
    )

    assert (
        result["checkpoints"]["0945"]
        ["pressure_ratio"]
        == 1.22
    )

    assert (
        result["checkpoints"]["1000"]
        ["pressure_ratio"]
        == 2.09
    )

    assert (
        result["checkpoints"]["1030"]
        ["pressure_ratio"]
        == 1.99
    )


def test_daily_summary_without_file(
    tmp_path,
):
    result = summarize_condor_risk_day(
        tmp_path / "missing.csv"
    )

    assert result == {
        "available": False,
        "status": "NO_DATA",
        "date": "missing",
    }
