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
