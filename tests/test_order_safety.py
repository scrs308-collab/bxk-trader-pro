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


def call_submit(confirm_live=True):
    return order_route.order_submit(
        strategy="iron_condor",
        dte=1,
        wing_width=25,
        contracts=1,
        confirm_live=confirm_live,
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

    result = call_submit()

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
                    "current-buying-power": "10000.00",
                    "change-in-buying-power": "831.88",
                    "new-buying-power": "9168.12",
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
    result = (
        order_route._evaluate_broker_dry_run(
            _valid_broker_dry_run(),
            {},
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
