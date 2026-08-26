from pathlib import Path


MIGRATION = Path(
    "alembic/versions/"
    "d8b3f42c9a61_"
    "create_overnight_alert_state.py"
)


def test_overnight_alert_migration():
    text = MIGRATION.read_text(
        encoding="utf-8"
    )

    assert (
        'revision: str = "d8b3f42c9a61"'
        in text
    )

    assert (
        '"c91f4e2a7b10"'
        in text
    )

    assert (
        '"overnight_alert_states"'
        in text
    )
