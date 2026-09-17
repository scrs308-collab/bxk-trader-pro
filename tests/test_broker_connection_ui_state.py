from pathlib import Path


def test_personal_grant_form_survives_background_refresh():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert "brokerConnectionFlowActive = true" in text
    assert "brokerConnectionFlowActive = false" in text
    assert "if (brokerConnectionFlowActive)" in text

    assert (
        'id="tastytradePersonalGrantForm"'
        in text
    )

    assert (
        "/api/broker-connection/verify"
        in text
    )

    assert (
        'id="tastytradeClientSecret"'
        in text
    )

    assert (
        'id="tastytradeRefreshToken"'
        in text
    )

    assert (
        'type="password"'
        in text
    )

    assert (
        "localStorage"
        not in text
    )

    assert (
        "sessionStorage"
        not in text
    )



def test_tastytrade_personal_grant_form_is_permission_gated():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert (
        'from "./access-control.js?v=4"'
        in text
    )

    assert (
        "hasBrokerOAuthAccess"
        in text
    )

    assert (
        "const canConnect"
        in text
    )

    assert (
        "if (!canConnect)"
        in text
    )

    assert (
        "Broker Connect has not been enabled"
        in text
    )

    assert (
        "if this beta account should be approved"
        in text
    )

    assert (
        'id="verifyTastytradeGrantButton"'
        in text
    )

    assert (
        "/api/broker-connection/connect"
        in text
    )

    assert (
        "/api/broker-connection/"
        "tastytrade/connect"
        not in text
    )


def test_dashboard_builds_tastytrade_account_after_dependencies():
    text = Path(
        "static/dashboard.js"
    ).read_text(encoding="utf-8")

    account_list_position = text.index(
        "const activeTastytradeAccounts"
    )

    selected_account_position = text.index(
        "const selectedTastytradeAccount"
    )

    display_account_position = text.index(
        "const tastyAccount ="
    )

    assert (
        account_list_position
        < selected_account_position
        < display_account_position
    )
