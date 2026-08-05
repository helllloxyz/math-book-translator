from typing import Any

import aiofiles

from app.services.book_storage import BookStorage


class ChapterSourceService:
    """Read complete chapter bodies for downstream LLM features."""

    @staticmethod
    async def _read_text(path) -> str:
        if not path.exists():
            return ""
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return await handle.read()

    @staticmethod
    async def read_preferred_body(book_uuid: str, chapter_index: str) -> dict[str, Any]:
        translated = await ChapterSourceService._read_text(
            BookStorage.translated_chapter_path(book_uuid, chapter_index)
        )
        raw = await ChapterSourceService._read_text(
            BookStorage.raw_chapter_path(book_uuid, chapter_index)
        )
        if translated.strip():
            return {"text": translated.strip(), "language": "translated"}
        return {"text": raw.strip(), "language": "source"}

    @staticmethod
    async def chapter_context(book_uuid: str, chapter) -> dict[str, Any]:
        source = await ChapterSourceService.read_preferred_body(book_uuid, chapter.chapter_index)
        return {
            "chapter_index": str(chapter.chapter_index),
            "title": chapter.title_zh or chapter.title_en or str(chapter.chapter_index),
            "body_language": source["language"],
            "body": source["text"],
        }
