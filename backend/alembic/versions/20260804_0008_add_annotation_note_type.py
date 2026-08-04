"""add annotation note type

Revision ID: 20260804_0008
Revises: 20260503_0007
Create Date: 2026-08-04 12:00:00
"""

from alembic import op


revision = "20260804_0008"
down_revision = "20260503_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE notetype ADD VALUE IF NOT EXISTS 'annotation'")


def downgrade() -> None:
    # SQLite stores this enum as text, while PostgreSQL cannot safely remove an
    # enum value without rebuilding the type and every dependent column.
    pass
