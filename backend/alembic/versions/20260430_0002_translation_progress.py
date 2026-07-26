"""add translation progress fields

Revision ID: 20260430_0002
Revises: 20260424_0001
Create Date: 2026-04-30 17:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260430_0002"
down_revision = "20260424_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("books")}
    if "translation_total" not in existing_columns:
        op.add_column("books", sa.Column("translation_total", sa.Integer(), nullable=True))
    if "translation_completed" not in existing_columns:
        op.add_column("books", sa.Column("translation_completed", sa.Integer(), nullable=True))
    if "translation_failed" not in existing_columns:
        op.add_column("books", sa.Column("translation_failed", sa.Integer(), nullable=True))
    op.execute("UPDATE books SET translation_total = 0 WHERE translation_total IS NULL")
    op.execute("UPDATE books SET translation_completed = 0 WHERE translation_completed IS NULL")
    op.execute("UPDATE books SET translation_failed = 0 WHERE translation_failed IS NULL")
    op.execute("UPDATE books SET status = 'loaded' WHERE status = 'ready'")
    op.execute("UPDATE books SET status = 'translating' WHERE status = 'processing'")
    op.execute("UPDATE books SET status = 'failed' WHERE status = 'error'")


def downgrade() -> None:
    op.execute("UPDATE books SET status = 'ready' WHERE status IN ('loaded', 'translated')")
    op.execute("UPDATE books SET status = 'processing' WHERE status = 'translating'")
    op.execute("UPDATE books SET status = 'error' WHERE status = 'failed'")
    op.drop_column("books", "translation_failed")
    op.drop_column("books", "translation_completed")
    op.drop_column("books", "translation_total")
