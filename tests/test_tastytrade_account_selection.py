from bxk_app.brokers import tastytrade as tastytrade_module
from bxk_app.brokers.tastytrade import TastytradeBroker


def account_item(account_number):
    return {
        "account": {
            "account-number": account_number,
        }
    }


def test_configured_account_is_selected_not_first(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        tastytrade_module,
        "TASTYTRADE_ACCOUNT_NUMBER",
        "BXK7178",
    )

    monkeypatch.setattr(
        broker,
        "get_accounts",
        lambda: [
            account_item("WRONG0001"),
            account_item("BXK7178"),
        ],
    )

    assert (
        broker.get_first_account_number()
        == "BXK7178"
    )
    assert broker.last_error is None


def test_missing_configured_account_fails_closed(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        tastytrade_module,
        "TASTYTRADE_ACCOUNT_NUMBER",
        "BXK7178",
    )

    monkeypatch.setattr(
        broker,
        "get_accounts",
        lambda: [
            account_item("WRONG0001"),
        ],
    )

    assert broker.get_first_account_number() is None
    assert (
        broker.last_error
        == "Configured Tastytrade account was not returned."
    )


def test_unconfigured_account_fails_closed(
    monkeypatch,
):
    broker = TastytradeBroker()

    monkeypatch.setattr(
        tastytrade_module,
        "TASTYTRADE_ACCOUNT_NUMBER",
        "",
    )

    def accounts_must_not_be_requested():
        raise AssertionError(
            "Accounts requested without a configured target."
        )

    monkeypatch.setattr(
        broker,
        "get_accounts",
        accounts_must_not_be_requested,
    )

    assert broker.get_first_account_number() is None
    assert (
        broker.last_error
        == "TASTYTRADE_ACCOUNT_NUMBER is not configured."
    )
