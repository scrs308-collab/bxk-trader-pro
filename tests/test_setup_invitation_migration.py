"""Exercise this migration alone, independent of older dialect-specific DDL."""

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/b23c45d67e89_add_secure_setup_invitations.py"
)


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location("setup_invitation_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def legacy_database():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    users = sa.Table(
        "users", metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
    )
    existing_users = [
        dict(
            id=uuid.uuid4(), username=f"migration-{role.lower()}",
            email=f"migration-{role.lower()}@example.invalid",
            password_hash=f"synthetic-existing-{role.lower()}-hash", role=role,
            is_active=role != "VIEWER", must_change_password=role != "OWNER",
        )
        for role in ("OWNER", "BETA", "VIEWER")
    ]
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        metadata.create_all(connection)
        connection.execute(users.insert(), existing_users)
        connection.commit()
        try:
            yield connection, users, existing_users
        finally:
            connection.rollback()
    engine.dispose()


def _apply(connection, operation):
    with Operations.context(MigrationContext.configure(connection)):
        operation()


def test_upgrade_and_downgrade_preserve_existing_users(migration, legacy_database):
    connection, users, existing_users = legacy_database
    assert migration.revision == "b23c45d67e89"
    assert migration.down_revision == "a12b34c56d78"

    _apply(connection, migration.upgrade)
    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("users")}
    assert columns["session_version"]["nullable"] is False
    assert str(columns["session_version"]["default"]).strip("'\"") == "0"

    upgraded_users = sa.Table("users", sa.MetaData(), autoload_with=connection)
    # SQLite reflects UUID storage as CHAR, so restore its Python value adapter.
    upgraded_users.c.id.type = sa.Uuid()
    for original in existing_users:
        upgraded = dict(connection.execute(
            sa.select(upgraded_users).where(upgraded_users.c.id == original["id"])
        ).mappings().one())
        assert upgraded.pop("session_version") == 0
        assert upgraded == original

    # Old insert paths that omit the new column also get revision zero.
    new_user = dict(existing_users[1], id=uuid.uuid4(), username="after-upgrade",
                    email="after-upgrade@example.invalid")
    connection.execute(users.insert(), new_user)
    assert connection.scalar(sa.select(upgraded_users.c.session_version).where(
        upgraded_users.c.id == new_user["id"]
    )) == 0

    _apply(connection, migration.downgrade)
    inspector = sa.inspect(connection)
    assert not inspector.has_table("setup_invitations")
    assert "session_version" not in {column["name"] for column in inspector.get_columns("users")}
    restored_users = list(connection.execute(sa.select(users)).mappings())
    assert {row["id"]: dict(row) for row in restored_users} == {
        row["id"]: row for row in [*existing_users, new_user]
    }


def test_invitation_schema_enforces_one_current_token_per_user(migration, legacy_database):
    connection, _, existing_users = legacy_database
    _apply(connection, migration.upgrade)
    invitations = sa.Table("setup_invitations", sa.MetaData(), autoload_with=connection)
    invitations.c.user_id.type = sa.Uuid()
    invitations.c.requested_by.type = sa.Uuid()
    assert set(invitations.c.keys()) == {
        "user_id", "token_hash", "recipient_email", "credential_version",
        "created_at", "expires_at", "consumed_at", "delivery_status", "requested_by",
    }
    assert list(invitations.primary_key.columns.keys()) == ["user_id"]
    assert {fk.parent.name for fk in invitations.foreign_keys} == {"user_id", "requested_by"}
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    row = dict(
        user_id=existing_users[1]["id"],
        token_hash=hashlib.sha256(b"synthetic-migration-token").hexdigest(),
        recipient_email=existing_users[1]["email"], credential_version=0,
        created_at=now, expires_at=now + timedelta(hours=24), consumed_at=None,
        delivery_status="ACCEPTED", requested_by=existing_users[0]["id"],
    )
    connection.execute(invitations.insert(), row)
    assert connection.scalar(sa.select(sa.func.count()).select_from(invitations)) == 1

    invalid_rows = [
        dict(row, token_hash="b" * 64),  # A second invitation for the same user.
        dict(row, user_id=existing_users[2]["id"]),  # A reused token digest.
        dict(row, user_id=uuid.uuid4(), token_hash="c" * 64),  # Missing recipient.
        dict(row, user_id=existing_users[2]["id"], token_hash="d" * 64,
             requested_by=uuid.uuid4()),  # Missing requester.
    ]
    for invalid in invalid_rows:
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(invitations.insert(), invalid)
    assert connection.scalar(sa.select(sa.func.count()).select_from(invitations)) == 1

    _apply(connection, migration.downgrade)
    assert not sa.inspect(connection).has_table("setup_invitations")
