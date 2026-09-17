from pathlib import Path


def test_beta_onboarding_status_ui_is_present():
    dashboard = Path(
        "static/dashboard.js"
    ).read_text(
        encoding="utf-8"
    )

    positions = Path(
        "static/position.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "Account & Trading Status" in dashboard
    assert "/api/broker-connection/status" in dashboard
    assert "SAFE MODE" in dashboard
    assert "real orders cannot" in dashboard
    assert "BXK OWNER" in dashboard

    assert (
        "bxk:broker-connection-changed"
        in dashboard
    )

    assert (
        "hasBrokerOAuthAccess"
        in positions
    )

    assert (
        "Broker Connect has not been enabled"
        in positions
    )

    assert (
        "/api/broker-connection/"
        "tastytrade/connect"
        in positions
    )

    assert (
        "brokerClientSecret"
        not in positions
    )

    assert (
        "brokerRefreshToken"
        not in positions
    )

    assert (
        "No open supported positions"
        in positions
    )

    assert (
        "No open SPX Iron Condor was found."
        not in positions
    )
