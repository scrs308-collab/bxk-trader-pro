import copy
import hashlib
import json
import secrets
import threading
import time
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from bxk_app.authorization import (
    require_owner_or_auth_disabled,
)
from bxk_app.brokers.tastytrade import broker
from bxk_app.config import (
    BXK_LIVE_TRADING_ENABLED,
    BXK_MIN_ORDER_CREDIT,
    BXK_MIN_REMAINING_BUYING_POWER,
    BXK_MAX_ORDER_RISK,
)
from bxk_app.routes.scanner import get_best_trade
from bxk_app.services.execution_audit import (
    write_order_audit,
)
from bxk_app.services.order_builder import build_order

def _write_execution_audit(
    event,
    **details,
):
    try:
        write_order_audit(
            event,
            **details,
        )
    except (
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        return str(exc)

    return None

router = APIRouter(
    prefix="/api",
    tags=["Orders"],
)


_MAX_ORDER_DTE = 10
_ORDER_REVIEW_TTL_SECONDS = 180
_ORDER_REVIEW_LOCKS = {}
_ORDER_REVIEW_LOCKS_GUARD = threading.Lock()
_ORDER_SUBMISSION_RESERVATIONS = {}
_ORDER_SUBMISSION_RESERVATIONS_GUARD = threading.Lock()
_ORDER_SUBMISSION_RESERVATION_SECONDS = 60


def _order_fingerprint(order: dict) -> str:
    """Create a stable, non-sensitive identity for an order."""

    material = {
        "strategy": order.get("strategy"),
        "symbol": order.get("symbol"),
        "expiration": order.get("expiration"),
        "quantity": order.get("quantity"),
        "limit_price": order.get("limit_price"),
        "legs": [
            {
                "action": leg.get("action"),
                "symbol": leg.get("symbol"),
                "quantity": leg.get("quantity"),
            }
            for leg in (order.get("legs") or [])
        ],
    }
    serialized = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def _reserve_order_submission(order: dict) -> bool:
    now = time.monotonic()
    fingerprint = _order_fingerprint(order)

    with _ORDER_SUBMISSION_RESERVATIONS_GUARD:
        expired = [
            key
            for key, expires_at
            in _ORDER_SUBMISSION_RESERVATIONS.items()
            if now >= expires_at
        ]
        for key in expired:
            _ORDER_SUBMISSION_RESERVATIONS.pop(
                key,
                None,
            )

        if fingerprint in _ORDER_SUBMISSION_RESERVATIONS:
            return False

        _ORDER_SUBMISSION_RESERVATIONS[fingerprint] = (
            now + _ORDER_SUBMISSION_RESERVATION_SECONDS
        )
        return True


def _release_order_submission(order: dict):
    with _ORDER_SUBMISSION_RESERVATIONS_GUARD:
        _ORDER_SUBMISSION_RESERVATIONS.pop(
            _order_fingerprint(order),
            None,
        )


def _order_reconciliation(order: dict) -> dict:
    status = str(order.get("status") or "").strip()

    return {
        "order_id": order.get("id"),
        "broker_status": status or None,
        "filled_quantity": order.get(
            "filled-quantity"
        ),
        "remaining_quantity": order.get(
            "remaining-quantity"
        ),
        "average_fill_price": (
            order.get("average-fill-price")
            or order.get("average-price")
            or order.get("fill-price")
        ),
        "updated_at": (
            order.get("updated-at")
            or order.get("received-at")
        ),
        "terminal": status.upper() in {
            "FILLED",
            "CANCELLED",
            "CANCELED",
            "REJECTED",
            "REMOVED",
            "EXPIRED",
        },
    }


def _review_lock_error(
    reason_code: str,
    message: str,
):
    return {
        "status": "BLOCKED",
        "reason_code": reason_code,
        "live_submission_enabled": False,
        "message": message,
        "errors": [message],
        "checks": [],
    }


def _prune_order_review_locks_locked(
    now: float,
):
    expired = [
        review_id
        for review_id, review
        in _ORDER_REVIEW_LOCKS.items()
        if (
            now
            >= review.get(
                "expires_at_monotonic",
                0.0,
            )
        )
    ]

    for review_id in expired:
        _ORDER_REVIEW_LOCKS.pop(
            review_id,
            None,
        )


def _create_order_review_lock(
    *,
    trade: dict,
    order: dict,
    strategy: str,
    dte: int,
    wing_width: int,
    contracts: int,
):
    review_id = secrets.token_urlsafe(24)
    now = time.monotonic()

    review = {
        "review_id": review_id,
        "created_at": datetime.now().isoformat(),
        "expires_at_monotonic": (
            now
            + _ORDER_REVIEW_TTL_SECONDS
        ),
        "consumed": False,
        "request": {
            "strategy": strategy,
            "dte": int(dte),
            "wing_width": int(wing_width),
            "contracts": int(contracts),
        },
        "trade": copy.deepcopy(trade),
        "order": copy.deepcopy(order),
    }

    with _ORDER_REVIEW_LOCKS_GUARD:
        _prune_order_review_locks_locked(
            now,
        )

        _ORDER_REVIEW_LOCKS[
            review_id
        ] = review

    return review_id


def _get_order_review_lock(
    review_id,
):
    if not review_id:
        return (
            None,
            _review_lock_error(
                "REVIEW_LOCK_REQUIRED",
                (
                    "A BXK order review lock "
                    "is required."
                ),
            ),
        )

    key = str(review_id).strip()

    if not key:
        return (
            None,
            _review_lock_error(
                "REVIEW_LOCK_REQUIRED",
                (
                    "A BXK order review lock "
                    "is required."
                ),
            ),
        )

    now = time.monotonic()

    with _ORDER_REVIEW_LOCKS_GUARD:
        review = _ORDER_REVIEW_LOCKS.get(
            key,
        )

        if review is None:
            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_NOT_FOUND",
                    (
                        "BXK order review lock "
                        "was not found."
                    ),
                ),
            )

        if review.get("consumed"):
            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_CONSUMED",
                    (
                        "BXK order review lock "
                        "has already been consumed."
                    ),
                ),
            )

        if (
            now
            >= review.get(
                "expires_at_monotonic",
                0.0,
            )
        ):
            _ORDER_REVIEW_LOCKS.pop(
                key,
                None,
            )

            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_EXPIRED",
                    (
                        "BXK order review lock "
                        "expired. Build a fresh "
                        "trade review."
                    ),
                ),
            )

        return (
            copy.deepcopy(review),
            None,
        )


