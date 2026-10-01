from pathlib import Path


def test_commercial_readiness_ui_is_owner_scoped_and_wired():
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
    module = Path(
        "static/commercial-readiness.js"
    ).read_text(
        encoding="utf-8"
    )

    assert 'id="commercialReadinessCard"' in index
    assert 'data-owner-only="true"' in index
    assert "initializeCommercialReadiness" in dashboard
    assert "./commercial-readiness.js?v=1" in dashboard
    assert "/api/admin/commercial-readiness" in module
    assert "Schwab commercial approval" in module
