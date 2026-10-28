"""Pure snapshot analysis. No broker calls, credentials or execution."""
import math
from datetime import datetime, timezone

def analyze_condors(snapshot, spot, expected_move, width=10, minimum_pop=70):
    values=(spot,expected_move,width,minimum_pop)
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in values):
        raise ValueError("Analysis inputs must be finite")
    if spot<=0 or expected_move<=0 or width<=0 or width>100 or not 1<=minimum_pop<=99:
        raise ValueError("Invalid analysis inputs")
    quotes={}
    now=datetime.now(timezone.utc)
    for q in snapshot.get("quotes",[]):
        try:
            age=(now-datetime.fromisoformat(q["timestamp"].replace("Z","+00:00"))).total_seconds()
            bid,ask,strike=float(q["bid"]),float(q["ask"]),float(q["strike"])
            if not (-60<=age<=120 and all(math.isfinite(x) for x in (bid,ask,strike)) and 0<=bid<=ask):
                continue
            if q["type"] in ("put","call"):
                quotes[(q["type"],strike)]=dict(q,mid=(bid+ask)/2,strike=strike)
        except (KeyError,ValueError,TypeError,AttributeError):
            continue
    spreads={"put":[],"call":[]}
    for (kind,strike),short in quotes.items():
        if (kind=="put" and strike>=spot) or (kind=="call" and strike<=spot):
            continue
        long=quotes.get((kind,strike-width if kind=="put" else strike+width))
        if long:
            credit=short["mid"]-long["mid"]
            if 0<credit<width:
                spreads[kind].append((short,long,credit))
    cdf=lambda x:(1+math.erf(x/math.sqrt(2)))/2
    results=[]
    for put in spreads["put"]:
        for call in spreads["call"]:
            credit=put[2]+call[2]
            if not 0<credit<width:
                continue
            lower,upper=put[0]["strike"]-credit,call[0]["strike"]+credit
            pop=100*max(0,min(1,cdf((upper-spot)/expected_move)-cdf((lower-spot)/expected_move)))
            if pop<minimum_pop:
                continue
            legs=[put[0],put[1],call[0],call[1]]
            results.append({"put_short":put[0]["strike"],"put_long":put[1]["strike"],
                "call_short":call[0]["strike"],"call_long":call[1]["strike"],
                "credit_points":round(credit,4),"premium_dollars":round(credit*100,2),
                "max_loss_before_fees":round((width-credit)*100,2),
                "lower_breakeven":round(lower,4),"upper_breakeven":round(upper,4),
                "modeled_pop":round(pop,2),"oldest_quote_timestamp":min(
                    (q["timestamp"] for q in legs),key=lambda x:datetime.fromisoformat(x.replace("Z","+00:00"))),
                "symbols":[q["symbol"] for q in legs]})
    results.sort(key=lambda x:(-x["premium_dollars"],-x["modeled_pop"]))
    return {"condors":results[:10],"matching_count":len(results),"contracts":1,
            "pop_source":"normal approximation using manual SPX reference and expected move",
            "order_submission_available":False,"snapshot_only":True}
