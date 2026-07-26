"""add source-aware note fields

Revision ID: 20260501_0005
Revises: 20260430_0004
Create Date: 2026-05-01 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260501_0005"
down_revision = "20260430_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("user_notes")}
    if "book_id" not in existing_columns:
        op.add_column("user_notes", sa.Column("book_id", sa.Integer(), nullable=True))
    if "source_type" not in existing_columns:
        op.add_column("user_notes", sa.Column("source_type", sa.String(), nullable=True))
    if "source_id" not in existing_columns:
        op.add_column("user_notes", sa.Column("source_id", sa.String(), nullable=True))
    if "source_title" not in existing_columns:
        op.add_column("user_notes", sa.Column("source_title", sa.String(), nullable=True))

    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("user_notes")}
    if op.f("ix_user_notes_book_id") not in existing_indexes:
        op.create_index(op.f("ix_user_notes_book_id"), "user_notes", ["book_id"], unique=False)
    if op.f("ix_user_notes_source_type") not in existing_indexes:
        op.create_index(op.f("ix_user_notes_source_type"), "user_notes", ["source_type"], unique=False)
    if op.f("ix_user_notes_source_id") not in existing_indexes:
        op.create_index(op.f("ix_user_notes_source_id"), "user_notes", ["source_id"], unique=False)

    op.execute(
        """
        UPDATE user_notes
        SET
          book_id = COALESCE(book_id, (SELECT chapters.book_id FROM chapters WHERE chapters.id = user_notes.chapter_id)),
          source_type = COALESCE(source_type, 'chapter_content'),
          source_id = COALESCE(source_id, 'chapter:' || chapter_id),
          source_title = COALESCE(source_title, (SELECT COALESCE(chapters.title_zh, chapters.title_en, chapters.chapter_index) FROM chapters WHERE chapters.id = user_notes.chapter_id))
        WHERE chapter_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_notes_source_id"), table_name="user_notes")
    op.drop_index(op.f("ix_user_notes_source_type"), table_name="user_notes")
    op.drop_index(op.f("ix_user_notes_book_id"), table_name="user_notes")
    op.drop_column("user_notes", "source_title")
    op.drop_column("user_notes", "source_id")
    op.drop_column("user_notes", "source_type")
    op.drop_column("user_notes", "book_id")
