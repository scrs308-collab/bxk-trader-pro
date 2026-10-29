import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from bxk_app import config
from bxk_app.database import Base, get_db
from bxk_app.db_models.user import User, UserRole
from bxk_app.db_models.message import ChatMessage
from bxk_app.routes.messages import router

@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setattr(config, 'BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED', False)
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        users=[User(username=n,email=n+'@example.com',password_hash='unused',role=r,is_active=True) for n,r in [('owner',UserRole.OWNER),('alice',UserRole.BETA),('bob',UserRole.VIEWER)]]
        s.add_all(users);s.commit();ids={u.username:str(u.id) for u in users}
    app=FastAPI();app.include_router(router)
    identity={'name':'owner'}
    @app.middleware('http')
    async def auth(request,call_next):
        if identity['name']:
            request.state.bxk_user={'user_id':ids[identity['name']]}
        return await call_next(request)
    def db():
        with Session(engine) as s: yield s
    app.dependency_overrides[get_db]=db
    with TestClient(app) as client:
        yield client,identity,ids,engine

def post(client,topic='group',body='hello',key=None):
    return client.post('/api/messages/'+topic,json={'body':body,'request_id':str(key or uuid.uuid4())})

def test_private_two_way_and_no_subscriber_snooping(chat):
    c,who,ids,_=chat
    assert post(c,'private?subscriber_id='+ids['alice'],'Hi Alice').status_code==200
    who['name']='alice'
    assert c.get('/api/messages/private').json()['messages'][0]['body']=='Hi Alice'
    assert post(c,'private','Hello owner').status_code==200
    assert c.get('/api/messages/subscribers').status_code==403
    assert c.get('/api/messages/private?subscriber_id='+ids['bob']).status_code==404
    who['name']='bob'
    assert c.get('/api/messages/private').json()['messages']==[]
    assert c.get('/api/messages/private?subscriber_id='+ids['alice']).status_code==404
    assert post(c,'private?subscriber_id='+ids['alice']).status_code==404
    who['name']='owner'
    rows=c.get('/api/messages/private?subscriber_id='+ids['alice']).json()['messages']
    assert [r['body'] for r in rows]==['Hi Alice','Hello owner']
    assert c.get('/api/messages/private').status_code==400

def test_group_unread_and_private_read_scope(chat):
    c,who,ids,_=chat
    mid=post(c).json()['id']; private_id=post(c,'private?subscriber_id='+ids['alice']).json()['id']
    who['name']='alice'
    unread=c.get('/api/messages/inbox').json()
    assert unread['total_unread']==2
    assert c.post('/api/messages/group/read',json={'last_read_id':private_id}).status_code==400
    assert c.post('/api/messages/group/read',json={'last_read_id':mid}).status_code==200
    assert c.get('/api/messages/inbox').json()['total_unread']==1
    assert c.post('/api/messages/group/read',json={'last_read_id':0}).status_code==200
    assert c.get('/api/messages/inbox').json()['unread'].get('group',0)==0
    who['name']='bob'
    assert c.get('/api/messages/group').json()['messages'][0]['body']=='hello'
    assert c.get('/api/messages/inbox').json()['total_unread']==1

def test_idempotency_csrf_validation_and_rate_limit(chat):
    c,who,ids,engine=chat
    key=uuid.uuid4();first=post(c,key=key)
    assert post(c,key=key).json()['id']==first.json()['id']
    assert post(c,body='different',key=key).status_code==409
    assert post(c,'private?subscriber_id='+ids['alice'],key=key).status_code==409
    assert post(c,body='   ').status_code==422
    assert post(c,body='x'*4001).status_code==422
    assert c.post('/api/messages/group',json={'body':'hello','request_id':str(uuid.uuid4())},headers={'Origin':'https://evil.example'}).status_code==403
    assert c.post('/api/messages/group',json={'body':'hello','request_id':str(uuid.uuid4()),'sender_id':ids['bob']}).status_code==422
    for _ in range(19): assert post(c).status_code==200
    assert post(c).status_code==429
    assert post(c,key=key).status_code==200
    with Session(engine) as s: assert len(s.scalars(select(ChatMessage)).all())==20

def test_owner_moderation_and_history_pagination(chat):
    c,who,ids,engine=chat
    with Session(engine) as s:
        s.add_all([ChatMessage(channel='group',sender_id=uuid.UUID(ids['alice']),request_id=uuid.uuid4(),body=str(n)) for n in range(60)])
        s.commit()
    latest=c.get('/api/messages/group').json();assert len(latest['messages'])==50 and latest['has_more']
    earlier=c.get('/api/messages/group?before='+str(latest['messages'][0]['id'])).json()
    assert len(earlier['messages'])==10 and not earlier['has_more']
    mid=latest['messages'][-1]['id']
    who['name']='bob';assert c.delete('/api/messages/items/'+str(mid)).status_code==403
    who['name']='owner';assert c.delete('/api/messages/items/'+str(mid)).status_code==200
    who['name']='bob';item=c.get('/api/messages/group').json()['messages'][-1]
    assert item['removed'] and item['body'] is None
    with Session(engine) as s: assert s.get(ChatMessage,mid).body==''

def test_inactive_expired_and_unauthenticated_access(chat,monkeypatch):
    c,who,ids,engine=chat
    who['name']=None;assert c.get('/api/messages/inbox').status_code==403
    who['name']='alice'
    with Session(engine) as s:
        u=s.get(User,uuid.UUID(ids['alice']));u.is_active=False;s.commit()
    assert c.get('/api/messages/group').status_code==403
    who['name']='owner';assert post(c,'private?subscriber_id='+ids['alice']).status_code==403
    who['name']='bob';monkeypatch.setattr(config,'BXK_SUBSCRIPTION_ENFORCEMENT_ENABLED',True)
    assert c.get('/api/messages/group').status_code==402
    assert post(c).status_code==402
    who['name']='owner';assert c.get('/api/messages/inbox').status_code==200

def test_roster_no_email_and_invalid_topic(chat):
    c,who,ids,_=chat
    data=c.get('/api/messages/subscribers').json()
    assert {u['username'] for u in data['subscribers']}=={'alice','bob'}
    assert all('email' not in u for u in data['subscribers'])
    assert c.get('/api/messages/subscribers?q=alice').json()['subscribers'][0]['id']==ids['alice']
    assert c.get('/api/messages/other').status_code==404
    assert c.get('/api/messages/group?subscriber_id='+ids['alice']).status_code==400
