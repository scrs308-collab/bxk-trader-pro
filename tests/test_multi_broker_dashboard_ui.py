from pathlib import Path


DASHBOARD = Path(
    "static/dashboard.js"
).read_text(
    encoding="utf-8"
)


def test_dashboard_exposes_multi_broker_controls():
    assert (
        "Account & Trading Status"
        in DASHBOARD
    )

    assert (
        "Account Data Source"
        in DASHBOARD
    )

    assert (
        "Execution Broker"
        in DASHBOARD
    )

    assert (
        "Connect Schwab"
        in DASHBOARD
    )

    assert (
        "Reconnect Schwab"
        in DASHBOARD
    )

    assert (
        "Select account"
        in DASHBOARD
    )


def test_dashboard_uses_multi_broker_endpoints():
    assert (
        "/api/broker-connection/status"
        in DASHBOARD
    )

    assert (
        "/api/broker-connection/brokers"
        in DASHBOARD
    )

    assert (
        "/api/broker-connection/schwab/connect"
        in DASHBOARD
    )

    assert (
        "/api/broker-connection/schwab/accounts"
        in DASHBOARD
    )

    assert (
        "select-schwab-account"
        in DASHBOARD
    )

    assert (
        "select-broker"
        in DASHBOARD
    )


def test_dashboard_keeps_execution_broker_explicit():
    assert (
        "Execution Broker remains Tastytrade only."
        in DASHBOARD
    )

    assert (
        "Schwab is read-only in this phase."
        in DASHBOARD
    )

    assert (
        "Changing the Account Data Source does not"
        in DASHBOARD
    )


def test_dashboard_preserves_beta_safe_mode_copy():
    assert (
        "SAFE MODE"
        in DASHBOARD
    )

    assert (
        "real orders cannot"
        in DASHBOARD
    )

    assert (
        "BXK OWNER"
        in DASHBOARD
    )


def test_dashboard_refreshes_after_broker_changes():
    assert (
        "bxk:broker-connection-changed"
        in DASHBOARD
    )

    assert (
        "dashboard-broker-controls"
        in DASHBOARD
    )


def test_dashboard_accepts_wrapped_schwab_accounts():
    assert (
        "schwabAccounts?.accounts"
        in DASHBOARD
    )

    assert (
        "schwabAccountList"
        in DASHBOARD
    )



def test_dashboard_supports_tastytrade_account_selection():
    assert (
        "/api/broker-connection/"
        "tastytrade/accounts"
        in DASHBOARD
    )

    assert (
        "select-tastytrade-account"
        in DASHBOARD
    )

    assert (
        "tastytradeAccountList"
        in DASHBOARD
    )

    assert (
        "tastytradeAccounts?.accounts"
        in DASHBOARD
    )


def test_dashboard_handles_tastytrade_oauth_callback():
    assert (
        'callbackBroker === "tastytrade"'
        in DASHBOARD
    )

    assert (
        "Tastytrade authorization completed successfully."
        in DASHBOARD
    )

    assert (
        "Tastytrade is connected. Select the account"
        in DASHBOARD
    )

    assert (
        "Tastytrade authorization needs attention."
        in DASHBOARD
    )
