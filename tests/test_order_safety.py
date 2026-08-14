import bxk_app.routes.order as order_route


def ready_preflight():
    return {
        "status": "BROKER_PREFLIGHT_PASSED",
        "checks": [],
        "broker_checks": [],
        "broker_preflight": {
            "passed": True,
        },
        "trade": {
            "strategy": "SPX Iron Condor",
        },
        "order": {
            "strategy": "SPX Iron Condor",
            "symbol": "SPX",
            "quantity": 1,
            "legs": [],
        },
    }


def call_submit(
    confirm_live=True,
    review_id=None,
):
    return order_route.order_submit(
        strategy="iron_condor",
        dte=1,
        wing_width=25,
        contracts=1,
        confirm_live=confirm_live,
        review_id=review_id,
    )


def test_submit_requires_explicit_confirmation(
    monkeypatch,
):
    def should_not_run(**kwargs):
        raise AssertionError(
            "Preflight must not run without confirmation."
        )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        should_not_run,
    )

    result = call_submit(
        confirm_live=False,
    )

    assert result["status"] == "BLOCKED"
    assert (
        "confirm_live must be true."
        in result["errors"]
    )


def test_submit_stops_when_preflight_blocks(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: {
            "status": "BLOCKED",
            "message": "Preflight failed.",
            "errors": ["Preflight failed."],
        },
    )

    def should_not_submit(*args, **kwargs):
        raise AssertionError(
            "Live submission must not occur."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        should_not_submit,
    )

    result = call_submit()

    assert result["status"] == "BLOCKED"
    assert result["message"] == "Preflight failed."


def test_live_switch_off_blocks_submission(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        False,
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: ready_preflight(),
    )

    def should_not_submit(*args, **kwargs):
        raise AssertionError(
            "Live submission was called with "
            "the master switch OFF."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        should_not_submit,
    )

    result = call_submit()

    assert (
        result["status"]
        == "LIVE_TRADING_DISABLED"
    )
    assert (
        result["live_submission_enabled"]
        is False
    )


def test_account_failure_blocks_submission(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: ready_preflight(),
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: None,
    )

    order_route.broker.last_error = (
        "Account unavailable."
    )

    def should_not_submit(*args, **kwargs):
        raise AssertionError(
            "Live submission must not occur "
            "without an account."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        should_not_submit,
    )

    result = call_submit()

    assert result["status"] == "BLOCKED"
    assert (
        "account verification failed"
        in result["message"].lower()
    )


def test_position_lookup_failure_blocks_submission(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: ready_preflight(),
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST1234",
    )

    def failed_positions(
        account_number=None,
    ):
        order_route.broker.last_error = (
            "Position lookup failed."
        )
        return []

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        failed_positions,
    )

    def should_not_submit(*args, **kwargs):
        raise AssertionError(
            "Live submission must not occur "
            "after position lookup failure."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        should_not_submit,
    )

    result = call_submit()

    assert result["status"] == "BLOCKED"
    assert (
        "verify existing positions"
        in result["message"].lower()
    )


def test_position_overlap_blocks_submission(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: ready_preflight(),
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST1234",
    )

    def positions(
        account_number=None,
    ):
        order_route.broker.last_error = None
        return [
            {
                "symbol": "SPXW TEST",
            }
        ]

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        positions,
    )

    monkeypatch.setattr(
        order_route,
        "_check_existing_position_overlap",
        lambda order, positions: {
            "passed": False,
            "message": "Overlap detected.",
        },
    )

    def should_not_submit(*args, **kwargs):
        raise AssertionError(
            "Live submission must not occur "
            "when positions overlap."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        should_not_submit,
    )

    result = call_submit()

    assert result["status"] == "BLOCKED"
    assert (
        result["position_overlap"]["passed"]
        is False
    )


