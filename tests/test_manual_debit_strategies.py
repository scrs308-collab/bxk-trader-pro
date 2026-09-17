from datetime import date, datetime, timedelta, timezone
import copy
import re

import pytest
from bxk_app.debit_strategies import (
    DEBIT_NAMES, PATTERNS, debit_risk, construct_legs, price_debit_legs, build_manual_debit,
)
from bxk_app.services.order_builder import build_order
from bxk_app.brokers.tastytrade import TastytradeBroker
from bxk_app.position_monitor import build_position_summaries
from test_per_user_broker_resolution import db_session, credential_key


STRIKES = {
    "reverse_iron_condor": [7550, 7570, 7640, 7660],
    "butterfly": [7580, 7600, 7620],
    "debit_call_spread": [7600, 7620],
    "debit_put_spread": [7600, 7580],
}


def trade_for(key, debit=11.7):
    expiry = date.today() + timedelta(days=2)
    legs = [{"action": action, "option_type": kind, "quantity": ratio,
             "strike": strike, "symbol": f"SPXW  {expiry:%y%m%d}{kind[0]}{strike * 1000:08d}",
             "streamer_symbol": str(index)}
            for index, (strike, (action, kind, ratio)) in enumerate(zip(STRIKES[key], PATTERNS[key]))]
    return {"strategy": DEBIT_NAMES[key], "symbol": "SPX", "spx_price": 7600, "expected_move": 70, "expiration": expiry.isoformat(),
            "dte": 2, "legs": legs, "quote_timestamp": datetime.now(timezone.utc).isoformat(),
            "playbook_status": "DENIED", **debit_risk(key, legs, debit)}


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_risk_order_and_atomic_payload(key):
    trade = trade_for(key)
    order = build_order(trade, quantity=3)
    payload = TastytradeBroker().build_dry_run_payload(order)
    assert payload["price-effect"] == "Debit"
    assert len(payload["legs"]) == len(PATTERNS[key])
    assert [l["quantity"] for l in payload["legs"]] == [p[2] * 3 for p in PATTERNS[key]]
    assert [l["action"] for l in payload["legs"]] == ["Buy to Open" if p[0] == "BUY" else "Sell to Open" for p in PATTERNS[key]]
    assert order["max_profit"] == 2490
    assert order["max_risk"] == 3510
    from bxk_app.routes.order import _validate_order
    checks, errors = _validate_order(order, requested_dte=2, requested_wing_width=20, requested_contracts=3)
    assert not errors, errors


def test_representative_reverse_condor():
    trade = trade_for("reverse_iron_condor")
    assert trade["max_loss"] == 1170
    assert trade["max_profit"] == 830
    assert trade["breakevens"] == [7558.3, 7651.7]


@pytest.mark.parametrize("key,expected", [("butterfly", [7591.7, 7608.3]), ("debit_call_spread", [7611.7]), ("debit_put_spread", [7588.3])])
def test_breakevens(key, expected):
    assert trade_for(key)["breakevens"] == expected


@pytest.mark.parametrize("key", DEBIT_NAMES)
@pytest.mark.parametrize("debit", [0, -1, 20, 21, float("nan"), float("inf")])
def test_invalid_debit(key, debit):
    with pytest.raises(ValueError):
        debit_risk(key, trade_for(key)["legs"], debit)


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_strike_and_ratio_validation(key):
    legs = trade_for(key)["legs"]
    legs[0]["strike"] = legs[1]["strike"]
    with pytest.raises(ValueError):
        debit_risk(key, legs, 5)
    legs = trade_for(key)["legs"]
    legs[1]["quantity"] = 3
    with pytest.raises(ValueError):
        debit_risk(key, legs, 5)


@pytest.mark.parametrize("key", ["reverse_iron_condor", "butterfly"])
def test_equal_width_required(key):
    legs = trade_for(key)["legs"]
    legs[-1]["strike"] += 5
    with pytest.raises(ValueError, match="widths"):
        debit_risk(key, legs, 5)


def reverse_quotes():
    # -4 + 10 + 9.7 - 4 = 11.7 debit.
    now = datetime.now(timezone.utc).isoformat()
    return {str(i): {"bid": mid - .1, "ask": mid + .1, "quote_timestamp": now}
            for i, mid in enumerate([4, 10, 9.7, 4])}


