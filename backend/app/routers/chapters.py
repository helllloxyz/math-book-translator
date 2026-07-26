import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.models.schema import Book, Chapter, LatexRepairApplyRequest, LatexRepairSuggestRequest
from app.services.latex_repair_service import LatexRepairService
from app.services.book_storage import BookStorage
from app.services.learning_context_service import LearningContextService
from app.services.translator import LLMConfigurationError

router = APIRouter()


async def chapter_with_book_uuid(chapter_id: int, db: AsyncSession):
    result = await db.execute(
        select(Chapter, Book.uuid).join(Book, Chapter.book_id == Book.id).where(Chapter.id == chapter_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return row


@router.get("/chapters/{chapter_id}/content")
async def get_chapter_content(chapter_id: int, db: AsyncSession = Depends(get_db)):
    chapter, book_uuid = await chapter_with_book_uuid(chapter_id, db)
    raw_path = BookStorage.raw_chapter_path(book_uuid, chapter.chapter_index)
    trans_path = BookStorage.translated_chapter_path(book_uuid, chapter.chapter_index)

    content_raw = content_translated = ""
    if raw_path.exists():
        async with aiofiles.open(raw_path, "r", encoding="utf-8") as handle:
            content_raw = await handle.read()
    if trans_path.exists():
        async with aiofiles.open(trans_path, "r", encoding="utf-8") as handle:
            content_translated = await handle.read()
    else:
        content_translated = content_raw

    return {
        "id": chapter.id,
        "content_raw": content_raw,
        "content_translated": content_translated,
    }


@router.post("/chapters/{chapter_id}/latex-repair/suggest")
async def suggest_latex_repair(
    chapter_id: int,
    request: LatexRepairSuggestRequest,
    db: AsyncSession = Depends(get_db),
):
    await chapter_with_book_uuid(chapter_id, db)
    try:
        replacement = await LatexRepairService.suggest_repair(
            selected_text=request.selected_text,
            failed_candidates=request.failed_candidates,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"replacement": replacement}


@router.post("/chapters/{chapter_id}/latex-repair/apply")
async def apply_latex_repair(
    chapter_id: int,
    request: LatexRepairApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    chapter, book_uuid = await chapter_with_book_uuid(chapter_id, db)
    updated = LatexRepairService.apply_exact_replacement(
        book_uuid=book_uuid,
        chapter_index=chapter.chapter_index,
        content_target=request.content_target,
        original_text=request.original_text,
        replacement_text=request.replacement_text,
    )
    return {
        "content": updated,
        "content_target": LatexRepairService.normalize_content_target(request.content_target),
    }


@router.get("/chapters/{chapter_id}/learning")
async def get_chapter_learning(chapter_id: int, db: AsyncSession = Depends(get_db)):
    chapter, book_uuid = await chapter_with_book_uuid(chapter_id, db)
    return LearningContextService.load_learning_context(book_uuid, chapter.chapter_index)