def test_success_path_uses_mocked_submission(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "_execution_session_gate",
        lambda: {
            "passed": True,
            "reason_code": None,
            "message": "RTH test session verified.",
            "policy": {
                "session": "RTH",
                "market_time":
                    "2026-08-12T10:00:00-04:00",
                "session_open": True,
                "day_order_allowed": True,
                "extended_order_required": False,
            },
        },
    )

    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    preflight = ready_preflight()

    review_id = (
        order_route._create_order_review_lock(
            trade=preflight["trade"],
            order=preflight["order"],
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: preflight,
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST1234",
    )

    def positions(
        account_number=None,
    ):
        order_route.broker.last_error = None
        return []

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        positions,
    )

    monkeypatch.setattr(
        order_route,
        "_check_existing_position_overlap",
        lambda order, positions: {
            "passed": True,
        },
    )

    submitted = {
        "called": False,
    }

    def fake_submit(
        order,
        account_number=None,
    ):
        submitted["called"] = True

        assert account_number == "TEST1234"

        return {
            "broker_response": {
                "data": {
                    "order": {
                        "id": "MOCK-ORDER-1",
                        "status": "Received",
                    }
                }
            }
        }

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        fake_submit,
    )

    result = call_submit(
        review_id=review_id,
    )

    assert submitted["called"] is True
    assert result["status"] == "SUBMITTED"
    assert result["order_id"] == "MOCK-ORDER-1"
    assert result["account"] == "***1234"

def _sample_overlap_order(action="BUY"):
    return {
        "legs": [
            {
                "symbol": "SPXW TEST OPTION",
                "action": action,
                "option_type": "CALL",
                "strike": 7825,
            }
        ]
    }


def _sample_position(direction):
    return {
        "symbol": "SPXW TEST OPTION",
        "quantity": "1",
        "quantity-direction": direction,
        "expires-at": "2026-08-13T20:00:00.000Z",
    }


def test_overlap_blocks_short_to_buy():
    result = (
        order_route._check_existing_position_overlap(
            _sample_overlap_order("BUY"),
            [_sample_position("Short")],
        )
    )

    assert result["passed"] is False
    assert len(result["overlaps"]) == 1


def test_overlap_blocks_long_to_sell():
    result = (
        order_route._check_existing_position_overlap(
            _sample_overlap_order("SELL"),
            [_sample_position("Long")],
        )
    )

    assert result["passed"] is False
    assert len(result["overlaps"]) == 1


def test_overlap_blocks_short_to_sell():
    result = (
        order_route._check_existing_position_overlap(
            _sample_overlap_order("SELL"),
            [_sample_position("Short")],
        )
    )

    assert result["passed"] is False
    assert len(result["overlaps"]) == 1


def test_overlap_blocks_long_to_buy():
    result = (
        order_route._check_existing_position_overlap(
            _sample_overlap_order("BUY"),
            [_sample_position("Long")],
        )
    )

    assert result["passed"] is False
    assert len(result["overlaps"]) == 1


def test_overlap_allows_different_symbol():
    result = (
        order_route._check_existing_position_overlap(
            _sample_overlap_order("BUY"),
            [
                {
                    "symbol": "SPXW DIFFERENT OPTION",
                    "quantity": "4",
                    "quantity-direction": "Short",
                }
            ],
        )
    )

    assert result["passed"] is True
    assert result["overlaps"] == []

def _valid_broker_dry_run():
    leg = {
        "symbol": "SPXW TEST OPTION",
        "action": "Sell to Open",
        "quantity": 1,
        "instrument-type": "Equity Option",
    }

    return {
        "payload": {
            "price": "1.75",
            "legs": [dict(leg)],
        },
        "broker_response": {
            "data": {
                "order": {
                    "status": "Received",
                    "price": "1.75",
                    "order-type": "Limit",
                    "time-in-force": "Day",
                    "price-effect": "Credit",
                    "legs": [dict(leg)],
                },
                "warnings": [],
                "buying-power-effect": {
                    "current-buying-power": "25000.00",
                    "change-in-buying-power": "831.88",
                    "new-buying-power": "24168.12",
                },
                "fee-calculation": {
                    "total-fees": "6.88",
                },
            }
        },
    }


def _broker_checks(result):
    return {
        item["name"]: item
        for item in result["checks"]
    }


def test_broker_preflight_accepts_valid_response():
    dry_run = _valid_broker_dry_run()

    data = dry_run["broker_response"]["data"]

    broker_impact = float(
        data["buying-power-effect"][
            "change-in-buying-power"
        ]
    )

    broker_fees = float(
        data["fee-calculation"]["total-fees"]
    )

    result = (
        order_route._evaluate_broker_dry_run(
            dry_run,
            {
                "buying_power": round(
                    broker_impact
                    - broker_fees,
                    2,
                ),
            },
        )
    )

    checks = _broker_checks(result)

    assert result["passed"] is True
    assert result["fees"] == 6.88

    assert (
        checks[
            "broker_buying_power_reconciled"
        ]["passed"]
        is True
    )

    assert (
        checks["broker_fees"]["passed"]
        is True
    )


