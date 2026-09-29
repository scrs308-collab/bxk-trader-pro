"""Authenticated trader's buying power reserve."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from bxk_app.authorization import require_owner_or_beta
from bxk_app.config import BXK_MIN_REMAINING_BUYING_POWER
from bxk_app.database import get_db
from bxk_app.db_models.user import User

router = APIRouter(prefix="/api", tags=["Buying Power Settings"])


class ReserveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_remaining_buying_power: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


def _current_user(session: Session, context: dict) -> User:
    try:
        user_id = uuid.UUID(str(context.get("user_id")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(403, "A database-backed trader account is required.") from exc
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(403, "Trader account unavailable.")
    return user


@router.get("/my-buying-power-reserve")
def get_reserve(
    context: dict = Depends(require_owner_or_beta),
    session: Session = Depends(get_db),
):
    user = _current_user(session, context)
    effective = user.min_remaining_buying_power
    return {
        "min_remaining_buying_power": float(
            BXK_MIN_REMAINING_BUYING_POWER if effective is None else effective
        ),
        "user_override": effective is not None,
    }


@router.put("/my-buying-power-reserve")
def update_reserve(
    payload: ReserveUpdate,
    context: dict = Depends(require_owner_or_beta),
    session: Session = Depends(get_db),
):
    user = _current_user(session, context)
    user.min_remaining_buying_power = payload.min_remaining_buying_power
    session.commit()
    return get_reserve(context, session)
