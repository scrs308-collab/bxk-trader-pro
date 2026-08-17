import csv

from bxk_app.condor_risk_profile import (
    build_condor_risk_profile,
)


FIELDS = [
    "timestamp",
    "session_phase",
    "minutes_since_open",
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


def test_profile_without_history(
    tmp_path,
):
    result = build_condor_risk_profile(
        current_implied_move=50,
        history_dir=tmp_path,
    )

    assert (
        result["status"]
        == "INSUFFICIENT_HISTORY"
    )

    assert result["sample_days"] == 0

    assert (
        result["range_expansion"]["available"]
        is False
    )

    assert (
        result["forward_risk"]["0945"]["available"]
        is False
    )

    assert (
        result["forward_risk"]["1000"]["available"]
        is False
    )

    assert (
        result["forward_risk"]["1030"]["available"]
        is False
    )


def test_profile_builds_checkpoint_risk(
    tmp_path,
):
    path = tmp_path / "2026-08-17.csv"

    write_day(
        path,
        [
            {
                "minutes_since_open": 0,
                "spx": 7800,
                "expected_move": 50,
                "upside_excursion": 0,
                "downside_excursion": 0,
                "max_directional_excursion": 0,
                "session_range": 0,
            },
            {
                "minutes_since_open": 15,
                "spx": 7810,
                "expected_move": 50,
                "upside_excursion": 10,
                "downside_excursion": 0,
                "max_directional_excursion": 10,
                "session_range": 10,
            },
            {
                "minutes_since_open": 30,
                "spx": 7820,
                "expected_move": 48,
                "upside_excursion": 20,
                "downside_excursion": 0,
                "max_directional_excursion": 20,
                "session_range": 20,
            },
            {
                "minutes_since_open": 60,
                "spx": 7830,
                "expected_move": 45,
                "upside_excursion": 30,
                "downside_excursion": 0,
                "max_directional_excursion": 30,
                "session_range": 30,
            },
            {
                "minutes_since_open": 180,
                "spx": 7860,
                "expected_move": 35,
                "upside_excursion": 60,
                "downside_excursion": 0,
                "max_directional_excursion": 60,
                "session_range": 60,
            },
        ],
    )

    result = build_condor_risk_profile(
        current_implied_move=52,
        history_dir=tmp_path,
    )

    assert result["status"] == "OBSERVING"
    assert result["sample_days"] == 1

    assert (
        result["range_expansion"]["available"]
        is True
    )

    profile_945 = (
        result["forward_risk"]["0945"]
    )

    assert profile_945["available"] is True
    assert profile_945["sample_days"] == 1

    assert (
        profile_945["worst_forward_move"]
        == 52.0
    )

    profile_1000 = (
        result["forward_risk"]["1000"]
    )

    assert profile_1000["available"] is True

    profile_1030 = (
        result["forward_risk"]["1030"]
    )

    assert profile_1030["available"] is True


def test_profile_becomes_available_at_ten_days(
    tmp_path,
):
    for day in range(1, 11):
        path = (
            tmp_path /
            f"2026-08-{day:02d}.csv"
        )

        write_day(
            path,
            [
                {
                    "minutes_since_open": 15,
                    "spx": 7800,
                    "expected_move": 50,
                    "upside_excursion": 10,
                    "downside_excursion": 0,
                    "max_directional_excursion": 10,
                    "session_range": 10,
                },
                {
                    "minutes_since_open": 30,
                    "spx": 7810,
                    "expected_move": 48,
                    "upside_excursion": 20,
                    "downside_excursion": 0,
                    "max_directional_excursion": 20,
                    "session_range": 20,
                },
                {
                    "minutes_since_open": 60,
                    "spx": 7820,
                    "expected_move": 45,
                    "upside_excursion": 30,
                    "downside_excursion": 0,
                    "max_directional_excursion": 30,
                    "session_range": 30,
                },
                {
                    "minutes_since_open": 180,
                    "spx": 7850,
                    "expected_move": 35,
                    "upside_excursion": 50,
                    "downside_excursion": 0,
                    "max_directional_excursion": 50,
                    "session_range": 50,
                },
            ],
        )

    result = build_condor_risk_profile(
        current_implied_move=50,
        history_dir=tmp_path,
    )

    assert result["sample_days"] == 10
    assert result["status"] == "AVAILABLE"
