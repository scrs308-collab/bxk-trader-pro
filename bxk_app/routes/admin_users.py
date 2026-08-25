from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import (
    BaseModel,
    ConfigDict,
)
from sqlalchemy.orm import Session

from bxk_app.authorization import (
    require_owner,
)
from bxk_app.database import get_db
from bxk_app.services.admin_user_service import (
    create_user,
    list_users,
    set_user_active,
)


router = APIRouter(
    prefix="/api/admin/users",
    tags=["Admin Users"],
)


class AdminUserStatusUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    is_active: bool


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    username: str
    email: str
    role: Literal[
        "BETA",
        "VIEWER",
    ]
    temporary_password: str


@router.get("")
def admin_list_users(
    _owner: dict = Depends(
        require_owner
    ),
    session: Session = Depends(
        get_db
    ),
):
    return {
        "users": list_users(
            session
        ),
    }


@router.post(
    "",
    status_code=201,
)
def admin_create_user(
    request_data: AdminUserCreate,
    _owner: dict = Depends(
        require_owner
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        user = create_user(
            session,
            username=request_data.username,
            email=request_data.email,
            role=request_data.role,
            temporary_password=(
                request_data
                .temporary_password
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "user": user,
    }

@router.patch("/{user_id}/status")
def admin_set_user_status(
    user_id: str,
    request_data: AdminUserStatusUpdate,
    _owner: dict = Depends(
        require_owner
    ),
    session: Session = Depends(
        get_db
    ),
):
    try:
        user = set_user_active(
            session,
            user_id=user_id,
            is_active=request_data.is_active,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "user": user,
    }
