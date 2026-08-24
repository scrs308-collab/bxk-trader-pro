from sqlalchemy import create_engine

import bxk_app.database as database


def test_database_health_not_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        database.config,
        "DATABASE_URL",
        "",
    )

    result = database.database_health_status()

    assert result == {
        "configured": False,
        "connected": False,
        "dialect": None,
        "schema_revision": None,
        "users_table_present": False,
    }


def test_database_health_connected(
    monkeypatch,
):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    database.Base.metadata.create_all(engine)

    monkeypatch.setattr(
        database,
        "get_engine",
        lambda: engine,
    )

    monkeypatch.setattr(
        database,
        "database_configured",
        lambda: True,
    )

    result = database.database_health_status()

    assert result["configured"] is True
    assert result["connected"] is True
    assert result["dialect"] == "sqlite"
    assert result["users_table_present"] is True
    assert result["schema_revision"] is None


def test_database_health_failure_is_safe(
    monkeypatch,
):
    def broken_engine():
        raise RuntimeError(
            "postgresql://secret-user:"
            "secret-password@private-host/db"
        )

    monkeypatch.setattr(
        database,
        "database_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        database,
        "get_engine",
        broken_engine,
    )

    result = database.database_health_status()

    assert result == {
        "configured": True,
        "connected": False,
        "dialect": None,
        "schema_revision": None,
        "users_table_present": False,
    }

    assert "secret" not in str(result)
