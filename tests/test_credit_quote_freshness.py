from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from types import SimpleNamespace

from bxk_app.debit_strategies import (
    credit_preview_metadata,
)
from bxk_app.live_option_engine import (
    quote_event_timestamp,
)
from bxk_app.routes.order import (
    _validate_order,
)
from bxk_app.routes import order as order_route


def credit_trade(
    *,
    timestamp,
):
    return {
        "strategy": "SPX Iron Condor",
        "symbol": "SPX",
        "expiration": "2099-12-31",
        "dte": 1,
        "quantity": 1,
        "wing_width": 25,
        "credit": 3.20,
        "max_profit": 320.0,
        "max_risk": 2180.0,
        "buying_power": 2180.0,
        "sell_put": 7560,
        "buy_put": 7535,
        "sell_call": 7710,
        "buy_call": 7735,
        "sell_put_symbol": "SELL-PUT",
        "buy_put_symbol": "BUY-PUT",
        "sell_call_symbol": "SELL-CALL",
        "buy_call_symbol": "BUY-CALL",
        "sell_put_streamer": "SELL-PUT",
        "buy_put_streamer": "BUY-PUT",
        "sell_call_streamer": "SELL-CALL",
        "buy_call_streamer": "BUY-CALL",
        "credit_details": {
            "quotes": {
                name: {
                    "bid": 1.0,
                    "ask": 1.1,
                    "quote_timestamp": timestamp,
                }
                for name in (
                    "SELL-PUT",
                    "BUY-PUT",
                    "SELL-CALL",
                    "BUY-CALL",
                )
            }
        },
    }


def test_quote_timestamp_uses_oldest_bid_and_ask():
    quote = SimpleNamespace(
        event_time=1_700_000_003_000,
        bid_time=1_700_000_001_000,
        ask_time=1_700_000_002_000,
    )

    assert (
        quote_event_timestamp(quote)
        == 1_700_000_001_000
    )


def test_quote_timestamp_falls_back_to_event_time():
    quote = SimpleNamespace(
        event_time=1_700_000_003_000,
        bid_time=0,
        ask_time=1_700_000_002_000,
    )

    assert (
        quote_event_timestamp(quote)
        == 1_700_000_002_000
    )

    quote.bid_time = 0
    quote.ask_time = 0

    assert (
        quote_event_timestamp(quote)
        == 1_700_000_003_000
    )


def test_quote_timestamp_falls_back_to_receipt_time():
    quote = SimpleNamespace(
        event_time=0,
        bid_time=0,
        ask_time=0,
    )

    assert (
        quote_event_timestamp(
            quote,
            received_at=1_700_000_004_000,
        )
        == 1_700_000_004_000
    )


def test_fresh_credit_quote_is_execution_ready():
    timestamp = (
        datetime.now(timezone.utc)
        - timedelta(seconds=2)
    ).timestamp() * 1000

    trade = credit_trade(
        timestamp=timestamp
    )

    credit_preview_metadata(
        trade
    )

    assert trade["quote_timestamp"]
    assert 0 <= trade["quote_age_seconds"] < 60
    assert trade["quote_is_fresh"] is True
    assert trade["execution"]["status"] == "READY"
    assert trade["execution"]["ready"] is True


def test_unrelated_shared_quotes_do_not_block_vertical():
    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    trade = credit_trade(
        timestamp=timestamp
    )

    trade["strategy"] = (
        "Bull Put Credit Spread"
    )

    trade["credit_details"]["quotes"][
        "UNRELATED-CANDIDATE"
    ] = {
        "bid": 9.0,
        "ask": 9.5,
        "quote_timestamp": None,
    }

    credit_preview_metadata(
        trade
    )

    assert trade["quote_is_fresh"] is True
    assert trade["execution"]["status"] == "READY"


def test_missing_credit_timestamp_blocks_execution():
    trade = credit_trade(
        timestamp=None
    )

    credit_preview_metadata(
        trade
    )

    assert trade["quote_timestamp"] is None
    assert trade["quote_age_seconds"] is None
    assert trade["quote_is_fresh"] is False
    assert trade["execution"]["status"] == "BLOCKED"
    assert trade["execution"]["ready"] is False


def test_incomplete_credit_quote_blocks_execution():
    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    trade = credit_trade(
        timestamp=timestamp
    )

    trade["credit_details"]["quotes"][
        "BUY-CALL"
    ]["ask"] = 0

    credit_preview_metadata(
        trade
    )

    assert trade["quote_timestamp"] is None
    assert trade["quote_age_seconds"] is None
    assert trade["quote_is_fresh"] is False
    assert trade["execution"]["status"] == "BLOCKED"


def test_stale_credit_timestamp_is_shown_but_blocked():
    timestamp = (
        datetime.now(timezone.utc)
        - timedelta(seconds=61)
    ).isoformat()

    trade = credit_trade(
        timestamp=timestamp
    )

    credit_preview_metadata(
        trade
    )

    assert trade["quote_timestamp"] is not None
    assert trade["quote_age_seconds"] >= 60
    assert trade["quote_is_fresh"] is False
    assert trade["execution"]["status"] == "BLOCKED"


def test_credit_order_validation_requires_fresh_quote():
    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    trade = credit_trade(
        timestamp=timestamp
    )

    credit_preview_metadata(
        trade
    )

    order = {
        **trade,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 3.20,
    }

    checks, errors = _validate_order(
        order,
        requested_dte=1,
        requested_wing_width=25,
        requested_contracts=1,
    )

    freshness = next(
        check
        for check in checks
        if check["name"] == "quote_freshness"
    )

    assert freshness["passed"] is True
    assert errors == []

    order["quote_timestamp"] = None

    checks, errors = _validate_order(
        order,
        requested_dte=1,
        requested_wing_width=25,
        requested_contracts=1,
    )

    freshness = next(
        check
        for check in checks
        if check["name"] == "quote_freshness"
    )

    assert freshness["passed"] is False
    assert (
        "Option quotes are missing or stale. "
        "Build a fresh preview."
        in errors
    )


def test_order_preview_blocks_before_creating_review_lock(
    monkeypatch,
):
    monkeypatch.setattr(
        order_route,
        "_build_current_order",
        lambda *args, **kwargs: (
            {
                "strategy": "SPX Iron Condor",
            },
            {
                "strategy": "SPX Iron Condor",
                "quote_timestamp": None,
            },
        ),
    )

    def must_not_create_review(**_kwargs):
        raise AssertionError(
            "Stale quote created a review lock."
        )

    monkeypatch.setattr(
        order_route,
        "_create_order_review_lock",
        must_not_create_review,
    )

    result = order_route.order_preview(
        strategy="iron_condor",
        dte=1,
        wing_width=25,
        contracts=1,
        user_context={"role": "OWNER"},
        session=None,
    )

    assert result["status"] == "BLOCKED"
    assert result["live_submission_enabled"] is False
    assert "missing or stale" in result["message"]


def test_trade_button_requires_execution_readiness():
    source = Path(
        "static/best-trade.js",
    ).read_text(encoding="utf-8")

    assert (
        "const tradeExecutable =\n"
        "      tradeApproved && executionReady;"
        in source
    )

    assert (
        "const executionReady =\n"
        "      quoteFresh &&"
        in source
    )

    assert "WAIT FOR FRESH QUOTE" in source
    assert "REFRESH FOR LIVE QUOTE" in source
    assert "REFRESHING LIVE QUOTE..." in source

    assert (
        'value == null || value === ""'
        in source
    )
