from bxk_app.services import position_service


class StockOnlyBroker:
    broker_name = "schwab"

    def authenticate(self):
        return True

    def get_position_summary(self):
        return [
            {
                "symbol": "FLYX",
                "quantity": 1000,
            },
            {
                "symbol": "NVDA",
                "quantity": 100,
            },
            {
                "symbol": "SPCX",
                "quantity": 50,
            },
        ]


def test_stock_positions_are_not_reported_as_unsupported(
    monkeypatch,
):
    monkeypatch.setattr(
        position_service.market_data,
        "get_snapshot",
        lambda: {},
    )

    monkeypatch.setattr(
        position_service,
        "_invoke_position_reconcile",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        position_service,
        "_get_open_journal_candidates_for_context",
        lambda **kwargs: [],
    )

    result = (
        position_service.get_position_monitor(
            broker_client=StockOnlyBroker(),
            user_context={
                "role": "BETA",
            },
        )
    )

    assert (
        result["status"]
        == "NO_SUPPORTED_POSITIONS"
    )

    assert result["connected"] is True
    assert result["positions"] == []
    assert result["position_count"] == 0
    assert result["leg_count"] == 3

    assert (
        result["ignored_position_count"]
        == 3
    )

    assert (
        result["message"]
        ==
        (
            "No supported SPX option positions found. "
            "3 non-SPX/non-option position(s) were ignored."
        )
    )
