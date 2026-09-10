from pathlib import Path


def test_connection_form_survives_background_refresh():
    text = Path(
        "static/position.js"
    ).read_text(encoding="utf-8")

    assert "brokerConnectionFlowActive = true" in text
    assert "brokerConnectionFlowActive = false" in text
    assert "if (brokerConnectionFlowActive)" in text
    assert 'id="brokerAccountNumber"' in text
    assert 'id="connectBrokerButton"' in text
