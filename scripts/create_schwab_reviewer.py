"""Create a tightly controlled Schwab reviewer account.

The script is intentionally dry-run by default. It never prints the temporary
password and does not create broker connections or enable live trading.

Usage:
    BXK_REVIEWER_USERNAME=schwab-reviewer \
    BXK_REVIEWER_EMAIL=reviewer@example.com \
    BXK_REVIEWER_TEMP_PASSWORD='temporary-secret' \
    python scripts/create_schwab_reviewer.py

Apply only after reviewing the dry-run output:
    python scripts/create_schwab_reviewer.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import func, select

from bxk_app.database import get_session_factory
from bxk_app.db_models.user import User
from bxk_app.services.admin_user_service import create_user
from bxk_app.services.subscription_service import (
    set_manual_subscription_access,
)


def _required_env(name: str) -> str:
    value = str(
        os.getenv(name, "")
    ).strip()

    if not value:
        raise ValueError(
            f"{name} is required."
        )

    return value


def reviewer_settings() -> dict:
    username = _required_env(
        "BXK_REVIEWER_USERNAME"
    )
    email = _required_env(
        "BXK_REVIEWER_EMAIL"
    )
    password = str(
        os.getenv(
            "BXK_REVIEWER_TEMP_PASSWORD",
            "",
        )
    )

    if len(password) < 12:
        raise ValueError(
            "BXK_REVIEWER_TEMP_PASSWORD must "
            "be at least 12 characters."
        )

    return {
        "username": username,
        "email": email,
        "temporary_password": password,
    }


def create_reviewer(*, apply: bool) -> int:
    settings = reviewer_settings()

    print(
        "Schwab reviewer account plan:"
    )
    print(
        f"  username: {settings['username']}"
    )
    print(
        f"  email: {settings['email']}"
    )
    print("  role: BETA")
    print("  broker connect: disabled")
    print("  live trading: disabled")
    print("  SMS alerts: disabled")
    print("  subscription access: manual reviewer access")
    print("  password change on first login: required")
    print("  temporary password: [not displayed]")

    if not apply:
        print(
            "\nDry run only. Re-run with --apply "
            "to create the account."
        )
        return 0

    factory = get_session_factory()

    with factory() as session:
        existing = session.scalar(
            select(User).where(
                (
                    func.lower(User.username)
                    == settings[
                        "username"
                    ].casefold()
                )
                | (
                    func.lower(User.email)
                    == settings[
                        "email"
                    ].casefold()
                )
            )
        )

        if existing is not None:
            raise ValueError(
                "Reviewer username or email "
                "already exists."
            )

        created = create_user(
            session,
            username=settings[
                "username"
            ],
            email=settings["email"],
            role="BETA",
            temporary_password=settings[
                "temporary_password"
            ],
        )

        user = session.get(
            User,
            created["id"],
        )

        if user is None:
            raise RuntimeError(
                "Reviewer account was created "
                "but could not be reloaded."
            )

        # Explicitly lock down reviewer capabilities.
        user.broker_oauth_enabled = False
        user.sms_alerts_enabled = False
        user.sms_phone_e164 = None
        user.preferred_broker = None
        user.must_change_password = True

        session.commit()

        set_manual_subscription_access(
            session,
            user_id=str(user.id),
            granted=True,
        )

        print(
            "\nReviewer account created safely."
        )
        print(
            f"  user_id: {user.id}"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Create the reviewer account. "
            "Without this flag, only a dry run "
            "is performed."
        ),
    )

    args = parser.parse_args()

    try:
        return create_reviewer(
            apply=args.apply
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
