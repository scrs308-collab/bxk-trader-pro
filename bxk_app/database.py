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
