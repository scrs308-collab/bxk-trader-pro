from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.position_monitor import (
    build_iron_condor_summary,
)


def get_position_monitor():
    """
    Return open SPX option legs grouped into one
    Iron Condor position summary.
    """

    try:
        positions = tastytrade_api.get_position_summary()

        if not positions:
            return {
                "status": "EMPTY",
                "connected": (
                    tastytrade_api
                    .get_status()
                    .get("connected", False)
                ),
                "position": None,
                "message": "No open positions found.",
            }

        snapshot = market_data.get_snapshot()

        spx_price = (
            (snapshot or {}).get("spx")
            or (snapshot or {}).get("spx_price")
            or (snapshot or {}).get("price")
        )

        if not spx_price:
            try:
                live_market = market_engine.update()

                if isinstance(live_market, dict):
                    spx_price = (
                        live_market.get("spx")
                        or live_market.get("spx_price")
                        or live_market.get("price")
                    )

            except Exception:
                spx_price = None

        try:
            spx_price = float(spx_price)
        except (TypeError, ValueError):
            spx_price = None

        if (
            spx_price is not None
            and spx_price <= 0
        ):
            spx_price = None

        summary = build_iron_condor_summary(
            positions=positions,
            spx_price=spx_price,
        )

        if not summary:
            return {
                "status": "UNSUPPORTED",
                "connected": (
                    tastytrade_api
                    .get_status()
                    .get("connected", False)
                ),
                "position": None,
                "leg_count": len(positions),
                "message": (
                    "Open positions could not be grouped "
                    "into one Iron Condor."
                ),
            }

        return {
            "status": "OK",
            "connected": (
                tastytrade_api
                .get_status()
                .get("connected", False)
            ),
            "position": summary,
        }

    except Exception as error:
        return {
            "status": "ERROR",
            "connected": False,
            "position": None,
            "message": str(error),
        }