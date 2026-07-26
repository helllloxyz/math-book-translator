"""add quiz tables

Revision ID: 20260503_0007
Revises: 20260503_0006
Create Date: 2026-05-03 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260503_0007"
down_revision = "20260503_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id"), nullable=True),
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
    op.create_index(op.f("ix_quiz_attempts_evaluation_status"), "quiz_attempts", ["evaluation_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_attempts_evaluation_status"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_chapter_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_book_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_question_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_index(op.f("ix_quiz_questions_difficulty"), table_name="quiz_questions")
    op.drop_index(op.f("ix_quiz_questions_question_type"), table_name="quiz_questions")
    op.drop_index(op.f("ix_quiz_questions_source"), table_name="quiz_questions")
    op.drop_index(op.f("ix_quiz_questions_chapter_id"), table_name="quiz_questions")
    op.drop_index(op.f("ix_quiz_questions_book_id"), table_name="quiz_questions")
    op.drop_index(op.f("ix_quiz_questions_id"), table_name="quiz_questions")
    op.drop_table("quiz_questions")
