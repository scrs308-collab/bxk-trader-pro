"""Authenticated, user-scoped in-app messaging. No external notifications."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from bxk_app.authorization import get_authenticated_user
from bxk_app.database import get_db
from bxk_app.db_models.user import User, UserRole
from bxk_app.db_models.message import ChatMessage, ChatReadState
from bxk_app.services.subscription_service import evaluate_subscription_access, get_user_subscription

router = APIRouter(tags=['Messages'])

def participant(request: Request, response: Response, session: Session = Depends(get_db)):
    context = get_authenticated_user(request)
    try:
        user_id = UUID(str(context.get('user_id') or ''))
    except ValueError:
        raise HTTPException(403, 'Sign in with your database account to use Messages.') from None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(403, 'An active account is required.')
    if not evaluate_subscription_access(user, get_user_subscription(session, user.id))['access_granted']:
        raise HTTPException(402, 'An active subscription is required for Messages.')
    response.headers['Cache-Control'] = 'no-store'
    return user

def same_origin(request: Request):
    origin = request.headers.get('origin')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Send messages from Trader Pro.')
    if origin:
        parsed = urlsplit(origin)
        # Compare the public Host rather than proxy-internal HTTP scheme.
        if parsed.netloc != request.url.netloc or parsed.scheme not in {'https', 'http'} or parsed.path not in {'', '/'}:
            raise HTTPException(403, 'Send messages from Trader Pro.')

def channel_for(topic, subscriber_id, user, session, *, sending=False):
    if topic == 'group':
        if subscriber_id is not None:
            raise HTTPException(400, 'Group chat has no private recipient.')
        return 'group'
    if topic != 'private':
        raise HTTPException(404, 'Conversation not found.')
    if user.role == UserRole.OWNER:
        if subscriber_id is None:
            raise HTTPException(400, 'Choose a subscriber.')
        target = session.get(User, subscriber_id)
        if target is None or target.role == UserRole.OWNER:
            raise HTTPException(404, 'Subscriber not found.')
        if sending and (not target.is_active or not evaluate_subscription_access(target, get_user_subscription(session, target.id))['access_granted']):
            raise HTTPException(403, 'This subscriber does not currently have messaging access.')
    else:
        if subscriber_id is not None and subscriber_id != user.id:
            raise HTTPException(404, 'Conversation not found.')
        subscriber_id = user.id
    return 'private:' + str(subscriber_id)

def visible(user):
    return or_(ChatMessage.channel == 'group', ChatMessage.channel.like('private:%')) if user.role == UserRole.OWNER else ChatMessage.channel.in_(['group', 'private:' + str(user.id)])

def message_data(item, sender, user):
    stamp = item.created_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return dict(id=item.id, sender=sender.username, owner=sender.role == UserRole.OWNER,
                mine=item.sender_id == user.id, body=None if item.removed_at else item.body,
                removed=item.removed_at is not None, created_at=stamp.isoformat())

class SendMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=1, max_length=4000)
    request_id: UUID
    @field_validator('body', mode='before')
    @classmethod
    def trim(cls, value):
        if isinstance(value, str) and '\x00' in value:
            raise ValueError('Messages cannot contain null characters.')
        return value.strip() if isinstance(value, str) else value

class ReadMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    last_read_id: int = Field(ge=0)

@router.get('/messages', include_in_schema=False)
def page(user=Depends(participant)):
    return FileResponse('static/messages.html', headers={'Cache-Control': 'no-store'})

@router.get('/api/messages/inbox')
def inbox(user=Depends(participant), session: Session = Depends(get_db)):
    rows = session.execute(select(ChatMessage.channel, func.count(ChatMessage.id)).outerjoin(
        ChatReadState, and_(ChatReadState.channel == ChatMessage.channel, ChatReadState.user_id == user.id)
    ).where(visible(user), ChatMessage.sender_id != user.id, ChatMessage.removed_at.is_(None),
            ChatMessage.id > func.coalesce(ChatReadState.last_read_id, 0)).group_by(ChatMessage.channel)).all()
    return dict(user_id=str(user.id), username=user.username, owner=user.role == UserRole.OWNER,
                unread=dict(rows), total_unread=sum(count for _, count in rows))

@router.get('/api/messages/subscribers')
def subscribers(q: str = Query('', max_length=100), offset: int = Query(0, ge=0),
                user=Depends(participant), session: Session = Depends(get_db)):
    if user.role != UserRole.OWNER:
        raise HTTPException(403, 'Owner access required.')
    users = session.scalars(select(User).where(User.role != UserRole.OWNER,
        User.username.contains(q, autoescape=True)).order_by(User.username, User.id).offset(offset).limit(51)).all()
    return dict(subscribers=[dict(id=str(u.id), username=u.username, active=u.is_active) for u in users[:50]], has_more=len(users)>50)

@router.get('/api/messages/{topic}')
def history(topic: str, subscriber_id: UUID | None = None, before: int | None = Query(None, gt=0),
            user=Depends(participant), session: Session = Depends(get_db)):
    channel = channel_for(topic, subscriber_id, user, session)
    query = select(ChatMessage, User).join(User, User.id == ChatMessage.sender_id).where(ChatMessage.channel == channel)
    if before:
        query = query.where(ChatMessage.id < before)
    rows = session.execute(query.order_by(ChatMessage.id.desc()).limit(51)).all()
    return dict(channel=channel, messages=[message_data(m, s, user) for m, s in reversed(rows[:50])], has_more=len(rows)>50)

@router.post('/api/messages/{topic}', dependencies=[Depends(same_origin)])
def send(topic: str, payload: SendMessage, subscriber_id: UUID | None = None,
         user=Depends(participant), session: Session = Depends(get_db)):
    channel = channel_for(topic, subscriber_id, user, session, sending=True)
    # Serialize sends per user to make the persisted limit effective across workers.
    session.execute(select(User.id).where(User.id == user.id).with_for_update()).first()
    previous = session.scalar(select(ChatMessage).where(ChatMessage.sender_id == user.id, ChatMessage.request_id == payload.request_id))
    if previous:
        if previous.channel != channel or previous.body != payload.body:
            raise HTTPException(409, 'This send identifier already belongs to a different message.')
        return message_data(previous, user, user)
    recent = session.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.sender_id == user.id,
        ChatMessage.created_at >= datetime.now(timezone.utc) - timedelta(minutes=1)))
    if recent >= 20:
        raise HTTPException(429, 'Please wait a minute before sending more messages.')
    item = ChatMessage(channel=channel, sender_id=user.id, request_id=payload.request_id, body=payload.body)
    session.add(item)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = session.scalar(select(ChatMessage).where(ChatMessage.sender_id == user.id, ChatMessage.request_id == payload.request_id))
        if previous and previous.channel == channel and previous.body == payload.body:
            return message_data(previous, user, user)
        raise HTTPException(409, 'Message could not be saved. Refresh and try again.') from None
    session.refresh(item)
    return message_data(item, user, user)

@router.post('/api/messages/{topic}/read', dependencies=[Depends(same_origin)])
def mark_read(topic: str, payload: ReadMessage, subscriber_id: UUID | None = None,
              user=Depends(participant), session: Session = Depends(get_db)):
    channel = channel_for(topic, subscriber_id, user, session)
    latest = session.scalar(select(func.max(ChatMessage.id)).where(ChatMessage.channel == channel)) or 0
    if payload.last_read_id and session.scalar(select(ChatMessage.id).where(ChatMessage.channel == channel, ChatMessage.id == payload.last_read_id)) is None:
        raise HTTPException(400, 'Read position does not belong to this conversation.')
    # Lock the same user row used by sends to avoid read-state creation races.
    session.execute(select(User.id).where(User.id == user.id).with_for_update()).first()
    state = session.get(ChatReadState, (user.id, channel))
    if state is None:
        state = ChatReadState(user_id=user.id, channel=channel, last_read_id=0)
        session.add(state)
    state.last_read_id = max(state.last_read_id, min(payload.last_read_id, latest))
    session.commit()
    return {'read': True}

@router.delete('/api/messages/items/{message_id}', dependencies=[Depends(same_origin)])
def remove(message_id: int, user=Depends(participant), session: Session = Depends(get_db)):
    if user.role != UserRole.OWNER:
        raise HTTPException(403, 'Only the owner can remove messages.')
    item = session.get(ChatMessage, message_id)
    if item is None:
        raise HTTPException(404, 'Message not found.')
    item.body = ''
    item.removed_at = datetime.now(timezone.utc)
    item.removed_by = user.id
    session.commit()
    return {'removed': True}
