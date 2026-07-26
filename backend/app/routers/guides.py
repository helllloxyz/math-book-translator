from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.models.schema import Book, Chapter
from app.services.guide_service import GuideService
from app.services.translator import TranslatorService

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
async def generate_top_down_guides(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    chapters_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order)
    )
    chapters = chapters_result.scalars().all()
    guides = await GuideService.generate_top_down_guides(book, chapters, TranslatorService(task="guides"))
    return {"guides": guides}
