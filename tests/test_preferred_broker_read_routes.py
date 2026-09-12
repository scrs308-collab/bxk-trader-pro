from bxk_app.routes import broker as broker_route
from bxk_app.routes import positions as positions_route
from bxk_app.services import position_service


class FakeBroker:
    broker_name = "schwab"

    def supports(
        self,
        capability,
    ):
        return capability in {
            "accounts",
            "balances",
            "positions",
        }


def test_account_summary_uses_preferred_schwab(
    monkeypatch,
):
    fake_broker = FakeBroker()
    fake_session = object()

    monkeypatch.setattr(
        broker_route,
        "get_user_preferred_broker_name",
        lambda session, *, user_context:
            "schwab",
    )

    def legacy_status_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Tastytrade status must not be checked "
            "when Schwab is preferred."
        )

    monkeypatch.setattr(
        broker_route,
        "get_broker_connection_status",
        legacy_status_must_not_run,
    )

    monkeypatch.setattr(
        broker_route,
        "resolve_preferred_broker",
        lambda session, *, user_context:
            fake_broker,
    )

    captured = {}

    def fake_summary(
        *,
        broker_client=None,
    ):
        captured[
            "broker_client"
        ] = broker_client

        return {
            "connected": True,
            "account": {
                "number":
                    "SCHWAB",
            },
        }

    monkeypatch.setattr(
        broker_route,
        "get_account_summary",
        fake_summary,
    )

    result = broker_route.account_summary(
        user_context={
            "role": "BETA",
        },
        session=fake_session,
    )

    assert (
        captured["broker_client"]
        is fake_broker
    )

    assert (
        result["account"]["number"]
        == "SCHWAB"
    )


def test_account_summary_preserves_legacy_tastytrade_owner(
    monkeypatch,
):
    monkeypatch.setattr(
        broker_route,
        "get_user_preferred_broker_name",
        lambda session, *, user_context:
            "tastytrade",
    )

    monkeypatch.setattr(
        broker_route,
        "get_broker_connection_status",
        lambda session, *, user_context: {
            "source":
                "legacy_owner",
        },
    )

    def preferred_resolver_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Legacy owner should retain the existing "
            "Tastytrade account-summary path."
        )

    monkeypatch.setattr(
        broker_route,
        "resolve_preferred_broker",
        preferred_resolver_must_not_run,
    )

    captured = {}

    def fake_summary(
        *,
        broker_client=None,
    ):
        captured[
            "broker_client"
        ] = broker_client

        return {
            "connected": True,
            "account": {},
        }

    monkeypatch.setattr(
        broker_route,
        "get_account_summary",
        fake_summary,
    )

    broker_route.account_summary(
        user_context={
            "role": "OWNER",
        },
        session=object(),
    )

    assert (
        captured["broker_client"]
        is None
    )


def test_position_monitor_uses_preferred_schwab(
    monkeypatch,
):
    fake_broker = FakeBroker()

    monkeypatch.setattr(
        positions_route,
        "get_user_preferred_broker_name",
        lambda session, *, user_context:
            "schwab",
    )

    def legacy_status_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Tastytrade status must not be checked "
            "when Schwab is preferred."
        )

    monkeypatch.setattr(
        positions_route,
        "get_broker_connection_status",
        legacy_status_must_not_run,
    )

    monkeypatch.setattr(
        positions_route,
        "resolve_preferred_broker",
        lambda session, *, user_context:
            fake_broker,
    )

    captured = {}

    def fake_monitor(
        *,
        broker_client=None,
        user_context=None,
    ):
        captured[
            "broker_client"
        ] = broker_client

        captured[
            "user_context"
        ] = user_context

        return {
            "status": "EMPTY",
            "positions": [],
        }

    monkeypatch.setattr(
        positions_route,
        "get_position_monitor",
        fake_monitor,
    )

    context = {
        "role": "BETA",
    }

    result = (
        positions_route.position_monitor(
            user_context=context,
            session=object(),
        )
    )

    assert (
        captured["broker_client"]
        is fake_broker
    )

    assert (
        captured["user_context"]
        == context
    )

    assert result["status"] == "EMPTY"


def test_position_monitor_preserves_legacy_tastytrade_owner(
    monkeypatch,
):
    monkeypatch.setattr(
        positions_route,
        "get_user_preferred_broker_name",
        lambda session, *, user_context:
            "tastytrade",
    )

    monkeypatch.setattr(
        positions_route,
        "get_broker_connection_status",
        lambda session, *, user_context: {
            "source":
                "legacy_owner",
        },
    )

    def preferred_resolver_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Legacy owner should retain the existing "
            "Tastytrade Position Monitor path."
        )

    monkeypatch.setattr(
        positions_route,
        "resolve_preferred_broker",
        preferred_resolver_must_not_run,
    )

    captured = {}

    def fake_monitor(
        *,
        broker_client=None,
        user_context=None,
    ):
        captured[
            "broker_client"
        ] = broker_client

        return {
            "status": "EMPTY",
            "positions": [],
        }

    monkeypatch.setattr(
        positions_route,
        "get_position_monitor",
        fake_monitor,
    )

    positions_route.position_monitor(
        user_context={
            "role": "OWNER",
        },
        session=object(),
    )

    assert (
        captured["broker_client"]
        is None
    )


def test_reconciliation_skips_broker_without_order_history(
    monkeypatch,
):
    fake_broker = FakeBroker()

    def reconciliation_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Order-history reconciliation must not run "
            "for a broker without order-history support."
        )

    monkeypatch.setattr(
        position_service,
        "_invoke_reconcile_missing_trade_journals",
        reconciliation_must_not_run,
    )

    result = (
        position_service
        ._reconcile_trade_journal_closures(
            [],
            broker_client=fake_broker,
            user_context={
                "role": "BETA",
            },
        )
    )

    assert result == {
        "checked": False,
        "reason":
            "BROKER_ORDER_HISTORY_UNSUPPORTED",
        "results": [],
    }
