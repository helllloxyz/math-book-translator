import json
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.schema import (
    Book,
    BookStatus,
    BookType,
    Chapter,
    NoteType,
    QuizAttempt,
    QuizQuestion,
    UserNote,
)
from app.services.book_management_service import BookManagementService
from app.services.book_storage import BookStorage


@pytest.mark.asyncio
async def test_management_snapshot_aggregates_content_quiz_and_profile_state(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(
        "app.services.learning_profile_service.SettingsService.learning_profile_enabled",
        staticmethod(lambda: True),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'management.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as db:
        book = Book(
            uuid="management-book",
            title="Topology",
            original_filename="topology.md",
            status=BookStatus.translated,
            type=BookType.uploaded,
            translation_total=2,
            translation_completed=1,
        )
        db.add(book)
        await db.flush()
        first = Chapter(book_id=book.id, chapter_index="1", title_en="Spaces", order=1)
        second = Chapter(book_id=book.id, chapter_index="2", title_en="Maps", order=2)
        third = Chapter(book_id=book.id, chapter_index="3", title_en="Split Fragment", order=3)
        db.add_all([first, second, third])
        await db.flush()
        question = QuizQuestion(
            book_id=book.id,
            chapter_id=first.id,
            quiz_mode="chapter",
            question_type="concept_explain",
            question_text="What is a topological space?",
            expected_points=["open sets"],
        )
        db.add(question)
        await db.flush()
        db.add(
            QuizAttempt(
                question_id=question.id,
                book_id=book.id,
                chapter_id=first.id,
                answer_text="It is a set with a family of open sets.",
                evaluation_status="completed",
                score=0.86,
                feedback_text="核心解释正确。",
            )
        )
        db.add(
            UserNote(
                book_id=book.id,
                chapter_id=first.id,
                note_content="Remember the empty set.",
                type=NoteType.custom_note,
            )
        )
        await db.commit()

        for chapter in (first, second, third):
            raw_path = BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                (
                    f"# {chapter.title_en}\n\nFragment."
                    if chapter is third
                    else f"# {chapter.title_en}\n\nSource body with enough complete mathematical context for guide generation."
                ),
                encoding="utf-8",
            )
        translated_path = BookStorage.translated_chapter_path(book.uuid, first.chapter_index)
        translated_path.parent.mkdir(parents=True, exist_ok=True)
        translated_path.write_text(
            "# 空间\n\n这一章完整介绍拓扑空间的定义、开集公理以及后续连续映射所需的基础。",
            encoding="utf-8",
        )

        guide_dir = BookStorage.guide_dir(book.uuid)
        guide_dir.mkdir(parents=True, exist_ok=True)
        guide_filename = "chapter-1-overview.md"
        (guide_dir / guide_filename).write_text("# 第一章导读", encoding="utf-8")
        BookStorage.guide_manifest_path(book.uuid).write_text(
            json.dumps(
                [
                    {
                        "id": f"guide:{guide_filename}",
                        "filename": guide_filename,
                        "title": "第一章导读",
                        "scope_type": "chapter",
                        "scope_id": "1",
                    }
                ]
            ),
            encoding="utf-8",
        )
        os.utime(guide_dir / guide_filename, (1, 1))

        snapshot = await BookManagementService.snapshot(book.id, db)

    await engine.dispose()

    assert snapshot["book"]["status_label"] == "可阅读"
    assert snapshot["book"]["readiness"] == "needs_attention"
    assert snapshot["content"]["translated_chapters"] == 1
    assert snapshot["content"]["chapter_guides_stale"] == 1
    assert snapshot["content"]["chapter_guides_missing"] == 1
    assert snapshot["content"]["chapter_guides_skipped"] == 1
    assert snapshot["chapters"][0]["guide"]["status"] == "stale"
    assert snapshot["chapters"][1]["translation"]["status"] == "missing"
    assert snapshot["chapters"][2]["guide"]["status"] == "skipped"
    assert snapshot["quiz"]["attempts"] == 1
    assert snapshot["quiz"]["average_score"] == 0.86
    assert snapshot["quiz"]["type_breakdown"][0]["label"] == "概念讲解"
    assert snapshot["activity"]["notes"] == 1
    assert snapshot["profile"]["should_analyze"] is True
    assert snapshot["profile"]["unprocessed_quiz_count"] == 1


def test_guide_state_marks_newer_guides_ready():
    source = {"modified_timestamp": 10}
    guides = [{"modified_timestamp": 11}]

    assert BookManagementService._guide_state(source, guides) == "ready"
    assert BookManagementService._guide_state(source, []) == "missing"
