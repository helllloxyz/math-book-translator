import json
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.schema import Book, Chapter, NoteType, UserNote
from app.services.learning_profile_service import LearningProfileService


def test_profile_does_not_treat_local_quiz_fallback_as_mastery_evidence():
    evidence = LearningProfileService._attempt_evidence(
        SimpleNamespace(
            id=7,
            chapter_id=2,
            chapter=None,
            question=SimpleNamespace(
                question_type="concept_explain",
                target_concepts=["basis"],
                question_text="请解释基。",
            ),
            answer_text="我的解释",
            evaluation_status="partial",
            score=0.5,
            missing_points=[],
            feedback_text="当前没有可用的模型，系统无法仅凭关键词可靠判断数学含义。",
        )
    )

    assert "Evaluation: unassessed" in evidence["text"]
    assert "do not infer mastery" in evidence["text"]
    assert "Score: not reliably scored" in evidence["text"]


def test_long_learning_records_are_split_into_multiple_complete_batches():
    long_text = "START-" + ("内容" * 20000) + "-END"

    batches = LearningProfileService._split_evidence([{"chapter_id": 4, "text": long_text}])
    parts = [entry["text"] for batch in batches for entry in batch]

    assert len(parts) >= 3
    assert parts[0].startswith("START-")
    assert "-END" in parts[-1]
    assert all(entry["chapter_id"] == 4 for batch in batches for entry in batch)


@pytest.mark.asyncio
async def test_learning_profile_is_incremental_per_book_and_keeps_only_user_chat_messages(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(
        "app.services.learning_profile_service.SettingsService.learning_profile_enabled",
        staticmethod(lambda: True),
    )
    prompts = []

    class FakeTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, user_prompt, system_prompt, temperature):
            prompts.append((user_prompt, system_prompt, temperature))
            if "Compress a batch" in system_prompt:
                return json.dumps(
                    {
                        "chapters": [
                            {
                                "chapter_id": 1,
                                "user_questions": ["为什么必须要求全部系数为零？"],
                                "improvement_points": ["继续区分条件和结论"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            return "## Quiz 与笔记总结\n\n- 用户正在追问定义中的必要条件。\n\n## 潜在改进点\n\n- 继续区分条件和结论。"

    monkeypatch.setattr("app.services.learning_profile_service.TranslatorService", FakeTranslator)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'profile.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as db:
        book = Book(uuid="profile-book", title="Linear Algebra", original_filename="book.md")
        other_book = Book(uuid="other-book", title="Topology", original_filename="other.md")
        db.add_all([book, other_book])
        await db.flush()
        chapter = Chapter(book_id=book.id, chapter_index="3.2", title_en="Independence", order=1)
        other_chapter = Chapter(book_id=other_book.id, chapter_index="1", title_en="Spaces", order=1)
        db.add_all([chapter, other_chapter])
        await db.flush()
        note = UserNote(
            book_id=book.id,
            chapter_id=chapter.id,
            source_type="chapter_content",
            source_id=f"chapter:{chapter.id}",
            source_title="3.2 线性无关",
            note_content=json.dumps(
                [
                    {"role": "user", "content": "为什么必须要求全部系数为零？"},
                    {"role": "assistant", "content": "这是一段不应进入画像的超长模型回答。"},
                    {"role": "user", "content": "它和基有什么关系？"},
                ],
                ensure_ascii=False,
            ),
            type=NoteType.chapter_chat,
        )
        db.add_all(
            [
                note,
                UserNote(
                    book_id=other_book.id,
                    chapter_id=other_chapter.id,
                    note_content="Other book private note",
                    type=NoteType.custom_note,
                ),
            ]
        )
        await db.commit()
        await db.refresh(note)

        await LearningProfileService.sync_reading_progress(
            book.id,
            [{"chapter_id": chapter.id, "progress": "finished", "difficulty": "easy"}],
            chapter.id,
            db,
        )
        result = await LearningProfileService.analyze(book.id, db)

        assert result["processed_notes_count"] == 1
        assert "已完成 1/1 章" in result["profile_markdown"]
        assert "最近进入：3.2 Independence" in result["profile_markdown"]
        assert "潜在改进点" in result["profile_markdown"]
        compression_prompt = prompts[0][0]
        assert "为什么必须要求全部系数为零" in compression_prompt
        assert "它和基有什么关系" in compression_prompt
        assert "不应进入画像" not in compression_prompt
        assert "Other book private note" not in compression_prompt

        status = await LearningProfileService.status(book.id, db)
        assert status["should_analyze"] is False
        meta = await LearningProfileService.read_meta(book.uuid)
        assert str(note.id) in meta["processed_note_hashes"]
        assert meta["reading_progress"]["confused_chapters"] == []

        note.note_content = json.dumps(
            [
                {"role": "user", "content": "为什么必须要求全部系数为零？"},
                {"role": "user", "content": "新增追问会被内容哈希发现吗？"},
            ],
            ensure_ascii=False,
        )
        await db.commit()
        changed_status = await LearningProfileService.status(book.id, db)
        assert changed_status["should_analyze"] is True
        assert changed_status["unprocessed_notes_count"] == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_profile_analysis_keeps_evidence_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(
        "app.services.learning_profile_service.SettingsService.learning_profile_enabled",
        staticmethod(lambda: True),
    )

    class FailingTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, *_args, **_kwargs):
            raise RuntimeError("temporary model failure")

    monkeypatch.setattr("app.services.learning_profile_service.TranslatorService", FailingTranslator)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'failure.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as db:
        book = Book(uuid="failure-book", title="Analysis", original_filename="book.md")
        db.add(book)
        await db.flush()
        note = UserNote(book_id=book.id, note_content="My note", type=NoteType.custom_note)
        db.add(note)
        await db.commit()

        result = await LearningProfileService.analyze(book.id, db)
        status = await LearningProfileService.status(book.id, db)
        meta = await LearningProfileService.read_meta(book.uuid)

        assert result["processed_notes_count"] == 0
        assert status["should_analyze"] is True
        assert meta["processed_note_hashes"] == {}
        assert "temporary model failure" in meta["last_error"]
        assert "Recent Evidence" not in result["profile_markdown"]

    await engine.dispose()
