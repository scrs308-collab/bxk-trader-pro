from pathlib import Path


MIGRATION = Path(
    "alembic/versions/"
    "c2e8a4f71b36_"
    "add_user_broker_oauth_permission.py"
)


def test_broker_oauth_permission_migration_structure():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert (
        'revision = "c2e8a4f71b36"'
        in text
    )

    assert (
        'down_revision = "b7e4c2d9f6a1"'
        in text
    )

    assert '"broker_oauth_enabled"' in text
    assert "server_default=sa.false()" in text
    assert "lower(username) = 'kdixon'" in text
