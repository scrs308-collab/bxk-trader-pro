from pathlib import Path


def test_reviewer_script_is_dry_run_by_default():
    source = Path(
        "scripts/create_schwab_reviewer.py"
    ).read_text(
        encoding="utf-8"
    )

    assert 'action="store_true"' in source
    assert "if not apply:" in source
    assert "Re-run with --apply" in source


def test_reviewer_script_keeps_sensitive_access_disabled():
    source = Path(
        "scripts/create_schwab_reviewer.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "user.broker_oauth_enabled = False"
        in source
    )
    assert (
        "user.sms_alerts_enabled = False"
        in source
    )
    assert (
        "user.must_change_password = True"
        in source
    )
    assert (
        "temporary password: [not displayed]"
        in source
    )
