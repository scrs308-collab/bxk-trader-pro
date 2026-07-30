from bxk_app.execution_engine import ExecutionEngine


engine = ExecutionEngine()


def test_valid_trade():

    trade = {
        "strategy": "Iron Condor",
        "expiration": "2026-07-30",
        "contracts": 3,
        "credit": 1.65,
        "buying_power": 2505,
        "max_risk": 2505,
        "pop": 84,
    }

    result = engine.validate(trade)

    assert result.ready
    assert result.status == "READY"


def test_invalid_credit():

    trade = {
        "strategy": "Iron Condor",
        "expiration": "2026-07-30",
        "contracts": 3,
        "credit": 0,
        "buying_power": 2505,
        "max_risk": 2505,
        "pop": 84,
    }

    result = engine.validate(trade)

    assert not result.ready
    assert result.reason == "Invalid credit"


def test_invalid_contracts():

    trade = {
        "strategy": "Iron Condor",
        "expiration": "2026-07-30",
        "contracts": 0,
        "credit": 1.65,
        "buying_power": 2505,
        "max_risk": 2505,
        "pop": 84,
    }

    result = engine.validate(trade)

    assert not result.ready
    assert result.reason == "Invalid contract quantity"