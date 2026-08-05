import json
import shutil

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import get_db
from app.models.schema import Book, BookStatus, Chapter, ImportBookRequest, RenameBookRequest, UserNote
from app.services.book_service import BookService
from app.services.book_management_service import BookManagementService
from app.services.book_storage import BookStorage
from app.services.guide_service import GuideService
from app.services.reader_tree_service import ReaderTreeService
from app.services.translator import LLMConfigurationError, TranslatorService

router = APIRouter()


@router.get("/books")
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).order_by(Book.created_at.desc()))
    return result.scalars().all()


@router.post("/books/import")
async def import_book(request: ImportBookRequest, db: AsyncSession = Depends(get_db)):
    return await BookService.handle_book_import(
        request.file_path,
        db,
        force=request.force,
        preflight=request.preflight,
        outline_selection=request.outline_selection,
        outline_plan=request.outline_plan,
    )


@router.post("/upload")
async def upload_book(
    file: UploadFile = File(...),
    force: bool = Form(False),
    preflight: bool = Form(True),
    outline_selection: str | None = Form(None),
    outline_plan: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are supported")
    content = (await file.read()).decode("utf-8")
    selected_headings = None
    confirmed_outline_plan = None
    if outline_selection:
        try:
            parsed_selection = json.loads(outline_selection)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="outline_selection must be a JSON array")
        if not isinstance(parsed_selection, list) or not all(isinstance(item, str) for item in parsed_selection):
            raise HTTPException(status_code=400, detail="outline_selection must be a JSON array of strings")
        selected_headings = parsed_selection
    if outline_plan:
        try:
            parsed_plan = json.loads(outline_plan)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="outline_plan must be a JSON object")
        if not isinstance(parsed_plan, dict):
            raise HTTPException(status_code=400, detail="outline_plan must be a JSON object")
        confirmed_outline_plan = parsed_plan
    return await BookService.create_book_from_content(
        file.filename,
        content,
        db,
        force=force,
        preflight=preflight,
        outline_selection=selected_headings,
        outline_plan=confirmed_outline_plan,
    )


@router.post("/books/import-package")
async def import_book_package(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await BookService.import_book_package(file, db)


@router.get("/books/{book_id}/export")
async def export_book_package(book_id: int, db: AsyncSession = Depends(get_db)):
    package_buffer, filename = await BookService.build_book_package(book_id, db)
    return StreamingResponse(
        package_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/books/{book_id}")
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Book).options(selectinload(Book.chapters)).where(Book.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.chapters.sort(key=lambda chapter: chapter.order)
    return book


@router.get("/books/{book_id}/management")
async def get_book_management(book_id: int, db: AsyncSession = Depends(get_db)):
    snapshot = await BookManagementService.snapshot(book_id, db)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return snapshot


@router.get("/books/{book_id}/reader-tree")
async def get_reader_tree(book_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Book).options(selectinload(Book.chapters)).where(Book.id == book_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.chapters.sort(key=lambda chapter: chapter.order)
    guides = await GuideService.list_guides(book.uuid)
    return {
        "book": ReaderTreeService.build_book_tree(book.chapters),
        "guide": ReaderTreeService.build_guide_tree(book.chapters, guides),
    }


async def chapter_for_reader_content(book_id: int, chapter_id: int, db: AsyncSession):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


async def read_chapter_content(book_uuid: str, chapter: Chapter) -> dict:
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
        "reader_type": "chapter",
        "chapter_id": chapter.id,
        "chapter_index": chapter.chapter_index,
        "content_raw": content_raw,
        "content_translated": content_translated,
    }


@router.get("/books/{book_id}/reader-content")
async def get_reader_content(
    book_id: int,
    reader_type: str = Query(..., description="Reader item type: chapter or guide"),
    chapter_id: int | None = Query(None),
    guide_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if reader_type == "chapter":
        if chapter_id is None:
            raise HTTPException(status_code=400, detail="chapter_id is required for chapter reader content")
        data = await read_chapter_content(book.uuid, await chapter_for_reader_content(book_id, chapter_id, db))
    elif reader_type == "guide":
        if not guide_id:
            raise HTTPException(status_code=400, detail="guide_id is required for guide reader content")
        guides = await GuideService.list_guides(book.uuid)
        guide = next((item for item in guides if item.get("id") == guide_id), None)
        if not guide:
            raise HTTPException(status_code=404, detail="Guide not found")
        resolved_filename = guide.get("filename")
        try:
            data = await GuideService.read_guide(book.uuid, resolved_filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        data = {
            **data,
            "reader_type": "guide",
            "guide_id": guide_id,
        }
    else:
        raise HTTPException(status_code=400, detail="reader_type must be chapter or guide")

    return data


@router.put("/books/{book_id}")
async def update_book(book_id: int, request: RenameBookRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.title = request.title
    await db.commit()
    await db.refresh(book)
    BookService.sync_meta_json_title(BookStorage.book_dir(book.uuid), book)
    return book


@router.delete("/books/{book_id}")
async def delete_book(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.uuid:
        book_dir = BookStorage.book_dir(book.uuid)
        if book_dir.exists():
            shutil.rmtree(book_dir)

    chapters_result = await db.execute(select(Chapter.id).where(Chapter.book_id == book_id))
    chapter_ids = chapters_result.scalars().all()
    if chapter_ids:
        await db.execute(delete(UserNote).where(UserNote.chapter_id.in_(chapter_ids)))
        await db.execute(delete(Chapter).where(Chapter.id.in_(chapter_ids)))
    await db.execute(delete(UserNote).where(UserNote.book_id == book_id))

    await db.delete(book)
    await db.commit()
    return {"message": "Book deleted successfully"}


@router.post("/books/{book_id}/translate")
async def trigger_translation(book_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status in (BookStatus.translating, BookStatus.generating, BookStatus.generating_guides):
        return {"message": "Translation already running"}
    chapters_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order))
    chapters = chapters_result.scalars().all()
    try:
        await BookService.require_translation_configuration(book, chapters)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(BookService.process_book_translation, book_id)
    return {"message": "Translation started"}


@router.post("/books/{book_id}/chapters/{chapter_id}/retranslate")
async def retranslate_chapter(
    book_id: int,
    chapter_id: int,
    background_tasks: BackgroundTasks,
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
    if not BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index).exists():
        raise HTTPException(status_code=400, detail="Chapter source is missing")
    try:
        TranslatorService.require_configured(task="translation")
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(BookService.process_chapter_retranslation, book_id, chapter_id)
    return {"message": "Chapter retranslation started", "chapter_id": chapter_id}
