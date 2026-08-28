from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.market_data import market_data
from bxk_app.market_engine import market_engine
from bxk_app.position_monitor import (
    build_position_summaries,
)
from bxk_app.services.execution_audit import (
    read_recent_submitted_orders,
)


def _leg_symbols(item: dict) -> frozenset[str]:
    return frozenset(
        str(leg.get("symbol") or "").strip()
        for leg in (item.get("legs") or [])
        if str(leg.get("symbol") or "").strip()
    )


def link_positions_to_submissions(
    summaries: list[dict],
    submissions: list[dict],
) -> list[dict]:
    """Link open positions to exact audited broker orders."""

    available_submissions = list(submissions or [])
    linked = []

    for summary in summaries or []:
        enriched = dict(summary)
        position_symbols = _leg_symbols(summary)
        match_index = None

        if len(position_symbols) == 4:
            for index, submission in enumerate(
                available_submissions
            ):
                order = submission.get("order") or {}

                if _leg_symbols(order) == position_symbols:
                    match_index = index
                    break

        if match_index is not None:
            submission = available_submissions.pop(
                match_index
            )
            order = submission.get("order") or {}
            enriched.update({
                "broker_linked": True,
                "broker_order_id": submission.get(
                    "order_id"
                ),
                "submitted_at": submission.get(
                    "timestamp_utc"
                ),
                "submitted_limit_credit": order.get(
                    "limit_price",
                    order.get("credit"),
                ),
            })
        else:
            enriched["broker_linked"] = False

        linked.append(enriched)

    return linked


def get_position_monitor():
    """
    Return open SPX option legs grouped into separate
    Iron Condor position summaries.
    """

    try:

        connected = tastytrade_api.authenticate()

        positions = (
            tastytrade_api.get_position_summary()
            if connected
            else []
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

        summaries = link_positions_to_submissions(
            summaries,
            read_recent_submitted_orders(),
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
