from pathlib import Path


MIGRATION = Path(
    "alembic/versions/"
    "3e8a7c1d9b42_add_stripe_event_ordering.py"
)


def test_stripe_event_ordering_migration_is_chained():
    source = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert 'revision = "3e8a7c1d9b42"' in source
    assert (
        'down_revision = "f2b8c4d1e690"'
        in source
    )
    assert '"provider_event_created_at"' in source
    assert '"provider_event_id"' in source
