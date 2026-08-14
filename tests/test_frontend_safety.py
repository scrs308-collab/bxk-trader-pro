from pathlib import Path


def test_unconfirmed_submission_requires_broker_verification():
    source = Path(
        "static/best-trade.js"
    ).read_text(encoding="utf-8")

    assert "SUBMISSION_UNCONFIRMED" in source
    assert (
        "VERIFY TASTYTRADE - DO NOT RETRY"
        in source
    )
    assert '"VERIFY TASTYTRADE"' in source
