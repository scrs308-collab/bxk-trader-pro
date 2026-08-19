from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnderlyingConfig:
    symbol: str
    display_name: str
    instrument_type: str
    option_chain_symbol: str
    settlement: str
    exercise_style: str
    early_assignment_risk: bool
    volatility_reference: str
    expected_move_method: str
    default_wing_width: int


UNDERLYINGS = {
    "SPX": UnderlyingConfig(
        symbol="SPX",
        display_name="S&P 500 Index",
        instrument_type="INDEX",
        option_chain_symbol="SPX",
        settlement="CASH",
        exercise_style="EUROPEAN",
        early_assignment_risk=False,
        volatility_reference="VIX/VIX1D",
        expected_move_method="VOLATILITY_INDEX",
        default_wing_width=25,
    ),
    "QQQ": UnderlyingConfig(
        symbol="QQQ",
        display_name="Invesco QQQ ETF",
        instrument_type="ETF",
        option_chain_symbol="QQQ",
        settlement="PHYSICAL",
        exercise_style="AMERICAN",
        early_assignment_risk=True,
        volatility_reference="VXN",
        expected_move_method="OPTION_CHAIN",
        default_wing_width=5,
    ),
}


SUPPORTED_UNDERLYINGS = tuple(UNDERLYINGS)


def normalize_underlying(symbol: str) -> str:
    """
    Normalize a user/API supplied underlying symbol.
    """
    if not isinstance(symbol, str):
        raise ValueError("Underlying symbol must be a string.")

    normalized = symbol.strip().upper()

    if not normalized:
        raise ValueError("Underlying symbol cannot be empty.")

    return normalized


def get_underlying_config(symbol: str) -> UnderlyingConfig:
    """
    Return configuration for a supported underlying.

    Fail closed for unknown symbols so an unsupported underlying can
    never silently fall back to SPX.
    """
    normalized = normalize_underlying(symbol)

    try:
        return UNDERLYINGS[normalized]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported underlying: {normalized}"
        ) from exc


def is_supported_underlying(symbol: str) -> bool:
    """
    Return True only for explicitly configured underlyings.
    """
    try:
        normalized = normalize_underlying(symbol)
    except ValueError:
        return False

    return normalized in UNDERLYINGS
