"""Create support requests table.

Revision ID: c5f8a12d6e31
Revises: b4e2c71a9d60
"""

from alembic import op
import sqlalchemy as sa


revision = "c5f8a12d6e31"
down_revision = "b4e2c71a9d60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="OPEN",
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
        "ix_support_requests_email",
        "support_requests",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_support_requests_status",
        "support_requests",
        ["status"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_support_requests_status",
        table_name="support_requests",
    )
    op.drop_index(
        "ix_support_requests_email",
        table_name="support_requests",
    )
    op.drop_table("support_requests")
