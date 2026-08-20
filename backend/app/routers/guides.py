from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.models.schema import Book, BookStatus, Chapter, GuideGenerationRequest
from app.services.book_service import BookService
from app.services.guide_service import GuideService
from app.services.translator import LLMConfigurationError, TranslatorService

router = APIRouter()


@router.get("/books/{book_id}/guides")
async def list_book_guides(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return await GuideService.list_guides(book.uuid)


@router.get("/books/{book_id}/guides/{filename}")
async def get_book_guide(book_id: int, filename: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        return await GuideService.read_guide(book.uuid, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/books/{book_id}/guides/top-down")
async def generate_top_down_guides(
    book_id: int,
    background_tasks: BackgroundTasks,
    request: GuideGenerationRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status in (BookStatus.translating, BookStatus.generating, BookStatus.generating_guides):
        raise HTTPException(status_code=409, detail="Book processing is already running")

    try:
        TranslatorService.require_configured(task="guides")
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mode = request.mode if request else "missing"
    background_tasks.add_task(
        BookService.process_book_guide_generation,
        book_id,
        mode,
    )
    return {"message": "Guide generation started", "mode": mode}


@router.post("/books/{book_id}/chapters/{chapter_id}/guides")
async def generate_chapter_guide(
    book_id: int,
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
):
    book = await db.scalar(select(Book).where(Book.id == book_id))
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status in (BookStatus.translating, BookStatus.generating, BookStatus.generating_guides):
        raise HTTPException(status_code=409, detail="Book processing is already running")

    chapter = await db.scalar(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id)
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    try:
        TranslatorService.require_configured(task="guides")
        guides = await GuideService.generate_chapter_guide(
            book,
            chapter,
            TranslatorService(task="guides"),
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"guides": guides, "chapter_id": chapter_id}
