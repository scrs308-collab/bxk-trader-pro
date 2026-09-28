from types import SimpleNamespace

from bxk_app import trade_builder
from bxk_app.trade_analyzer import analyze_trade


def test_pop_target_selects_nearest_live_condor_and_keeps_strikes(monkeypatch):
    market = SimpleNamespace(score=100, market_regime="TRADE", trend="MIXED",
                             vix_state="IDEAL", expected_move_state="HEALTHY")
    monkeypatch.setattr(trade_builder, "refresh_live_trade_context",
                        lambda: (market, {"spx": 6000, "expected_move": 50}, None))
    candidates = [{"strike": strike} for strike in (5930, 5940, 5950)]
    scan_args = {}

    def scan(**kwargs):
        scan_args.update(kwargs)
        return candidates

    monkeypatch.setattr(trade_builder, "generate_candidate_condors", scan)

    def normalize(candidate, **kwargs):
        short = candidate["strike"]
        return {"sell_put": short, "buy_put": short - 25,
                "sell_call": 12000 - short, "buy_call": 12025 - short,
                "wing_width": 25, "expiration": "2026-09-29"}

    monkeypatch.setattr(trade_builder, "normalize_candidate", normalize)
    pops = {5930: 80, 5940: 75.7, 5950: 70.5}
    monkeypatch.setattr(trade_builder, "calculate_iron_condor_credit",
                        lambda trade: {"live_credit": 2.0, "pop": pops[trade["sell_put"]],
                                       "short_put_delta": .15, "short_call_delta": .15})

    result = trade_builder.build_best_trade(target_pop=75)
    assert scan_args["search_points"] == 100
    assert result["best_trade"]["sell_put"] == 5940
    assert result["best_trade"]["target_pop"] == 75
    assert result["best_trade"]["pop"] == 75.7

    monkeypatch.setattr(trade_builder, "calculate_iron_condor_credit",
                        lambda trade: {"live_credit": 2.0, "pop": None})
    assert trade_builder.build_best_trade(target_pop=70)["best_trade"] is None


def test_selected_pop_profile_scores_actual_risk_without_changing_market_gate():
    trade = {"credit": 3, "pop": 70, "probability_of_touch": 30,
             "risk_reward": 7, "wing_width": 25, "put_distance": 35,
             "call_distance": 35, "market_regime": "TRADE", "target_pop": 70}
    selected = analyze_trade(trade)
    baseline = analyze_trade({key: value for key, value in trade.items()
                              if key != "target_pop"})
    assert selected["trade_score"] > baseline["trade_score"]
    assert selected["final_decision"] == "ENTER TRADE"
    assert analyze_trade({**trade, "market_regime": "WAIT"})["final_decision"] == "NO TRADE"
