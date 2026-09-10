from pathlib import Path


def read(path):
    return Path(path).read_text(
        encoding="utf-8"
    )


def test_production_cleanup_and_diagnostics():
    debug = read(
        "bxk_app/routes/debug.py"
    )
    options = read(
        "bxk_app/routes/options.py"
    )
    scanner = read(
        "bxk_app/routes/scanner.py"
    )
    market = read(
        "bxk_app/routes/market.py"
    )
    health = read(
        "bxk_app/routes/health.py"
    )
    position = read(
        "static/position.js"
    )
    best_trade = read(
        "static/best-trade.js"
    )
    dashboard = read(
        "static/dashboard.js"
    )

    # Production diagnostics must require OWNER
    # access when application authentication is
    # enabled.
    assert (
        "require_owner_or_auth_disabled"
        in debug
    )
    assert (
        "require_owner_or_auth_disabled"
        in options
    )

    for route in (
        "/test-wing-optimizer",
        "/test-scanner-engine",
        "/test-candidates",
        "/test-first-candidate-credit",
        "/test-candidate-grid",
    ):
        start = scanner.index(route)
        block = scanner[
            start:start + 240
        ]
        assert (
            "require_owner_or_auth_disabled"
            in block
        )

    market_start = market.index(
        '"/debug/market"'
    )
    assert (
        "require_owner_or_auth_disabled"
        in market[
            market_start:
            market_start + 240
        ]
    )

    env_start = health.index(
        '"/api/test-env"'
    )
    assert (
        "require_owner_or_auth_disabled"
        in health[
            env_start:
            env_start + 240
        ]
    )

    # Railway process health remains public.
    health_start = health.index(
        '"/health"'
    )
    health_block = health[
        health_start:
        health_start + 160
    ]
    assert (
        "require_owner_or_auth_disabled"
        not in health_block
    )

    assert (
        "No Open SPX Position"
        not in position
    )
    assert (
        "No Open Supported Position"
        in position
    )

    assert (
        '"BXK order preview:"'
        not in best_trade
    )
    assert (
        '"BXK broker preflight:"'
        not in best_trade
    )
    assert (
        '"BXK order submission:"'
        not in best_trade
    )
    assert (
        "BXK Trader Pro Dashboard - V10"
        not in dashboard
    )

    backups = [
        Path(
            "static/best-trade.js.backup"
        ),
        Path(
            "static/best-trade.js.backup-20260804-213242"
        ),
        Path(
            "static/best-trade.js.backup-20260804-214636"
        ),
        Path(
            "static/best-trade.js.backup-20260804-214856"
        ),
        Path(
            "static/best-trade.js.backup-20260804-215017"
        ),
        Path(
            "static/style.css.backup-20260804-214636"
        ),
        Path(
            "static/style.css.backup-20260804-214856"
        ),
        Path(
            "static/style.css.backup-20260804-215017"
        ),
    ]

    assert not any(
        path.exists()
        for path in backups
    )
