"""
=========================================================
BXK TRADER PRO
Execution Engine
=========================================================

Purpose
-------
Validates a completed trade before it is sent to
a broker.

This module DOES NOT communicate with any broker.

Responsibilities
----------------
• Validate trade parameters
• Validate contracts
• Validate credit
• Validate buying power
• Build execution package
• Return READY / NOT READY

Future
------
This engine will feed:

- Tastytrade
- Schwab
- Interactive Brokers
- Paper Trading
- Auto Trading

=========================================================
"""

from dataclasses import dataclass
from typing import Optional


# =========================================================
# Execution Result
# =========================================================

@dataclass
class ExecutionResult:
    ready: bool
    status: str
    reason: str

    strategy: str

    expiration: str

    contracts: int

    credit: float

    buying_power: float

    max_risk: float

    pop: float

    execution_package: Optional[dict] = None
# =========================================================
# Individual Validators
# =========================================================

# =========================================================
# Execution Engine
# =========================================================

class ExecutionEngine:

    # =====================================================
    # Individual Validators
    # =====================================================

    def validate_strategy(
        self,
        trade: dict,
    ) -> tuple[bool, str]:

        strategy = trade.get("strategy")

        if not strategy:
            return False, "Missing strategy"

        return True, ""


    def validate_contracts(
        self,
        trade: dict,
    ) -> tuple[bool, str]:

        contracts = trade.get(
            "contracts",
            0,
        )

        if contracts <= 0:
            return False, "Invalid contract quantity"

        return True, ""


    def validate_credit(
        self,
        trade: dict,
    ) -> tuple[bool, str]:

        credit = trade.get(
            "credit",
            0,
        )

        if credit <= 0:
            return False, "Invalid credit"

        return True, ""


    def validate_buying_power(
        self,
        trade: dict,
    ) -> tuple[bool, str]:

        buying_power = trade.get(
            "buying_power",
            0,
        )

        if buying_power <= 0:
            return False, "Buying power unavailable"

        return True, ""


    def validate_pop(
        self,
        trade: dict,
    ) -> tuple[bool, str]:

        pop = trade.get(
            "pop",
            0,
        )

        if pop < 60:
            return False, "POP below minimum"

        return True, ""


    # =====================================================
    # Main Validation
    # =====================================================

    def validate(
        self,
        trade: dict,
    ) -> ExecutionResult:
        """
        Validate a trade before execution.
        """

        checks = [
            self.validate_strategy(trade),
            self.validate_contracts(trade),
            self.validate_credit(trade),
            self.validate_buying_power(trade),
            self.validate_pop(trade),
        ]

        for passed, reason in checks:

            if not passed:

                return ExecutionResult(
                    ready=False,
                    status="NOT READY",
                    reason=reason,

                    strategy=trade.get(
                        "strategy",
                        "",
                    ),

                    expiration=trade.get(
                        "expiration",
                        "",
                    ),

                    contracts=trade.get(
                        "contracts",
                        0,
                    ),

                    credit=trade.get(
                        "credit",
                        0.0,
                    ),

                    buying_power=trade.get(
                        "buying_power",
                        0.0,
                    ),

                    max_risk=trade.get(
                        "max_risk",
                        0.0,
                    ),

                    pop=trade.get(
                        "pop",
                        0.0,
                    ),
                )

        return ExecutionResult(
            ready=True,
            status="READY",
            reason="All validation checks passed",

            strategy=trade.get(
                "strategy",
                "",
            ),

            expiration=trade.get(
                "expiration",
                "",
            ),

            contracts=trade.get(
                "contracts",
                0,
            ),

            credit=trade.get(
                "credit",
                0.0,
            ),

            buying_power=trade.get(
                "buying_power",
                0.0,
            ),

            max_risk=trade.get(
                "max_risk",
                0.0,
            ),

            pop=trade.get(
                "pop",
                0.0,
            ),
        )