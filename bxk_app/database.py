from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from bxk_app import config


class Base(DeclarativeBase):
    pass


def normalize_database_url(
    database_url: str,
) -> str:
    url = str(database_url or "").strip()

    if url.startswith("postgres://"):
        return (
            "postgresql+psycopg://"
            + url[len("postgres://"):]
        )

    if url.startswith("postgresql://"):
        return (
            "postgresql+psycopg://"
            + url[len("postgresql://"):]
        )

    return url


def database_configured() -> bool:
    return bool(
        str(config.DATABASE_URL or "").strip()
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = normalize_database_url(
        config.DATABASE_URL
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db():
    session = get_session_factory()()

    try:
        yield session
    finally:
        session.close()


def database_health_status() -> dict:
    """Return safe database connectivity/schema status."""

    if not database_configured():
        return {
            "configured": False,
            "connected": False,
            "dialect": None,
            "schema_revision": None,
            "users_table_present": False,
        }

    try:
        from sqlalchemy import inspect, text
        from sqlalchemy.exc import SQLAlchemyError

        engine = get_engine()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

            inspector = inspect(connection)

            users_table_present = (
                inspector.has_table("users")
            )

            schema_revision = None

            try:
                result = connection.execute(
                    text(
                        "SELECT version_num "
                        "FROM alembic_version "
                        "LIMIT 1"
                    )
                ).scalar_one_or_none()

                schema_revision = (
                    str(result)
                    if result is not None
                    else None
                )
            except SQLAlchemyError:
                # Database may be reachable before its
                # first migration has been applied.
                schema_revision = None

        return {
            "configured": True,
            "connected": True,
            "dialect": engine.dialect.name,
            "schema_revision": schema_revision,
            "users_table_present":
                users_table_present,
        }

    except Exception:
        # Never expose connection strings, passwords,
        # hostnames, or raw database errors.
        return {
            "configured": True,
            "connected": False,
            "dialect": None,
            "schema_revision": None,
            "users_table_present": False,
        }
