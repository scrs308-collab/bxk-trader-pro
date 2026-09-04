import copy
import uuid

from sqlalchemy.orm import Session

from bxk_app.db_models.execution_audit import (
    ExecutionAudit,
)


def _user_id(
    user_context: dict,
) -> uuid.UUID:
    if not isinstance(
        user_context,
        dict,
    ):
        raise ValueError(
            "Authenticated user context is required."
        )

    raw_user_id = user_context.get(
        "user_id"
    )

    if not raw_user_id:
        raise ValueError(
            "Database-backed user ID is required."
        )

    if isinstance(
        raw_user_id,
        uuid.UUID,
    ):
        return raw_user_id

    try:
        return uuid.UUID(
            str(raw_user_id)
        )
    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as exc:
        raise ValueError(
            "Authenticated user ID is invalid."
        ) from exc


def _masked_account(
    account,
):
    value = str(
        account or ""
    ).strip()

    if not value:
        return None

    if len(value) < 4:
        return "***"

    return (
        "***"
        + value[-4:]
    )


def _review_reference(
    review_id,
):
    value = str(
        review_id or ""
    ).strip()

    if not value:
        return None

    return value[:12]


def _safe_order(
    order,
):
    if not isinstance(
        order,
        dict,
    ):
        return None

    allowed = {
        "strategy",
        "symbol",
        "quantity",
        "limit_price",
        "credit",
        "max_profit",
        "max_risk",
        "buying_power",
        "expiration",
        "dte",
        "wing_width",
        "legs",
    }

    return copy.deepcopy(
        {
            key: value
            for key, value
            in order.items()
            if key in allowed
        }
    )


def write_user_order_audit(
    session: Session,
    *,
    user_context: dict,
    event,
    status=None,
    reason_code=None,
    review_id=None,
    account=None,
    order_id=None,
    broker_status=None,
    order=None,
) -> dict:
    clean_event = str(
        event or ""
    ).strip().upper()

    if not clean_event:
        raise ValueError(
            "Audit event is required."
        )

    audit = ExecutionAudit(
        user_id=_user_id(
            user_context
        ),
        broker="tastytrade",
        event=clean_event,
        status=(
            str(status).strip()
            if status is not None
            else None
        ),
        reason_code=(
            str(reason_code).strip()
            if reason_code is not None
            else None
        ),
        review_reference=(
            _review_reference(
                review_id
            )
        ),
        account_masked=(
            _masked_account(
                account
            )
        ),
        order_id=(
            str(order_id).strip()
            if order_id is not None
            else None
        ),
        broker_status=(
            str(broker_status).strip()
            if broker_status is not None
            else None
        ),
        order_snapshot=(
            _safe_order(
                order
            )
        ),
    )

    session.add(
        audit
    )

    session.commit()
    session.refresh(
        audit
    )

    return {
        "id": str(
            audit.id
        ),
        "user_id": str(
            audit.user_id
        ),
        "event": audit.event,
        "status": audit.status,
        "reason_code": audit.reason_code,
        "review_reference":
            audit.review_reference,
        "account": audit.account_masked,
        "order_id": audit.order_id,
        "broker_status":
            audit.broker_status,
    }
