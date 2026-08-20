from fastapi import APIRouter, HTTPException, Query

from bxk_app.services.overnight_risk_service import (
    get_live_overnight_risk,
)

from bxk_app.services.market_service import (
    get_debug_market,
    get_live_market,
    get_market_brief,
    get_recent_condor_risk_summaries,
    get_today_condor_risk_summary,
    refresh_market_data,
)
from bxk_app.universal_underlying_service import (
    discover_underlying,
)
from bxk_app.universal_option_analysis_service import (
    analyze_underlying,
)


router = APIRouter(
    prefix="/api",
    tags=["Market"],
)


@router.get("/refresh-market")
def refresh_market():
    return refresh_market_data()


@router.get("/market-brief")
def market_brief():
    return get_market_brief()


@router.get("/live-market")
def live_market(
    underlying: str = Query(
        "SPX",
        description=(
            "Currently enabled live analytical "
            "underlying: SPX or QQQ"
        ),
    ),
):
    try:
        return get_live_market(underlying)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/underlying-discovery")
def underlying_discovery(
    symbol: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Underlying symbol to discover "
            "through the broker option chain"
        ),
    ),
):
    try:
        return discover_underlying(
            symbol
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/underlying-analysis")
def underlying_analysis(
    symbol: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Option underlying symbol"
        ),
    ),
    dte: int | None = Query(
        None,
        ge=0,
        le=3650,
        description=(
            "Exact days to expiration"
        ),
    ),
    wing_width: float | None = Query(
        None,
        gt=0,
        description=(
            "Requested iron-condor wing width"
        ),
    ),
):
    try:
        return analyze_underlying(
            symbol,
            days_to_expiration=dte,
            wing_width=wing_width,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/overnight-risk")
def overnight_risk(
    prior_spx_close: float = Query(
        ...,
        gt=0,
        description=(
            "Prior regular-session SPX close"
        ),
    ),
    es_anchor_price: float | None = Query(
        None,
        gt=0,
        description=(
            "Optional ES price captured alongside "
            "the SPX closing snapshot"
        ),
    ),
):
    return get_live_overnight_risk(
        prior_spx_close=prior_spx_close,
        es_anchor_price=es_anchor_price,
    )


@router.get("/debug/market")
def debug_market():
    return get_debug_market()


@router.get("/condor-risk-summary/today")
def condor_risk_summary_today():
    return get_today_condor_risk_summary()


@router.get("/condor-risk-summary/recent")
def condor_risk_summary_recent(
    limit: int = 10,
):
    return get_recent_condor_risk_summaries(
        limit=limit
    )
