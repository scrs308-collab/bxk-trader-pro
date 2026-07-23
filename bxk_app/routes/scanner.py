from fastapi import APIRouter

from bxk_app.services.scanner_service import (
    get_best_bear_call,
    get_best_bull_put,
    get_best_trade,
    get_strategy_rankings,
    get_test_candidate_grid,
    get_test_candidates,
    get_test_first_candidate_credit,
    get_test_scanner_engine,
    get_test_wing_optimizer,
)


router = APIRouter(
    prefix="/api",
    tags=["Scanner"],
)


@router.get("/test-wing-optimizer")
def test_wing_optimizer():
    return get_test_wing_optimizer()


@router.get("/test-scanner-engine")
def test_scanner_engine():
    return get_test_scanner_engine()


@router.get("/test-candidates")
def test_candidates():
    return get_test_candidates()


@router.get("/test-first-candidate-credit")
def test_first_candidate_credit():
    return get_test_first_candidate_credit()


@router.get("/test-candidate-grid")
def test_candidate_grid():
    return get_test_candidate_grid()


@router.get("/best-trade")
def best_trade():
    return get_best_trade()


@router.get("/best-bull-put")
def best_bull_put():
    return get_best_bull_put()


@router.get("/best-bear-call")
def best_bear_call():
    return get_best_bear_call()


@router.get("/strategy-rankings")
def strategy_rankings():
    return get_strategy_rankings()