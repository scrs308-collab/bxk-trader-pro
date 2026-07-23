from fastapi import APIRouter

from bxk_app.broker_tastytrade import tastytrade_api
from bxk_app.brokers.tastytrade import (
    broker as new_tastytrade_broker,
)
from bxk_app.tastytrade_client import tastytrade_client


router = APIRouter(
    prefix="/api",
    tags=["Broker"],
)


@router.get("/test-tastytrade")
def test_tastytrade():
    connected = tastytrade_client.connect()

    return {
        "connected": connected,
        "status": tastytrade_client.get_status(),
        "accounts": tastytrade_client.get_accounts(),
    }


@router.get("/test-tastytrade-rest")
def test_tastytrade_rest():
    connected = tastytrade_api.authenticate()

    accounts = (
        tastytrade_api.get_accounts()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "accounts": accounts,
    }


@router.get("/test-tastytrade-balances")
def test_tastytrade_balances():
    connected = tastytrade_api.authenticate()

    balances = (
        tastytrade_api.get_balances()
        if connected
        else None
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "balances": balances,
    }


@router.get("/test-tastytrade-positions")
def test_tastytrade_positions():
    connected = tastytrade_api.authenticate()

    positions = (
        tastytrade_api.get_positions()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "positions": positions,
    }


@router.get("/positions-summary")
def positions_summary():
    connected = tastytrade_api.authenticate()

    positions = (
        tastytrade_api.get_position_summary()
        if connected
        else []
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "count": len(positions),
        "positions": positions,
    }


@router.get("/account-summary")
def account_summary():
    connected = tastytrade_api.authenticate()

    account = (
        tastytrade_api.get_account_summary()
        if connected
        else None
    )

    return {
        "connected": connected,
        "account": account,
    }


@router.get("/test-quote/{symbol}")
def test_quote(symbol: str):
    connected = tastytrade_api.authenticate()

    quote = (
        tastytrade_api.get_quote(
            symbol.upper()
        )
        if connected
        else None
    )

    return {
        "connected": connected,
        "status": tastytrade_api.get_status(),
        "symbol": symbol.upper(),
        "quote": quote,
    }


@router.get("/test-new-broker")
def test_new_broker():
    connected = new_tastytrade_broker.authenticate()

    return {
        "connected": connected,
        "status": new_tastytrade_broker.get_status(),
        "account": (
            new_tastytrade_broker.get_account_summary()
            if connected
            else None
        ),
        "spx": (
            new_tastytrade_broker.get_quote("SPX")
            if connected
            else None
        ),
        "vix": (
            new_tastytrade_broker.get_quote("VIX")
            if connected
            else None
        ),
    }