import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bxk_app import config
from bxk_app.db_models.user import (
    User,
    UserRole,
)


def get_owner_bootstrap_configuration() -> dict:
    username = str(
        config.BXK_APP_USERNAME or ""
    ).strip()

    email = str(
        os.getenv("BXK_APP_EMAIL", "") or ""
    ).strip()

    password_hash = str(
        config.BXK_APP_PASSWORD_HASH or ""
    ).strip()

    return {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "configured": bool(
            username
            and email
            and password_hash
        ),
    }


def bootstrap_owner_user(
    session: Session,
) -> dict:
    configuration = (
        get_owner_bootstrap_configuration()
    )

    if not configuration["configured"]:
        return {
            "configured": False,
            "created": False,
            "existing": False,
            "user_id": None,
        }

    username = configuration["username"]
    email = configuration["email"]
    password_hash = configuration[
        "password_hash"
    ]

    existing_username = session.scalar(
        select(User).where(
            func.lower(User.username)
            == username.casefold()
        )
    )

    if existing_username is not None:
        if existing_username.email.casefold() != (
            email.casefold()
        ):
            raise RuntimeError(
                "Configured OWNER username already "
                "exists with a different email."
            )

        return {
            "configured": True,
            "created": False,
            "existing": True,
            "user_id": str(
                existing_username.id
            ),
        }

    existing_email = session.scalar(
        select(User).where(
            func.lower(User.email)
            == email.casefold()
        )
    )

    if existing_email is not None:
        raise RuntimeError(
            "Configured OWNER email already "
            "belongs to another user."
        )

    owner = User(
        username=username,
        email=email,
        password_hash=password_hash,
        role=UserRole.OWNER,
        is_active=True,
        must_change_password=False,
    )

    session.add(owner)
    session.commit()
    session.refresh(owner)

    return {
        "configured": True,
        "created": True,
        "existing": False,
        "user_id": str(owner.id),
    }
