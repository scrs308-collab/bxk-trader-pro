from datetime import datetime

from bxk_app.brokers.tastytrade import broker
from bxk_app.overnight_baseline import (
    load_overnight_baseline,
)
from bxk_app.overnight_reference import (
    calculate_overnight_spx_reference,
    evaluate_future_quote_health,
)
from bxk_app.overnight_risk import (
    calculate_overnight_risk,
)
from bxk_app.overnight_session import (
    get_spx_gth_session,
)
from bxk_app.services.position_service import (
    get_position_monitor,
)


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_position_fields(position):
    """
    Convert the existing position-summary payload
    into Overnight Risk Guard inputs.
    """

    if not isinstance(position, dict):
        return None

    required = {
        "long_put": position.get("buy_put"),
        "short_put": position.get("sell_put"),
        "short_call": position.get("sell_call"),
        "long_call": position.get("buy_call"),
        "quantity": position.get("quantity"),
        "opening_credit": position.get(
            "opening_credit"
        ),
        "dte": position.get("dte"),
    }

    if any(
        value is None
        for key, value in required.items()
        if key != "dte"
    ):
        return None

    return required


def _unavailable(
    reason_code,
    *,
    state="UNAVAILABLE",
    **extra,
):
    payload = {
        "available": False,
        "observation_only": True,
        "execution_authorized": False,
        "state": state,
        "reason_code": reason_code,
    }

    payload.update(extra)

    return payload


