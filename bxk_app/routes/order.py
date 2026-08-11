from datetime import date, datetime

from fastapi import APIRouter, Query

from bxk_app.brokers.tastytrade import broker
from bxk_app.routes.scanner import get_best_trade
from bxk_app.services.order_builder import build_order


router = APIRouter(
    prefix="/api",
    tags=["Orders"],
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

    def check(name, passed, message):
        checks.append({
            "name": name,
            "passed": bool(passed),
            "message": message,
        })

        if not passed:
            errors.append(message)

    legs = order.get("legs") or []
    quantity = order.get("quantity")
    expiration = order.get("expiration")
    credit = _number(order.get("limit_price"))
    max_risk = _number(order.get("max_risk"))

    strategy_key = (
        str(order.get("strategy") or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    check(
        "strategy",
        "iron_condor" in strategy_key,
        "Strategy must be an iron condor.",
    )

    check(
        "underlying",
        str(order.get("symbol", "")).upper()
        in {"SPX", "SPXW"},
        "Underlying must be SPX or SPXW.",
    )

    check(
        "quantity",
        quantity == requested_contracts
        and 1 <= requested_contracts <= 10,
        "Contract quantity is invalid or changed.",
    )

    check(
        "leg_count",
        len(legs) == 4,
        "Iron condor must contain exactly four legs.",
    )

    expected_legs = [
        ("SELL", "PUT"),
        ("BUY", "PUT"),
        ("SELL", "CALL"),
        ("BUY", "CALL"),
    ]

    if len(legs) == 4:
        directions_valid = all(
            str(leg.get("action", "")).upper() == action
            and str(leg.get("option_type", "")).upper()
            == option_type
            for leg, (action, option_type)
            in zip(legs, expected_legs)
        )

        symbols_present = all(
            bool(leg.get("symbol"))
            for leg in legs
        )

        strikes = [
            _number(leg.get("strike"), -1)
            for leg in legs
        ]

        strike_order_valid = (
            strikes[0] > strikes[1] > 0
            and strikes[3] > strikes[2] > 0
            and strikes[0] < strikes[2]
        )

        put_width = strikes[0] - strikes[1]
        call_width = strikes[3] - strikes[2]

        width_valid = (
            put_width == requested_wing_width
            and call_width == requested_wing_width
        )
    else:
        directions_valid = False
        symbols_present = False
        strike_order_valid = False
        width_valid = False

    check(
        "leg_directions",
        directions_valid,
        "Option leg directions or types are invalid.",
    )

    check(
        "option_symbols",
        symbols_present,
        "One or more option symbols are missing.",
    )

    check(
        "strike_order",
        strike_order_valid,
        "Iron-condor strikes are not ordered correctly.",
    )

    check(
        "wing_width",
        width_valid,
        "Actual wing widths do not match the request.",
    )

    expiration_valid = False

    if expiration:
        try:
            expiration_date = datetime.strptime(
                str(expiration)[:10],
                "%Y-%m-%d",
            ).date()

            expiration_valid = expiration_date >= date.today()
        except ValueError:
            expiration_valid = False

    check(
        "expiration",
        expiration_valid,
        "Expiration is missing, invalid, or already passed.",
    )

    check(
        "dte",
        requested_dte in {0, 1, 2, 3},
        "Requested DTE is outside the approved range.",
    )

    check(
        "limit_credit",
        credit > 0,
        "Limit credit must be greater than zero.",
    )

    check(
        "maximum_risk",
        max_risk > 0,
        "Maximum risk must be greater than zero.",
    )

    check(
        "order_type",
        order.get("order_type") == "LIMIT",
        "Only limit orders are permitted.",
    )

    check(
        "time_in_force",
        order.get("time_in_force") == "DAY",
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
    dte: int = Query(1, ge=0, le=3),
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

    return {
        "status": "READY",
        "trade": trade,
        "order": order,
    }


@router.get("/order-validate")
def order_validate(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=3),
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


def _evaluate_broker_dry_run(
    dry_run: dict,
    order: dict,
):
    """
    Fail-closed evaluation of Tastytrade dry-run response.
    """

    checks = []
    errors = []

    def check(name, passed, message):
        checks.append({
            "name": name,
            "passed": bool(passed),
            "message": message,
        })

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

    check(
        "broker_warning_free",
        len(warnings) == 0,
        (
            "Tastytrade returned one or more "
            "broker warnings."
        ),
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

    try:
        total_fees = float(
            fees.get("total-fees") or 0
        )
    except (TypeError, ValueError):
        total_fees = 0.0

    return {
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "buying_power": {
            "current": round(current_bp, 2),
            "impact": round(bp_impact, 2),
            "remaining": round(new_bp, 2),
        },
        "fees": round(total_fees, 2),
        "warnings": warnings,
    }


@router.post("/order-dry-run")
def order_dry_run(
    strategy: str = Query("auto"),
    dte: int = Query(1, ge=0, le=3),
    wing_width: int = Query(25),
    contracts: int = Query(1, ge=1, le=10),
):
    """
    Run the current BXK order through Tastytrade broker preflight.

    SAFETY:
    This endpoint cannot submit a live order.
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
            "message": (
                "No approved BXK trade "
                "is currently available."
            ),
            "errors": [
                "No approved trade available."
            ],
        }

    checks, errors = _validate_order(
        order,
        requested_dte=dte,
        requested_wing_width=wing_width,
        requested_contracts=contracts,
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

    return {
        "status": "BROKER_PREFLIGHT_PASSED",
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