from bxk_app import option_chain_service as service


def sample_chain():
    return {
        "items": [
            {
                "expirations": [
                    {
                        "expiration-date": "2099-01-01",
                        "settlement-type": "PM",
                        "strikes": [
                            {
                                "strike-price": "718",
                                "call": "QQQ CALL 718",
                                "put": "QQQ PUT 718",
                                "call-streamer-symbol": ".QQQCALL718",
                                "put-streamer-symbol": ".QQQPUT718",
                            },
                            {
                                "strike-price": "720",
                                "call": "QQQ CALL 720",
                                "put": "QQQ PUT 720",
                                "call-streamer-symbol": ".QQQCALL720",
                                "put-streamer-symbol": ".QQQPUT720",
                            },
                            {
                                "strike-price": "722",
                                "call": "QQQ CALL 722",
                                "put": "QQQ PUT 722",
                                "call-streamer-symbol": ".QQQCALL722",
                                "put-streamer-symbol": ".QQQPUT722",
                            },
                        ],
                    }
                ]
            }
        ]
    }


def test_generic_chain_uses_requested_symbol(monkeypatch):
    captured = {}

    def fake_chain(symbol):
        captured["symbol"] = symbol
        return sample_chain()

    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        fake_chain,
    )

    result = service.get_nested_option_chain(" qqq ")

    assert captured["symbol"] == "QQQ"
    assert result == sample_chain()


def test_get_qqq_strikes_exact_dte(monkeypatch):
    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda symbol: sample_chain(),
    )

    monkeypatch.setattr(
        service,
        "calculate_actual_dte",
        lambda expiration: 0,
    )

    strikes = service.get_strikes_by_dte(
        "QQQ",
        0,
    )

    assert len(strikes) == 3
    assert strikes[1]["strike"] == 720.0
    assert (
        strikes[1]["call_streamer"]
        == ".QQQCALL720"
    )
    assert (
        strikes[1]["put_streamer"]
        == ".QQQPUT720"
    )
    assert strikes[1]["underlying"] == "QQQ"


def test_missing_exact_dte_does_not_substitute(
    monkeypatch,
):
    monkeypatch.setattr(
        service.tastytrade_api,
        "get_nested_option_chain",
        lambda symbol: sample_chain(),
    )

    monkeypatch.setattr(
        service,
        "calculate_actual_dte",
        lambda expiration: 1,
    )

    strikes = service.get_strikes_by_dte(
        "QQQ",
        0,
    )

    assert strikes == []


def test_qqq_expected_move_uses_atm_straddle(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "get_strikes_by_dte",
        lambda symbol, dte: [
            {
                "underlying": "QQQ",
                "strike": 718.0,
                "call_streamer": ".CALL718",
                "put_streamer": ".PUT718",
                "expiration_date": "2026-08-19",
                "days_to_expiration": 0,
            },
            {
                "underlying": "QQQ",
                "strike": 720.0,
                "call_streamer": ".CALL720",
                "put_streamer": ".PUT720",
                "expiration_date": "2026-08-19",
                "days_to_expiration": 0,
            },
        ],
    )

    monkeypatch.setattr(
        service,
        "get_live_market_data",
        lambda symbols: {
            ".CALL720": {
                "bid": 3.40,
                "ask": 3.60,
            },
            ".PUT720": {
                "bid": 3.10,
                "ask": 3.30,
            },
        },
    )

    result = (
        service
        .calculate_atm_straddle_expected_move(
            "QQQ",
            719.74,
            0,
        )
    )

    assert result["available"] is True
    assert result["signal_ready"] is True
    assert result["atm_strike"] == 720.0

    assert result["call_mid"] == 3.50
    assert result["put_mid"] == 3.20
    assert result["expected_move"] == 6.70

    assert (
        result["source"]
        == "OPTION_CHAIN_ATM_STRADDLE"
    )

    assert (
        result["reason_code"]
        == "OPTION_CHAIN_EXPECTED_MOVE_READY"
    )


def test_expected_move_fails_closed_without_chain(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "get_strikes_by_dte",
        lambda symbol, dte: [],
    )

    result = (
        service
        .calculate_atm_straddle_expected_move(
            "QQQ",
            719.74,
            0,
        )
    )

    assert result["available"] is False
    assert result["signal_ready"] is False
    assert result["expected_move"] is None
    assert (
        result["reason_code"]
        == "OPTION_CHAIN_UNAVAILABLE"
    )
