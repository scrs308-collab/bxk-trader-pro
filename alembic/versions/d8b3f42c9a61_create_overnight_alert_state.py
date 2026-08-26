"""create overnight alert state

Revision ID: d8b3f42c9a61
Revises: c91f4e2a7b10
Create Date: 2026-08-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8b3f42c9a61"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "c91f4e2a7b10"
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "overnight_alert_states",
        sa.Column(
            "scope",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "reason_code",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column(
            "last_alerted_state",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "last_alerted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("scope"),
    )


def downgrade() -> None:
    op.drop_table(
        "overnight_alert_states"
    )
