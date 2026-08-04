import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.schema import Book, Chapter, CreateNoteRequest, NoteType
from app.routers.legacy import create_note, get_book_notes, get_source_notes


@pytest.mark.asyncio
async def test_annotation_round_trips_with_source_notes_and_stays_out_of_notes_page():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with sessions() as session:
            book = Book(title="Topology", original_filename="topology.md")
            session.add(book)
            await session.flush()
            chapter = Chapter(
                book_id=book.id,
                chapter_index="1",
                title_en="Open sets",
                order=1,
            )
            session.add(chapter)
            await session.commit()

            created = await create_note(
                CreateNoteRequest(
                    book_id=book.id,
                    chapter_id=chapter.id,
                    source_type="chapter_content",
                    source_id=f"chapter:{chapter.id}",
                    source_title="Open sets",
                    selected_text="open neighborhood",
                    start_index=42,
                    note_content='{"style":"highlight","content_target":"translated"}',
                    type="annotation",
                ),
                session,
            )

            assert created.type is NoteType.annotation
            assert created.start_index == 42

            source_notes = await get_source_notes(
                book.id,
                "chapter_content",
                f"chapter:{chapter.id}",
                db=session,
            )
            assert [note.id for note in source_notes] == [created.id]

            visible_notes = await get_book_notes(book.id, db=session)
            assert visible_notes == []
    finally:
        await engine.dispose()