def _consume_order_review_lock(
    review_id,
):
    if not review_id:
        return (
            None,
            _review_lock_error(
                "REVIEW_LOCK_REQUIRED",
                (
                    "A BXK order review lock "
                    "is required."
                ),
            ),
        )

    key = str(review_id).strip()
    now = time.monotonic()

    with _ORDER_REVIEW_LOCKS_GUARD:
        review = _ORDER_REVIEW_LOCKS.get(
            key,
        )

        if review is None:
            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_NOT_FOUND",
                    (
                        "BXK order review lock "
                        "was not found."
                    ),
                ),
            )

        if review.get("consumed"):
            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_CONSUMED",
                    (
                        "BXK order review lock "
                        "has already been consumed."
                    ),
                ),
            )

        if (
            now
            >= review.get(
                "expires_at_monotonic",
                0.0,
            )
        ):
            _ORDER_REVIEW_LOCKS.pop(
                key,
                None,
            )

            return (
                None,
                _review_lock_error(
                    "REVIEW_LOCK_EXPIRED",
                    (
                        "BXK order review lock "
                        "expired. Build a fresh "
                        "trade review."
                    ),
                ),
            )

        review["consumed"] = True
        review["consumed_at"] = (
            datetime.now().isoformat()
        )

        return (
            copy.deepcopy(review),
            None,
        )


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_order(
    order: dict,
    *,
    requested_dte: int,
    requested_wing_width: int,
    requested_contracts: int,
):
    errors = []
    checks = []

    def check(
        name,
        passed,
        success_message,
        failure_message,
    ):
        passed = bool(passed)

        message = (
            success_message
            if passed
            else failure_message
        )

        checks.append({
            "name": name,
            "passed": passed,
            "message": message,
        })

        if not passed:
            errors.append(failure_message)

    legs = order.get("legs") or []
    quantity = order.get("quantity")
    expiration = order.get("expiration")

    try:
        actual_dte = int(order.get("dte"))
    except (TypeError, ValueError):
        actual_dte = -1

    credit = _number(order.get("limit_price"))
    max_risk = _number(order.get("max_risk"))

    strategy_key = (
        str(order.get("strategy") or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    is_iron_condor = (
        "iron_condor" in strategy_key
    )

    is_bull_put = (
        "bull_put" in strategy_key
        or "put_credit_spread" in strategy_key
    )

    is_bear_call = (
        "bear_call" in strategy_key
        or "call_credit_spread" in strategy_key
    )

    supported_strategy = (
        is_iron_condor
        or is_bull_put
        or is_bear_call
    )

    check(
        "strategy",
        supported_strategy,
        (
            "Strategy verified as an approved "
            "defined-risk credit structure."
        ),
        (
            "Strategy must be an Iron Condor, "
            "Bull Put Credit Spread, or "
            "Bear Call Credit Spread."
        ),
    )

    check(
        "underlying",
        str(order.get("symbol", "")).upper()
        in {"SPX", "SPXW"},
        "Underlying verified as SPX/SPXW.",
        "Underlying must be SPX or SPXW.",
    )

    check(
        "quantity",
        quantity == requested_contracts
        and 1 <= requested_contracts <= 10,
        "Contract quantity verified.",
        "Contract quantity is invalid or changed.",
    )

    expected_leg_count = (
        4 if is_iron_condor else 2
    )

    check(
        "leg_count",
        (
            supported_strategy
            and len(legs) == expected_leg_count
        ),
        (
            f"{expected_leg_count}-leg "
            "strategy structure verified."
        ),
        (
            "Order contains an invalid number "
            "of option legs for the strategy."
        ),
    )

    expected_legs = []

    if is_iron_condor:
        expected_legs = [
            ("SELL", "PUT"),
            ("BUY", "PUT"),
            ("SELL", "CALL"),
            ("BUY", "CALL"),
        ]

    elif is_bull_put:
        expected_legs = [
            ("SELL", "PUT"),
            ("BUY", "PUT"),
        ]

    elif is_bear_call:
        expected_legs = [
            ("SELL", "CALL"),
            ("BUY", "CALL"),
        ]

    structure_length_valid = (
        supported_strategy
        and len(legs) == len(expected_legs)
    )

    if structure_length_valid:
        directions_valid = all(
            (
                str(
                    leg.get("action", "")
                ).upper()
                == action
            )
            and (
                str(
                    leg.get(
                        "option_type",
                        "",
                    )
                ).upper()
                == option_type
            )
            for leg, (action, option_type)
            in zip(
                legs,
                expected_legs,
            )
        )

        symbols_present = all(
            bool(leg.get("symbol"))
            for leg in legs
        )

        strikes = [
            _number(
                leg.get("strike"),
                -1,
            )
            for leg in legs
        ]

        if is_iron_condor:
            strike_order_valid = (
                strikes[0] > strikes[1] > 0
                and strikes[3] > strikes[2] > 0
                and strikes[0] < strikes[2]
            )

            put_width = (
                strikes[0]
                - strikes[1]
            )

            call_width = (
                strikes[3]
                - strikes[2]
            )

            width_valid = (
                put_width
                == requested_wing_width
                and call_width
                == requested_wing_width
            )

        elif is_bull_put:
            strike_order_valid = (
                strikes[0]
                > strikes[1]
                > 0
            )

            spread_width = (
                strikes[0]
                - strikes[1]
            )

            width_valid = (
                spread_width
                == requested_wing_width
            )

        elif is_bear_call:
            strike_order_valid = (
                strikes[1]
                > strikes[0]
                > 0
            )

            spread_width = (
                strikes[1]
                - strikes[0]
            )

            width_valid = (
                spread_width
                == requested_wing_width
            )

        else:
            strike_order_valid = False
            width_valid = False

    else:
        directions_valid = False
        symbols_present = False
        strike_order_valid = False
        width_valid = False

    check(
        "leg_directions",
        directions_valid,
        (
            "Option leg directions and "
            "types verified."
        ),
        (
            "Option leg directions or "
            "types are invalid."
        ),
    )

    check(
        "option_symbols",
        symbols_present,
        "All option symbols are present.",
        (
            "One or more option symbols "
            "are missing."
        ),
    )

    check(
        "strike_order",
        strike_order_valid,
        (
            "Strategy strike order verified."
        ),
        (
            "Strategy strikes are not "
            "ordered correctly."
        ),
    )

    check(
        "wing_width",
        width_valid,
        (
            "Spread width matches "
            "the request."
        ),
        (
            "Actual spread width does "
            "not match the request."
        ),
    )

    expiration_valid = False

    if expiration:
        try:
            expiration_date = datetime.strptime(
                str(expiration)[:10],
                "%Y-%m-%d",
            ).date()

            expiration_valid = (
                expiration_date >= date.today()
            )
        except ValueError:
            expiration_valid = False

    check(
        "expiration",
        expiration_valid,
        "Expiration is valid and not expired.",
        "Expiration is missing, invalid, or already passed.",
    )

    check(
        "dte",
        0 <= requested_dte <= _MAX_ORDER_DTE,
        "Requested DTE is within the approved range.",
        "Requested DTE is outside the approved range.",
    )

    check(
        "dte_match",
        actual_dte == requested_dte,
        (
            "Actual order DTE matches "
            "the requested DTE."
        ),
        (
            "Actual order DTE does not match "
            "the requested DTE."
        ),
    )

    check(
        "limit_credit",
        credit > 0,
        "Limit credit is greater than zero.",
        "Limit credit must be greater than zero.",
    )

    check(
        "minimum_credit",
        credit >= BXK_MIN_ORDER_CREDIT,
        (
            "Limit credit meets the "
            f"${BXK_MIN_ORDER_CREDIT:,.2f} BXK minimum."
        ),
        (
            f"Limit credit ${credit:,.2f} is below "
            f"the ${BXK_MIN_ORDER_CREDIT:,.2f} BXK minimum."
        ),
    )
    check(
        "maximum_risk",
        max_risk > 0,
        "Maximum risk is greater than zero.",
        "Maximum risk must be greater than zero.",
    )

    check(
        "maximum_risk_limit",
        (
            max_risk > 0
            and max_risk <= BXK_MAX_ORDER_RISK
        ),
        (
            "Maximum risk is within the "
            f"${BXK_MAX_ORDER_RISK:,.2f} BXK limit."
        ),
        (
            f"Maximum risk ${max_risk:,.2f} exceeds "
            f"the ${BXK_MAX_ORDER_RISK:,.2f} BXK limit."
        ),
    )
    check(
        "order_type",
        order.get("order_type") == "LIMIT",
        "Limit order type verified.",
        "Only limit orders are permitted.",
    )

    check(
        "time_in_force",
        order.get("time_in_force") == "DAY",
        "DAY time-in-force verified.",
        "Only DAY orders are permitted.",
    )

    return checks, errors


def _build_current_order(
    strategy: str,
    dte: int,
    wing_width: int,
    contracts: int,
):
    result = get_best_trade(
        strategy=strategy,
        dte=dte,
        wing_width=wing_width,
        contracts=contracts,
    )

    trade = result.get("best_trade")

    if not trade:
        return None, None

    order = build_order(
        trade,
        quantity=contracts,
    )

    return trade, order


@router.get("/order-preview")
def order_preview(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=_MAX_ORDER_DTE),
    wing_width: int = Query(25),
    contracts: int = Query(1, ge=1, le=10),
):
    """
    Build a broker-independent preview from the current best trade.
    This endpoint cannot submit an order.
    """

    trade, order = _build_current_order(
        strategy,
        dte,
        wing_width,
        contracts,
    )

    if not trade:
        return {
            "status": "NO_TRADE",
            "message": "No approved trade available.",
        }

    review_id = _create_order_review_lock(
        trade=trade,
        order=order,
        strategy=strategy,
        dte=dte,
        wing_width=wing_width,
        contracts=contracts,
    )

    return {
        "status": "READY",
        "review_id": review_id,
        "review_expires_in_seconds": (
            _ORDER_REVIEW_TTL_SECONDS
        ),
        "live_submission_enabled": (
            BXK_LIVE_TRADING_ENABLED
        ),
        "trading_mode": (
            "LIVE"
            if BXK_LIVE_TRADING_ENABLED
            else "TEST"
        ),
        "trade": trade,
        "order": order,
    }


@router.get(
    "/order-validate",
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)
def order_validate(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=_MAX_ORDER_DTE),
    wing_width: int = Query(25),
    contracts: int = Query(1, ge=1, le=10),
):
    """
    Rebuild and validate the proposed order server-side.

    SAFETY: This endpoint cannot submit an order.
    """

    trade, order = _build_current_order(
        strategy,
        dte,
        wing_width,
        contracts,
    )

    if not trade:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "errors": [
                "No approved trade is currently available."
            ],
            "checks": [],
        }

    checks, errors = _validate_order(
        order,
        requested_dte=dte,
        requested_wing_width=wing_width,
        requested_contracts=contracts,
    )

    authenticated = broker.authenticate()

    account_number = (
        broker.get_first_account_number()
        if authenticated
        else None
    )

    checks.append({
        "name": "broker_authentication",
        "passed": authenticated,
        "message": (
            "Tastytrade authentication confirmed."
            if authenticated
            else broker.last_error
            or "Tastytrade authentication failed."
        ),
    })

    checks.append({
        "name": "account_verification",
        "passed": bool(account_number),
        "message": (
            "Tastytrade account verified."
            if account_number
            else broker.last_error
            or "No Tastytrade account was available."
        ),
    })

    if not authenticated:
        errors.append(
            broker.last_error
            or "Tastytrade authentication failed."
        )

    if not account_number:
        errors.append(
            broker.last_error
            or "No Tastytrade account was available."
        )

    masked_account = None

    if account_number:
        account_text = str(account_number)

        masked_account = (
            f"***{account_text[-4:]}"
            if len(account_text) >= 4
            else "***"
        )

    return {
        "status": (
            "VALIDATED"
            if not errors
            else "BLOCKED"
        ),
        "live_submission_enabled": False,
        "message": (
            "Order passed validation. Live submission remains disabled."
            if not errors
            else "Order validation failed."
        ),
        "account": masked_account,
        "errors": errors,
        "checks": checks,
        "trade": trade,
        "order": order,
    }


