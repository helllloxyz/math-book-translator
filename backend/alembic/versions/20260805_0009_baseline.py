"""Consolidated baseline schema for the first public release.

Revision ID: 20260805_0009
Revises:
Create Date: 2026-08-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0009"
down_revision = None
branch_labels = None
depends_on = None


book_status = sa.Enum(
    "loaded",
    "translating",
    "translated",
    "generating",
    "generating_guides",
    "failed",
    name="bookstatus",
)
book_type = sa.Enum("uploaded", "generated", name="booktype")
agent_stage = sa.Enum(
    "init",
    "architecting",
    "reviewing",
    "confirmed",
    "writing",
    "ready",
    name="agentstage",
)
note_type = sa.Enum(
    "translation",
    "explanation",
    "custom_note",
    "chapter_chat",
    "selection_chat",
    "quiz_chat",
    "annotation",
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
        sa.Column("content_type", sa.String(), nullable=True),
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

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column(
            "quiz_mode",
            sa.String(),
            nullable=False,
            server_default="chapter",
        ),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("question_type", sa.String(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("target_concepts", sa.JSON(), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("expected_points", sa.JSON(), nullable=True),
        sa.Column("common_mistakes", sa.JSON(), nullable=True),
        sa.Column("context_refs", sa.JSON(), nullable=True),
        sa.Column("evaluation_rubric", sa.JSON(), nullable=True),
        sa.Column("followup_strategy", sa.Text(), nullable=True),
        sa.Column("times_seen", sa.Integer(), nullable=True),
        sa.Column("attempts_count", sa.Integer(), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=True),
        sa.Column("partial_count", sa.Integer(), nullable=True),
        sa.Column("wrong_count", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_quiz_questions_id"), "quiz_questions", ["id"], unique=False)
    op.create_index(op.f("ix_quiz_questions_book_id"), "quiz_questions", ["book_id"], unique=False)
    op.create_index(op.f("ix_quiz_questions_chapter_id"), "quiz_questions", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_quiz_questions_quiz_mode"), "quiz_questions", ["quiz_mode"], unique=False)
    op.create_index(op.f("ix_quiz_questions_source"), "quiz_questions", ["source"], unique=False)
    op.create_index(op.f("ix_quiz_questions_question_type"), "quiz_questions", ["question_type"], unique=False)
    op.create_index(op.f("ix_quiz_questions_difficulty"), "quiz_questions", ["difficulty"], unique=False)

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("quiz_questions.id"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("evaluation_status", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("missing_points", sa.JSON(), nullable=True),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("followup_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_quiz_attempts_id"), "quiz_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_question_id"), "quiz_attempts", ["question_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_book_id"), "quiz_attempts", ["book_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_chapter_id"), "quiz_attempts", ["chapter_id"], unique=False)
    op.create_index(
        op.f("ix_quiz_attempts_evaluation_status"),
        "quiz_attempts",
        ["evaluation_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_questions")
    op.drop_table("user_notes")
    op.drop_table("chapters")
    op.drop_table("books")
