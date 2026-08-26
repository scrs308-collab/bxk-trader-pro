from pathlib import Path


def test_sms_consent_migration_structure():
    path = Path(
        "alembic/versions/"
        "e4c7a912b6d3_create_sms_consents.py"
    )

    text = path.read_text(
        encoding="utf-8"
    )

    assert (
        'revision = "e4c7a912b6d3"'
        in text
    )

    assert (
        'down_revision = "d8b3f42c9a61"'
        in text
    )

    assert (
        '"sms_consents"'
        in text
    )

    assert (
        '"phone_e164"'
        in text
    )

    assert (
        '"consent_text"'
        in text
    )
