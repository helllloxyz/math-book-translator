"""add chapter content type

Revision ID: 20260503_0006
Revises: 20260501_0005
Create Date: 2026-05-03 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0006"
down_revision = "20260501_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("chapters")}
    if "content_type" not in existing_columns:
        op.add_column("chapters", sa.Column("content_type", sa.String(), nullable=True))
    op.execute("UPDATE chapters SET content_type = 'main_text' WHERE content_type IS NULL OR content_type = ''")


def downgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("chapters")}
    if "content_type" in existing_columns:
        op.drop_column("chapters", "content_type")
