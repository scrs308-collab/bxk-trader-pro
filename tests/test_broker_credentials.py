import pytest
from cryptography.fernet import Fernet

from bxk_app import config
from bxk_app.services.broker_credential_service import (
    BrokerCredentialError,
    broker_credential_encryption_configured,
    decrypt_broker_secret,
    encrypt_broker_secret,
)


def test_broker_credential_round_trip(
    monkeypatch,
):
    key = Fernet.generate_key().decode()

    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        key,
    )

    plaintext = "super-secret-refresh-token"

    ciphertext = encrypt_broker_secret(
        plaintext
    )

    assert ciphertext != plaintext
    assert plaintext not in ciphertext

    assert (
        decrypt_broker_secret(ciphertext)
        == plaintext
    )


def test_broker_credential_key_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        Fernet.generate_key().decode(),
    )

    assert (
        broker_credential_encryption_configured()
        is True
    )


def test_broker_credential_missing_key_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        "",
    )

    assert (
        broker_credential_encryption_configured()
        is False
    )

    with pytest.raises(
        BrokerCredentialError
    ):
        encrypt_broker_secret(
            "secret"
        )


def test_broker_credential_invalid_ciphertext_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(
        config,
        "BXK_BROKER_CREDENTIAL_KEY",
        Fernet.generate_key().decode(),
    )

    with pytest.raises(
        BrokerCredentialError
    ):
        decrypt_broker_secret(
            "this-is-not-valid-ciphertext"
        )
