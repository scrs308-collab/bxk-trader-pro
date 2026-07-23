from fastapi import APIRouter

from bxk_app.services.position_service import (
    get_position_monitor,
)


router = APIRouter(
    prefix="/api",
    tags=["Positions"],
)


@router.get("/position-monitor")
def position_monitor():
    return get_position_monitor()