import pytest
import bxk_app.routes.order as order_route
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from bxk_app import config
from bxk_app.database import (
    Base,
    get_db,
)
from bxk_app.db_models.execution_audit import (
    ExecutionAudit,
)
from bxk_app.db_models.user import (
    User,
    UserRole,
)
from bxk_app.main import app
from bxk_app.market_data import MarketData
from bxk_app.services import auth_service
from bxk_app.services.system_settings_service import (
    hash_app_password,
)


def make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    return sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )


def configure_auth(
    monkeypatch,
    factory,
):
    monkeypatch.setattr(
        config,
        "BXK_AUTH_ENABLED",
        True,
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_SECRET",
        "a" * 64,
    )

    monkeypatch.setattr(
        config,
        "BXK_SESSION_TTL_SECONDS",
        3600,
    )

    monkeypatch.setattr(
        config,
        "BXK_AUTH_COOKIE_SECURE",
        False,
    )

    monkeypatch.setattr(
        auth_service,
        "database_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        auth_service,
        "get_session_factory",
        lambda: factory,
    )

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[
        get_db
    ] = override_get_db


def add_user(
    factory,
    *,
    username,
    role,
):
    with factory() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_app_password(
                "Password123!"
            ),
            role=role,
            is_active=True,
            must_change_password=False,
        )

        session.add(user)
        session.commit()

        return str(user.id)


