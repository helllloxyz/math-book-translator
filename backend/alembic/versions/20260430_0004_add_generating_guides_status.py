"""add generating guides book status

Revision ID: 20260430_0004
Revises: 20260430_0003
Create Date: 2026-04-30 19:00:00
"""

from alembic import op


revision = "20260430_0004"
down_revision = "20260430_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite stores SQLAlchemy Enum values as text here. PostgreSQL deployments
    # need the enum value added before rows can use it.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE bookstatus ADD VALUE IF NOT EXISTS 'generating_guides'")


def downgrade() -> None:
    op.execute("UPDATE books SET status = 'translated' WHERE status = 'generating_guides'")
