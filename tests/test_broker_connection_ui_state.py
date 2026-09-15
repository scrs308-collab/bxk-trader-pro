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



def test_tastytrade_oauth_button_is_owner_gated():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert (
        'from "./access-control.js"'
        in text
    )

    assert (
        "hasOwnerAccess"
        in text
    )

    assert (
        "const ownerCanConnect"
        in text
    )

    assert (
        "if (!ownerCanConnect)"
        in text
    )

    assert (
        "Tastytrade self-service connection is"
        in text
    )

    assert (
        "temporarily unavailable for beta accounts"
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
