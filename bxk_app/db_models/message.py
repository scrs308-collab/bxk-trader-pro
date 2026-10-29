"""In-app messages; private threads are keyed by subscriber, never by recipient input."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from bxk_app.database import Base

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        UniqueConstraint('sender_id', 'request_id', name='uq_chat_sender_request'),
        Index('ix_chat_channel_id', 'channel', 'id'),
        Index('ix_chat_sender_created', 'sender_id', 'created_at'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id'), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey('users.id'))

class ChatReadState(Base):
    __tablename__ = 'chat_read_states'
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    channel: Mapped[str] = mapped_column(String(48), primary_key=True)
    last_read_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
