from datetime import datetime, time
from zoneinfo import ZoneInfo

from bxk_app.brokers.tastytrade import broker
from bxk_app.overnight_baseline import (
    save_overnight_baseline,
)
from bxk_app.overnight_reference import (
    select_future_reference_price,
)


EASTERN = ZoneInfo("America/New_York")

CAPTURE_START = time(15, 58)
CAPTURE_END = time(16, 0)


def _eastern_now(
    value: datetime | None = None,
):
    if value is None:
        return datetime.now(EASTERN)

    if value.tzinfo is None:
        return value.replace(
            tzinfo=EASTERN
        )

    return value.astimezone(
        EASTERN
    )


def _positive_float(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def maybe_capture_overnight_baseline(
    *,
    spx_price,
    now=None,
    directory=None,
):
    """
    Capture a synchronized SPX / ES baseline
    during the final two minutes of RTH.

    Observation only. Never submits orders.

    Repeated captures are intentional:
    the baseline store replaces the same-date
    file so the latest valid snapshot wins.
    """

    market_now = _eastern_now(
        now
    )

    clock = market_now.time().replace(
        tzinfo=None
    )

    if (
        market_now.weekday() >= 5
        or clock < CAPTURE_START
        or clock >= CAPTURE_END
    ):
        return {
            "captured": False,
            "reason_code":
                "BASELINE_CAPTURE_WINDOW_INACTIVE",
            "captured_at":
                market_now.isoformat(
                    timespec="seconds"
                ),
        }

    spx = _positive_float(
        spx_price
    )

    if spx is None:
        return {
            "captured": False,
            "reason_code":
                "SPX_CAPTURE_PRICE_UNAVAILABLE",
        }

    contract = broker.get_active_future(
        "ES"
    )

    if not contract:
        return {
            "captured": False,
            "reason_code":
                "ACTIVE_ES_CONTRACT_UNAVAILABLE",
            "broker_error":
                broker.last_error,
        }

    symbol = str(
        contract.get("symbol")
        or ""
    ).strip()

    if not symbol:
        return {
            "captured": False,
            "reason_code":
                "ACTIVE_ES_SYMBOL_UNAVAILABLE",
        }

    quote = broker.get_future_quote(
        symbol
    )

    if not quote:
        return {
            "captured": False,
            "reason_code":
                "ES_CAPTURE_QUOTE_UNAVAILABLE",
            "es_symbol": symbol,
            "broker_error":
                broker.last_error,
        }

    es_price, price_source = (
        select_future_reference_price(
            quote
        )
    )

    if es_price is None:
        return {
            "captured": False,
            "reason_code":
                "ES_CAPTURE_PRICE_UNAVAILABLE",
            "es_symbol": symbol,
        }

    baseline = save_overnight_baseline(
        spx_close=spx,
        es_anchor_price=es_price,
        es_symbol=symbol,
        captured_at=market_now,
        directory=directory,
    )

    return {
        "captured": True,
        "reason_code":
            "OVERNIGHT_BASELINE_CAPTURED",
        "price_source":
            price_source,
        "baseline": baseline,
    }