def _check_existing_position_overlap(
    order: dict,
    positions: list[dict],
):
    """
    Fail closed when a proposed BXK opening leg uses
    an option symbol already held in the account.

    This prevents Tastytrade from changing an intended
    opening action into a closing action.
    """

    proposed_legs = order.get("legs") or []

    proposed_symbols = {
        str(leg.get("symbol") or "").strip(): leg
        for leg in proposed_legs
        if str(leg.get("symbol") or "").strip()
    }

    overlaps = []

    for position in positions or []:
        symbol = str(
            position.get("symbol") or ""
        ).strip()

        if not symbol:
            continue

        if symbol not in proposed_symbols:
            continue

        try:
            quantity = float(
                position.get("quantity") or 0
            )
        except (TypeError, ValueError):
            quantity = 0.0

        if quantity <= 0:
            continue

        intended_leg = proposed_symbols[symbol]

        overlaps.append({
            "symbol": symbol,
            "existing_direction": position.get(
                "quantity-direction"
            ),
            "existing_quantity": quantity,
            "proposed_action": intended_leg.get(
                "action"
            ),
            "option_type": intended_leg.get(
                "option_type"
            ),
            "strike": intended_leg.get(
                "strike"
            ),
            "expires_at": position.get(
                "expires-at"
            ),
        })

    return {
        "passed": len(overlaps) == 0,
        "overlaps": overlaps,
        "message": (
            "No proposed option legs overlap "
            "existing account positions."
            if not overlaps
            else (
                "One or more proposed option legs "
                "already exist in the account."
            )
        ),
    }


