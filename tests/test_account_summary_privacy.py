from bxk_app.routes.broker import (
    _mask_account_summary_payload,
)


def test_account_summary_masks_account_identifiers():
    payload = {
        "connected": True,
        "account": {
            "number": "12345678",
            "account_number": "ABCDEFGH",
            "net_liquidation": 10000.0,
        },
    }

    result = _mask_account_summary_payload(
        payload
    )

    assert (
        result["account"]["number"]
        == "****5678"
    )

    assert (
        result["account"]["account_number"]
        == "****EFGH"
    )

    assert (
        result["account"]["net_liquidation"]
        == 10000.0
    )

    # Sanitizing the API response must not mutate
    # the broker's original internal object.
    assert (
        payload["account"]["number"]
        == "12345678"
    )
