import os

from fastapi import APIRouter, Depends

from bxk_app import config
from bxk_app.authorization import require_owner
from bxk_app.database import database_health_status


router = APIRouter(
    prefix="/api/admin/commercial-readiness",
    tags=["Commercial Readiness"],
)


def _configured(value) -> bool:
    return bool(
        str(value or "").strip()
    )


@router.get("")
def commercial_readiness(
    _owner: dict = Depends(require_owner),
):
    database = database_health_status()

    auth = {
        "enabled": bool(
            config.BXK_AUTH_ENABLED
        ),
        "secure_cookie": bool(
            config.BXK_AUTH_COOKIE_SECURE
        ),
        "session_secret_configured":
            len(
                str(
                    config.BXK_SESSION_SECRET
                    or ""
                )
            ) >= 32,
    }

    security = {
        "broker_credential_key_configured":
            _configured(
                config.BXK_BROKER_CREDENTIAL_KEY
            ),
        "live_trading_enabled": bool(
            config.BXK_LIVE_TRADING_ENABLED
        ),
        "review_demo_enabled": bool(
            config.BXK_REVIEW_DEMO_ENABLED
        ),
    }

    schwab = {
        "client_id_configured":
            _configured(
                config.SCHWAB_CLIENT_ID
            ),
        "client_secret_configured":
            _configured(
                config.SCHWAB_CLIENT_SECRET
            ),
        "redirect_uri_configured":
            _configured(
                config.SCHWAB_REDIRECT_URI
            ),
        "commercial_approval":
            "PENDING_EXTERNAL_APPROVAL",
    }

    operational_email = {
        "recipient_configured": _configured(
            os.getenv(
                "BXK_SUPPORT_EMAIL",
                os.getenv(
                    "BXK_APP_EMAIL",
                    "",
                ),
            )
        ),
        "sender_configured": _configured(
            os.getenv(
                "BXK_SMTP_FROM",
                "",
            )
        ),
        "provider_key_configured": _configured(
            os.getenv(
                "BXK_RESEND_API_KEY",
                os.getenv(
                    "BXK_SMTP_PASSWORD",
                    "",
                ),
            )
        ),
    }

    stripe = {
        "billing_enabled": bool(
            config.BXK_BILLING_ENABLED
        ),
        "subscription_enforcement_enabled":
            bool(
                config
                .BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED
            ),
        "secret_key_configured":
            _configured(
                config.STRIPE_SECRET_KEY
            ),
        "webhook_secret_configured":
            _configured(
                config.STRIPE_WEBHOOK_SECRET
            ),
        "monthly_price_configured":
            _configured(
                config.STRIPE_PRICE_PRO_MONTHLY
            ),
        "annual_price_configured":
            _configured(
                config.STRIPE_PRICE_PRO_ANNUAL
            ),
        "public_app_url":
            config.BXK_PUBLIC_APP_URL,
    }

    checks = {
        "authentication_ready": (
            auth["enabled"]
            and auth[
                "session_secret_configured"
            ]
        ),
        "database_ready": bool(
            database.get("connected")
            and database.get(
                "users_table_present"
            )
        ),
        "broker_secret_storage_ready":
            security[
                "broker_credential_key_configured"
            ],
        "schwab_oauth_configured": all([
            schwab[
                "client_id_configured"
            ],
            schwab[
                "client_secret_configured"
            ],
            schwab[
                "redirect_uri_configured"
            ],
        ]),
        "stripe_checkout_configured": all([
            stripe[
                "secret_key_configured"
            ],
            stripe[
                "webhook_secret_configured"
            ],
            (
                stripe[
                    "monthly_price_configured"
                ]
                or stripe[
                    "annual_price_configured"
                ]
            ),
        ]),
        "reviewer_safe_mode": not bool(
            config.BXK_LIVE_TRADING_ENABLED
        ),
        "production_demo_hidden": not bool(
            config.BXK_REVIEW_DEMO_ENABLED
        ),
        "operational_email_ready": all([
            operational_email[
                "recipient_configured"
            ],
            operational_email[
                "sender_configured"
            ],
            operational_email[
                "provider_key_configured"
            ],
        ]),
    }

    ready_count = sum(
        value is True
        for value in checks.values()
    )

    return {
        "checks": checks,
        "ready_count": ready_count,
        "check_count": len(checks),
        "auth": auth,
        "database": database,
        "security": security,
        "schwab": schwab,
        "stripe": stripe,
        "operational_email":
            operational_email,
    }
