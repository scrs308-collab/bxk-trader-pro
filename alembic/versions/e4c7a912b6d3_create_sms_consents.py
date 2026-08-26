"""create sms consents

Revision ID: e4c7a912b6d3
Revises: d8b3f42c9a61
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "e4c7a912b6d3"
down_revision = "d8b3f42c9a61"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sms_consents",
        sa.Column(
            "phone_e164",
            sa.String(length=20),
            primary_key=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "consent_version",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "consent_text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "consent_source",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table(
        "sms_consents"
    )
