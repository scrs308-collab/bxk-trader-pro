from pathlib import Path


STATIC = Path("static")


def read(name):
    return (
        STATIC / name
    ).read_text(
        encoding="utf-8"
    )


def test_owner_only_tabs_are_marked():
    html = read("index.html")

    assert (
        'data-tab="positionMonitorTab"'
        in html
    )

    assert (
        'data-tab="systemTab"'
        in html
    )

    assert html.count(
        'data-owner-only="true"'
    ) >= 4


def test_dashboard_uses_access_control():
    js = read("dashboard.js")

    assert "hasOwnerAccess" in js
    assert "setAccessContext" in js

    assert (
        "await initializeAuthUi()"
        in js
    )


def test_beta_refresh_skips_positions():
    js = read("dashboard.js")

    assert (
        "if (hasOwnerAccess())"
        in js
    )

    assert "loadPositions()" in js


def test_beta_skips_overnight_owner_risk():
    js = read("dashboard.js")

    assert (
        "OWNER_ACCESS_REQUIRED"
        in js
    )

    assert (
        "? fetchOvernightRisk()"
        in js
    )


def test_beta_preview_skips_broker_execution():
    js = read("best-trade.js")

    assert (
        "if (!hasOwnerAccess())"
        in js
    )

    assert (
        "OWNER EXECUTION ONLY"
        in js
    )

    assert (
        "runBrokerPreflight();"
        in js
    )


def test_frontend_access_defaults_closed():
    js = read("access-control.js")

    assert (
        "if (!authStatus)"
        in js
    )

    assert (
        "return false;"
        in js
    )
