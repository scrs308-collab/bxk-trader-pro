"""Add secure setup invitations and database session revocation.

Revision ID: b23c45d67e89
Revises: a12b34c56d78
"""
from alembic import op
import sqlalchemy as sa

revision = "b23c45d67e89"
down_revision = "a12b34c56d78"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "setup_invitations",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id")),
    )


def downgrade():
    op.drop_table("setup_invitations")
    op.drop_column("users", "session_version")
