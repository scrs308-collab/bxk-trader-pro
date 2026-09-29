"""Add per-user buying power reserve.

Revision ID: a9c18d7e2f40
Revises: 3e8a7c1d9b42
"""

from alembic import op
import sqlalchemy as sa

revision = "a9c18d7e2f40"
down_revision = "3e8a7c1d9b42"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("min_remaining_buying_power", sa.Numeric(12, 2), nullable=True),
    )
    op.execute(
        "UPDATE users SET min_remaining_buying_power = 1000.00 "
        "WHERE lower(username) = 'katiedixon530' AND role = 'BETA'"
    )


def downgrade():
    op.drop_column("users", "min_remaining_buying_power")
