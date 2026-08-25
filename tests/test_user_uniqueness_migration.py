from pathlib import Path


MIGRATION = Path(
    "alembic/versions/"
    "c91f4e2a7b10_add_case_insensitive_user_uniqueness.py"
)


def test_case_insensitive_user_uniqueness_migration_exists():
    assert MIGRATION.exists()


def test_username_lower_unique_index_defined():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert "uq_users_username_lower" in text
    assert "lower(username)" in text
    assert "unique=True" in text


def test_email_lower_unique_index_defined():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert "uq_users_email_lower" in text
    assert "lower(email)" in text
    assert "unique=True" in text


def test_migration_revises_users_table_migration():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert "bb8d65457c1d" in text