def test_broker_warning_fails_preflight():
    dry_run = _valid_broker_dry_run()

    dry_run["broker_response"]["data"][
        "warnings"
    ] = [
        {
            "code": "tif.next_valid_session",
            "message": (
                "Your order will begin working "
                "during next valid session."
            ),
        }
    ]

    result = (
        order_route._evaluate_broker_dry_run(
            dry_run,
            {},
        )
    )

    checks = _broker_checks(result)

    assert result["passed"] is False

    assert (
        checks["broker_warning_free"]["passed"]
        is False
    )


def test_buying_power_mismatch_fails_preflight():
    dry_run = _valid_broker_dry_run()

    dry_run["broker_response"]["data"][
        "buying-power-effect"
    ]["new-buying-power"] = "9000.00"

    result = (
        order_route._evaluate_broker_dry_run(
            dry_run,
            {},
        )
    )

    checks = _broker_checks(result)

    assert result["passed"] is False

    assert (
        checks[
            "broker_buying_power_reconciled"
        ]["passed"]
        is False
    )


def test_invalid_fee_data_fails_preflight():
    dry_run = _valid_broker_dry_run()

    dry_run["broker_response"]["data"][
        "fee-calculation"
    ] = {}

    result = (
        order_route._evaluate_broker_dry_run(
            dry_run,
            {},
        )
    )

    checks = _broker_checks(result)

    assert result["passed"] is False

    assert (
        checks["broker_fees"]["passed"]
        is False
    )

def test_execution_session_gate_allows_rth(
    monkeypatch,
):
    from bxk_app import trading_session

    monkeypatch.setattr(
        trading_session,
        "get_spx_execution_policy",
        lambda: {
            "session": "RTH",
            "market_time":
                "2026-08-12T10:00:00-04:00",
            "session_open": True,
            "day_order_allowed": True,
            "extended_order_required": False,
        },
    )

    result = (
        order_route._execution_session_gate()
    )

    assert result["passed"] is True
    assert result["reason_code"] is None


def test_order_dry_run_blocks_gth_before_scan(
    monkeypatch,
):
    from bxk_app import trading_session

    monkeypatch.setattr(
        trading_session,
        "get_spx_execution_policy",
        lambda: {
            "session": "GTH",
            "market_time":
                "2026-08-12T22:00:00-04:00",
            "session_open": True,
            "day_order_allowed": False,
            "extended_order_required": True,
        },
    )

    def scanner_must_not_run(*args, **kwargs):
        raise AssertionError(
            "Scanner must not run when "
            "DAY execution is session-blocked."
        )

    monkeypatch.setattr(
        order_route,
        "_build_current_order",
        scanner_must_not_run,
    )

    result = order_route.order_dry_run(
        strategy="iron_condor",
        dte=1,
        wing_width=25,
        contracts=1,
    )

    assert result["status"] == "BLOCKED"

    assert (
        result["reason_code"]
        == "EXTENDED_SESSION_REQUIRES_GTH_ORDER"
    )

    assert result["session"] == "GTH"

    assert (
        result["checks"][0]["name"]
        == "execution_session"
    )

    assert (
        result["checks"][0]["passed"]
        is False
    )

