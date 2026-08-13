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
