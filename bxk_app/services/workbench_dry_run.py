"""Read-only broker dry-run orchestration. Never creates an execution review lock."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import HTTPException

def build_review_order(review, payload):
    p=review["position"]
    expiry=date.fromisoformat(payload.expiration)
    dte=(expiry-datetime.now(ZoneInfo("America/New_York")).date()).days
    credit=float(Decimal(str(payload.credit_points)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))
    if abs(credit-p["credit_points"])>0.10+1e-9:
        raise HTTPException(409,"Premium changed; review again")
    strikes=[p[k] for k in ("put_short","put_long","call_short","call_long")]
    if len(p["symbols"])!=4 or len(set(p["symbols"]))!=4:
        raise HTTPException(409,"Four distinct contracts required")
    compact=payload.expiration[2:4]+payload.expiration[5:7]+payload.expiration[8:10]
    for symbol,strike,kind in zip(p["symbols"],strikes,("P","P","C","C")):
        if symbol!=f"SPXW  {compact}{kind}{round(strike*1000):08d}":
            raise HTTPException(409,"Contract identifier does not match reviewed strikes")
    if payload.width!=int(payload.width):
        raise HTTPException(400,"Whole-point wing width required")
    risk=round((payload.width-credit)*100,2)
    return {"strategy":"iron_condor","symbol":"SPX","quantity":1,"expiration":payload.expiration,
        "dte":dte,"limit_price":credit,"price_effect":"Credit","max_risk":risk,"buying_power":risk,
        "order_type":"LIMIT","time_in_force":"DAY","quote_timestamp":p["oldest_quote_timestamp"],
        "legs":[{"symbol":symbol,"strike":strike,"action":action,"option_type":kind,"quantity":1}
                for symbol,strike,action,kind in zip(p["symbols"],strikes,
                    ("SELL","BUY","SELL","BUY"),("PUT","PUT","CALL","CALL"))]}

def production_policy():
    from bxk_app.routes import order
    return {"validate":order._validate_order,"overlap":order._check_existing_position_overlap,
            "evaluate":order._evaluate_broker_dry_run,"reserve":order._user_buying_power_reserve,
            "session":order._execution_session_gate}

def run_dry_run(review,payload,broker,session,user,policy=None):
    policy=policy or production_policy()
    order=build_review_order(review,payload)
    checks,errors=policy["validate"](order,requested_dte=order["dte"],
        requested_wing_width=int(payload.width),requested_contracts=1)
    session_check=policy["session"]()
    checks.append({"name":"execution_session","passed":session_check["passed"],
                   "message":session_check["message"]})
    if errors or not session_check["passed"]:
        return {"passed":False,"checks":checks,"broker_contacted":False,
                "order_submission_available":False,"review_lock_issued":False}
    reserve=policy["reserve"](session,user)
    if not broker.authenticate():
        raise HTTPException(503,"User broker authentication unavailable")
    account=broker.get_default_account_number()
    if not account:
        raise HTTPException(503,"Verified user broker account unavailable")
    positions=broker.get_positions(account_number=account)
    if broker.last_error or not isinstance(positions,list):
        raise HTTPException(503,"Existing positions could not be verified")
    overlap=policy["overlap"](order,positions)
    checks.append({"name":"existing_position_overlap","passed":overlap["passed"],
                   "message":overlap["message"]})
    if not overlap["passed"]:
        return {"passed":False,"checks":checks,"broker_contacted":True,
                "order_submission_available":False,"review_lock_issued":False}
    raw=broker.preview_order(order,account_number=account)
    if not isinstance(raw,dict):
        raise HTTPException(502,"Broker rejected dry-run; no order submitted")
    evaluation=policy["evaluate"](raw,order,min_remaining_buying_power=reserve)
    # Never expose raw broker responses, account identifiers or execution tokens.
    return {"passed":evaluation["passed"],"checks":checks+evaluation["checks"],
            "buying_power":evaluation.get("buying_power"),"fees":evaluation.get("fees"),
            "minimum_reserve":reserve,"broker_contacted":True,"user_scoped":True,
            "order_submission_available":False,"review_lock_issued":False,
            "dry_run_only":True,"submitted":False,
            "reviewed_credit":order["limit_price"],"defined_risk":order["max_risk"]}