_TERMINAL_ORDER_STATUSES = {
    "CANCELLED",
    "CANCELED",
    "FILLED",
    "REJECTED",
    "REMOVED",
    "EXPIRED",
}


def _check_existing_order_overlap(
    order: dict,
    live_orders: list[dict],
):
    proposed_symbols = {
        str(
            leg.get("symbol") or ""
        ).strip()
        for leg in (
            order.get("legs") or []
        )
        if str(
            leg.get("symbol") or ""
        ).strip()
    }

    overlaps = []

    for existing_order in live_orders or []:
        status = str(
            existing_order.get("status") or ""
        ).strip()

        if (
            status.upper()
            in _TERMINAL_ORDER_STATUSES
        ):
            continue

        for leg in (
            existing_order.get("legs") or []
        ):
            symbol = str(
                leg.get("symbol") or ""
            ).strip()

            if (
                not symbol
                or symbol not in proposed_symbols
            ):
                continue

            try:
                remaining_quantity = float(
                    leg.get(
                        "remaining-quantity",
                        leg.get("quantity", 0),
                    )
                    or 0
                )
            except (TypeError, ValueError):
                remaining_quantity = 0.0

            overlaps.append({
                "order_id":
                    existing_order.get("id"),
                "status": status or None,
                "cancellable":
                    existing_order.get(
                        "cancellable"
                    ),
                "symbol": symbol,
                "action": leg.get("action"),
                "remaining_quantity":
                    remaining_quantity,
            })

    return {
        "passed": len(overlaps) == 0,
        "overlaps": overlaps,
        "message": (
            "No proposed option legs overlap "
            "existing working orders."
            if not overlaps
            else (
                "One or more proposed option legs "
                "already exist in a working order."
            )
        ),
    }

