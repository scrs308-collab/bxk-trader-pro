import csv

from bxk_app.range_expansion import (
    calculate_range_expansion_profile,
    load_range_expansion_history,
    summarize_daily_file,
)


FIELDNAMES = [
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
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        for row in rows:
            base = {
                field: ""
                for field in FIELDNAMES
            }

            base.update(row)
            writer.writerow(base)


def test_summarize_daily_range_expansion(
    tmp_path,
):
    path = tmp_path / "2026-08-17.csv"

    write_day(
        path,
        [
            {
                "timestamp":
                    "2026-08-17T09:31:00",
                "expected_move": 50,
                "upside_excursion": 5,
                "downside_excursion": 2,
                "max_directional_excursion": 5,
                "session_range": 7,
            },
            {
                "timestamp":
                    "2026-08-17T11:00:00",
                "expected_move": 48,
                "upside_excursion": 35,
                "downside_excursion": 8,
                "max_directional_excursion": 35,
                "session_range": 43,
            },
            {
                "timestamp":
                    "2026-08-17T15:59:00",
                "expected_move": 20,
                "upside_excursion": 42,
                "downside_excursion": 12,
                "max_directional_excursion": 42,
                "session_range": 54,
            },
        ],
    )

    result = summarize_daily_file(path)

    assert result is not None
    assert result.date == "2026-08-17"

    # First valid implied move is the reference.
    assert result.opening_implied_move == 50.0

    assert result.max_upside_excursion == 42.0
    assert result.max_downside_excursion == 12.0
    assert (
        result.max_directional_excursion
        == 42.0
    )

    assert result.final_session_range == 54.0
    assert result.expansion_ratio == 0.84


def test_load_history_in_date_order(
    tmp_path,
):
    for date, move in [
        ("2026-08-17", 40),
        ("2026-08-18", 60),
        ("2026-08-19", 80),
    ]:
        write_day(
            tmp_path / f"{date}.csv",
            [
                {
                    "expected_move": 50,
                    "upside_excursion": move,
                    "downside_excursion": 0,
                    "max_directional_excursion":
                        move,
                    "session_range": move,
                }
            ],
        )

    history = load_range_expansion_history(
        tmp_path,
        limit=2,
    )

    assert len(history) == 2
    assert history[0].date == "2026-08-18"
    assert history[1].date == "2026-08-19"


def test_expansion_profile_and_stress_moves(
    tmp_path,
):
    ratios = [
        0.80,
        0.90,
        1.00,
        1.20,
        1.50,
    ]

    for index, ratio in enumerate(
        ratios,
        start=17,
    ):
        move = 50 * ratio

        write_day(
            tmp_path /
            f"2026-08-{index:02d}.csv",
            [
                {
                    "expected_move": 50,
                    "upside_excursion": move,
                    "downside_excursion": 0,
                    "max_directional_excursion":
                        move,
                    "session_range": move,
                }
            ],
        )

    history = load_range_expansion_history(
        tmp_path
    )

    result = calculate_range_expansion_profile(
        history,
        current_implied_move=52,
    )

    assert result["available"] is True
    assert result["sample_days"] == 5
    assert result["status"] == "OBSERVING"

    assert (
        result["median_expansion_ratio"]
        == 1.0
    )

    assert (
        result["p75_expansion_ratio"]
        == 1.2
    )

    assert (
        result["p90_expansion_ratio"]
        == 1.38
    )

    assert (
        result["worst_expansion_ratio"]
        == 1.5
    )

    assert (
        result["normal_stress_move"]
        == 62.4
    )

    assert (
        result["high_stress_move"]
        == 71.76
    )

    assert (
        result["recent_extreme_move"]
        == 78.0
    )


def test_profile_requires_history():
    result = calculate_range_expansion_profile(
        [],
        current_implied_move=50,
    )

    assert result == {
        "available": False,
        "status": "INSUFFICIENT_HISTORY",
        "sample_days": 0,
    }
