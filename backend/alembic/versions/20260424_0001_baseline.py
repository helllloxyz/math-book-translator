"""baseline schema

Revision ID: 20260424_0001
Revises: 
Create Date: 2026-04-24 10:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260424_0001"
down_revision = None
branch_labels = None
depends_on = None


book_status = sa.Enum("loaded", "translating", "translated", "generating", "generating_guides", "failed", name="bookstatus")
book_type = sa.Enum("uploaded", "generated", name="booktype")
agent_stage = sa.Enum("init", "architecting", "reviewing", "confirmed", "writing", "ready", name="agentstage")
note_type = sa.Enum(
    "translation",
    "explanation",
    "custom_note",
    "chapter_chat",
    "selection_chat",
    "quiz_chat",
    name="notetype",
)


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("status", book_status, nullable=True),
        sa.Column("translation_total", sa.Integer(), nullable=True),
        sa.Column("translation_completed", sa.Integer(), nullable=True),
        sa.Column("translation_failed", sa.Integer(), nullable=True),
        sa.Column("type", book_type, nullable=True),
        sa.Column("agent_stage", agent_stage, nullable=True),
        sa.Column("vision", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_books_id"), "books", ["id"], unique=False)
    op.create_index(op.f("ix_books_title"), "books", ["title"], unique=False)
    op.create_index(op.f("ix_books_uuid"), "books", ["uuid"], unique=True)

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=True),
        sa.Column("chapter_index", sa.String(), nullable=True),
        sa.Column("title_en", sa.String(), nullable=True),
        sa.Column("title_zh", sa.String(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=True),
    )
    op.create_index(op.f("ix_chapters_id"), "chapters", ["id"], unique=False)

    op.create_table(
        "user_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("source_title", sa.String(), nullable=True),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("note_content", sa.Text(), nullable=True),
        sa.Column("type", note_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_user_notes_id"), "user_notes", ["id"], unique=False)
    op.create_index(op.f("ix_user_notes_book_id"), "user_notes", ["book_id"], unique=False)
    op.create_index(op.f("ix_user_notes_source_type"), "user_notes", ["source_type"], unique=False)
    op.create_index(op.f("ix_user_notes_source_id"), "user_notes", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_notes_source_id"), table_name="user_notes")
    op.drop_index(op.f("ix_user_notes_source_type"), table_name="user_notes")
    op.drop_index(op.f("ix_user_notes_book_id"), table_name="user_notes")
    op.drop_index(op.f("ix_user_notes_id"), table_name="user_notes")
    op.drop_table("user_notes")
    op.drop_index(op.f("ix_chapters_id"), table_name="chapters")
    op.drop_table("chapters")
    op.drop_index(op.f("ix_books_uuid"), table_name="books")
    op.drop_index(op.f("ix_books_title"), table_name="books")
    op.drop_index(op.f("ix_books_id"), table_name="books")
    op.drop_table("books")
