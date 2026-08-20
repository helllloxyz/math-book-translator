import re
from typing import Any

import aiofiles

from app.services.book_storage import BookStorage


class ChapterSourceService:
    """Read complete chapter bodies for downstream LLM features."""

    MIN_GUIDE_BODY_CHARS = 30

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

    @staticmethod
    def guide_body_character_count(text: str) -> int:
        """Count substantive chapter characters, excluding split headings and markup noise."""
        body_lines = [
            line
            for line in str(text or "").splitlines()
            if not re.match(r"^\s{0,3}#{1,6}(?:\s+|$)", line)
        ]
        plain_text = re.sub(r"[\s#*_>`\[\](){}-]+", "", "\n".join(body_lines))
        return len(plain_text)

    @staticmethod
    def is_guide_body_eligible(text: str) -> bool:
        return (
            ChapterSourceService.guide_body_character_count(text)
            >= ChapterSourceService.MIN_GUIDE_BODY_CHARS
        )
