import pytest

from bxk_app.underlyings import (
    SUPPORTED_UNDERLYINGS,
    get_underlying_config,
    is_supported_underlying,
    normalize_underlying,
)


def test_supported_underlyings_are_spx_and_qqq():
    assert SUPPORTED_UNDERLYINGS == ("SPX", "QQQ")


def test_spx_configuration_preserves_current_behavior():
    config = get_underlying_config("SPX")

    assert config.symbol == "SPX"
    assert config.instrument_type == "INDEX"
    assert config.option_chain_symbol == "SPX"
    assert config.settlement == "CASH"
    assert config.exercise_style == "EUROPEAN"
    assert config.early_assignment_risk is False
    assert config.default_wing_width == 25


def test_qqq_configuration_has_assignment_protection_metadata():
    config = get_underlying_config("QQQ")

    assert config.symbol == "QQQ"
    assert config.instrument_type == "ETF"
    assert config.option_chain_symbol == "QQQ"
    assert config.settlement == "PHYSICAL"
    assert config.exercise_style == "AMERICAN"
    assert config.early_assignment_risk is True
    assert config.expected_move_method == "OPTION_CHAIN"
    assert config.default_wing_width == 5


def test_underlying_lookup_is_case_insensitive():
    assert get_underlying_config(" qqq ").symbol == "QQQ"
    assert normalize_underlying(" spx ") == "SPX"


def test_unknown_underlying_fails_closed():
    with pytest.raises(
        ValueError,
        match="Unsupported underlying",
    ):
        get_underlying_config("ABC")


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("SPX", True),
        ("QQQ", True),
        ("qqq", True),
        (" SPX ", True),
        ("IWM", False),
        ("", False),
    ],
)
def test_is_supported_underlying(symbol, expected):
    assert is_supported_underlying(symbol) is expected
