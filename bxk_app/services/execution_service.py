"""
Execution Service

Connects the recommendation engine
to the Execution Engine.
"""

from bxk_app.execution_engine import (
    ExecutionEngine,
)


engine = ExecutionEngine()


def validate_trade(
    trade: dict,
):
    """
    Validate a recommended trade.
    """

    return engine.validate(trade)