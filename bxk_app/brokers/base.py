from abc import ABC, abstractmethod


class BrokerBase(ABC):
    """
    Broker-neutral interface used by BXK Trader Pro.

    Broker adapters may expose additional broker-specific methods, but
    application code should prefer this interface whenever possible.
    """

    broker_name = "unknown"

    capabilities = frozenset()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    @abstractmethod
    def authenticate(self):
        pass

    @abstractmethod
    def get_status(self):
        pass

    @abstractmethod
    def get_accounts(self):
        pass

    @abstractmethod
    def get_balances(self, account_number=None):
        pass

    @abstractmethod
    def get_positions(self, account_number=None):
        pass

    @abstractmethod
    def get_quote(self, symbol: str):
        pass

    def get_account_summary(self):
        """
        Return a Trader Pro normalized account summary.

        Broker implementations should translate their
        native balance payload into the common shape.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not provide "
            "a normalized account summary."
        )

    def get_position_summary(self):
        """
        Return Trader Pro normalized open-position legs.

        Broker implementations should translate native
        positions before returning them to Position Monitor.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not provide "
            "normalized position summaries."
        )

    def get_default_account_number(self):
        """
        Return the account selected for broker operations.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not support default account selection"
        )

    def get_order(self, order_id, account_number=None):
        """
        Fetch one broker order by ID.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not support order lookup"
        )

    def preview_order(self, order: dict, account_number=None):
        """
        Validate/preview an order without submitting it.

        Individual brokers implement this using whatever preflight
        mechanism their API provides.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not support order preview"
        )

    def submit_order(self, order: dict, account_number=None):
        """
        Submit a previously validated order.
        """
        raise NotImplementedError(
            f"{self.broker_name} does not support order submission"
        )

    def cancel_order(self, order_id, account_number=None):
        raise NotImplementedError(
            f"{self.broker_name} does not support order cancellation"
        )

    def replace_order(
        self,
        order_id,
        order: dict,
        account_number=None,
    ):
        raise NotImplementedError(
            f"{self.broker_name} does not support order replacement"
        )
