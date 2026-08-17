import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class DailyRangeExpansion:
    date: str
    opening_implied_move: float
    max_upside_excursion: float
    max_downside_excursion: float
    max_directional_excursion: float
    final_session_range: float
    expansion_ratio: float


def _to_float(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return number


def _percentile(values, percentile):
    """
    Linear-interpolated percentile without external dependencies.
    """

    clean = sorted(
        float(value)
        for value in values
        if value is not None
    )

    if not clean:
        return None

    if len(clean) == 1:
        return clean[0]

    position = (
        (len(clean) - 1) *
        (percentile / 100.0)
    )

    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(clean) - 1,
    )

    fraction = position - lower_index

    lower = clean[lower_index]
    upper = clean[upper_index]

    return lower + (
        (upper - lower) * fraction
    )


def summarize_daily_file(path):
    """
    Convert one Condor Stability CSV into a daily
    range-expansion summary.

    The first valid expected_move becomes the day's opening
    implied-move reference.

    Excursion values are already measured from the session open
    by condor_stability.py.
    """

    path = Path(path)

    if not path.exists():
        return None

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            rows.append(row)

    if not rows:
        return None

    valid_implied = []

    upside_values = []
    downside_values = []
    directional_values = []
    range_values = []

    for row in rows:
        implied = _to_float(
            row.get("expected_move")
        )

        if implied is not None and implied > 0:
            valid_implied.append(implied)

        upside = _to_float(
            row.get("upside_excursion")
        )

        downside = _to_float(
            row.get("downside_excursion")
        )

        directional = _to_float(
            row.get("max_directional_excursion")
        )

        session_range = _to_float(
            row.get("session_range")
        )

        if upside is not None:
            upside_values.append(upside)

        if downside is not None:
            downside_values.append(downside)

        if directional is not None:
            directional_values.append(
                directional
            )

        if session_range is not None:
            range_values.append(
                session_range
            )

    if not valid_implied:
        return None

    opening_implied_move = valid_implied[0]

    max_upside = max(
        upside_values,
        default=0.0,
    )

    max_downside = max(
        downside_values,
        default=0.0,
    )

    max_directional = max(
        directional_values,
        default=max(
            max_upside,
            max_downside,
        ),
    )

    final_session_range = max(
        range_values,
        default=0.0,
    )

    expansion_ratio = (
        max_directional /
        opening_implied_move
    )

    return DailyRangeExpansion(
        date=path.stem,
        opening_implied_move=round(
            opening_implied_move,
            2,
        ),
        max_upside_excursion=round(
            max_upside,
            2,
        ),
        max_downside_excursion=round(
            max_downside,
            2,
        ),
        max_directional_excursion=round(
            max_directional,
            2,
        ),
        final_session_range=round(
            final_session_range,
            2,
        ),
        expansion_ratio=round(
            expansion_ratio,
            4,
        ),
    )


def load_range_expansion_history(
    directory,
    *,
    limit=20,
):
    """
    Load recent completed daily Condor Stability files.
    """

    directory = Path(directory)

    if not directory.exists():
        return []

    paths = sorted(
        directory.glob("*.csv"),
        reverse=True,
    )

    summaries = []

    for path in paths:
        summary = summarize_daily_file(path)

        if summary is not None:
            summaries.append(summary)

        if len(summaries) >= limit:
            break

    return list(reversed(summaries))


def calculate_range_expansion_profile(
    history,
    *,
    current_implied_move=None,
):
    """
    Build rolling expansion statistics.

    Observation-only for now. No trade permission is changed.
    """

    ratios = [
        item.expansion_ratio
        for item in history
        if item.expansion_ratio > 0
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
        "median_expansion_ratio": round(
            med,
            2,
        ),
        "p75_expansion_ratio": round(
            p75,
            2,
        ),
        "p90_expansion_ratio": round(
            p90,
            2,
        ),
        "worst_expansion_ratio": round(
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
            "normal_stress_move": round(
                implied * p75,
                2,
            ),
            "high_stress_move": round(
                implied * p90,
                2,
            ),
            "recent_extreme_move": round(
                implied * worst,
                2,
            ),
        })

    return result
