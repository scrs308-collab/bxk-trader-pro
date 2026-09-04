from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    get_authenticated_user,
)
from bxk_app.database import get_db
from bxk_app.services.broker_connection_service import (
    BrokerConnectionInvalid,
    BrokerConnectionRequired,
    get_broker_connection_status,
    resolve_tastytrade_broker,
)
from bxk_app.services.position_service import (
    get_position_monitor,
)


router = APIRouter(
    prefix="/api",
    tags=["Positions"],
)


def _position_user_context(
    request_user: dict = Depends(
        get_authenticated_user
    ),
):
    return request_user


@router.get("/position-monitor")
def position_monitor(
    user_context: dict = Depends(
        _position_user_context
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        status = (
            get_broker_connection_status(
                session,
                user_context=
                    user_context,
            )
        )

        # Preserve Joe's current production Position
        # Monitor path until the OWNER account is
        # explicitly migrated into broker_connections.
        if (
            status.get("source")
            == "legacy_owner"
        ):
            return get_position_monitor(
                user_context=
                    user_context,
            )

        broker_client = (
            resolve_tastytrade_broker(
                session,
                user_context=
                    user_context,
            )
        )

        return get_position_monitor(
            broker_client=
                broker_client,
            user_context=
                user_context,
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
