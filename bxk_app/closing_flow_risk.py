from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")

CLOSING_RISK_START = time(15, 40)
TIGHT_MONITOR_START = time(15, 45)
REGULAR_CLOSE = time(16, 0)

SHORT_PREMIUM_STRATEGIES = (
    "IRON CONDOR",
    "BULL PUT",
    "BEAR CALL",
    "CREDIT SPREAD",
)


def _as_eastern(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(EASTERN)

    if now.tzinfo is None:
        return now.replace(tzinfo=EASTERN)

    return now.astimezone(EASTERN)


def _observed_fixed_holiday(
    year: int,
    month: int,
    day: int,
) -> date:
    holiday = date(year, month, day)

    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)

    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)

    return holiday


def _nth_weekday(
    year: int,
    month: int,
    weekday: int,
    occurrence: int,
) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7

    return current + timedelta(
        days=offset + (occurrence - 1) * 7
    )


def _last_weekday(
    year: int,
    month: int,
    weekday: int,
) -> date:
    if month == 12:
        current = date(year + 1, 1, 1)
    else:
        current = date(year, month + 1, 1)

    current -= timedelta(days=1)

    while current.weekday() != weekday:
        current -= timedelta(days=1)

    return current


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (
        19 * a
        + b
        - d
        - g
        + 15
    ) % 30
    i = c // 4
    k = c % 4
    l = (
        32
        + 2 * e
        + 2 * i
        - h
        - k
    ) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (
        h
        + l
        - 7 * m
        + 114
    ) // 31
    day = (
        (
            h
            + l
            - 7 * m
            + 114
        )
        % 31
    ) + 1

    return date(year, month, day)


def _market_holidays(year: int) -> set[date]:
    holidays = {
        _observed_fixed_holiday(
            year,
            1,
            1,
        ),
        _nth_weekday(
            year,
            1,
            0,
            3,
        ),
        _nth_weekday(
            year,
            2,
            0,
            3,
        ),
        _easter_sunday(
            year
        ) - timedelta(days=2),
        _last_weekday(
            year,
            5,
            0,
        ),
        _observed_fixed_holiday(
            year,
            7,
            4,
        ),
        _nth_weekday(
            year,
            9,
            0,
            1,
        ),
        _nth_weekday(
            year,
            11,
            3,
            4,
        ),
        _observed_fixed_holiday(
            year,
            12,
            25,
        ),
    }

    if year >= 2022:
        holidays.add(
            _observed_fixed_holiday(
                year,
                6,
                19,
            )
        )

    # A Saturday Jan. 1 is observed on Dec. 31
    # of the prior calendar year.
    next_new_year_observed = (
        _observed_fixed_holiday(
            year + 1,
            1,
            1,
        )
    )

    if next_new_year_observed.year == year:
        holidays.add(
            next_new_year_observed
        )

    return holidays


def _is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False

    return day not in _market_holidays(
        day.year
    )


def _next_trading_day(day: date) -> date:
    candidate = day + timedelta(days=1)

    for _ in range(10):
        if _is_trading_day(candidate):
            return candidate

        candidate += timedelta(days=1)

    return candidate


def is_month_end_session(
    now: datetime | None = None,
) -> bool:
    local = _as_eastern(now)
    trading_day = local.date()

    if not _is_trading_day(trading_day):
        return False

    return (
        _next_trading_day(
            trading_day
        ).month
        != trading_day.month
    )


def is_quarter_end_session(
    now: datetime | None = None,
) -> bool:
    local = _as_eastern(now)

    return (
        local.month in (3, 6, 9, 12)
        and is_month_end_session(local)
    )


def is_short_premium_strategy(
    strategy,
) -> bool:
    normalized = (
        str(strategy or "")
        .upper()
        .replace("_", " ")
        .replace("-", " ")
    )
    normalized = " ".join(
        normalized.split()
    )

    return any(
        token in normalized
        for token in SHORT_PREMIUM_STRATEGIES
    )


def _coerce_dte(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def evaluate_closing_flow_risk(
    *,
    dte,
    strategy,
    now: datetime | None = None,
) -> dict:
    """
    Evaluate the late-session risk guard for short-premium 0DTE trades.

    The guard is intentionally narrow:
    - only short-premium structures
    - only 0DTE
    - 3:40 PM through the 4:00 PM ET close
    - month/quarter-end receives a hard new-entry block
    - after 3:45 PM, open-position monitoring widens its
      warning thresholds to 0.40% / 0.60% of SPX
    """

    local = _as_eastern(now)
    dte_value = _coerce_dte(dte)
    short_premium = (
        is_short_premium_strategy(
            strategy
        )
    )
    month_end = is_month_end_session(
        local
    )
    quarter_end = (
        local.month in (3, 6, 9, 12)
        and month_end
    )

    minute_of_day = (
        local.hour * 60
        + local.minute
    )
    risk_start = 15 * 60 + 40
    monitor_start = 15 * 60 + 45
    close_minute = 16 * 60

    in_closing_window = (
        risk_start
        <= minute_of_day
        <= close_minute
    )

    active = (
        dte_value == 0
        and short_premium
        and in_closing_window
    )

    tighten_monitor = (
        active
        and minute_of_day >= monitor_start
    )

    level = "NORMAL"
    event = "NONE"
    score_penalty = 0
    block_new_entry = False
    message = (
        "No late-session closing-flow guard is active."
    )

    if active:
        if quarter_end:
            level = "HIGH"
            event = "QUARTER_END"
            score_penalty = 20
            block_new_entry = True
            message = (
                "Quarter-end MOC/rebalancing window. "
                "Avoid new 0DTE short-premium entries; "
                "closing-auction flow can overwhelm normal intraday signals."
            )

        elif month_end:
            level = "HIGH"
            event = "MONTH_END"
            score_penalty = 15
            block_new_entry = True
            message = (
                "Month-end MOC/rebalancing window. "
                "Avoid new 0DTE short-premium entries; "
                "closing-auction flow can accelerate late moves."
            )

        else:
            level = "ELEVATED"
            event = "LATE_SESSION"
            score_penalty = 8
            message = (
                "Late-session gamma/closing-flow window. "
                "New 0DTE short-premium entries carry elevated risk "
                "after 3:40 PM ET."
            )

    return {
        "active": active,
        "level": level,
        "event": event,
        "dte": dte_value,
        "short_premium": short_premium,
        "month_end_session": month_end,
        "quarter_end_session": quarter_end,
        "score_penalty": score_penalty,
        "block_new_entry": block_new_entry,
        "tighten_position_monitor": (
            tighten_monitor
        ),
        "red_distance_pct": (
            0.004
            if tighten_monitor
            else None
        ),
        "orange_distance_pct": (
            0.006
            if tighten_monitor
            else None
        ),
        "window_start_et": "15:40",
        "monitor_start_et": "15:45",
        "close_et": "16:00",
        "timestamp_et": local.isoformat(),
        "message": message,
    }
