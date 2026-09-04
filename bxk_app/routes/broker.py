from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    get_authenticated_user,
    require_owner_or_auth_disabled,
)
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    get_broker_connection_status,
    resolve_tastytrade_broker,
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


@router.get("/account-summary")
def account_summary(
    user_context: dict = Depends(
        get_authenticated_user
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
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
            return get_account_summary()

        broker_client = (
            resolve_tastytrade_broker(
                session,
                user_context=user_context,
            )
        )

        return get_account_summary(
            broker_client=broker_client,
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