def get_live_overnight_risk(
    *,
    prior_spx_close=None,
    es_anchor_price=None,
):
    """
    Build one live observation-only overnight
    SPX iron-condor risk assessment.

    Normal operation automatically loads the
    synchronized RTH-close SPX / ES baseline.

    Manual prior_spx_close and es_anchor_price
    remain available for diagnostics.

    This service does NOT submit, modify,
    authorize, or cancel orders.
    """

    # -------------------------------------------------
    # Session gate first.
    #
    # Outside GTH there is no reason to require,
    # load, or validate an overnight baseline.
    # -------------------------------------------------

    session = get_spx_gth_session()

    if not session.get("active", False):
        return _unavailable(
            "SPX_GTH_INACTIVE",
            state="INACTIVE",
            recommendation="NONE",
            session=session,
        )

    # -------------------------------------------------
    # Resolve baseline/reference inputs.
    # -------------------------------------------------

    manual_close = _safe_float(
        prior_spx_close
    )

    baseline = None
    baseline_source = "MANUAL"

    close = manual_close
    anchor = _safe_float(
        es_anchor_price
    )

    es_symbol = None
    active_contract = None

    if close is None:
        baseline = load_overnight_baseline()

        if not baseline:
            return _unavailable(
                "OVERNIGHT_BASELINE_UNAVAILABLE",
                session=session,
            )

        close = _safe_float(
            baseline.get("spx_close")
        )

        anchor = _safe_float(
            baseline.get(
                "es_anchor_price"
            )
        )

        es_symbol = str(
            baseline.get("es_symbol")
            or ""
        ).strip()

        if (
            close is None
            or close <= 0
            or anchor is None
            or anchor <= 0
            or not es_symbol
        ):
            return _unavailable(
                "OVERNIGHT_BASELINE_INVALID",
                session=session,
                baseline=baseline,
            )

        baseline_source = "STORED"

    elif close <= 0:
        return _unavailable(
            "PRIOR_SPX_CLOSE_UNAVAILABLE",
            session=session,
        )

    # -------------------------------------------------
    # Stored baseline:
    #
    # Use the SAME ES contract captured at RTH close.
    # This protects the proxy from futures rollover.
    # -------------------------------------------------

    if baseline_source == "STORED":
        quote_symbol = es_symbol

    else:
        active_contract = (
            broker.get_active_future("ES")
        )

        if not active_contract:
            return _unavailable(
                "ACTIVE_ES_CONTRACT_UNAVAILABLE",
                session=session,
                broker_error=broker.last_error,
            )

        quote_symbol = str(
            active_contract.get("symbol")
            or ""
        ).strip()

        if not quote_symbol:
            return _unavailable(
                "ACTIVE_ES_SYMBOL_UNAVAILABLE",
                session=session,
            )

    # -------------------------------------------------
    # Retrieve current ES quote.
    # -------------------------------------------------

    es_quote = broker.get_future_quote(
        quote_symbol
    )

    if not es_quote:
        return _unavailable(
            "ES_QUOTE_UNAVAILABLE",
            session=session,
            baseline=baseline,
            es_symbol=quote_symbol,
            broker_error=broker.last_error,
        )

    returned_symbol = str(
        es_quote.get("symbol")
        or ""
    ).strip()

    if (
        returned_symbol
        and returned_symbol.upper()
        != quote_symbol.upper()
    ):
        return _unavailable(
            "ES_QUOTE_SYMBOL_MISMATCH",
            session=session,
            baseline=baseline,
            requested_symbol=quote_symbol,
            returned_symbol=returned_symbol,
        )

    # -------------------------------------------------
    # Quote health gate.
    #
    # Never calculate overnight risk from stale or
    # explicitly halted ES market data.
    # -------------------------------------------------

    quote_health = evaluate_future_quote_health(
        quote=es_quote,
    )

    if not quote_health.get(
        "healthy",
        False,
    ):
        return _unavailable(
            quote_health.get(
                "reason_code",
                "ES_QUOTE_UNHEALTHY",
            ),
            session=session,
            baseline=baseline,
            es_symbol=quote_symbol,
            quote_health=quote_health,
        )

    # -------------------------------------------------
    # Calculate overnight SPX proxy.
    # -------------------------------------------------

    reference = (
        calculate_overnight_spx_reference(
            prior_spx_close=close,
            es_quote=es_quote,
            es_anchor_price=anchor,
        )
    )

    if not reference.get("available"):
        return _unavailable(
            "OVERNIGHT_REFERENCE_UNAVAILABLE",
            session=session,
            baseline=baseline,
            reference=reference,
        )

    # -------------------------------------------------
    # Retrieve actual open SPX condor(s).
    # -------------------------------------------------

    monitor = get_position_monitor()

    positions = (
        monitor.get("positions")
        if isinstance(monitor, dict)
        else None
    ) or []

    if not positions:
        return _unavailable(
            "NO_OPEN_SPX_CONDOR",
            state="NO_POSITION",
            session=session,
            baseline=baseline,
            reference=reference,
        )

    results = []

    for position in positions:
        fields = _extract_position_fields(
            position
        )

        if fields is None:
            continue

        risk = calculate_overnight_risk(
            reference_price=(
                reference["estimated_spx"]
            ),
            prior_close=close,
            long_put=fields["long_put"],
            short_put=fields["short_put"],
            short_call=fields["short_call"],
            long_call=fields["long_call"],
            quantity=fields["quantity"],
            opening_credit=fields[
                "opening_credit"
            ],
            reference_source=(
                reference[
                    "reference_source"
                ]
            ),
            market_status="GTH",
            dte=fields["dte"],
            timestamp=datetime.now().isoformat(
                timespec="seconds"
            ),
        )

        results.append(
            {
                "position": position,
                "risk": risk,
            }
        )

    if not results:
        return _unavailable(
            "SUPPORTED_POSITION_UNAVAILABLE",
            session=session,
            baseline=baseline,
            reference=reference,
        )

    # -------------------------------------------------
    # Roll multiple positions into one headline state.
    # -------------------------------------------------

    state_rank = {
        "GREEN": 0,
        "YELLOW": 1,
        "ORANGE": 2,
        "RED": 3,
        "CRITICAL": 4,
    }

    worst = max(
        results,
        key=lambda item: state_rank.get(
            item["risk"].get("state"),
            -1,
        ),
    )

    contract_metadata = {
        "symbol": quote_symbol,
        "selection_source": (
            "BASELINE"
            if baseline_source == "STORED"
            else "ACTIVE_MONTH"
        ),
    }

    if active_contract:
        contract_metadata.update(
            {
                "streamer_symbol":
                    active_contract.get(
                        "streamer-symbol"
                    ),
                "expiration_date":
                    active_contract.get(
                        "expiration-date"
                    ),
                "active_month":
                    active_contract.get(
                        "active-month"
                    ),
            }
        )

    return {
        "available": True,
        "observation_only": True,
        "execution_authorized": False,

        "state": worst[
            "risk"
        ].get("state"),

        "recommendation": worst[
            "risk"
        ].get("recommendation"),

        "reason_code": worst[
            "risk"
        ].get("reason_code"),

        "session": session,

        "baseline_source":
            baseline_source,

        "baseline": baseline,

        "quote_health":
            quote_health,

        "reference": reference,

        "position_count":
            len(results),

        "positions": results,

        "es_contract":
            contract_metadata,
    }