def _evaluate_broker_dry_run(
    dry_run: dict,
    order: dict,
):
    """
    Fail-closed evaluation of Tastytrade dry-run response.
    """

    checks = []
    errors = []

    success_messages = {
        "broker_response":
            "Tastytrade broker response received.",
        "broker_order_status":
            "Tastytrade dry-run status verified as Received.",
        "broker_warning_free":
            "Tastytrade returned no broker warnings.",
        "broker_leg_count":
            "Broker leg count matches the BXK order.",
        "broker_legs_match":
            "All broker legs exactly match the BXK order.",
        "broker_limit_price":
            "Broker limit price matches the BXK order.",
        "broker_order_type":
            "Broker order type verified as Limit.",
        "broker_time_in_force":
            "Broker time in force verified as Day.",
        "broker_price_effect":
            "Broker price effect verified as Credit.",
        "broker_buying_power":
            "Broker buying-power information is valid.",
        "broker_buying_power_reconciled":
            "Broker buying-power impact reconciles exactly.",
        "broker_buying_power_matches_bxk":
            "Broker buying-power impact matches BXK risk plus fees.",
        "broker_fees":
            "Broker fee calculation is valid.",
    }

    def check(
        name,
        passed,
        message,
        *,
        success_message=None,
        advisory=False,
    ):
        passed = bool(passed)

        if passed:
            display_message = (
                success_message
                or success_messages.get(
                    name,
                    "Broker check passed.",
                )
            )
        else:
            display_message = message

        result = {
            "name": name,
            "passed": passed,
            "message": display_message,
        }

        if advisory:
            result["advisory"] = True

        checks.append(result)

        if not passed:
            errors.append(message)

    broker_response = (
        dry_run.get("broker_response") or {}
    )

    data = broker_response.get("data") or {}

    broker_order = data.get("order") or {}

    warnings = data.get("warnings") or []

    buying_power = (
        data.get("buying-power-effect") or {}
    )

    fees = (
        data.get("fee-calculation") or {}
    )

    payload = dry_run.get("payload") or {}

    expected_legs = payload.get("legs") or []
    broker_legs = broker_order.get("legs") or []

    check(
        "broker_response",
        bool(data),
        "Tastytrade did not return broker order data.",
    )

    check(
        "broker_order_status",
        broker_order.get("status") == "Received",
        (
            "Tastytrade dry-run order status "
            "was not Received."
        ),
    )

    approved_warning_codes = {
        "tif.next_valid_session",
    }

    advisory_warnings = []
    blocking_warnings = []

    for warning in warnings:
        warning_code = ""

        if isinstance(warning, dict):
            warning_code = str(
                warning.get("code") or ""
            ).strip()

        if warning_code in approved_warning_codes:
            advisory_warnings.append(warning)
        else:
            blocking_warnings.append(warning)

    if blocking_warnings:
        blocking_codes = [
            (
                str(
                    warning.get("code")
                    or "<missing code>"
                )
                if isinstance(warning, dict)
                else "<invalid warning>"
            )
            for warning in blocking_warnings
        ]

        warning_failure_message = (
            "Tastytrade returned one or more "
            "unapproved broker warnings: "
            + ", ".join(blocking_codes)
            + "."
        )
    else:
        warning_failure_message = (
            "Tastytrade returned an "
            "unapproved broker warning."
        )

    if advisory_warnings:
        warning_success_message = (
            "Tastytrade dry-run accepted with "
            "approved next-session advisory."
        )
    else:
        warning_success_message = (
            "Tastytrade returned no broker warnings."
        )

    check(
        "broker_warning_free",
        len(blocking_warnings) == 0,
        warning_failure_message,
        success_message=warning_success_message,
        advisory=bool(advisory_warnings),
    )

    check(
        "broker_leg_count",
        len(broker_legs) == len(expected_legs),
        (
            "Tastytrade broker leg count does "
            "not match the BXK order."
        ),
    )

    legs_match = (
        len(broker_legs) == len(expected_legs)
    )

    if legs_match:
        for expected, actual in zip(
            expected_legs,
            broker_legs,
        ):
            if (
                expected.get("symbol")
                != actual.get("symbol")
                or expected.get("action")
                != actual.get("action")
                or int(expected.get("quantity") or 0)
                != int(actual.get("quantity") or 0)
                or expected.get("instrument-type")
                != actual.get("instrument-type")
            ):
                legs_match = False
                break

    check(
        "broker_legs_match",
        legs_match,
        (
            "Tastytrade dry-run legs do not "
            "exactly match the BXK order."
        ),
    )

    try:
        expected_price = round(
            float(payload.get("price")),
            2,
        )

        broker_price = round(
            float(broker_order.get("price")),
            2,
        )

        price_match = (
            expected_price == broker_price
        )
    except (TypeError, ValueError):
        price_match = False

    check(
        "broker_limit_price",
        price_match,
        (
            "Tastytrade dry-run limit price "
            "does not match the BXK order."
        ),
    )

    check(
        "broker_order_type",
        broker_order.get("order-type") == "Limit",
        (
            "Tastytrade dry-run order type "
            "is not Limit."
        ),
    )

    check(
        "broker_time_in_force",
        broker_order.get("time-in-force") == "Day",
        (
            "Tastytrade dry-run time in force "
            "is not Day."
        ),
    )

    check(
        "broker_price_effect",
        broker_order.get("price-effect") == "Credit",
        (
            "Tastytrade dry-run is not "
            "a credit order."
        ),
    )

    try:
        current_bp = float(
            buying_power.get(
                "current-buying-power"
            )
        )

        bp_impact = float(
            buying_power.get(
                "change-in-buying-power"
            )
        )

        new_bp = float(
            buying_power.get(
                "new-buying-power"
            )
        )

        buying_power_valid = (
            current_bp > 0
            and bp_impact > 0
            and new_bp >= 0
            and new_bp < current_bp
        )

    except (TypeError, ValueError):
        current_bp = 0.0
        bp_impact = 0.0
        new_bp = 0.0
        buying_power_valid = False

    check(
        "broker_buying_power",
        buying_power_valid,
        (
            "Tastytrade returned invalid "
            "buying-power information."
        ),
    )

    buying_power_reserve_valid = (
        buying_power_valid
        and new_bp
        >= BXK_MIN_REMAINING_BUYING_POWER
    )

    check(
        "broker_buying_power_reserve",
        buying_power_reserve_valid,
        (
            f"Remaining buying power ${new_bp:,.2f} "
            "is below the "
            f"${BXK_MIN_REMAINING_BUYING_POWER:,.2f} "
            "BXK reserve."
        ),
    )
    buying_power_reconciled = (
        buying_power_valid
        and abs(
            (current_bp - new_bp)
            - bp_impact
        ) <= 0.01
    )

    check(
        "broker_buying_power_reconciled",
        buying_power_reconciled,
        (
            "Tastytrade buying-power impact "
            "does not reconcile with current "
            "and new buying power."
        ),
    )

    fee_value = fees.get("total-fees")

    try:
        total_fees = float(fee_value)

        fees_valid = (
            bool(fees)
            and fee_value is not None
            and total_fees >= 0
        )

    except (TypeError, ValueError):
        total_fees = 0.0
        fees_valid = False

    check(
        "broker_fees",
        fees_valid,
        (
            "Tastytrade returned invalid "
            "fee-calculation information."
        ),
    )

    try:
        bxk_buying_power = float(
            order.get("buying_power")
        )
    except (TypeError, ValueError):
        bxk_buying_power = 0.0

    expected_broker_impact = round(
        bxk_buying_power
        + total_fees,
        2,
    )

    broker_bp_variance = round(
        bp_impact
        - expected_broker_impact,
        2,
    )

    buying_power_matches_bxk = (
        buying_power_valid
        and fees_valid
        and bxk_buying_power > 0
        and abs(broker_bp_variance) <= 0.05
    )

    check(
        "broker_buying_power_matches_bxk",
        buying_power_matches_bxk,
        (
            "Tastytrade buying-power impact does not "
            "match BXK expected risk plus broker fees. "
            f"BXK expected ${expected_broker_impact:.2f}; "
            f"Tastytrade returned ${bp_impact:.2f}."
        ),
    )

    return {
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "buying_power": {
            "current": round(current_bp, 2),
            "impact": round(bp_impact, 2),
            "remaining": round(new_bp, 2),
            "bxk_expected": round(
                bxk_buying_power,
                2,
            ),
            "expected_with_fees": round(
                expected_broker_impact,
                2,
            ),
            "variance": round(
                broker_bp_variance,
                2,
            ),
        },
        "fees": round(total_fees, 2),
        "warnings": warnings,
    }


