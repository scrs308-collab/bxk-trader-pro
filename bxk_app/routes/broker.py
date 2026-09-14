from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    require_owner_or_beta,
    require_owner_or_auth_disabled,
)
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    get_broker_connection_status,
    get_user_preferred_broker_name,
    resolve_preferred_broker,
)
from bxk_app.services.broker_service import (
    get_account_summary,
    get_positions_summary,
    get_test_new_broker,
    get_test_quote,
    get_test_tastytrade,
    get_test_tastytrade_balances,
    get_test_tastytrade_positions,
    get_test_tastytrade_rest,
)


router = APIRouter(
    prefix="/api",
    tags=["Broker"],
)

OWNER_ONLY = [
    Depends(
        require_owner_or_auth_disabled
    )
]


@router.get(
    "/test-tastytrade",
    dependencies=OWNER_ONLY,
)
def test_tastytrade():
    return get_test_tastytrade()


@router.get(
    "/test-tastytrade-rest",
    dependencies=OWNER_ONLY,
)
def test_tastytrade_rest():
    return get_test_tastytrade_rest()


@router.get(
    "/test-tastytrade-balances",
    dependencies=OWNER_ONLY,
)
def test_tastytrade_balances():
    return get_test_tastytrade_balances()


@router.get(
    "/test-tastytrade-positions",
    dependencies=OWNER_ONLY,
)
def test_tastytrade_positions():
    return get_test_tastytrade_positions()


@router.get(
    "/positions-summary",
    dependencies=OWNER_ONLY,
)
def positions_summary():
    return get_positions_summary()


def _mask_account_identifier(value):
    text = str(value or "").strip()

    if not text:
        return value

    suffix = (
        text[-4:]
        if len(text) >= 4
        else text
    )

    return f"****{suffix}"


def _mask_account_summary_payload(payload):
    if not isinstance(payload, dict):
        return payload

    safe_payload = dict(payload)

    account = safe_payload.get("account")

    if not isinstance(account, dict):
        return safe_payload

    safe_account = dict(account)

    for key in (
        "number",
        "account_number",
    ):
        if safe_account.get(key):
            safe_account[key] = (
                _mask_account_identifier(
                    safe_account[key]
                )
            )

    safe_payload["account"] = safe_account

    return safe_payload


@router.get("/account-summary")
def account_summary(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        preferred_broker = (
            get_user_preferred_broker_name(
                session,
                user_context=user_context,
            )
        )

        if preferred_broker == "tastytrade":
            status = (
                get_broker_connection_status(
                    session,
                    user_context=user_context,
                )
            )

            if (
                status.get("source")
                == "legacy_owner"
            ):
                return _mask_account_summary_payload(
                get_account_summary()
            )

        broker_client = (
            resolve_preferred_broker(
                session,
                user_context=user_context,
            )
        )

        return _mask_account_summary_payload(
            get_account_summary(
                broker_client=broker_client,
            )
        )

    except BrokerConnectionRequired as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except BrokerConnectionInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/test-quote/{symbol}",
    dependencies=OWNER_ONLY,
)
def test_quote(symbol: str):
    return get_test_quote(symbol)


@router.get(
    "/test-new-broker",
    dependencies=OWNER_ONLY,
)
def test_new_broker():
    return get_test_new_broker()
