from fastapi import APIRouter

from bxk_app.services.broker_service import (
    get_account_summary,
    get_positions_summary,
    get_test_new_broker,
    get_test_quote,
    get_test_tastytrade,
    get_test_tastytrade_balances,
    get_test_tastytrade_positions,
    get_test_tastytrade_rest,
)

router = APIRouter(
    prefix="/api",
    tags=["Broker"],
)


@router.get("/test-tastytrade")
def test_tastytrade():
    return get_test_tastytrade()


@router.get("/test-tastytrade-rest")
def test_tastytrade_rest():
    return get_test_tastytrade_rest()


@router.get("/test-tastytrade-balances")
def test_tastytrade_balances():
    return get_test_tastytrade_balances()


@router.get("/test-tastytrade-positions")
def test_tastytrade_positions():
    return get_test_tastytrade_positions()


@router.get("/positions-summary")
def positions_summary():
    return get_positions_summary()


@router.get("/account-summary")
def account_summary():
    return get_account_summary()


@router.get("/test-quote/{symbol}")
def test_quote(symbol: str):
    return get_test_quote(symbol)


@router.get("/test-new-broker")
def test_new_broker():
    return get_test_new_broker()