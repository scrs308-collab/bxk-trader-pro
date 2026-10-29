"""Add in-app private and group messages."""
from alembic import op
import sqlalchemy as sa
revision = 'c34d56e78f90'
down_revision = 'b23c45d67e89'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('channel', sa.String(48), nullable=False),
        sa.Column('sender_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('removed_at', sa.DateTime(timezone=True)),
        sa.Column('removed_by', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.UniqueConstraint('sender_id', 'request_id', name='uq_chat_sender_request'))
    op.create_index('ix_chat_channel_id', 'chat_messages', ['channel', 'id'])
    op.create_index('ix_chat_sender_created', 'chat_messages', ['sender_id', 'created_at'])
    op.create_table('chat_read_states',
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('channel', sa.String(48), primary_key=True),
        sa.Column('last_read_id', sa.Integer(), nullable=False))

def downgrade():
    op.drop_table('chat_read_states')
    op.drop_index('ix_chat_sender_created', table_name='chat_messages')
    op.drop_index('ix_chat_channel_id', table_name='chat_messages')
    op.drop_table('chat_messages')
