from fastapi import APIRouter, Depends

from bxk_app.authorization import (
    require_owner_or_auth_disabled,
)

from bxk_app.services.position_service import (
    get_position_monitor,
)


router = APIRouter(
    prefix="/api",
    tags=["Positions"],
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)


@router.get("/position-monitor")
def position_monitor():
    return get_position_monitor()
