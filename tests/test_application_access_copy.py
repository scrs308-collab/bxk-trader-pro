from pathlib import Path


def test_access_request_does_not_imply_unsupported_brokers():
    text = Path(
        "static/application-access.html"
    ).read_text(
        encoding="utf-8"
    )

    assert "Fidelity" not in text
    assert "Interactive Brokers" not in text
    assert "Broker you currently use" in text
    assert (
        "does not imply that every broker is supported"
        in text
    )