def client_with_user(user_id):
    client = TestClient(app)

    token = (
        auth_service
        .create_database_session_token(
            user_id
        )
    )

    client.cookies.set(
        auth_service.SESSION_COOKIE_NAME,
        token,
    )

    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/api/positions-summary",
        "/api/test-tastytrade",
        "/api/test-tastytrade-rest",
        "/api/test-tastytrade-balances",
        "/api/test-tastytrade-positions",
        "/api/test-new-broker",
        "/api/system-settings",
        "/api/refresh-market",
        "/api/overnight-risk",
    ],
)
def test_beta_cannot_access_owner_private_routes(
    monkeypatch,
    path,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta1",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    client = client_with_user(beta_id)

    response = client.get(path)

    assert response.status_code == 403


def test_beta_position_monitor_requires_own_broker(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_position",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def override_get_db():
        session = factory()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[
        get_db
    ] = override_get_db

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/position-monitor"
    )

    assert response.status_code == 409

def test_beta_account_summary_requires_own_broker(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_account",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def override_get_db():
        session = factory()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[
        get_db
    ] = override_get_db

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/account-summary"
    )

    assert response.status_code == 409

def test_beta_account_summary_uses_own_broker(
    monkeypatch,
):
    from bxk_app.routes import broker as broker_route

    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_account_connected",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def override_get_db():
        session = factory()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[
        get_db
    ] = override_get_db

    class FakeBroker:
        def authenticate(self):
            return True

        def get_account_summary(self):
            return {
                "account_number":
                    "BETA-ONLY",
                "net_liquidating_value":
                    12345.67,
            }

    fake_broker = FakeBroker()

    monkeypatch.setattr(
        broker_route,
        "get_broker_connection_status",
        lambda session, *, user_context: {
            "source":
                "user_connection",
            "connected":
                True,
        },
    )

    monkeypatch.setattr(
        broker_route,
        "resolve_tastytrade_broker",
        lambda session, *, user_context:
            fake_broker,
    )

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/account-summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["connected"] is True
    assert (
        data["account"]["account_number"]
        == "BETA-ONLY"
    )

def test_market_header_hides_owner_context():
    data = MarketData()

    data.account = {
        "number": "SECRET_ACCOUNT",
        "net_liquidation": 999999,
    }

    data.positions = [
        {
            "symbol": "PRIVATE_POSITION",
        }
    ]

    header = data.get_header(
        include_account_context=False
    )

    assert header["account"] == {}
    assert header["positions"] == []


def test_beta_live_market_requests_market_only_mode(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta1",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    captured = {}

    def fake_live_market(
        underlying,
        *,
        include_account_context=True,
    ):
        captured[
            "include_account_context"
        ] = include_account_context

        return {
            "underlying": underlying,
            "account": {},
            "positions": [],
        }

    monkeypatch.setattr(
        "bxk_app.routes.market.get_live_market",
        fake_live_market,
    )

    client = client_with_user(beta_id)

    response = client.get(
        "/api/live-market?underlying=SPX"
    )

    assert response.status_code == 200

    assert (
        captured[
            "include_account_context"
        ]
        is False
    )

    assert response.json()["account"] == {}
    assert response.json()["positions"] == []


def test_owner_live_market_keeps_account_mode(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    captured = {}

    def fake_live_market(
        underlying,
        *,
        include_account_context=True,
    ):
        captured[
            "include_account_context"
        ] = include_account_context

        return {
            "underlying": underlying,
        }

    monkeypatch.setattr(
        "bxk_app.routes.market.get_live_market",
        fake_live_market,
    )

    client = client_with_user(owner_id)

    response = client.get(
        "/api/live-market?underlying=SPX"
    )

    assert response.status_code == 200

    assert (
        captured[
            "include_account_context"
        ]
        is True
    )


def test_beta_can_still_use_order_preview(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_preview",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._build_current_order",
        lambda *args, **kwargs: (
            None,
            None,
        ),
    )

    client = client_with_user(beta_id)

    response = client.get(
        "/api/order-preview"
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "NO_TRADE"
    )


def test_beta_order_validate_requires_own_broker(
    monkeypatch,
):
    from bxk_app.services.broker_connection_service import (
        BrokerConnectionRequired,
    )

    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_validate",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def missing_broker(
        session,
        *,
        user_context,
    ):
        raise BrokerConnectionRequired(
            "BETA broker connection required."
        )

    monkeypatch.setattr(
        "bxk_app.routes.order.resolve_tastytrade_broker",
        missing_broker,
    )

    def forbidden_body(*args, **kwargs):
        raise AssertionError(
            "order_validate body executed "
            "without a BETA broker"
        )

    monkeypatch.setattr(
        "bxk_app.routes.order._build_current_order",
        forbidden_body,
    )

    client = client_with_user(beta_id)

    response = client.get(
        "/api/order-validate"
    )

    assert response.status_code == 409


def test_beta_order_dry_run_requires_own_broker(
    monkeypatch,
):
    from bxk_app.services.broker_connection_service import (
        BrokerConnectionRequired,
    )

    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_dryrun",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def missing_broker(
        session,
        *,
        user_context,
    ):
        raise BrokerConnectionRequired(
            "BETA broker connection required."
        )

    monkeypatch.setattr(
        "bxk_app.routes.order.resolve_tastytrade_broker",
        missing_broker,
    )

    def forbidden_body():
        raise AssertionError(
            "order_dry_run body executed "
            "without a BETA broker"
        )

    monkeypatch.setattr(
        "bxk_app.routes.order._execution_session_gate",
        forbidden_body,
    )

    client = client_with_user(beta_id)

    response = client.post(
        "/api/order-dry-run"
    )

    assert response.status_code == 409


def test_beta_order_validate_uses_own_broker(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_validate_connected",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    class FakeBroker:
        last_error = None

        def authenticate(self):
            return True

        def get_first_account_number(self):
            return "BETA1234"

    fake_broker = FakeBroker()

    monkeypatch.setattr(
        "bxk_app.routes.order.resolve_tastytrade_broker",
        lambda session, *, user_context:
            fake_broker,
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._build_current_order",
        lambda *args, **kwargs: (
            {"strategy": "TEST"},
            {
                "strategy": "TEST",
                "symbol": "SPX",
                "legs": [],
            },
        ),
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._validate_order",
        lambda *args, **kwargs: (
            [],
            [],
        ),
    )

    client = client_with_user(beta_id)

    response = client.get(
        "/api/order-validate"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "VALIDATED"
    assert data["account"] == "***1234"


def test_beta_order_dry_run_uses_own_broker(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_dryrun_connected",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    class FakeBroker:
        last_error = None

        def authenticate(self):
            return True

        def get_first_account_number(self):
            return "BETA5678"

        def get_positions(
            self,
            *,
            account_number,
        ):
            assert account_number == "BETA5678"
            return []

        def dry_run_order(
            self,
            order,
            *,
            account_number,
        ):
            assert account_number == "BETA5678"

            return {
                "test": "beta-only-dry-run",
            }

    fake_broker = FakeBroker()

    monkeypatch.setattr(
        "bxk_app.routes.order.resolve_tastytrade_broker",
        lambda session, *, user_context:
            fake_broker,
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._execution_session_gate",
        lambda: {
            "passed": True,
            "reason_code": "REGULAR_SESSION",
            "message": "Regular session.",
            "policy": {},
        },
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._get_order_review_lock",
        lambda review_id, **_kwargs: (
            {
                "review_id": "beta-review",
                "trade": {
                    "strategy": "TEST",
                },
                "order": {
                    "strategy": "TEST",
                    "symbol": "SPX",
                    "legs": [],
                },
                "request": {
                    "dte": 1,
                    "wing_width": 25,
                    "contracts": 1,
                },
            },
            None,
        ),
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._validate_order",
        lambda *args, **kwargs: (
            [],
            [],
        ),
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._check_existing_position_overlap",
        lambda *args, **kwargs: {
            "passed": True,
            "overlaps": [],
            "message": "No overlap.",
        },
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._evaluate_broker_dry_run",
        lambda *args, **kwargs: {
            "passed": True,
            "errors": [],
            "checks": [],
        },
    )

    def forbidden_owner_audit(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "BETA dry-run wrote OWNER "
            "execution audit"
        )

    monkeypatch.setattr(
        "bxk_app.routes.order._write_execution_audit",
        forbidden_owner_audit,
    )

    client = client_with_user(beta_id)

    response = client.post(
        "/api/order-dry-run"
        "?review_id=beta-review"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["status"]
        == "BROKER_PREFLIGHT_PASSED"
    )

    assert data["account"] == "***5678"

def test_beta_cannot_run_order_submit(
    monkeypatch,
):
    factory = make_session_factory()

    beta_id = add_user(
        factory,
        username="beta_submit",
        role=UserRole.BETA,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    def forbidden_preflight(*args, **kwargs):
        raise AssertionError(
            "order_submit reached broker "
            "preflight for BETA user"
        )

    monkeypatch.setattr(
        "bxk_app.routes.order.order_dry_run",
        forbidden_preflight,
    )

    client = client_with_user(beta_id)

    response = client.post(
        "/api/order-submit?confirm_live=true"
    )

    assert response.status_code == 409


def test_owner_can_reach_order_validate(
    monkeypatch,
):
    factory = make_session_factory()

    owner_id = add_user(
        factory,
        username="owner_validate",
        role=UserRole.OWNER,
    )

    configure_auth(
        monkeypatch,
        factory,
    )

    monkeypatch.setattr(
        "bxk_app.routes.order._build_current_order",
        lambda *args, **kwargs: (
            None,
            None,
        ),
    )

    client = client_with_user(owner_id)

    response = client.get(
        "/api/order-validate"
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "BLOCKED"
    )


def test_beta_order_submit_requires_live_permission(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    beta_id = add_user(
        session_factory,
        username="beta_submit_disabled",
        role=UserRole.BETA,
    )

    class DisabledBroker:
        live_trading_enabled = False

    monkeypatch.setattr(
        order_route,
        "_resolve_request_broker",
        lambda session, user_context:
            DisabledBroker(),
    )

    def must_not_submit(**kwargs):
        raise AssertionError(
            "Internal live submit must not run "
            "when user live trading is disabled."
        )

    monkeypatch.setattr(
        order_route,
        "order_submit",
        must_not_submit,
    )

    client = client_with_user(
        beta_id
    )

    response = client.post(
        (
            "/api/order-submit"
            "?confirm_live=true"
            "&review_id=beta-disabled-review"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["reason_code"]
        == "USER_LIVE_TRADING_DISABLED"
    )

    assert (
        payload[
            "user_live_trading_enabled"
        ]
        is False
    )


def test_beta_order_submit_uses_own_broker_and_db_audit(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    beta_id = add_user(
        session_factory,
        username="beta_submit_enabled",
        role=UserRole.BETA,
    )

    class EnabledBroker:
        live_trading_enabled = True

    beta_broker = EnabledBroker()

    monkeypatch.setattr(
        order_route,
        "_resolve_request_broker",
        lambda session, user_context:
            beta_broker,
    )

    def global_audit_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "BETA submission must not write "
            "to OWNER execution audit."
        )

    monkeypatch.setattr(
        order_route,
        "_write_execution_audit",
        global_audit_must_not_run,
    )

    captured = {}

    def fake_internal_submit(
        **kwargs,
    ):
        captured.update(
            kwargs
        )

        audit_error = (
            kwargs[
                "execution_audit_writer"
            ](
                "SUBMISSION_ATTEMPT",
                status="PENDING",
                review_id=
                    "beta-review-123456",
                account=
                    "BETA12345678",
                order={
                    "strategy":
                        "SPX Iron Condor",
                    "symbol":
                        "SPX",
                    "quantity":
                        1,
                },
            )
        )

        assert audit_error is None

        return {
            "status": "SUBMITTED",
            "test": True,
        }

    monkeypatch.setattr(
        order_route,
        "order_submit",
        fake_internal_submit,
    )

    client = client_with_user(
        beta_id
    )

    response = client.post(
        (
            "/api/order-submit"
            "?confirm_live=true"
            "&review_id=beta-review-123456"
        )
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "SUBMITTED"
    )

    assert (
        captured[
            "broker_client"
        ]
        is beta_broker
    )

    assert (
        captured[
            "write_preflight_audit"
        ]
        is False
    )

    assert (
        str(
            captured[
                "user_context"
            ]["user_id"]
        )
        == beta_id
    )

    with session_factory() as session:
        rows = (
            session.query(
                ExecutionAudit
            )
            .all()
        )

        assert len(rows) == 1

        audit = rows[0]

        assert (
            str(audit.user_id)
            == beta_id
        )

        assert (
            audit.event
            == "SUBMISSION_ATTEMPT"
        )

        assert (
            audit.account_masked
            == "***5678"
        )


def test_beta_order_status_without_broker_returns_409(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    beta_id = add_user(
        session_factory,
        username="beta_status_none",
        role=UserRole.BETA,
    )

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/order-status?order_id=ORDER-77"
    )

    assert response.status_code == 409


def test_beta_order_status_uses_own_broker(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    beta_id = add_user(
        session_factory,
        username="beta_status_own",
        role=UserRole.BETA,
    )

    class BetaBroker:
        last_error = None

        def get_first_account_number(
            self,
        ):
            return "BETA1234"

        def get_order(
            self,
            order_id,
            account_number=None,
        ):
            assert (
                account_number
                == "BETA1234"
            )

            return {
                "id": order_id,
                "status": "Filled",
                "filled-quantity": "1",
                "remaining-quantity": "0",
                "average-fill-price": "3.25",
            }

    beta_broker = BetaBroker()

    monkeypatch.setattr(
        order_route,
        "_resolve_request_broker",
        lambda session, user_context:
            beta_broker,
    )

    client = client_with_user(
        beta_id
    )

    response = client.get(
        "/api/order-status?order_id=ORDER-77"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["status"]
        == "RECONCILED"
    )

    assert (
        payload["order_id"]
        == "ORDER-77"
    )


def test_viewer_cannot_use_order_status(
    monkeypatch,
):
    session_factory = (
        make_session_factory()
    )

    configure_auth(
        monkeypatch,
        session_factory,
    )

    viewer_id = add_user(
        session_factory,
        username="viewer_status",
        role=UserRole.VIEWER,
    )

    def resolver_must_not_run(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "VIEWER must be rejected before "
            "broker resolution."
        )

    monkeypatch.setattr(
        order_route,
        "_resolve_request_broker",
        resolver_must_not_run,
    )

    client = client_with_user(
        viewer_id
    )

    response = client.get(
        "/api/order-status?order_id=ORDER-77"
    )

    assert response.status_code == 403
