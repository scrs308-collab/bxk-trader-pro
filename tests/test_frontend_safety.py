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

def test_broker_preflight_displays_specific_error():
    source = Path(
        "static/best-trade.js"
    ).read_text(encoding="utf-8")

    specific_error = (
        "result?.errors?.[0] ||"
    )
    generic_message = (
        "result?.message ||"
    )

    error_block_start = source.index(
        "const errorMessage ="
    )
    error_block_end = source.index(
        '"Tastytrade broker preflight did not pass."',
        error_block_start,
    )

    error_block = source[
        error_block_start:error_block_end
    ]

    assert specific_error in error_block
    assert generic_message in error_block
    assert (
        error_block.index(specific_error)
        < error_block.index(generic_message)
    )