def test_submit_blocks_if_session_changes_after_preflight(
    monkeypatch,
):
    """
    A successful RTH broker preflight must not authorize
    submission if the SPX session changes before the
    actual live-order call.
    """

    order = {
        "strategy": "SPX Iron Condor",
        "legs": [],
    }

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: {
            "status": "BROKER_PREFLIGHT_PASSED",
            "trade": {
                "strategy": "SPX Iron Condor",
            },
            "order": order,
            "checks": [],
            "broker_checks": [],
            "broker_preflight": {
                "passed": True,
            },
        },
    )

    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST1234",
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        lambda account_number=None: [],
    )

    monkeypatch.setattr(
        order_route.broker,
        "last_error",
        None,
    )

    monkeypatch.setattr(
        order_route,
        "_check_existing_position_overlap",
        lambda order, positions: {
            "passed": True,
            "message": (
                "No existing position overlap."
            ),
            "overlaps": [],
        },
    )

    monkeypatch.setattr(
        order_route,
        "_execution_session_gate",
        lambda: {
            "passed": False,
            "reason_code":
                "EXTENDED_SESSION_REQUIRES_GTH_ORDER",
            "message": (
                "SPX is in Global Trading Hours. "
                "BXK DAY-order execution is disabled "
                "during this session."
            ),
            "policy": {
                "session": "GTH",
                "market_time":
                    "2026-08-12T20:15:01-04:00",
                "session_open": True,
                "day_order_allowed": False,
                "extended_order_required": True,
            },
        },
    )

    submitted = {
        "called": False,
    }

    def must_not_submit(
        order,
        account_number=None,
    ):
        submitted["called"] = True
        raise AssertionError(
            "Live broker submission must not occur "
            "after the session changes."
        )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        must_not_submit,
    )

    result = order_route.order_submit(
        strategy="iron_condor",
        dte=1,
        wing_width=25,
        contracts=1,
        confirm_live=True,
    )

    assert result["status"] == "BLOCKED"

    assert (
        result["reason_code"]
        == "EXTENDED_SESSION_REQUIRES_GTH_ORDER"
    )

    assert result["session"] == "GTH"

    assert (
        "Trading session changed"
        in result["message"]
    )

    assert submitted["called"] is False


def test_broker_buying_power_matches_bxk_risk_and_fees():
    dry_run = _valid_broker_dry_run()

    data = dry_run["broker_response"]["data"]

    broker_impact = float(
        data["buying-power-effect"][
            "change-in-buying-power"
        ]
    )

    broker_fees = float(
        data["fee-calculation"]["total-fees"]
    )

    bxk_buying_power = round(
        broker_impact - broker_fees,
        2,
    )

    result = order_route._evaluate_broker_dry_run(
        dry_run,
        {
            "buying_power": bxk_buying_power,
        },
    )

    checks = _broker_checks(result)

    assert (
        checks[
            "broker_buying_power_matches_bxk"
        ]["passed"]
        is True
    )


def test_broker_buying_power_difference_fails_preflight():
    dry_run = _valid_broker_dry_run()

    data = dry_run["broker_response"]["data"]

    broker_impact = float(
        data["buying-power-effect"][
            "change-in-buying-power"
        ]
    )

    broker_fees = float(
        data["fee-calculation"]["total-fees"]
    )

    bxk_buying_power = round(
        broker_impact - broker_fees,
        2,
    )

    result = order_route._evaluate_broker_dry_run(
        dry_run,
        {
            "buying_power":
                bxk_buying_power - 100.00,
        },
    )

    checks = _broker_checks(result)

    assert result["passed"] is False

    assert (
        checks[
            "broker_buying_power_matches_bxk"
        ]["passed"]
        is False
    )


