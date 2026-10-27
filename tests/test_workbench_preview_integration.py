from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from bxk_app.routes import workbench_preview as routes
from bxk_app.authorization import require_owner
from bxk_app.database import get_db
from bxk_app.services.workbench_dry_run import run_dry_run, production_policy
from bxk_app.services.workbench_analysis import analyze_condors


def fixture():
    expiry=datetime.now(timezone.utc).date().isoformat()
    compact=expiry[2:4]+expiry[5:7]+expiry[8:10]
    strikes=[7660,7650,7725,7735]
    symbols=[f'SPXW  {compact}{kind}{s*1000:08d}' for s,kind in zip(strikes,['P','P','C','C'])]
    p=dict(zip(['put_short','put_long','call_short','call_long'],strikes))
    p.update(credit_points=2.5,symbols=symbols,oldest_quote_timestamp=datetime.now(timezone.utc).isoformat())
    payload=routes.PositionReviewRequest(**{k:v for k,v in p.items() if k not in ['symbols','oldest_quote_timestamp']},expiration=expiry,min_strike=7640,max_strike=7740,spot=7700,expected_move=20,width=10,minimum_pop=70)
    return {'position':p},payload


def setup_broker():
    broker=Mock(last_error=None)
    broker.authenticate.return_value=True
    broker.get_default_account_number.return_value='PRIVATE_ACCOUNT'
    broker.get_positions.return_value=[]
    broker.get_live_orders.return_value=[]
    def preview(order,account_number):
        legs=[{'instrument-type':'Equity Option','symbol':x['symbol'],'quantity':1,'action':'Sell to Open' if x['action']=='SELL' else 'Buy to Open'} for x in order['legs']]
        payload={'legs':legs,'price':str(order['limit_price']),'order-type':'Limit','time-in-force':'Day','price-effect':'Credit'}
        impact=order['max_risk']+6.88
        return {'payload':payload,'broker_response':{'data':{'order':dict(payload,status='Received'),'warnings':[], 'errors':[], 'buying-power-effect':{'current-buying-power':20000,'change-in-buying-power':impact,'new-buying-power':20000-impact},'fee-calculation':{'total-fees':6.88}}}}
    broker.preview_order.side_effect=preview
    return broker


def policy():
    p=production_policy()
    p['session']=lambda:dict(passed=True,message='Session verified')
    p['reserve']=lambda session,user:15000
    return p


def test_real_production_checks_pass_without_execution_lock():
    review,payload=fixture();broker=setup_broker()
    result=run_dry_run(review,payload,broker,None,{'user_id':'fixture'},policy())
    assert result['passed'],result
    assert result['fees']==6.88 and result['buying_power']['impact']==756.88
    assert result['submitted'] is False and result['review_lock_issued'] is False
    broker.submit_order.assert_not_called();broker.submit_live_order.assert_not_called()


@pytest.mark.parametrize('blocked',['session','risk','position','pending_order','unavailable_positions','reserve'])
def test_risk_failures_block(blocked):
    review,payload=fixture();broker=setup_broker();p=policy()
    if blocked=='session':p['session']=lambda:dict(passed=False,message='Closed')
    elif blocked=='risk':p['validate']=lambda *a,**k:([{'name':'risk','passed':False,'message':'Risk too high'}],['blocked'])
    elif blocked=='position':broker.get_positions.return_value=[{'symbol':review['position']['symbols'][0],'quantity':1,'quantity-direction':'Long'}]
    elif blocked=='pending_order':broker.get_live_orders.return_value=[{'id':'1','status':'Live','legs':[{'symbol':review['position']['symbols'][0]}]}]
    elif blocked=='unavailable_positions':broker.get_positions.return_value=None
    elif blocked=='reserve':p['reserve']=lambda session,user:19999
    if blocked=='unavailable_positions':
        with pytest.raises(HTTPException):run_dry_run(review,payload,broker,None,{},p)
    else:
        assert not run_dry_run(review,payload,broker,None,{},p)['passed']
    if blocked!='reserve':broker.preview_order.assert_not_called()
    broker.submit_order.assert_not_called()


def test_tampered_contract_rejected():
    review,payload=fixture();review['position']['symbols'][0]='wrong'
    broker=setup_broker()
    with pytest.raises(HTTPException):run_dry_run(review,payload,broker,None,{},policy())
    broker.authenticate.assert_not_called()


