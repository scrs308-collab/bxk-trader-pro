import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class ForwardMove:
    date: str
    checkpoint_minute: int
    actual_minute: int
    checkpoint_spx: float
    implied_move: float
    max_up_after: float
    max_down_after: float
    max_directional_after: float
    forward_move_ratio: float


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _percentile(values, percentile):
    values = sorted(
        float(value)
        for value in values
        if value is not None
    )

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1) *
        (percentile / 100.0)
    )

    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(values) - 1,
    )

    fraction = position - lower_index

    return (
        values[lower_index] +
        (
            values[upper_index] -
            values[lower_index]
        ) * fraction
    )


def load_rows(path):
    path = Path(path)

    if not path.exists():
        return []

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            minute = _to_int(
                row.get("minutes_since_open")
            )

            spx = _to_float(
                row.get("spx")
            )

            implied = _to_float(
                row.get("expected_move")
            )

            if (
                minute is None
                or spx is None
                or implied is None
                or implied <= 0
            ):
                continue

            rows.append({
                "minute": minute,
                "spx": spx,
                "implied_move": implied,
            })

    return sorted(
        rows,
        key=lambda row: row["minute"],
    )


def analyze_forward_move(
    path,
    checkpoint_minute,
    *,
    tolerance_minutes=2,
):
    """
    Measure sampled SPX movement after a checkpoint.

    Example checkpoints:
        15 = 09:45
        30 = 10:00
        60 = 10:30

    The first observation at or shortly after the requested
    checkpoint becomes the reference price.

    This uses minute-sampled SPX observations. It does not yet
    claim to capture every intraminute high/low.
    """

    path = Path(path)
    rows = load_rows(path)

    if not rows:
        return None

    checkpoint = None

    for row in rows:
        if (
            checkpoint_minute
            <= row["minute"]
            <= checkpoint_minute + tolerance_minutes
        ):
            checkpoint = row
            break

    if checkpoint is None:
        return None

    future_rows = [
        row
        for row in rows
        if row["minute"] >= checkpoint["minute"]
    ]

    if not future_rows:
        return None

    checkpoint_spx = checkpoint["spx"]

    future_high = max(
        row["spx"]
        for row in future_rows
    )

    future_low = min(
        row["spx"]
        for row in future_rows
    )

    max_up = max(
        0.0,
        future_high - checkpoint_spx,
    )

    max_down = max(
        0.0,
        checkpoint_spx - future_low,
    )

    max_directional = max(
        max_up,
        max_down,
    )

    implied = checkpoint["implied_move"]

    ratio = (
        max_directional / implied
        if implied > 0
        else 0.0
    )

    return ForwardMove(
        date=path.stem,
        checkpoint_minute=checkpoint_minute,
        actual_minute=checkpoint["minute"],
        checkpoint_spx=round(
            checkpoint_spx,
            2,
        ),
        implied_move=round(
            implied,
            2,
        ),
        max_up_after=round(
            max_up,
            2,
        ),
        max_down_after=round(
            max_down,
            2,
        ),
        max_directional_after=round(
            max_directional,
            2,
        ),
        forward_move_ratio=round(
            ratio,
            4,
        ),
    )


def load_forward_history(
    directory,
    checkpoint_minute,
    *,
    limit=20,
    exclude_date=None,
):
    directory = Path(directory)

    if not directory.exists():
        return []

    paths = sorted(
        directory.glob("*.csv"),
        reverse=True,
    )

    results = []

    for path in paths:
        if (
            exclude_date is not None
            and path.stem == str(exclude_date)
        ):
            continue

        result = analyze_forward_move(
            path,
            checkpoint_minute,
        )

        if result is not None:
            results.append(result)

        if len(results) >= limit:
            break

    return list(reversed(results))


def calculate_forward_profile(
    history,
    *,
    current_implied_move=None,
):
    ratios = [
        item.forward_move_ratio
        for item in history
        if item.forward_move_ratio >= 0
    ]

    if not ratios:
        return {
            "available": False,
            "status": "INSUFFICIENT_HISTORY",
            "sample_days": 0,
        }

    med = median(ratios)
    p75 = _percentile(ratios, 75)
    p90 = _percentile(ratios, 90)
    worst = max(ratios)

    result = {
        "available": True,
        "status": (
            "OBSERVING"
            if len(ratios) < 10
            else "AVAILABLE"
        ),
        "sample_days": len(ratios),
        "median_forward_ratio": round(
            med,
            2,
        ),
        "p75_forward_ratio": round(
            p75,
            2,
        ),
        "p90_forward_ratio": round(
            p90,
            2,
        ),
        "worst_forward_ratio": round(
            worst,
            2,
        ),
    }

    implied = _to_float(
        current_implied_move
    )

    if implied is not None and implied > 0:
        result.update({
            "current_implied_move": round(
                implied,
                2,
            ),
            "p75_forward_move": round(
                implied * p75,
                2,
            ),
            "p90_forward_move": round(
                implied * p90,
                2,
            ),
            "worst_forward_move": round(
                implied * worst,
                2,
            ),
        })

    return result
