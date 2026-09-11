import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import RedirectResponse
from pydantic import (
    BaseModel,
    Field,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    require_owner_or_beta,
)
from bxk_app.database import get_db
from bxk_app.services import (
    broker_connection_service,
    schwab_connection_service,
    schwab_oauth_service,
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
        require_owner_or_beta
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
        require_owner_or_beta
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
        require_owner_or_beta
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
        require_owner_or_beta
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


def _database_user_id(
    user_context: dict,
) -> uuid.UUID:
    raw_user_id = user_context.get(
        "user_id"
    )

    if raw_user_id in (
        None,
        "",
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "A database-backed user "
                "account is required."
            ),
        )

    try:
        return uuid.UUID(
            str(raw_user_id)
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Authenticated user ID "
                "is invalid."
            ),
        ) from exc


def _mask_account_number(
    account_number: str,
) -> str:
    value = str(
        account_number or ""
    ).strip()

    if not value:
        return ""

    if len(value) <= 4:
        return "*" * len(value)

    return (
        "*" * (
            len(value) - 4
        )
        + value[-4:]
    )


@router.get("/schwab/connect")
def connect_schwab(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
    session: Session = Depends(
        get_db
    ),
):
    user_id = _database_user_id(
        user_context
    )

    try:
        result = (
            schwab_connection_service
            .begin_schwab_oauth(
                session,
                user_id=user_id,
            )
        )
    except (
        schwab_connection_service
        .SchwabConnectionError,
        schwab_oauth_service
        .SchwabOAuthError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=result[
            "authorization_url"
        ],
        status_code=303,
    )


@router.get("/schwab/callback")
def schwab_callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(
        get_db
    ),
):
    if error:
        if state:
            (
                schwab_connection_service
                .cancel_schwab_oauth(
                    session,
                    state=state,
                )
            )

        return RedirectResponse(
            url=(
                "/?broker=schwab"
                "&status=denied"
            ),
            status_code=303,
        )

    if not state or not code:
        raise HTTPException(
            status_code=400,
            detail=(
                "Schwab OAuth callback is "
                "missing required parameters."
            ),
        )

    try:
        result = (
            schwab_connection_service
            .complete_schwab_oauth(
                session,
                state=state,
                code=code,
            )
        )
    except (
        schwab_connection_service
        .SchwabOAuthStateInvalid
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except (
        schwab_connection_service
        .SchwabConnectionError
    ):
        return RedirectResponse(
            url=(
                "/?broker=schwab"
                "&status=error"
            ),
            status_code=303,
        )

    if result.get(
        "account_number"
    ):
        status = "connected"
    else:
        status = "select-account"

    return RedirectResponse(
        url=(
            "/?broker=schwab"
            f"&status={status}"
        ),
        status_code=303,
    )


@router.get("/schwab/accounts")
def schwab_accounts(
    user_context: dict = Depends(
        require_owner_or_beta
    ),
    session: Session = Depends(
        get_db
    ),
):
    user_id = _database_user_id(
        user_context
    )

    accounts = (
        schwab_connection_service
        .list_schwab_accounts(
            session,
            user_id=user_id,
        )
    )

    safe_accounts = []

    for account in accounts:
        safe_accounts.append({
            "id":
                account["id"],
            "account_number_masked":
                _mask_account_number(
                    account[
                        "account_number"
                    ]
                ),
            "nickname":
                account.get(
                    "nickname"
                ),
            "account_type":
                account.get(
                    "account_type"
                ),
            "is_default":
                bool(
                    account.get(
                        "is_default"
                    )
                ),
            "is_active":
                bool(
                    account.get(
                        "is_active"
                    )
                ),
        })

    return {
        "broker": "schwab",
        "accounts": safe_accounts,
    }


@router.post(
    "/schwab/accounts/{account_id}/select"
)
def select_schwab_account(
    account_id: uuid.UUID,
    user_context: dict = Depends(
        require_owner_or_beta
    ),
    session: Session = Depends(
        get_db
    ),
):
    user_id = _database_user_id(
        user_context
    )

    try:
        account = (
            schwab_connection_service
            .select_schwab_account(
                session,
                user_id=user_id,
                account_id=account_id,
            )
        )
    except (
        schwab_connection_service
        .SchwabAccountSelectionError
    ) as exc:
        raise HTTPException(
            status_code=404,
            detail="Schwab account not found.",
        ) from exc

    return {
        "broker":
            "schwab",
        "selected":
            True,
        "account": {
            "id":
                account["id"],
            "account_number_masked":
                _mask_account_number(
                    account[
                        "account_number"
                    ]
                ),
            "nickname":
                account.get(
                    "nickname"
                ),
            "account_type":
                account.get(
                    "account_type"
                ),
            "is_default":
                True,
        },
    }

