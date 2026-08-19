import json

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.models.schema import (
    AgentInitRequest,
    AgentInteractRequest,
    Book,
    BuildStructureRequest,
    Chapter,
    ConfirmStructureRequest,
    CreateNoteRequest,
    GenerateTitleRequest,
    NoteType,
    RegenerateNodeRequest,
    UpdateNoteRequest,
    UserNote,
)
from app.services.agent_service import AgentService
from app.services.book_storage import BookStorage
from app.services.translator import TranslatorService

router = APIRouter()


@router.get("/health")
def read_root():
    return {"message": "Math Book Translator API is running"}


@router.post("/notes")
async def create_note(note: CreateNoteRequest, db: AsyncSession = Depends(get_db)):
    try:
        note_type_enum = NoteType(note.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid note type") from exc

    book_id = note.book_id
    source_type = note.source_type
    source_id = note.source_id
    source_title = note.source_title
    if note.chapter_id and (not book_id or not source_type or not source_id):
        result = await db.execute(select(Chapter).where(Chapter.id == note.chapter_id))
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        book_id = book_id or chapter.book_id
        source_type = source_type or "chapter_content"
        source_id = source_id or f"chapter:{chapter.id}"
        source_title = source_title or chapter.title_zh or chapter.title_en or chapter.chapter_index

    if not book_id or not source_type or not source_id:
        raise HTTPException(status_code=400, detail="book_id, source_type, and source_id are required")

    new_note = UserNote(
        book_id=book_id,
        chapter_id=note.chapter_id,
        source_type=source_type,
        source_id=source_id,
        source_title=source_title,
        selected_text=note.selected_text,
        start_index=note.start_index,
        note_content=note.note_content,
        title=note.title,
        type=note_type_enum,
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    return new_note


@router.put("/notes/{note_id}")
async def update_note(note_id: int, request: UpdateNoteRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserNote).where(UserNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if request.title is not None:
        note.title = request.title
    if request.note_content is not None:
        note.note_content = request.note_content
    await db.commit()
    return note


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserNote).where(UserNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()
    return {"message": "Note deleted"}


@router.post("/generate-title")
async def generate_title(request: GenerateTitleRequest):
    title = await TranslatorService(task="note_title").generate_title(request.context, request.prompt)
    return {"title": title}


@router.get("/chapters/{chapter_id}/notes")
async def get_chapter_notes(chapter_id: int, type: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(UserNote).where(
        or_(
            (UserNote.source_type == "chapter_content") & (UserNote.source_id == f"chapter:{chapter_id}"),
            (UserNote.source_type.is_(None)) & (UserNote.chapter_id == chapter_id),
        )
    )
    if type:
        try:
            note_type = NoteType(type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid note type") from exc
        query = query.where(UserNote.type == note_type)
    result = await db.execute(query.order_by(UserNote.created_at.desc()))
    return result.scalars().all()


@router.get("/books/{book_id}/notes/source")
async def get_source_notes(
    book_id: int,
    source_type: str,
    source_id: str,
    type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(UserNote).where(
        UserNote.book_id == book_id,
        UserNote.source_type == source_type,
        UserNote.source_id == source_id,
    )
    if source_type == "chapter_content" and source_id.startswith("chapter:"):
        try:
            chapter_id = int(source_id.split(":", 1)[1])
        except ValueError:
            chapter_id = None
        if chapter_id is not None:
            query = select(UserNote).where(
                or_(
                    (UserNote.book_id == book_id)
                    & (UserNote.source_type == source_type)
                    & (UserNote.source_id == source_id),
                    (UserNote.source_type.is_(None)) & (UserNote.chapter_id == chapter_id),
                )
            )
    if type:
        try:
            note_type = NoteType(type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid note type") from exc
        query = query.where(UserNote.type == note_type)
    result = await db.execute(query.order_by(UserNote.created_at.desc()))
    return result.scalars().all()


@router.get("/books/{book_id}/notes")
async def get_book_notes(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserNote)
        .outerjoin(Chapter, UserNote.chapter_id == Chapter.id)
        .where(
            or_(UserNote.book_id == book_id, Chapter.book_id == book_id),
        )
        .order_by(UserNote.created_at.desc())
    )
    return result.scalars().all()


@router.post("/agent/init")
async def agent_init(request: AgentInitRequest, db: AsyncSession = Depends(get_db)):
    return await AgentService.initialize_agent_book(request.domain, db)


@router.post("/agent/build-structure")
async def agent_build_structure(
    request: BuildStructureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    background_tasks.add_task(AgentService.architect_book_structure, request.book_id, None)
    return {"message": "Full architecting started"}


@router.get("/agent/{book_id}/manifest")
async def agent_get_manifest(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    manifest_path = BookStorage.manifest_path(book.uuid)
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")

    async with aiofiles.open(manifest_path, "r", encoding="utf-8") as handle:
        return json.loads(await handle.read())


@router.get("/agent/{book_id}/history")
async def agent_get_history(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    from app.services.interaction_service import InteractionService

    return await InteractionService.get_history(book.uuid)


@router.post("/agent/confirm-structure")
async def agent_confirm_structure(
    request: ConfirmStructureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await AgentService.confirm_structure(request.book_id, request.manifest, db, background_tasks)
    return {"message": "Structure confirmed, content generation started"}


@router.post("/agent/regenerate-node")
async def agent_regenerate_node(
    request: RegenerateNodeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    background_tasks.add_task(
        AgentService.regenerate_node,
        request.book_id,
        request.node_id,
        request.instruction,
        None,
    )
    return {"message": "Regeneration started"}


@router.post("/agent/{book_id}/interact")
async def agent_interact(
    book_id: int,
    request: AgentInteractRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await AgentService.handle_interaction(book_id, request.message, db, background_tasks)
