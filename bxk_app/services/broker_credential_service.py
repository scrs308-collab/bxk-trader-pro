from cryptography.fernet import (
    Fernet,
    InvalidToken,
)

from bxk_app import config


class BrokerCredentialError(RuntimeError):
    pass


def broker_credential_encryption_configured() -> bool:
    return bool(
        str(
            config.BXK_BROKER_CREDENTIAL_KEY
            or ""
        ).strip()
    )


def _get_fernet() -> Fernet:
    raw_key = str(
        config.BXK_BROKER_CREDENTIAL_KEY
        or ""
    ).strip()

    if not raw_key:
        raise BrokerCredentialError(
            "Broker credential encryption is not configured."
        )

    try:
        return Fernet(
            raw_key.encode("utf-8")
        )
    except Exception as exc:
        raise BrokerCredentialError(
            "Broker credential encryption key is invalid."
        ) from exc


def encrypt_broker_secret(
    plaintext: str,
) -> str:
    value = str(
        plaintext or ""
    )

    if not value:
        raise BrokerCredentialError(
            "Broker credential may not be empty."
        )

    encrypted = _get_fernet().encrypt(
        value.encode("utf-8")
    )

    return encrypted.decode("utf-8")


def decrypt_broker_secret(
    ciphertext: str,
) -> str:
    value = str(
        ciphertext or ""
    ).strip()

    if not value:
        raise BrokerCredentialError(
            "Encrypted broker credential is empty."
        )

    try:
        decrypted = _get_fernet().decrypt(
            value.encode("utf-8")
        )
    except InvalidToken as exc:
        raise BrokerCredentialError(
            "Broker credential could not be decrypted."
        ) from exc

    return decrypted.decode("utf-8")
