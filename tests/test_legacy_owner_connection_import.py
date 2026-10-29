import uuid
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from bxk_app import config
from bxk_app.database import Base
from bxk_app.db_models.user import User, UserRole
from bxk_app.services import broker_connection_service as service
from bxk_app.services.broker_credential_service import decrypt_broker_secret

@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    for name, value in dict(BXK_APP_USERNAME='owner', TASTYTRADE_CLIENT_SECRET='existing-secret', TASTYTRADE_REFRESH_TOKEN='existing-token', TASTYTRADE_ACCOUNT_NUMBER='account-7178', BXK_BROKER_CREDENTIAL_KEY=Fernet.generate_key().decode()).items():
        monkeypatch.setattr(config, name, value)
    with Session(engine) as session:
        user = User(username='owner', email='owner@example.com', password_hash='unused', role=UserRole.OWNER, is_active=True)
        session.add(user)
        session.commit()
        yield session, dict(user_id=str(user.id), username='owner', role='OWNER', auth_source='DATABASE')

def test_import_verifies_encrypts_and_is_shared_and_idempotent(setup, monkeypatch):
    session, context = setup
    calls = []
    def verify(**kwargs):
        calls.append(kwargs)
        return [{'account_number': 'account-7178'}]
    monkeypatch.setattr(service, 'verify_tastytrade_credentials', verify)
    connection = service.import_legacy_owner_connection(session, user_context=context)
    assert calls == [dict(client_secret='existing-secret', refresh_token='existing-token')]
    assert connection.is_verified and connection.is_active
    assert not connection.live_trading_enabled
    assert connection.client_secret_encrypted != 'existing-secret'
    assert decrypt_broker_secret(connection.refresh_token_encrypted) == 'existing-token'
    assert service.get_broker_connection_status(session, user_context=context)['source'] == 'user_connection'
    assert service.import_legacy_owner_connection(session, user_context=context).id == connection.id
    assert len(calls) == 1
    assert service.resolve_tastytrade_broker(session, user_context=context) is not service.owner_broker
    connection.is_active = False
    session.commit()
    assert service.import_legacy_owner_connection(session, user_context=context) is None
    assert len(calls) == 1

@pytest.mark.parametrize('change', [dict(username='another-owner'), dict(role='BETA'), dict(auth_source='LEGACY'), dict(user_id=None)])
def test_other_identities_cannot_import(setup, monkeypatch, change):
    session, context = setup
    monkeypatch.setattr(service, 'connect_tastytrade_account', lambda *a, **k: pytest.fail('must not import'))
    assert service.import_legacy_owner_connection(session, user_context={**context, **change}) is None

def test_failed_verification_does_not_save(setup, monkeypatch):
    session, context = setup
    monkeypatch.setattr(service, 'verify_tastytrade_credentials', lambda **k: [])
    with pytest.raises(service.BrokerVerificationError):
        service.import_legacy_owner_connection(session, user_context=context)
    assert service.get_any_user_tastytrade_connection(session, user_id=uuid.UUID(context['user_id'])) is None

@pytest.mark.parametrize('global_enabled', [False, True])
def test_owner_broker_matches_global_switch_without_enabling_beta(setup, monkeypatch, global_enabled):
    session, context = setup
    monkeypatch.setattr(service, 'verify_tastytrade_credentials', lambda **k: [{'account_number': 'account-7178'}])
    connection = service.import_legacy_owner_connection(session, user_context=context)
    assert connection.live_trading_enabled is False
    monkeypatch.setattr(config, 'BXK_LIVE_TRADING_ENABLED', global_enabled)
    broker = service.resolve_tastytrade_broker(session, user_context=context)
    assert broker.live_trading_enabled is global_enabled
    assert service.get_broker_connection_status(session, user_context=context)['live_trading_enabled'] is global_enabled
    beta_context = {**context, 'role': 'BETA'}
    assert service.resolve_tastytrade_broker(session, user_context=beta_context).live_trading_enabled is False
    assert service.get_broker_connection_status(session, user_context=beta_context)['live_trading_enabled'] is False
