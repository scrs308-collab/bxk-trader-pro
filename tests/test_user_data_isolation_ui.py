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
        'data-tab="performanceTab"'
        in html
    )

    assert (
        'data-tab="systemTab"'
        in html
    )

    # Performance is available to OWNER/BETA.
    performance_nav_start = html.index(
        'data-tab="performanceTab"'
    )

    performance_nav_end = html.index(
        "</button>",
        performance_nav_start,
    )

    performance_nav = html[
        performance_nav_start:
        performance_nav_end
    ]

    assert (
        'data-trading-only="true"'
        in performance_nav
    )

    assert (
        'data-owner-only="true"'
        not in performance_nav
    )

    # Performance panel follows the same rule.
    performance_panel_start = html.index(
        'id="performanceTab"'
    )

    system_panel_start = html.index(
        'id="systemTab"'
    )

    performance_panel = html[
        performance_panel_start:
        system_panel_start
    ]

    assert (
        'data-trading-only="true"'
        in performance_panel
    )

    assert (
        'data-owner-only="true"'
        not in performance_panel
    )

    # System controls remain OWNER-only.
    system_section = html[
        system_panel_start:
    ]

    assert (
        'data-owner-only="true"'
        in system_section
    )

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

    # OWNER and BETA share the private-trading
    # frontend boundary. VIEWER remains excluded.
    assert (
        "hasTradingAccess"
        in js
    )

    assert (
        "if (!hasTradingAccess())"
        in js
    )

    # SAFE-mode BETA may review the trade but
    # cannot submit a real order.
    assert (
        "SAFE MODE - LIVE OFF"
        in js
    )

    assert (
        "liveSubmissionEnabled"
        in js
    )

    assert (
        "if (!liveSubmissionEnabled)"
        in js
    )

    assert (
        "runBrokerPreflight();"
        in js
    )

    # Old OWNER-only browser restriction must
    # not return.
    assert (
        "OWNER EXECUTION ONLY"
        not in js
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
