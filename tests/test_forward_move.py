import csv

from bxk_app.forward_move import (
    analyze_forward_move,
    calculate_forward_profile,
    load_forward_history,
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


def test_forward_move_from_945(
    tmp_path,
):
    path = tmp_path / "2026-08-17.csv"

    write_day(
        path,
        [
            {
                "minutes_since_open": 10,
                "spx": 7800,
                "expected_move": 50,
            },
            {
                "minutes_since_open": 15,
                "spx": 7810,
                "expected_move": 50,
            },
            {
                "minutes_since_open": 30,
                "spx": 7835,
                "expected_move": 47,
            },
            {
                "minutes_since_open": 90,
                "spx": 7770,
                "expected_move": 42,
            },
            {
                "minutes_since_open": 389,
                "spx": 7805,
                "expected_move": 20,
            },
        ],
    )

    result = analyze_forward_move(
        path,
        15,
    )

    assert result is not None
    assert result.checkpoint_spx == 7810.0
    assert result.implied_move == 50.0
    assert result.max_up_after == 25.0
    assert result.max_down_after == 40.0
    assert (
        result.max_directional_after
        == 40.0
    )
    assert result.forward_move_ratio == 0.8


def test_checkpoint_allows_small_delay(
    tmp_path,
):
    path = tmp_path / "2026-08-18.csv"

    write_day(
        path,
        [
            {
                "minutes_since_open": 16,
                "spx": 7800,
                "expected_move": 50,
            },
            {
                "minutes_since_open": 40,
                "spx": 7850,
                "expected_move": 45,
            },
        ],
    )

    result = analyze_forward_move(
        path,
        15,
    )

    assert result is not None
    assert result.actual_minute == 16
    assert result.max_up_after == 50.0
    assert result.forward_move_ratio == 1.0


def test_load_forward_history(
    tmp_path,
):
    for day, final_spx in [
        (17, 7820),
        (18, 7840),
        (19, 7860),
    ]:
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
                },
                {
                    "minutes_since_open": 389,
                    "spx": final_spx,
                    "expected_move": 20,
                },
            ],
        )

    history = load_forward_history(
        tmp_path,
        15,
        limit=2,
    )

    assert len(history) == 2
    assert history[0].date == "2026-08-18"
    assert history[1].date == "2026-08-19"


def test_forward_profile():
    class Item:
        def __init__(self, ratio):
            self.forward_move_ratio = ratio

    history = [
        Item(0.50),
        Item(0.75),
        Item(1.00),
        Item(1.50),
        Item(2.00),
    ]

    result = calculate_forward_profile(
        history,
        current_implied_move=50,
    )

    assert result["available"] is True
    assert result["sample_days"] == 5
    assert result["status"] == "OBSERVING"

    assert result["median_forward_ratio"] == 1.0
    assert result["p75_forward_ratio"] == 1.5
    assert result["p90_forward_ratio"] == 1.8
    assert result["worst_forward_ratio"] == 2.0

    assert result["p75_forward_move"] == 75.0
    assert result["p90_forward_move"] == 90.0
    assert result["worst_forward_move"] == 100.0


def test_forward_profile_requires_history():
    result = calculate_forward_profile(
        [],
        current_implied_move=50,
    )

    assert result == {
        "available": False,
        "status": "INSUFFICIENT_HISTORY",
        "sample_days": 0,
    }
