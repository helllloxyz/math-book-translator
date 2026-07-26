"""remove legacy book status values

Revision ID: 20260430_0003
Revises: 20260430_0002
Create Date: 2026-04-30 18:00:00
"""

from alembic import op


revision = "20260430_0003"
down_revision = "20260430_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE books SET status = 'loaded' WHERE status = 'ready'")
    op.execute("UPDATE books SET status = 'translating' WHERE status = 'processing'")
    op.execute("UPDATE books SET status = 'failed' WHERE status = 'error'")


def downgrade() -> None:
    op.execute("UPDATE books SET status = 'ready' WHERE status IN ('loaded', 'translated')")
    op.execute("UPDATE books SET status = 'processing' WHERE status = 'translating'")
    op.execute("UPDATE books SET status = 'error' WHERE status = 'failed'")