def _execution_session_gate() -> dict:
    """
    Fail closed unless the current BXK DAY-order path
    is valid for the active SPX trading session.

    GTH and CURB are recognized as open sessions, but
    BXK does not yet build the extended-session order
    type required for those sessions.
    """

    from bxk_app.trading_session import (
        get_spx_execution_policy,
    )

    policy = get_spx_execution_policy()

    session = str(
        policy.get("session") or "CLOSED"
    ).upper()

    if policy.get("day_order_allowed"):
        return {
            "passed": True,
            "reason_code": None,
            "message": (
                "SPX Regular Trading Hours verified. "
                "BXK DAY-order execution is allowed."
            ),
            "policy": policy,
        }

    if session == "GTH":
        reason_code = (
            "EXTENDED_SESSION_REQUIRES_GTH_ORDER"
        )
        message = (
            "SPX is in Global Trading Hours. "
            "BXK DAY-order execution is disabled "
            "during this session."
        )

    elif session == "CURB":
        reason_code = (
            "EXTENDED_SESSION_REQUIRES_CURB_ORDER"
        )
        message = (
            "SPX is in Curb Trading Hours. "
            "BXK DAY-order execution is disabled "
            "during this session."
        )

    else:
        reason_code = "MARKET_SESSION_CLOSED"
        message = (
            "SPX is outside an executable BXK "
            "trading session."
        )

    return {
        "passed": False,
        "reason_code": reason_code,
        "message": message,
        "policy": policy,
    }


@router.post(
    "/order-dry-run",
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)
def order_dry_run(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=_MAX_ORDER_DTE),
    wing_width: int = Query(25),
    contracts: int = Query(1, ge=1, le=10),
    review_id: str | None = Query(None),
):
    """
    Run the current BXK order through Tastytrade broker preflight.

    SAFETY:
    This endpoint cannot submit a live order.
    """

    session_gate = _execution_session_gate()

    if session_gate["passed"]:
        session_check_message = (
            session_gate["message"]
        )
    else:
        session_check_message = (
            "Dry-run/preflight only. "
            "Live DAY-order submission remains blocked. "
            + session_gate["message"]
        )

    review, review_error = (
        _get_order_review_lock(
            review_id,
        )
    )

    if review_error:
        return review_error

    trade = review["trade"]
    order = review["order"]

    review_request = (
        review.get("request") or {}
    )

    checks, errors = _validate_order(
        order,
        requested_dte=int(
            review_request.get("dte", -1)
        ),
        requested_wing_width=int(
            review_request.get(
                "wing_width",
                -1,
            )
        ),
        requested_contracts=int(
            review_request.get(
                "contracts",
                -1,
            )
        ),
    )

    checks.insert(
        0,
        {
            "name": "execution_session",
            "passed": True,
            "advisory": (
                not session_gate["passed"]
            ),
            "reason_code": (
                session_gate["reason_code"]
            ),
            "message": session_check_message,
        },
    )

    if errors:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "BXK internal validation failed."
            ),
            "errors": errors,
            "checks": checks,
            "trade": trade,
            "order": order,
        }

    authenticated = broker.authenticate()

    if not authenticated:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "Tastytrade authentication failed."
            ),
            "errors": [
                broker.last_error
                or "Tastytrade authentication failed."
            ],
            "checks": checks,
        }

    account_number = (
        broker.get_first_account_number()
    )

    if not account_number:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "Tastytrade account verification failed."
            ),
            "errors": [
                broker.last_error
                or "No Tastytrade account available."
            ],
            "checks": checks,
        }

    positions = broker.get_positions(
        account_number=account_number,
    )

    if broker.last_error:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "BXK could not verify existing "
                "Tastytrade positions."
            ),
            "errors": [
                broker.last_error
                or "Position verification failed."
            ],
            "checks": checks,
            "trade": trade,
            "order": order,
        }

    position_overlap = (
        _check_existing_position_overlap(
            order,
            positions,
        )
    )

    checks.append({
        "name": "existing_position_overlap",
        "passed": position_overlap["passed"],
        "message": position_overlap["message"],
    })

    if not position_overlap["passed"]:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "Proposed BXK order overlaps an "
                "existing Tastytrade position."
            ),
            "errors": [
                (
                    "Existing option position "
                    "conflicts with a proposed "
                    "opening leg."
                )
            ],
            "checks": checks,
            "position_overlap": position_overlap,
            "trade": trade,
            "order": order,
        }

    dry_run = broker.dry_run_order(
        order,
        account_number=account_number,
    )

    if dry_run is None:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "Tastytrade dry-run failed."
            ),
            "errors": [
                broker.last_error
                or "Tastytrade dry-run failed."
            ],
            "checks": checks,
            "trade": trade,
            "order": order,
        }

    broker_preflight = (
        _evaluate_broker_dry_run(
            dry_run,
            order,
        )
    )

    account_text = str(account_number)

    masked_account = (
        f"***{account_text[-4:]}"
        if len(account_text) >= 4
        else "***"
    )

    if not broker_preflight["passed"]:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": False,
            "message": (
                "Tastytrade broker preflight "
                "did not pass."
            ),
            "account": masked_account,
            "errors": (
                broker_preflight["errors"]
            ),
            "checks": checks,
            "broker_checks": (
                broker_preflight["checks"]
            ),
            "broker_preflight": broker_preflight,
            "trade": trade,
            "order": order,
            "dry_run": dry_run,
        }

    audit_error = _write_execution_audit(
        "PREFLIGHT_PASSED",
        status="BROKER_PREFLIGHT_PASSED",
        review_id=review["review_id"],
        account=account_number,
        order=order,
    )

    if audit_error:
        return {
            "status": "BLOCKED",
            "reason_code":
                "AUDIT_WRITE_FAILED",
            "live_submission_enabled": False,
            "message": (
                "BXK broker preflight passed, "
                "but the required execution audit "
                "record could not be created."
            ),
            "errors": [
                (
                    "Execution audit is unavailable. "
                    "No live submission is permitted."
                )
            ],
            "checks": checks,
            "broker_checks":
                broker_preflight["checks"],
            "broker_preflight":
                broker_preflight,
            "trade": trade,
            "order": order,
        }

    return {
        "status": "BROKER_PREFLIGHT_PASSED",
        "review_id": review["review_id"],
        "live_submission_enabled": False,
        "message": (
            "BXK validation and Tastytrade "
            "broker preflight passed. "
            "Live submission remains disabled."
        ),
        "account": masked_account,
        "errors": [],
        "checks": checks,
        "broker_checks": (
            broker_preflight["checks"]
        ),
        "broker_preflight": broker_preflight,
        "trade": trade,
        "order": order,
        "dry_run": dry_run,
    }

