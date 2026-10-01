from pathlib import Path


def test_owner_request_admin_ui_is_wired():
    index = Path(
        "static/index.html"
    ).read_text(
        encoding="utf-8"
    )

    dashboard = Path(
        "static/dashboard.js"
    ).read_text(
        encoding="utf-8"
    )

    admin_requests = Path(
        "static/admin-requests.js"
    ).read_text(
        encoding="utf-8"
    )

    assert 'id="adminRequestsCard"' in index
    assert 'data-owner-only="true"' in index
    assert "initializeAdminRequests" in dashboard
    assert "./admin-requests.js?v=1" in dashboard
    assert "/api/access-requests" in admin_requests
    assert "/api/support-requests" in admin_requests
    assert 'method: "PATCH"' in admin_requests
    assert "Prepare User" in admin_requests
    assert "bxkAdminUsername" in admin_requests
    assert "bxkAdminEmail" in admin_requests