def test_flag_off_and_owner_boundary(monkeypatch):
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[get_db]=lambda:None
    app.dependency_overrides[require_owner]=lambda:{'role':'OWNER','user_id':str(uuid.uuid4())}
    monkeypatch.delenv('BXK_WORKBENCH_PREVIEW_ENABLED',raising=False)
    client=TestClient(app)
    assert client.get('/api/workbench-preview/expirations').status_code==404
    app.dependency_overrides.pop(require_owner)
    monkeypatch.setenv('BXK_WORKBENCH_PREVIEW_ENABLED','true')
    assert client.get('/api/workbench-preview/expirations').status_code==403


def test_scoped_connection_never_uses_owner_fallback():
    from bxk_app.services import broker_connection_service as service
    user={'user_id':str(uuid.uuid4()),'role':'OWNER'}
    with patch.object(service,'get_user_tastytrade_connection',return_value=None),patch.object(service,'resolve_tastytrade_broker') as resolve:
        with pytest.raises(HTTPException):routes.scoped_broker(None,user)
        resolve.assert_not_called()


def test_no_preview_submission_routes():
    assert not any('submit' in route.path for route in routes.router.routes)


def test_http_analysis_review_and_dry_run(monkeypatch):
    from bxk_app.services import workbench_dry_run as dry
    review,payload=fixture();broker=setup_broker()
    stamp=datetime.now(timezone.utc).isoformat()
    data={'quotes':[dict(symbol=symbol,strike=strike,type=kind,bid=bid,ask=bid,timestamp=stamp) for symbol,strike,kind,bid in zip(review['position']['symbols'],[7660,7650,7725,7735],['put','put','call','call'],[2,.75,2,.75])], 'checked_at':stamp}
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[get_db]=lambda:None
    app.dependency_overrides[require_owner]=lambda:{'role':'OWNER','user_id':str(uuid.uuid4())}
    monkeypatch.setenv('BXK_WORKBENCH_PREVIEW_ENABLED','true')
    monkeypatch.setattr(routes,'scoped_broker',lambda session,user:broker)
    monkeypatch.setattr(routes,'quote_snapshot',lambda *a:data)
    monkeypatch.setattr(dry,'production_policy',policy)
    client=TestClient(app)
    body=payload.model_dump()
    params={k:body[k] for k in ['expiration','min_strike','max_strike','spot','expected_move','width','minimum_pop']}
    response=client.get('/api/workbench-preview/condors',params=params)
    assert response.status_code==200 and len(response.json()['condors'])==1
    response=client.post('/api/workbench-preview/position-review',json=body)
    assert response.status_code==200 and response.json()['review_lock_issued'] is False
    response=client.post('/api/workbench-preview/dry-run',json=body)
    assert response.status_code==200 and response.json()['passed'],response.text
    assert 'PRIVATE_ACCOUNT' not in response.text
    broker.submit_order.assert_not_called()


def test_broker_errors_block_success():
    review,payload=fixture();broker=setup_broker();original=broker.preview_order.side_effect
    def error(*a,**k):
        result=original(*a,**k);result['broker_response']['data']['errors']=[{'code':'blocked'}];return result
    broker.preview_order.side_effect=error
    assert not run_dry_run(review,payload,broker,None,{},policy())['passed']


def test_dry_run_cannot_create_live_review_lock():
    from bxk_app.routes import order as legacy
    before=set(legacy._ORDER_REVIEW_LOCKS)
    review,payload=fixture()
    result=run_dry_run(review,payload,setup_broker(),None,{},policy())
    assert result['passed']
    assert set(legacy._ORDER_REVIEW_LOCKS)==before
    assert not any(k in result for k in ['review_id','confirmation_token','account','broker_response'])


def test_preview_page_flag_owner_and_csp(monkeypatch):
    from bxk_app.workbench_preview import workbench_page
    from starlette.requests import Request
    request=Request({'type':'http','method':'GET','path':'/workbench','headers':[]})
    monkeypatch.delenv('BXK_WORKBENCH_PREVIEW_ENABLED',raising=False)
    with pytest.raises(HTTPException) as error:workbench_page(request)
    assert error.value.status_code==404
    monkeypatch.setenv('BXK_WORKBENCH_PREVIEW_ENABLED','true')
    with pytest.raises(HTTPException) as error:workbench_page(request)
    assert error.value.status_code==403
    request.state.bxk_user={'role':'OWNER'}
    response=workbench_page(request)
    assert response.headers['cache-control']=='no-store'
    assert "form-action 'none'" in response.headers['content-security-policy']
