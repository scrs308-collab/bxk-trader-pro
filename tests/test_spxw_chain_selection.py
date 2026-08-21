from bxk_app import option_scanner


def sample_chain():
    return {
        "items": [
            {
                "underlying-symbol": "SPX",
                "root-symbol": "SPX",
                "option-chain-type": "Standard",
                "expirations": [
                    {
                        "expiration-date": "2026-08-21",
                        "settlement-type": "AM",
                        "strikes": [
                            {
                                "strike-price": "6000",
                                "call-streamer-symbol": "SPX_AM_CALL",
                                "put-streamer-symbol": "SPX_AM_PUT",
                            }
                        ],
                    },
                    {
                        "expiration-date": "2026-09-18",
                        "settlement-type": "AM",
                        "strikes": [],
                    },
                ],
            },
            {
                "underlying-symbol": "SPX",
                "root-symbol": "SPXW",
                "option-chain-type": "Standard",
                "expirations": [
                    {
                        "expiration-date": "2026-08-21",
                        "settlement-type": "PM",
                        "strikes": [
                            {
                                "strike-price": "7000",
                                "call-streamer-symbol": "SPXW_0_CALL",
                                "put-streamer-symbol": "SPXW_0_PUT",
                            }
                        ],
                    },
                    {
                        "expiration-date": "2026-08-24",
                        "settlement-type": "PM",
                        "strikes": [
                            {
                                "strike-price": "7005",
                                "call-streamer-symbol": "SPXW_3_CALL",
                                "put-streamer-symbol": "SPXW_3_PUT",
                            }
                        ],
                    },
                    {
                        "expiration-date": "2026-08-25",
                        "settlement-type": "PM",
                        "strikes": [
                            {
                                "strike-price": "7010",
                                "call-streamer-symbol": "SPXW_4_CALL",
                                "put-streamer-symbol": "SPXW_4_PUT",
                            }
                        ],
                    },
                ],
            },
        ]
    }


def install_chain(monkeypatch):
    monkeypatch.setattr(
        option_scanner.tastytrade_api,
        "get_spx_option_chain",
        sample_chain,
    )

    dtes = {
        "2026-08-21": 0,
        "2026-08-24": 3,
        "2026-08-25": 4,
        "2026-09-18": 28,
    }

    monkeypatch.setattr(
        option_scanner,
        "calculate_actual_dte",
        lambda value: dtes[value],
    )


def test_selects_spxw_chain():
    item = option_scanner.get_spxw_chain_item(
        sample_chain()
    )

    assert item is not None
    assert item["root-symbol"] == "SPXW"


def test_missing_1dte_reports_next_spxw_expiration(
    monkeypatch,
):
    install_chain(monkeypatch)

    status = option_scanner.get_spx_expiration_status(
        1
    )

    assert status["chain_available"] is True
    assert status["exact_available"] is False
    assert status["next_available_dte"] == 3
    assert status["next_expiration"] == "2026-08-24"
    assert status["substitution_made"] is False


def test_exact_dte_uses_spxw_pm_contracts(
    monkeypatch,
):
    install_chain(monkeypatch)

    strikes = option_scanner.get_spx_strikes_by_dte(
        3
    )

    assert len(strikes) == 1
    assert strikes[0]["strike"] == 7005.0
    assert strikes[0]["days_to_expiration"] == 3
    assert strikes[0]["settlement_type"] == "PM"
    assert (
        strikes[0]["call_streamer"]
        == "SPXW_3_CALL"
    )
