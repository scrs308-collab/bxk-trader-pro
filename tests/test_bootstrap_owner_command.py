import bxk_app.commands.bootstrap_owner as command


def test_owner_bootstrap_command_success(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        command,
        "run_owner_bootstrap",
        lambda: {
            "configured": True,
            "created": True,
            "existing": False,
            "user_id": "test-user-id",
        },
    )

    result = command.main()

    captured = capsys.readouterr()

    assert result == 0
    assert "test-user-id" in captured.out
    assert "password" not in captured.out.lower()


def test_owner_bootstrap_command_unconfigured(
    monkeypatch,
):
    monkeypatch.setattr(
        command,
        "run_owner_bootstrap",
        lambda: {
            "configured": False,
            "created": False,
            "existing": False,
            "user_id": None,
        },
    )

    assert command.main() == 2


def test_owner_bootstrap_command_failure_is_safe(
    monkeypatch,
    capsys,
):
    def fail():
        raise RuntimeError(
            "postgresql://user:"
            "secret-password@host/db"
        )

    monkeypatch.setattr(
        command,
        "run_owner_bootstrap",
        fail,
    )

    result = command.main()

    captured = capsys.readouterr()

    assert result == 1
    assert "RuntimeError" in captured.err
    assert "secret-password" not in captured.err