@router.get(
    "/order-status",
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)
def order_status(
    order_id: str = Query(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9-]+$",
    ),
):
    """Independently reconcile one Tastytrade order."""

    account_number = broker.get_first_account_number()

    if not account_number:
        return {
            "status": "RECONCILIATION_FAILED",
            "message": (
                "Tastytrade account verification failed."
            ),
            "errors": [
                broker.last_error
                or "No Tastytrade account available."
            ],
        }

    broker_order = broker.get_order(
        order_id,
        account_number=account_number,
    )

    if broker_order is None:
        return {
            "status": "RECONCILIATION_PENDING",
            "order_id": order_id,
            "message": (
                "Tastytrade has not returned the order "
                "for independent verification yet."
            ),
            "errors": [
                broker.last_error
                or "Order reconciliation failed."
            ],
        }

    broker_order_id = str(
        broker_order.get("id") or ""
    ).strip()

    if broker_order_id != str(order_id).strip():
        return {
            "status": "RECONCILIATION_FAILED",
            "order_id": order_id,
            "message": (
                "Tastytrade returned a different order ID."
            ),
            "errors": ["Broker order ID mismatch."],
        }

    return {
        "status": "RECONCILED",
        "message": (
            "Order independently verified with Tastytrade."
        ),
        **_order_reconciliation(broker_order),
    }


