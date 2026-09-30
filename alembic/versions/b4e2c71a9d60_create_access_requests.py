"""Create access requests table.

Revision ID: b4e2c71a9d60
Revises: a9c18d7e2f40
"""

from alembic import op
import sqlalchemy as sa


revision = "b4e2c71a9d60"
down_revision = "a9c18d7e2f40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("broker", sa.String(length=64), nullable=True),
        sa.Column("intended_use", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_access_requests_email",
        "access_requests",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_access_requests_status",
        "access_requests",
        ["status"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_access_requests_status",
        table_name="access_requests",
    )
    op.drop_index(
        "ix_access_requests_email",
        table_name="access_requests",
    )
    op.drop_table("access_requests")
