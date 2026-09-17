from pathlib import Path


def test_connection_form_survives_background_refresh():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert "brokerConnectionFlowActive = true" in text
    assert "brokerConnectionFlowActive = false" in text
    assert "if (brokerConnectionFlowActive)" in text

    assert (
        'id="connectTastytradeButton"'
        in text
    )

    assert (
        "/api/broker-connection/"
        "tastytrade/connect"
        in text
    )

    assert (
        'id="brokerClientSecret"'
        not in text
    )

    assert (
        'id="brokerRefreshToken"'
        not in text
    )

    assert (
        'id="brokerAccountNumber"'
        not in text
    )

    assert (
        "/api/broker-connection/verify"
        not in text
    )



def test_tastytrade_oauth_button_is_permission_gated():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert (
        'from "./access-control.js?v=3"'
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
        'id="connectTastytradeButton"'
        in text
    )

    assert (
        "/api/broker-connection/"
        "tastytrade/connect"
        in text
    )
