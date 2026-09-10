from pathlib import Path


def test_beta_end_to_end_frontend_access():
    access = Path(
        "static/access-control.js"
    ).read_text(
        encoding="utf-8"
    )

    best_trade = Path(
        "static/best-trade.js"
    ).read_text(
        encoding="utf-8"
    )

    dashboard = Path(
        "static/dashboard.js"
    ).read_text(
        encoding="utf-8"
    )

    index = Path(
        "static/index.html"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "export function hasTradingAccess()"
        in access
    )

    assert 'role === "OWNER"' in access
    assert 'role === "BETA"' in access

    assert (
        "if (!hasTradingAccess())"
        in best_trade
    )

    assert (
        "OWNER EXECUTION ONLY"
        not in best_trade
    )

    assert (
        "SAFE MODE - LIVE OFF"
        in best_trade
    )

    assert (
        "real orders "
        in best_trade
    )

    assert (
        "cannot be submitted."
        in best_trade
    )

    assert (
        "if (!hasTradingAccess())"
        in dashboard
    )

    assert (
        'targetId === "performanceTab"'
        in dashboard
    )

    assert (
        "&& hasTradingAccess()"
        in dashboard
    )

    assert (
        "function applyTradingVisibility()"
        in dashboard
    )

    assert (
        'data-tab="performanceTab"'
        in index
    )

    assert (
        'data-trading-only="true"'
        in index
    )

    performance_start = index.index(
        'id="performanceTab"'
    )

    system_start = index.index(
        'id="systemTab"'
    )

    performance_section = index[
        performance_start:system_start
    ]

    assert (
        'data-trading-only="true"'
        in performance_section
    )

    assert (
        'data-owner-only="true"'
        not in performance_section
    )

    system_section = index[
        system_start:
    ]

    assert (
        'data-owner-only="true"'
        in system_section
    )
