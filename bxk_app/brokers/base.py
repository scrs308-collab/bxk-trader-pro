from abc import ABC, abstractmethod


class BrokerBase(ABC):
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
    