@router.post(
    "/order-submit",
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)
def order_submit(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=_MAX_ORDER_DTE),
    wing_width: int = Query(25),
    contracts: int = Query(1, ge=1, le=10),
    confirm_live: bool = Query(False),
    review_id: str | None = Query(None),
):
    """
    Submit the current approved BXK order to Tastytrade.

    SAFETY:
    Requires explicit confirmation and the BXK
    live-trading master switch to be enabled.
    """

    if not confirm_live:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": BXK_LIVE_TRADING_ENABLED,
            "message": (
                "Explicit live-trade confirmation "
                "is required."
            ),
            "errors": [
                "confirm_live must be true."
            ],
        }

    preflight = order_dry_run(
        strategy=strategy,
        dte=dte,
        wing_width=wing_width,
        contracts=contracts,
        review_id=review_id,
    )

    if preflight.get("status") != "BROKER_PREFLIGHT_PASSED":
        return preflight

    if not BXK_LIVE_TRADING_ENABLED:
        audit_error = _write_execution_audit(
            "SUBMISSION_BLOCKED",
            status="LIVE_TRADING_DISABLED",
            reason_code=
                "LIVE_TRADING_DISABLED",
            review_id=review_id,
            account=preflight.get("account"),
            order=preflight.get("order"),
        )

        return {
            "audit_recorded":
                audit_error is None,
            "status": "LIVE_TRADING_DISABLED",
            "live_submission_enabled": False,
            "message": (
                "BXK validation and Tastytrade "
                "broker preflight passed, but "
                "live trading is disabled."
            ),
            "errors": [
                "BXK live trading is disabled."
            ],
            "checks": preflight.get("checks", []),
            "broker_checks": preflight.get(
                "broker_checks", []
            ),
            "broker_preflight": preflight.get(
                "broker_preflight"
            ),
            "trade": preflight.get("trade"),
            "order": preflight.get("order"),
        }

    account_number = broker.get_first_account_number()

    if not account_number:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": True,
            "message": (
                "Tastytrade account verification "
                "failed before submission."
            ),
            "errors": [
                broker.last_error
                or "No Tastytrade account available."
            ],
        }

    positions = broker.get_positions(
        account_number=account_number,
    )

    if broker.last_error:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": True,
            "message": (
                "BXK could not verify existing "
                "positions immediately before "
                "submission."
            ),
            "errors": [
                broker.last_error
                or "Position verification failed."
            ],
        }

    order = preflight.get("order") or {}

    position_overlap = _check_existing_position_overlap(
        order,
        positions,
    )

    if not position_overlap["passed"]:
        return {
            "status": "BLOCKED",
            "live_submission_enabled": True,
            "message": (
                "Proposed BXK order now overlaps "
                "an existing Tastytrade position."
            ),
            "errors": [
                (
                    "Account positions changed "
                    "after broker preflight."
                )
            ],
            "position_overlap": position_overlap,
            "trade": preflight.get("trade"),
            "order": order,
        }

    live_orders = broker.get_live_orders(
        account_number=account_number,
    )

    if broker.last_error:
        return {
            "status": "BLOCKED",
            "reason_code":
                "WORKING_ORDER_VERIFICATION_FAILED",
            "live_submission_enabled": False,
            "message": (
                "BXK could not verify working "
                "orders immediately before "
                "submission."
            ),
            "errors": [
                broker.last_error
                or (
                    "Working-order verification "
                    "failed."
                )
            ],
            "trade": preflight.get("trade"),
            "order": order,
        }

    working_order_overlap = (
        _check_existing_order_overlap(
            order,
            live_orders,
        )
    )

    if not working_order_overlap["passed"]:
        return {
            "status": "BLOCKED",
            "reason_code":
                "WORKING_ORDER_OVERLAP",
            "live_submission_enabled": False,
            "message": (
                "Proposed BXK order now overlaps "
                "an existing Tastytrade working "
                "order."
            ),
            "errors": [
                (
                    "Broker working orders changed "
                    "after preflight."
                )
            ],
            "working_order_overlap":
                working_order_overlap,
            "trade": preflight.get("trade"),
            "order": order,
        }

    submission_session_gate = (
        _execution_session_gate()
    )

    if not submission_session_gate["passed"]:
        policy = submission_session_gate[
            "policy"
        ]

        return {
            "status": "BLOCKED",
            "reason_code": (
                submission_session_gate[
                    "reason_code"
                ]
            ),
            "live_submission_enabled": (
                BXK_LIVE_TRADING_ENABLED
            ),
            "session": policy.get("session"),
            "market_time": (
                policy.get("market_time")
            ),
            "session_policy": policy,
            "message": (
                "Trading session changed before "
                "live submission. "
                + submission_session_gate[
                    "message"
                ]
            ),
            "errors": [
                submission_session_gate[
                    "message"
                ]
            ],
            "trade": preflight.get("trade"),
            "order": order,
        }

    consumed_review, consume_error = (
        _consume_order_review_lock(
            review_id,
        )
    )

    if consume_error:
        consume_error[
            "live_submission_enabled"
        ] = BXK_LIVE_TRADING_ENABLED

        return consume_error

    locked_order = (
        consumed_review.get("order") or {}
    )

    if locked_order != order:
        return {
            "status": "BLOCKED",
            "reason_code":
                "REVIEW_LOCK_ORDER_MISMATCH",
            "live_submission_enabled":
                BXK_LIVE_TRADING_ENABLED,
            "message": (
                "BXK review-lock order no longer "
                "matches the broker-preflight order."
            ),
            "errors": [
                (
                    "Frozen order changed between "
                    "preflight and submission."
                )
            ],
            "trade": (
                consumed_review.get("trade")
            ),
            "order": locked_order,
        }

    order = locked_order

    if not _reserve_order_submission(order):
        return {
            "status": "BLOCKED",
            "reason_code":
                "DUPLICATE_SUBMISSION_IN_PROGRESS",
            "live_submission_enabled": False,
            "message": (
                "An identical order was submitted or is "
                "still being reconciled. Do not retry."
            ),
            "errors": [
                "Duplicate order reservation is active."
            ],
            "trade": preflight.get("trade"),
            "order": order,
        }

    audit_error = _write_execution_audit(
        "SUBMISSION_ATTEMPT",
        status="PENDING",
        review_id=review_id,
        account=account_number,
        order=order,
    )

    if audit_error:
        _release_order_submission(order)
        return {
            "status": "BLOCKED",
            "reason_code":
                "AUDIT_WRITE_FAILED",
            "live_submission_enabled": False,
            "message": (
                "BXK could not create the "
                "required execution audit record. "
                "No broker submission was attempted."
            ),
            "errors": [
                (
                    "Execution audit is unavailable. "
                    "Build a fresh review after the "
                    "audit problem is corrected."
                )
            ],
            "trade": preflight.get("trade"),
            "order": order,
        }

    live_order = broker.submit_live_order(
        order,
        account_number=account_number,
    )

    if live_order is None:
        audit_error = _write_execution_audit(
            "SUBMISSION_UNCONFIRMED",
            status="SUBMISSION_UNCONFIRMED",
            reason_code=
                "BROKER_SUBMISSION_NO_RESPONSE",
            review_id=review_id,
            account=account_number,
            order=order,
        )

        return {
            "status":
                "SUBMISSION_UNCONFIRMED",
            "reason_code":
                "BROKER_SUBMISSION_NO_RESPONSE",
            "live_submission_enabled": False,
            "submission_uncertain": True,
            "audit_recorded":
                audit_error is None,
            "message": (
                "Tastytrade did not return a "
                "confirmed live-order response. "
                "Do not retry automatically. "
                "Verify the broker account first."
            ),
            "errors": [
                broker.last_error
                or (
                    "No confirmed broker response "
                    "was received."
                )
            ],
            "trade": preflight.get("trade"),
            "order": order,
        }

    broker_response = (
        live_order.get("broker_response") or {}
    )
    data = broker_response.get("data") or {}
    submitted_order = data.get("order") or {}

    order_id = submitted_order.get("id")
    broker_status = str(
        submitted_order.get("status") or ""
    ).strip()

    accepted_statuses = {
        "RECEIVED",
        "ROUTED",
        "IN FLIGHT",
        "LIVE",
        "PARTIALLY FILLED",
        "FILLED",
        "PENDING",
    }

    submission_confirmed = (
        bool(order_id)
        and broker_status.upper()
        in accepted_statuses
    )

    if not submission_confirmed:
        audit_error = _write_execution_audit(
            "SUBMISSION_UNCONFIRMED",
            status="SUBMISSION_UNCONFIRMED",
            reason_code=
                "BROKER_SUBMISSION_UNCONFIRMED",
            review_id=review_id,
            account=account_number,
            order_id=order_id,
            broker_status=
                broker_status or None,
            order=order,
        )

        return {
            "audit_recorded":
                audit_error is None,
            "status":
                "SUBMISSION_UNCONFIRMED",
            "reason_code":
                "BROKER_SUBMISSION_UNCONFIRMED",
            "live_submission_enabled": False,
            "submission_uncertain": True,
            "message": (
                "Tastytrade did not return a "
                "confirmed live-order result. "
                "Do not retry automatically. "
                "Verify the broker account first."
            ),
            "errors": [
                (
                    "Missing broker order ID or "
                    "unrecognized broker status."
                )
            ],
            "broker_status":
                broker_status or None,
            "broker_order": submitted_order,
            "trade": preflight.get("trade"),
            "order": order,
        }

    audit_error = _write_execution_audit(
        "SUBMITTED",
        status="SUBMITTED",
        review_id=review_id,
        account=account_number,
        order_id=order_id,
        broker_status=broker_status,
        order=order,
    )

    submission_message = (
        (
            "BXK live order was submitted "
            "to Tastytrade."
        )
        if audit_error is None
        else (
            "BXK live order was submitted "
            "to Tastytrade, but the local "
            "execution audit could not be written. "
            "Verify the broker account."
        )
    )

    account_text = str(account_number)
    masked_account = (
        f"***{account_text[-4:]}"
        if len(account_text) >= 4
        else "***"
    )

    reconciled_order = broker.get_order(
        order_id,
        account_number=account_number,
    )
    reconciliation_error = broker.last_error
    reconciliation = (
        {
            "status": "RECONCILED",
            **_order_reconciliation(
                reconciled_order
            ),
        }
        if (
            isinstance(reconciled_order, dict)
            and str(reconciled_order.get("id") or "")
            == str(order_id)
        )
        else {
            "status": "RECONCILIATION_PENDING",
            "order_id": order_id,
            "error": reconciliation_error,
        }
    )

    return {
        "status": "SUBMITTED",
        "live_submission_enabled": True,
        "message": submission_message,
        "audit_recorded":
            audit_error is None,
        "account": masked_account,
        "order_id": submitted_order.get("id"),
        "broker_status": submitted_order.get(
            "status"
        ),
        "reconciliation": reconciliation,
        "trade": preflight.get("trade"),
        "order": order,
        "broker_order": submitted_order,
    }
