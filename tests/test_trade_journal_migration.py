from pathlib import Path


def test_trade_journal_migration():
    path = Path(
        "alembic/versions/"
        "f6a1c9d82b47_create_trade_journals.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        'revision = "f6a1c9d82b47"'
        in source
    )

    assert (
        'down_revision = "e4c7a912b6d3"'
        in source
    )

    assert (
        '"trade_journals"'
        in source
    )

    assert (
        '"broker_order_id"'
        in source
    )

    assert (
        '"user_id"'
        in source
    )

    assert (
        '"entry_snapshot"'
        in source
    )


def test_trade_journal_closure_migration():
    path = Path(
        "alembic/versions/"
        "0c3e7a9f1b24_"
        "add_trade_journal_closure_fields.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        'revision = "0c3e7a9f1b24"'
        in source
    )

    assert (
        'down_revision = "f6a1c9d82b47"'
        in source
    )

    assert (
        '"closing_broker_order_id"'
        in source
    )

    assert (
        '"close_snapshot"'
        in source
    )
