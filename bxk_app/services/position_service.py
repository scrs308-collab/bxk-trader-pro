from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.position_monitor import (
    build_position_summaries,
)


def get_position_monitor():
    """
    Return open SPX option legs grouped into separate
    Iron Condor position summaries.
    """

    try:
        positions = (
            tastytrade_api
            .get_position_summary()
        )

        connected = (
            tastytrade_api
            .get_status()
            .get("connected", False)
        )

        if not positions:
            return {
                "status": "EMPTY",
                "connected": connected,
                "position": None,
                "positions": [],
                "position_count": 0,
                "total_open_pnl": 0.0,
                "message": (
                    "No open positions found."
                ),
            }

        snapshot = (
            market_data.get_snapshot()
        )

        spx_price = (
            (snapshot or {}).get("spx")
            or (snapshot or {}).get(
                "spx_price"
            )
            or (snapshot or {}).get(
                "price"
            )
        )

        if not spx_price:
            try:
                live_market = (
                    market_engine.update()
                )

                if isinstance(
                    live_market,
                    dict,
                ):
                    spx_price = (
                        live_market.get("spx")
                        or live_market.get(
                            "spx_price"
                        )
                        or live_market.get(
                            "price"
                        )
                    )

            except Exception:
                spx_price = None

        try:
            spx_price = float(
                spx_price
            )

        except (
            TypeError,
            ValueError,
        ):
            spx_price = None

        if (
            spx_price is not None
            and spx_price <= 0
        ):
            spx_price = None

        summaries = (
            build_position_summaries(
                positions=positions,
                spx_price=spx_price,
            )
        )

        if not summaries:
            return {
                "status": "UNSUPPORTED",
                "connected": connected,
                "position": None,
                "positions": [],
                "position_count": 0,
                "total_open_pnl": 0.0,
                "leg_count": len(
                    positions
                ),
                "message": (
                    "Open positions could not "
                    "be grouped into supported "
                    "Iron Condor positions."
                ),
            }

        total_open_pnl = round(
            sum(
                float(
                    summary.get(
                        "pnl",
                        0,
                    )
                    or 0
                )
                for summary in summaries
            ),
            2,
        )

        return {
            "status": "OK",
            "connected": connected,

            # Keep this temporarily so the existing
            # dashboard does not break before the UI
            # is updated for multiple cards.
            "position": summaries[0],

            # New multi-position payload.
            "positions": summaries,
            "position_count": len(
                summaries
            ),
            "total_open_pnl": (
                total_open_pnl
            ),
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "connected": False,
            "position": None,
            "positions": [],
            "position_count": 0,
            "total_open_pnl": 0.0,
            "message": str(error),
        }