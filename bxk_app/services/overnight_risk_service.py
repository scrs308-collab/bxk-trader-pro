from datetime import datetime

from bxk_app.brokers.tastytrade import broker
from bxk_app.overnight_reference import (
    calculate_overnight_spx_reference,
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


def get_live_overnight_risk(
    *,
    prior_spx_close,
    es_anchor_price=None,
):
    """
    Build one live observation-only overnight
    SPX iron-condor risk assessment.

    This service:
      - discovers the active ES future
      - retrieves its live quote
      - estimates the overnight SPX level
      - retrieves the current open SPX condor
      - evaluates overnight position risk

    It does NOT submit or modify orders.
    """

    close = _safe_float(
        prior_spx_close
    )

    if close is None or close <= 0:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "PRIOR_SPX_CLOSE_UNAVAILABLE",
        }

    session = get_spx_gth_session()

    if not session.get("active", False):
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "INACTIVE",
            "recommendation": "NONE",
            "reason_code":
                "SPX_GTH_INACTIVE",
            "session": session,
        }

    active_contract = (
        broker.get_active_future("ES")
    )

    if not active_contract:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "ACTIVE_ES_CONTRACT_UNAVAILABLE",
            "broker_error":
                broker.last_error,
        }

    es_symbol = active_contract.get(
        "symbol"
    )

    if not es_symbol:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "ACTIVE_ES_SYMBOL_UNAVAILABLE",
        }

    es_quote = broker.get_future_quote(
        es_symbol
    )

    if not es_quote:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "ES_QUOTE_UNAVAILABLE",
            "es_symbol": es_symbol,
            "broker_error":
                broker.last_error,
        }

    reference = (
        calculate_overnight_spx_reference(
            prior_spx_close=close,
            es_quote=es_quote,
            es_anchor_price=es_anchor_price,
        )
    )

    if not reference.get(
        "available"
    ):
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "OVERNIGHT_REFERENCE_UNAVAILABLE",
            "reference": reference,
        }

    monitor = get_position_monitor()

    positions = (
        monitor.get("positions")
        if isinstance(monitor, dict)
        else None
    ) or []

    if not positions:
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "NO_POSITION",
            "reason_code":
                "NO_OPEN_SPX_CONDOR",
            "reference": reference,
        }

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
            long_put=fields[
                "long_put"
            ],
            short_put=fields[
                "short_put"
            ],
            short_call=fields[
                "short_call"
            ],
            long_call=fields[
                "long_call"
            ],
            quantity=fields[
                "quantity"
            ],
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
        return {
            "available": False,
            "observation_only": True,
            "execution_authorized": False,
            "state": "UNAVAILABLE",
            "reason_code":
                "SUPPORTED_POSITION_UNAVAILABLE",
            "reference": reference,
        }

    state_rank = {
        "GREEN": 0,
        "YELLOW": 1,
        "ORANGE": 2,
        "RED": 3,
        "CRITICAL": 4,
    }

    worst = max(
        results,
        key=lambda item: (
            state_rank.get(
                item["risk"].get(
                    "state"
                ),
                -1,
            )
        ),
    )

    return {
        "available": True,
        "observation_only": True,
        "execution_authorized": False,

        "state": worst[
            "risk"
        ].get(
            "state"
        ),

        "recommendation": worst[
            "risk"
        ].get(
            "recommendation"
        ),

        "reason_code": worst[
            "risk"
        ].get(
            "reason_code"
        ),

        "session": session,

        "reference": reference,

        "position_count":
            len(results),

        "positions": results,

        "es_contract": {
            "symbol": es_symbol,
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
        },
    }
