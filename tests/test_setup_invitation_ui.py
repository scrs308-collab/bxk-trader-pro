from pathlib import Path
import shutil
import subprocess

import pytest


def test_setup_invitation_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for executable frontend behavior tests")
    result = subprocess.run(
        [node, "tests/setup_invitation_ui.test.mjs"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_approval_and_creation_copy_explains_separate_setup_email():
    requests = Path("static/admin-requests.js").read_text(encoding="utf-8")
    users = Path("static/admin-users.js").read_text(encoding="utf-8")
    assert "Approve sends a status notification" in requests
    assert "does not create an account or send a password setup link" in requests
    assert "Prepare User, then Create User, then Send Setup Link" in requests
    assert "The temporary password is not emailed" in requests
    assert "The temporary password is not emailed" in users
    assert "No email has been sent" in users
    assert "expected_email: user.email" in users
    assert "expected_username: user.username" in users


def test_password_change_requires_fresh_login_after_success():
    html = Path("static/change-password.html").read_text(encoding="utf-8")
    success_handler = html.split('"Password changed successfully.')[1].split("} catch")[0]
    assert 'window.location.replace("/login")' in success_handler
    assert 'window.location.replace("/")' not in success_handler
    assert '"newPassword"' in success_handler
    assert '"confirmPassword"' in success_handler
