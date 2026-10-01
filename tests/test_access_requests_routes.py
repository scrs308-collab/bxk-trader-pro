import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.access_request import AccessRequest
from bxk_app.db_models.user import User, UserRole
from bxk_app.main import app
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import hash_app_password


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def configure_auth(monkeypatch, session_factory):
    monkeypatch.setattr(config, "BXK_AUTH_ENABLED", True)
    monkeypatch.setattr(config, "BXK_SESSION_SECRET", "a" * 64)
    monkeypatch.setattr(config, "BXK_SESSION_TTL_SECONDS", 3600)
    monkeypatch.setattr(config, "BXK_AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "database_configured", lambda: True)
    monkeypatch.setattr(
        auth_service,
        "get_session_factory",
        lambda: session_factory,
    )

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db


def add_user(session_factory, role):
    with session_factory() as session:
        user = User(
            username=f"{role.value.lower()}-access",
            email=f"{role.value.lower()}-access@example.com",
            password_hash=hash_app_password("Password123!"),
            role=role,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        session.commit()
        return str(user.id)


def client_with_user(user_id):
    client = TestClient(app)
    token = auth_service.create_database_session_token(user_id)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_public_user_can_submit_access_request(monkeypatch):
    factory = make_session_factory()
    configure_auth(monkeypatch, factory)

    response = TestClient(app).post(
        "/api/access-requests",
        json={
            "full_name": "Review User",
            "email": "review@example.com",
            "broker": "Schwab",
            "intended_use": "Evaluate the platform.",
            "website": None,
        },
    )

    assert response.status_code == 202
    assert response.json()["accepted"] is True

    with factory() as session:
        item = session.execute(
            select(AccessRequest)
        ).scalar_one()
        assert item.email == "review@example.com"
        assert item.status == "PENDING"


def test_duplicate_pending_access_request_is_idempotent(monkeypatch):
    factory = make_session_factory()
    configure_auth(monkeypatch, factory)
    client = TestClient(app)

    payload = {
        "full_name": "Review User",
        "email": "review@example.com",
        "broker": "Schwab",
        "intended_use": None,
        "website": None,
    }

    first = client.post("/api/access-requests", json=payload)
    second = client.post("/api/access-requests", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202

    with factory() as session:
        assert len(session.execute(select(AccessRequest)).scalars().all()) == 1


def test_owner_can_list_access_requests(monkeypatch):
    factory = make_session_factory()
    owner_id = add_user(factory, UserRole.OWNER)
    configure_auth(monkeypatch, factory)

    TestClient(app).post(
        "/api/access-requests",
        json={
            "full_name": "Review User",
            "email": "review@example.com",
            "broker": "Schwab",
            "intended_use": None,
            "website": None,
        },
    )

    response = client_with_user(owner_id).get(
        "/api/access-requests"
    )

    assert response.status_code == 200
    assert len(response.json()["requests"]) == 1


def test_beta_cannot_list_access_requests(monkeypatch):
    factory = make_session_factory()
    beta_id = add_user(factory, UserRole.BETA)
    configure_auth(monkeypatch, factory)

    response = client_with_user(beta_id).get(
        "/api/access-requests"
    )

    assert response.status_code == 403



def test_owner_can_update_access_request_status(monkeypatch):
    factory = make_session_factory()
    owner_id = add_user(factory, UserRole.OWNER)
    configure_auth(monkeypatch, factory)

    create_response = TestClient(app).post(
        "/api/access-requests",
        json={
            "full_name": "Review User",
            "email": "review-status@example.com",
            "broker": "Schwab",
            "intended_use": None,
            "website": None,
        },
    )

    request_id = create_response.json()[
        "request_id"
    ]

    response = client_with_user(owner_id).patch(
        f"/api/access-requests/{request_id}/status",
        json={"status": "APPROVED"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


def test_beta_cannot_update_access_request_status(monkeypatch):
    factory = make_session_factory()
    beta_id = add_user(factory, UserRole.BETA)
    configure_auth(monkeypatch, factory)

    create_response = TestClient(app).post(
        "/api/access-requests",
        json={
            "full_name": "Review User",
            "email": "review-beta@example.com",
            "broker": None,
            "intended_use": None,
            "website": None,
        },
    )

    request_id = create_response.json()[
        "request_id"
    ]

    response = client_with_user(beta_id).patch(
        f"/api/access-requests/{request_id}/status",
        json={"status": "APPROVED"},
    )

    assert response.status_code == 403