def test_live_combo_midpoint():
    result = price_debit_legs("reverse_iron_condor", trade_for("reverse_iron_condor")["legs"], reverse_quotes())
    assert result["midpoint"] == 11.7
    assert result["max_loss"] == 1170
    assert result["quote_age_seconds"] < 5


@pytest.mark.parametrize("mutation", ["missing", "stale", "no_time", "crossed", "nan"])
def test_quote_validation(mutation):
    quotes = reverse_quotes()
    if mutation == "missing":
        del quotes["0"]["ask"]
    elif mutation == "stale":
        quotes["0"]["quote_timestamp"] = (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()
    elif mutation == "no_time":
        del quotes["0"]["quote_timestamp"]
    elif mutation == "crossed":
        quotes["0"]["ask"] = 1
    else:
        quotes["0"]["bid"] = float("nan")
    with pytest.raises(ValueError):
        price_debit_legs("reverse_iron_condor", trade_for("reverse_iron_condor")["legs"], quotes)


def chain():
    expiry = (date.today() + timedelta(days=2)).isoformat()
    return [{"strike": s, "call": f"C{s}", "put": f"P{s}", "call_streamer": f"C{s}",
             "put_streamer": f"P{s}", "expiration_date": expiry} for s in range(7520, 7690, 5)]


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_chain_construction_and_unavailable_strikes(key):
    legs = construct_legs(key, chain(), 7600, 20, 70)
    assert [(l["action"], l["option_type"], l["quantity"]) for l in legs] == PATTERNS[key]
    assert all(l["strike"] in {r["strike"] for r in chain()} for l in legs)
    debit_risk(key, legs, 5)
    with pytest.raises(ValueError):
        construct_legs(key, chain()[:1], 7600, 20, 70)


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_preview_and_api_acceptance(monkeypatch, key):
    import bxk_app.services.scanner_service as scanner
    import bxk_app.routes.scanner as route
    import bxk_app.routes.order as orders
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setattr(scanner, "run_trade_quality", lambda: {"score": 50})
    monkeypatch.setattr(scanner, "build_manual_debit", lambda *args: {"status": "READY", "best_trade": trade_for(key)})
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/best-trade", params={"strategy": key, "dte": 2, "wing_width": 20})
    assert response.status_code == 200
    assert response.json()["best_trade"]["strategy"] == DEBIT_NAMES[key]
    assert response.json()["best_trade"]["playbook_status"] in {"APPROVED", "CAUTION", "DENIED"}
    monkeypatch.setattr(orders, "get_best_trade", lambda **kwargs: {"best_trade": trade_for(key)})
    preview = orders.order_preview(strategy=key, dte=2, wing_width=20, contracts=1, user_context={"role": "OWNER"}, session=None)
    assert preview["status"] == "READY"
    assert preview["order"]["price_effect"] == "Debit"
    assert preview["order"]["playbook_status"] == "DENIED"


@pytest.mark.parametrize("key", DEBIT_NAMES)
@pytest.mark.parametrize("change", [-1, 1])
def test_monitor_recognition_and_profit_direction(key, change):
    trade = trade_for(key)
    mids = [4, 10, 9.7, 4] if key == "reverse_iron_condor" else [20, 10, 5] if key == "butterfly" else [15, 5]
    positions = [{"symbol": leg["symbol"], "direction": "LONG" if leg["action"] == "BUY" else "SHORT",
                  "quantity": leg["quantity"], "average_open_price": mid,
                  "current_price": mid + (change if leg["action"] == "BUY" else 0), "multiplier": 100}
                 for leg, mid in zip(trade["legs"], mids)]
    summaries = build_position_summaries(positions, 7600)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["spread_type"] == "DEBIT"
    assert summary["pnl"] * change > 0
    assert summary["breakevens"]
    if key in {"reverse_iron_condor", "butterfly"}:
        assert summary["position_type"] == key.upper()
    assert summary["stop_value"] < summary["opening_debit"] < summary["profit_target_value"]


def test_journal_signed_entry_and_ratio(monkeypatch):
    from test_trade_journal import make_factory, create_user
    from bxk_app.db_models.trade_journal import TradeJournal
    import bxk_app.services.trade_journal_service as journal
    factory = make_factory()
    user_id = create_user(factory)
    monkeypatch.setattr(journal, "database_configured", lambda: True)
    order = build_order(trade_for("butterfly", 5))
    result = journal.record_submitted_trade(user_context={"user_id": str(user_id)}, broker_order_id="DEBIT-1",
        broker_status="FILLED", order=order, trade=order, broker_order={},
        reconciliation={"average_fill_price": "5", "filled_quantity": "1"}, session_factory=factory)
    assert result["recorded"]
    with factory() as session:
        row = session.query(TradeJournal).one()
        assert row.user_id == user_id
        assert row.submitted_credit == -5
        assert row.entry_fill_credit == -5
        assert row.entry_snapshot["order"]["legs"][1]["quantity"] == 2
    filled = {"legs": [{"action": action, "quantity": q, "fills": [{"fill-price": p, "quantity": q}]}
                        for action, q, p in [("Buy to Open", 1, 20), ("Sell to Open", 2, 10), ("Buy to Open", 1, 5)]]}
    assert journal._opening_fill_credit(filled) == -5


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_broker_preflight_debit_and_ratio(key):
    from test_order_safety import _valid_broker_dry_run
    from bxk_app.routes.order import _evaluate_broker_dry_run
    order = build_order(trade_for(key))
    payload = TastytradeBroker().build_dry_run_payload(order)
    dry = _valid_broker_dry_run()
    dry["payload"] = copy.deepcopy(payload)
    data = dry["broker_response"]["data"]
    data["order"] = {**copy.deepcopy(payload), "status": "Received"}
    impact = order["buying_power"] + 6.88
    data["buying-power-effect"] = {"current-buying-power": 25000, "change-in-buying-power": impact, "new-buying-power": 25000 - impact}
    assert _evaluate_broker_dry_run(dry, order)["passed"]
    data["order"]["price-effect"] = "Credit"
    assert not _evaluate_broker_dry_run(dry, order)["passed"]
    data["order"]["price-effect"] = "Debit"
    data["order"]["legs"][1]["quantity"] += 1
    assert not _evaluate_broker_dry_run(dry, order)["passed"]


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_builder_uses_live_chain_and_fails_closed(monkeypatch, key):
    import bxk_app.trade_builder as builder
    import bxk_app.option_scanner as scanner
    import bxk_app.live_option_engine as live
    monkeypatch.setattr(builder, "refresh_live_trade_context", lambda: ({}, {"spx": 7600, "expected_move": 70}, None))
    monkeypatch.setattr(scanner, "get_spx_strikes_by_dte", lambda dte: chain())
    def quotes(symbols):
        # Fixed fixtures in leg order, including the butterfly double short.
        mids = [4, 10, 9.7, 4] if key == "reverse_iron_condor" else [20, 10, 5] if key == "butterfly" else [15, 5]
        return {s: {"bid": mid - .1, "ask": mid + .1, "quote_timestamp": datetime.now(timezone.utc).isoformat()}
                for s, mid in zip(symbols, mids)}
    monkeypatch.setattr(live, "get_live_market_data", quotes)
    result = build_manual_debit(key, 2, 20)
    assert result["status"] == "READY"
    assert result["best_trade"]["structure_validated"]
    monkeypatch.setattr(live, "get_live_market_data", lambda symbols: {})
    result = build_manual_debit(key, 2, 20)
    assert result["best_trade"] is None
    assert "incomplete" in result["message"]
    monkeypatch.setattr(scanner, "get_spx_strikes_by_dte", lambda dte: [])
    assert build_manual_debit(key, 2, 20)["best_trade"] is None


def test_reverse_playbook_expansion_and_cost():
    from bxk_app.strategy_ranker import reverse_condor_playbook
    contained = {"spx_price": 7600, "session_open": 7600, "implied_move": 70, "range_expansion_pressure": {"pressure_ratio": .7}}
    expansion = {**contained, "spx_price": 7640, "event_driven_movement": True, "range_expansion_pressure": {"pressure_ratio": 1.8}}
    assert reverse_condor_playbook(expansion)["score"] > reverse_condor_playbook(contained)["score"]
    good = trade_for("reverse_iron_condor", 7)
    bad = trade_for("reverse_iron_condor", 19)
    bad.update(combo_bid=5, combo_ask=30, dte=0)
    assert reverse_condor_playbook(expansion, good)["score"] > reverse_condor_playbook(expansion, bad)["score"]


def test_auto_allowlist_unchanged(monkeypatch):
    import bxk_app.services.scanner_service as scanner
    monkeypatch.setattr(scanner, "run_trade_quality", lambda: {})
    monkeypatch.setattr(scanner, "rank_strategies", lambda *args: [{"name": name, "status": "APPROVED"} for name in DEBIT_NAMES.values()])
    monkeypatch.setattr(scanner, "build_manual_debit", lambda *args: pytest.fail("Auto selected manual strategy"))
    assert scanner.get_best_trade(strategy="auto")["best_trade"] is None


def test_debit_audit_retains_effect_and_ratio():
    from test_user_execution_audit import make_session_factory, add_beta_user
    from bxk_app.services.user_execution_audit_service import write_user_order_audit
    from bxk_app.db_models.execution_audit import ExecutionAudit
    factory = make_session_factory()
    user_id = add_beta_user(factory)
    with factory() as session:
        write_user_order_audit(session, user_context={"user_id": user_id, "role": "BETA"},
            event="SUBMISSION_ATTEMPT", account="BETA1234", order=build_order(trade_for("butterfly")))
        row = session.query(ExecutionAudit).one()
        assert str(row.user_id) == user_id
        assert row.order_snapshot["price_effect"] == "Debit"
        assert row.order_snapshot["legs"][1]["quantity"] == 2


def test_selector_order_and_manual_review():
    from pathlib import Path
    source = Path("static/index.html").read_text(encoding="utf-8")
    select = source.split('<select id="strategySelector">')[1].split('</select>')[0]
    assert re.findall(r'value="([^"]+)"', select) == ["auto", "iron_condor", "reverse_iron_condor", "butterfly", "bull_put_credit_spread", "bear_call_credit_spread", "debit_call_spread", "debit_put_spread"]
    source = Path("static/best-trade.js").read_text(encoding="utf-8")
    assert 'const tradeApproved = manualPreviewReady ||' in source
    assert 'Strategy Playbook:' in source


@pytest.mark.parametrize("key", DEBIT_NAMES)
def test_per_user_live_payload_isolation(monkeypatch, db_session, credential_key, key):
    from test_per_user_broker_resolution import make_user, add_connection, context_for
    from bxk_app.db_models.user import UserRole
    from bxk_app.services.broker_connection_service import resolve_tastytrade_broker, BrokerConnectionRequired
    import bxk_app.brokers.tastytrade as tasty
    monkeypatch.setattr(tasty, "BXK_LIVE_TRADING_ENABLED", True)
    seen = []
    class Response:
        def json(self):
            return {"data": {"order": {"id": "TEST", "status": "Received"}}}
    for label in ["alpha", "bravo"]:
        user = make_user(db_session, username=label, role=UserRole.BETA)
        add_connection(db_session, user=user, client_secret=label + "-secret", refresh_token=label + "-refresh", account_number=label + "123", live_trading_enabled=True)
        broker = resolve_tastytrade_broker(db_session, user_context=context_for(user))
        monkeypatch.setattr(broker, "get_accounts", lambda: [{"account": {"account-number": label + "123"}}])
        def request(method, path, json_body=None, **kwargs):
            seen.append((broker.client_secret, path, copy.deepcopy(json_body)))
            return Response()
        monkeypatch.setattr(broker, "_request", request)
        assert broker.submit_live_order(build_order(trade_for(key), 2))
    assert [entry[0] for entry in seen] == ["alpha-secret", "bravo-secret"]
    assert [entry[1] for entry in seen] == ["/accounts/alpha123/orders", "/accounts/bravo123/orders"]
    assert all(entry[2]["price-effect"] == "Debit" for entry in seen)
    assert all([leg["quantity"] for leg in entry[2]["legs"]] == [p[2] * 2 for p in PATTERNS[key]] for entry in seen)
    unconnected = make_user(db_session, username="missing", role=UserRole.BETA)
    with pytest.raises(BrokerConnectionRequired):
        resolve_tastytrade_broker(db_session, user_context=context_for(unconnected))
