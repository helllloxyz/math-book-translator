"""add explicit quiz mode

Revision ID: 20260805_0009
Revises: 20260804_0008
Create Date: 2026-08-05 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0009"
down_revision = "20260804_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_questions",
        sa.Column("quiz_mode", sa.String(), nullable=False, server_default="chapter"),
    )
    op.create_index(
        op.f("ix_quiz_questions_quiz_mode"),
        "quiz_questions",
        ["quiz_mode"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_questions_quiz_mode"), table_name="quiz_questions")
    op.drop_column("quiz_questions", "quiz_mode")