def test_review_lock_preserves_exact_order_snapshot():
    trade = {
        "strategy": "SPX Iron Condor",
    }

    order = {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "quantity": 1,
        "limit_price": 3.32,
        "max_risk": 2168.00,
        "buying_power": 2168.00,
        "legs": [
            {
                "action": "SELL_TO_OPEN",
                "symbol": "LOCKED-LEG-1",
            },
        ],
    }

    review_id = (
        order_route._create_order_review_lock(
            trade=trade,
            order=order,
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    # Deliberately mutate the originals after locking.
    # The server-side snapshot must not change.
    order["limit_price"] = 1.00
    order["legs"][0]["symbol"] = "MUTATED"
    trade["strategy"] = "MUTATED"

    review, error = (
        order_route._get_order_review_lock(
            review_id,
        )
    )

    assert error is None
    assert review is not None

    assert (
        review["order"]["limit_price"]
        == 3.32
    )

    assert (
        review["order"]["legs"][0]["symbol"]
        == "LOCKED-LEG-1"
    )

    assert (
        review["trade"]["strategy"]
        == "SPX Iron Condor"
    )


def test_order_dry_run_uses_frozen_review_order(
    monkeypatch,
):
    frozen_order = {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "quantity": 1,
        "limit_price": 3.32,
        "max_risk": 2168.00,
        "buying_power": 2168.00,
        "legs": [
            {
                "action": "SELL_TO_OPEN",
                "symbol": "FROZEN-SPX-OPTION",
            },
        ],
    }

    review_id = (
        order_route._create_order_review_lock(
            trade={
                "strategy": "SPX Iron Condor",
            },
            order=frozen_order,
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    def scanner_must_not_run(*args, **kwargs):
        raise AssertionError(
            "Scanner rebuilt a reviewed order."
        )

    monkeypatch.setattr(
        order_route,
        "_build_current_order",
        scanner_must_not_run,
    )

    monkeypatch.setattr(
        order_route,
        "_execution_session_gate",
        lambda: {
            "passed": True,
            "reason_code": None,
            "message": "RTH execution permitted.",
            "policy": {
                "session": "RTH",
                "market_time":
                    "2026-08-13T10:30:00-04:00",
            },
        },
    )

    monkeypatch.setattr(
        order_route,
        "_validate_order",
        lambda *args, **kwargs: (
            [],
            [],
        ),
    )

    monkeypatch.setattr(
        order_route.broker,
        "authenticate",
        lambda: True,
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST7178",
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        lambda account_number=None: [],
    )

    order_route.broker.last_error = None

    monkeypatch.setattr(
        order_route,
        "_check_existing_position_overlap",
        lambda order, positions: {
            "passed": True,
            "message":
                "No existing position overlap.",
            "overlaps": [],
        },
    )

    captured = {}

    def fake_dry_run_order(
        order,
        account_number=None,
    ):
        captured["order"] = order
        captured["account"] = account_number

        return {
            "payload": {},
            "broker_response": {},
        }

    monkeypatch.setattr(
        order_route.broker,
        "dry_run_order",
        fake_dry_run_order,
    )

    monkeypatch.setattr(
        order_route,
        "_evaluate_broker_dry_run",
        lambda dry_run, order: {
            "passed": True,
            "checks": [],
            "errors": [],
            "buying_power": {},
            "fees": 0.0,
        },
    )

    result = order_route.order_dry_run(
        review_id=review_id,
    )

    assert (
        result["status"]
        == "BROKER_PREFLIGHT_PASSED"
    )

    assert (
        captured["order"]["limit_price"]
        == 3.32
    )

    assert (
        captured["order"]["legs"][0]["symbol"]
        == "FROZEN-SPX-OPTION"
    )


def test_order_dry_run_requires_review_lock(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "_execution_session_gate",
        lambda: {
            "passed": True,
            "reason_code": None,
            "message": "RTH test session verified.",
            "policy": {
                "session": "RTH",
                "market_time":
                    "2026-08-14T10:00:00-04:00",
            },
        },
    )
    result = order_route.order_dry_run(
        review_id=None,
    )

    assert result["status"] == "BLOCKED"

    assert (
        result["reason_code"]
        == "REVIEW_LOCK_REQUIRED"
    )


def test_consumed_review_lock_cannot_be_reused():
    review_id = (
        order_route._create_order_review_lock(
            trade={
                "strategy": "SPX Iron Condor",
            },
            order={
                "strategy": "SPX Iron Condor",
                "symbol": "SPX",
                "quantity": 1,
                "limit_price": 3.32,
                "legs": [],
            },
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    review, error = (
        order_route._consume_order_review_lock(
            review_id,
        )
    )

    assert error is None
    assert review is not None

    second_review, second_error = (
        order_route._get_order_review_lock(
            review_id,
        )
    )

    assert second_review is None

    assert (
        second_error["reason_code"]
        == "REVIEW_LOCK_CONSUMED"
    )

def test_expired_review_lock_is_rejected(
    monkeypatch,
):
    clock = iter([
        100.0,
        (
            100.0
            + order_route._ORDER_REVIEW_TTL_SECONDS
        ),
    ])

    monkeypatch.setattr(
        order_route.time,
        "monotonic",
        lambda: next(clock),
    )

    review_id = (
        order_route._create_order_review_lock(
            trade={
                "strategy": "SPX Iron Condor",
            },
            order={
                "strategy": "SPX Iron Condor",
                "symbol": "SPX",
                "quantity": 1,
                "limit_price": 3.25,
                "max_risk": 2175.0,
                "buying_power": 2175.0,
                "legs": [],
            },
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    review, error = (
        order_route._get_order_review_lock(
            review_id,
        )
    )

    assert review is None
    assert error["status"] == "BLOCKED"
    assert (
        error["reason_code"]
        == "REVIEW_LOCK_EXPIRED"
    )


def test_unconfirmed_broker_response_blocks_success(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "_execution_session_gate",
        lambda: {
            "passed": True,
            "reason_code": None,
            "message": "RTH test session verified.",
            "policy": {
                "session": "RTH",
                "market_time":
                    "2026-08-14T10:00:00-04:00",
                "session_open": True,
                "day_order_allowed": True,
                "extended_order_required": False,
            },
        },
    )

    monkeypatch.setattr(
        order_route,
        "BXK_LIVE_TRADING_ENABLED",
        True,
    )

    preflight = ready_preflight()

    review_id = (
        order_route._create_order_review_lock(
            trade=preflight["trade"],
            order=preflight["order"],
            strategy="iron_condor",
            dte=1,
            wing_width=25,
            contracts=1,
        )
    )

    monkeypatch.setattr(
        order_route,
        "order_dry_run",
        lambda **kwargs: preflight,
    )

    monkeypatch.setattr(
        order_route.broker,
        "get_first_account_number",
        lambda: "TEST1234",
    )

    def positions(
        account_number=None,
    ):
        order_route.broker.last_error = None
        return []

    monkeypatch.setattr(
        order_route.broker,
        "get_positions",
        positions,
    )

    monkeypatch.setattr(
        order_route,
        "_check_existing_position_overlap",
        lambda order, positions: {
            "passed": True,
        },
    )

    monkeypatch.setattr(
        order_route.broker,
        "submit_live_order",
        lambda order, account_number=None: {
            "broker_response": {
                "data": {
                    "order": {
                        "status": "Received",
                    }
                }
            }
        },
    )

    result = call_submit(
        review_id=review_id,
    )

    assert (
        result["status"]
        == "SUBMISSION_UNCONFIRMED"
    )
    assert (
        result["reason_code"]
        == "BROKER_SUBMISSION_UNCONFIRMED"
    )
    assert result["submission_uncertain"] is True
    assert result["live_submission_enabled"] is False

    review, error = (
        order_route._get_order_review_lock(
            review_id,
        )
    )

    assert review is None
    assert (
        error["reason_code"]
        == "REVIEW_LOCK_CONSUMED"
    )

def risk_limit_check(
    monkeypatch,
    max_risk,
):
    monkeypatch.setattr(
        order_route,
        "BXK_MAX_ORDER_RISK",
        7500.0,
    )

    order = dict(
        ready_preflight()["order"]
    )

    order["max_risk"] = max_risk
    order["buying_power"] = max_risk

    checks, errors = (
        order_route._validate_order(
            order,
            requested_dte=1,
            requested_wing_width=25,
            requested_contracts=1,
        )
    )

    risk_check = next(
        check
        for check in checks
        if check["name"]
        == "maximum_risk_limit"
    )

    return risk_check, errors


def test_order_risk_below_limit_is_allowed(
    monkeypatch,
):
    risk_check, errors = risk_limit_check(
        monkeypatch,
        7499.99,
    )

    assert risk_check["passed"] is True
    assert not any(
        "BXK limit" in error
        for error in errors
    )


def test_order_risk_equal_to_limit_is_allowed(
    monkeypatch,
):
    risk_check, errors = risk_limit_check(
        monkeypatch,
        7500.00,
    )

    assert risk_check["passed"] is True
    assert not any(
        "BXK limit" in error
        for error in errors
    )


def test_order_risk_above_limit_is_blocked(
    monkeypatch,
):
    risk_check, errors = risk_limit_check(
        monkeypatch,
        7500.01,
    )

    assert risk_check["passed"] is False
    assert any(
        "$7,500.01 exceeds the $7,500.00 BXK limit."
        in error
        for error in errors
    )

def dte_range_check(
    requested_dte,
):
    order = dict(
        ready_preflight()["order"]
    )

    order["dte"] = requested_dte

    checks, errors = (
        order_route._validate_order(
            order,
            requested_dte=requested_dte,
            requested_wing_width=25,
            requested_contracts=1,
        )
    )

    dte_check = next(
        check
        for check in checks
        if check["name"] == "dte"
    )

    return dte_check, errors


def test_order_dte_zero_is_allowed():
    dte_check, errors = dte_range_check(0)

    assert dte_check["passed"] is True
    assert (
        "Requested DTE is outside the approved range."
        not in errors
    )


def test_order_dte_ten_is_allowed():
    dte_check, errors = dte_range_check(10)

    assert dte_check["passed"] is True
    assert (
        "Requested DTE is outside the approved range."
        not in errors
    )


def test_order_dte_above_maximum_is_blocked():
    dte_check, errors = dte_range_check(11)

    assert dte_check["passed"] is False
    assert (
        "Requested DTE is outside the approved range."
        in errors
    )

def minimum_credit_check(
    monkeypatch,
    credit,
):
    monkeypatch.setattr(
        order_route,
        "BXK_MIN_ORDER_CREDIT",
        1.00,
    )

    order = dict(
        ready_preflight()["order"]
    )

    order["limit_price"] = credit

    checks, errors = (
        order_route._validate_order(
            order,
            requested_dte=1,
            requested_wing_width=25,
            requested_contracts=1,
        )
    )

    credit_check = next(
        check
        for check in checks
        if check["name"] == "minimum_credit"
    )

    return credit_check, errors


def test_order_credit_below_minimum_is_blocked(
    monkeypatch,
):
    credit_check, errors = minimum_credit_check(
        monkeypatch,
        0.99,
    )

    assert credit_check["passed"] is False
    assert any(
        "$0.99 is below the $1.00 BXK minimum."
        in error
        for error in errors
    )


def test_order_credit_equal_to_minimum_is_allowed(
    monkeypatch,
):
    credit_check, errors = minimum_credit_check(
        monkeypatch,
        1.00,
    )

    assert credit_check["passed"] is True
    assert not any(
        "BXK minimum" in error
        for error in errors
    )


def test_order_credit_above_minimum_is_allowed(
    monkeypatch,
):
    credit_check, errors = minimum_credit_check(
        monkeypatch,
        1.01,
    )

    assert credit_check["passed"] is True
    assert not any(
        "BXK minimum" in error
        for error in errors
    )

def buying_power_reserve_check(
    monkeypatch,
    remaining_buying_power,
):
    monkeypatch.setattr(
        order_route,
        "BXK_MIN_REMAINING_BUYING_POWER",
        15000.0,
    )

    dry_run = _valid_broker_dry_run()
    data = dry_run["broker_response"]["data"]
    buying_power = data["buying-power-effect"]

    broker_impact = float(
        buying_power["change-in-buying-power"]
    )

    broker_fees = float(
        data["fee-calculation"]["total-fees"]
    )

    buying_power["new-buying-power"] = (
        f"{remaining_buying_power:.2f}"
    )

    buying_power["current-buying-power"] = (
        f"{remaining_buying_power + broker_impact:.2f}"
    )

    result = order_route._evaluate_broker_dry_run(
        dry_run,
        {
            "buying_power": round(
                broker_impact - broker_fees,
                2,
            ),
        },
    )

    checks = _broker_checks(result)

    return (
        result,
        checks["broker_buying_power_reserve"],
    )


def test_buying_power_below_reserve_is_blocked(
    monkeypatch,
):
    result, reserve_check = (
        buying_power_reserve_check(
            monkeypatch,
            14999.99,
        )
    )

    assert result["passed"] is False
    assert reserve_check["passed"] is False
    assert (
        "$14,999.99 is below the $15,000.00 BXK reserve."
        in reserve_check["message"]
    )


def test_buying_power_equal_to_reserve_is_allowed(
    monkeypatch,
):
    result, reserve_check = (
        buying_power_reserve_check(
            monkeypatch,
            15000.00,
        )
    )

    assert result["passed"] is True
    assert reserve_check["passed"] is True


def test_buying_power_above_reserve_is_allowed(
    monkeypatch,
):
    result, reserve_check = (
        buying_power_reserve_check(
            monkeypatch,
            15000.01,
        )
    )

    assert result["passed"] is True
    assert reserve_check["passed"] is True
