from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from bxk_app.authorization import (
    require_owner_or_auth_disabled,
)

from bxk_app.services.system_settings_service import (
    get_system_settings,
    update_system_settings,
)


router = APIRouter(
    prefix="/api",
    tags=["System Settings"],
    dependencies=[
        Depends(
            require_owner_or_auth_disabled
        )
    ],
)


class SystemSettingsUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    app_username: str | None = None
    app_password: str | None = None

    tastytrade_client_id: str | None = None
    tastytrade_client_secret: str | None = None
    tastytrade_refresh_token: str | None = None
    tastytrade_username: str | None = None
    tastytrade_password: str | None = None
    tastytrade_account_number: str | None = None
    tastytrade_base_url: str | None = None

    max_order_risk: float | None = None
    min_order_credit: float | None = None
    min_remaining_buying_power: float | None = None


@router.get("/system-settings")
def system_settings():
    return get_system_settings()


@router.post("/system-settings")
def save_system_settings(
    settings: SystemSettingsUpdate,
):
    try:
        return update_system_settings(
            settings.model_dump(
                exclude_none=True,
            )
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
