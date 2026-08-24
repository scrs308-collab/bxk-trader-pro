import json
import sys

from bxk_app.database import (
    database_configured,
    get_session_factory,
)
from bxk_app.services.user_service import (
    bootstrap_owner_user,
)


def run_owner_bootstrap() -> dict:
    if not database_configured():
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    session_factory = get_session_factory()

    with session_factory() as session:
        return bootstrap_owner_user(session)


def main() -> int:
    try:
        result = run_owner_bootstrap()

        # Safe output only. No email, username,
        # password hash, or database credentials.
        print(
            json.dumps(
                {
                    "configured":
                        result["configured"],
                    "created":
                        result["created"],
                    "existing":
                        result["existing"],
                    "user_id":
                        result["user_id"],
                },
                sort_keys=True,
            )
        )

        if not result["configured"]:
            return 2

        return 0

    except Exception as exc:
        print(
            "OWNER bootstrap failed: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
