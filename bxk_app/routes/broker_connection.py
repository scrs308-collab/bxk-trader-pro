from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    get_authenticated_user,
)
from bxk_app.database import get_db
from bxk_app.services import (
    broker_connection_service,
)
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerVerificationError,
)


router = APIRouter(
    prefix="/api/broker-connection",
    tags=["Broker Connection"],
)


class TastytradeVerifyRequest(
    BaseModel
):
    client_secret: str = Field(
        min_length=1,
    )

    refresh_token: str = Field(
        min_length=1,
    )


class TastytradeConnectRequest(
    TastytradeVerifyRequest
):
    account_number: str | None = None


@router.get("/status")
def broker_connection_status(
    user_context: dict = Depends(
        get_authenticated_user
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        return (
            broker_connection_service
            .get_broker_connection_status(
                session,
                user_context=user_context,
            )
        )

    except BrokerConnectionInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/verify")
def verify_tastytrade_connection(
    request_data: TastytradeVerifyRequest,
    _user_context: dict = Depends(
        get_authenticated_user
    ),
):
    try:
        accounts = (
            broker_connection_service
            .verify_tastytrade_credentials(
                client_secret=(
                    request_data
                    .client_secret
                ),
                refresh_token=(
                    request_data
                    .refresh_token
                ),
            )
        )

        return {
            "verified": True,
            "accounts": accounts,
        }

    except BrokerVerificationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/connect")
def connect_tastytrade(
    request_data: TastytradeConnectRequest,
    user_context: dict = Depends(
        get_authenticated_user
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        return (
            broker_connection_service
            .connect_tastytrade_account(
                session,
                user_context=user_context,
                client_secret=(
                    request_data
                    .client_secret
                ),
                refresh_token=(
                    request_data
                    .refresh_token
                ),
                account_number=(
                    request_data
                    .account_number
                ),
            )
        )

    except (
        BrokerConnectionInvalid,
        BrokerVerificationError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.delete("")
def disconnect_tastytrade(
    user_context: dict = Depends(
        get_authenticated_user
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        disconnected = (
            broker_connection_service
            .disconnect_tastytrade_account(
                session,
                user_context=user_context,
            )
        )

        return {
            "disconnected":
                disconnected,
            "status": (
                broker_connection_service
                .get_broker_connection_status(
                    session,
                    user_context=(
                        user_context
                    ),
                )
            ),
        }

    except BrokerConnectionInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
