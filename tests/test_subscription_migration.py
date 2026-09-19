from pathlib import Path


MIGRATION = Path(
    "alembic/versions/"
    "f2b8c4d1e690_create_subscription_foundation.py"
)


def test_subscription_migration_has_expected_tables():
    source = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert 'revision = "f2b8c4d1e690"' in source
    assert (
        'down_revision = "d3f7a91c6b24"'
        in source
    )
    assert '"user_subscriptions"' in source
    assert '"billing_webhook_events"' in source
    assert '"provider_subscription_id"' in source
    assert '"manual_access_granted"' in source
