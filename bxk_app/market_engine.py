import logging
from datetime import date
from functools import wraps
from math import sqrt
from threading import RLock

from bxk_app.condor_stability import (
    calculate_condor_stability_metrics,
)
from bxk_app.condor_stability_score import (
    calculate_condor_stability_score,
)
from bxk_app.condor_risk_profile import (
    build_condor_risk_profile,
)
from bxk_app.market_session import (
    get_market_session_phase,
)
from bxk_app.range_expansion_pressure import (
    calculate_range_expansion_pressure,
)
from bxk_app.market_data import market_data
from bxk_app.brokers.tastytrade import broker
from bxk_app.services.condor_stability_logger import (
    log_condor_stability,
)


from bxk_app.services.overnight_baseline_service import (
    maybe_capture_overnight_baseline,
)

logger = logging.getLogger(__name__)

_market_update_lock = RLock()


def _serialized_market_update(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with _market_update_lock:
            return func(*args, **kwargs)

    return wrapper


def calculate_expected_move(spx_price: float, vix1d_value: float) -> float:
    """
    Estimate the one-trading-day SPX expected move using VIX1D.

    Formula:
        SPX × (VIX1D / 100) ÷ sqrt(252)
    """
    if spx_price <= 0 or vix1d_value <= 0:
        return 0.0

    return round(
        spx_price * (vix1d_value / 100) / sqrt(252),
        2,
    )

def get_quote_price(quote):
    """
    Safely extract a price from a Tastytrade quote.
    """

    if not quote:
        return 0.0

    value = (
        quote.get("last")
        or quote.get("last_price")
        or quote.get("mark")
        or quote.get("mid")
        or 0
    )

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
    
class MarketEngine:

    @_serialized_market_update
    def update(
        self,
        spx=None,
        vix=None,
        vix1d=None,
        account=None,
        positions=None,
        qqq=None,
        include_account_context=True,
    ):
        """
        Fetch live Tastytrade data when values are not supplied,
        then update the shared market-data cache.
        """

        broker.authenticate()

        if spx is None:
            spx = broker.get_quote("SPX")

        if vix is None:
            vix = broker.get_quote("VIX")

        if vix1d is None:
            vix1d = broker.get_quote("$VIX1D")

        if qqq is None:
            qqq = broker.get_quote("QQQ")

        if include_account_context:
            if account is None:
                account = broker.get_account_summary()

            if positions is None:
                positions = broker.get_position_summary()

        spx_price = get_quote_price(spx)
        vix_value = get_quote_price(vix)
        vix1d_value = get_quote_price(vix1d)

        if vix1d_value > 0:
            volatility_value = vix1d_value
            expected_move_source = "VIX1D"
        elif vix_value > 0:
            volatility_value = vix_value
            expected_move_source = "VIX"
        else:
            volatility_value = 0.0
            expected_move_source = "NONE"

        expected_move = calculate_expected_move(spx_price, volatility_value)

        spx_quote = spx if isinstance(spx, dict) else {}

        condor_stability = calculate_condor_stability_metrics(
            spx_price=spx_price,
            expected_move=expected_move,
            session_open=spx_quote.get("open"),
            day_high=spx_quote.get("day-high-price"),
            day_low=spx_quote.get("day-low-price"),
            prev_close=spx_quote.get("prev-close"),
            expected_move_source=expected_move_source,
            market_status=market_data.market_status(),
        )

        session = get_market_session_phase()

        expansion_pressure = (
            calculate_range_expansion_pressure(
                directional_consumed_pct=
                    condor_stability.get(
                        "directional_consumed_pct"
                    ),
                minutes_since_open=
                    session["minutes_since_open"],
                session_phase=
                    session["session_phase"],
                signal_ready=
                    condor_stability.get(
                        "signal_ready",
                        False,
                    ),
            )
        )

        condor_stability[
            "session_phase"
        ] = session["session_phase"]

        condor_stability[
            "minutes_since_open"
        ] = session["minutes_since_open"]

        condor_stability[
            "range_expansion_pressure"
        ] = expansion_pressure

        stability_score = (
            calculate_condor_stability_score(
                signal_ready=
                    condor_stability.get(
                        "signal_ready",
                        False,
                    ),
                directional_consumed_pct=
                    condor_stability.get(
                        "directional_consumed_pct"
                    ),
                current_displacement_pct=
                    condor_stability.get(
                        "current_displacement_pct"
                    ),
                range_band_consumed_pct=
                    condor_stability.get(
                        "range_band_consumed_pct"
                    ),
                overnight_gap_pct=
                    condor_stability.get(
                        "overnight_gap_pct"
                    ),
                pressure_ratio=
                    expansion_pressure.get(
                        "pressure_ratio"
                    ),
            )
        )

        condor_stability[
            "stability_score"
        ] = stability_score

        condor_risk_profile = build_condor_risk_profile(
            current_implied_move=expected_move,
            exclude_date=date.today().isoformat(),
        )

        market_data.update(
            spx=spx_price,
            vix=vix_value,
            vix1d=vix1d_value,
            expected_move=expected_move,
            condor_stability=condor_stability,
            condor_risk_profile=condor_risk_profile,
        )

        if include_account_context:
            market_data.account = account or {}
            market_data.positions = positions or []

        market_data.qqq = qqq or {}

        # Observation logging must never interfere with
        # market analysis or trade decisions.
        try:
            log_condor_stability(market_data)
        except Exception:
            logger.exception(
                "Condor Stability logging failed"
            )

        # Capture a synchronized SPX / ES overnight
        # baseline near the regular-session close.
        #
        # Observation only. Failure here must never
        # interfere with market analysis or trading.
        try:
            maybe_capture_overnight_baseline(
                spx_price=spx_price,
            )
        except Exception:
            logger.exception(
                "Overnight baseline capture failed"
            )

        # Record the official next regular-session SPX
        # open for overnight carry-learning rows.
        #
        # This is observational only and deliberately
        # isolated from market analysis and execution.
        try:
            if (
                session.get(
                    "minutes_since_open"
                )
                is not None
            ):
                spx_session_open = (
                    spx_quote.get("open")
                )

                if spx_session_open:
                    from bxk_app.services.trade_journal_service import (
                        record_next_open_outcomes,
                    )

                    record_next_open_outcomes(
                        spx_open=spx_session_open,
                        trading_date=(
                            date.today().isoformat()
                        ),
                    )
        except Exception:
            logger.exception(
                "Next-open journal learning failed"
            )

        return market_data.get_header(
            include_account_context=(
                include_account_context
            )
        )


market_engine = MarketEngine()
