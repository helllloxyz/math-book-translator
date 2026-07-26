import json
from datetime import datetime
from typing import Any

import aiofiles
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import Book, Chapter, QuizAttempt, UserNote
from app.services.book_storage import BookStorage
from app.services.translator import TranslatorService


class LearningProfileService:
    PROFILE_FILENAME = "User.md"
    META_FILENAME = "profile_meta.json"
    MAX_SOURCE_TEXT_CHARS = 12000

    @staticmethod
    def _empty_meta() -> dict[str, Any]:
        return {
            "last_analyzed_at": None,
            "last_note_id": 0,
            "last_quiz_attempt_id": 0,
            "analysis_count": 0,
        }

    @staticmethod
    async def read_meta(book_uuid: str) -> dict[str, Any]:
        path = BookStorage.user_profile_meta_path(book_uuid)
        if not path.exists():
            return LearningProfileService._empty_meta()
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as handle:
                data = json.loads(await handle.read())
            return {**LearningProfileService._empty_meta(), **data}
        except (OSError, json.JSONDecodeError):
            return LearningProfileService._empty_meta()

    @staticmethod
    async def write_meta(book_uuid: str, meta: dict[str, Any]) -> None:
        path = BookStorage.user_profile_meta_path(book_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(meta, ensure_ascii=False, indent=2))

    @staticmethod
    async def read_profile(book_uuid: str) -> str:
        path = BookStorage.user_profile_path(book_uuid)
        if not path.exists():
            return "# User Learning Profile\n\nNo analyzed learning activity yet.\n"
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return await handle.read()

    @staticmethod
    async def write_profile(book_uuid: str, markdown: str) -> None:
        path = BookStorage.user_profile_path(book_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(markdown)

    @staticmethod
    async def _book_or_404(book_id: int, db: AsyncSession) -> Book | None:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _new_notes(book_id: int, meta: dict[str, Any], db: AsyncSession) -> list[UserNote]:
        last_note_id = int(meta.get("last_note_id") or 0)
        result = await db.execute(
            select(UserNote)
            .outerjoin(Chapter, UserNote.chapter_id == Chapter.id)
            .where(or_(UserNote.book_id == book_id, Chapter.book_id == book_id), UserNote.id > last_note_id)
            .order_by(UserNote.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _new_attempts(book_id: int, meta: dict[str, Any], db: AsyncSession) -> list[QuizAttempt]:
        last_attempt_id = int(meta.get("last_quiz_attempt_id") or 0)
        result = await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.book_id == book_id, QuizAttempt.id > last_attempt_id)
            .order_by(QuizAttempt.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _activity_text(notes: list[UserNote], attempts: list[QuizAttempt]) -> str:
        lines: list[str] = []
        for note in notes:
            lines.append(
                "\n".join(
                    [
                        f"Note #{note.id} [{getattr(note.type, 'value', note.type)}] {note.source_title or ''}",
                        str(note.title or ""),
                        str(note.selected_text or ""),
                        str(note.note_content or "")[:2500],
                    ]
                )
            )
        for attempt in attempts:
            lines.append(
                "\n".join(
                    [
                        f"Quiz attempt #{attempt.id} status={attempt.evaluation_status}",
                        f"Answer: {attempt.answer_text}",
                        f"Feedback: {attempt.feedback_text or ''}",
                        f"Missing: {', '.join(attempt.missing_points or [])}",
                    ]
                )
            )
        text = "\n\n---\n\n".join(lines)
        return text[: LearningProfileService.MAX_SOURCE_TEXT_CHARS]

    @staticmethod
    async def status(book_id: int, db: AsyncSession) -> dict[str, Any]:
        book = await LearningProfileService._book_or_404(book_id, db)
        if not book:
            return {"book": None}
        meta = await LearningProfileService.read_meta(book.uuid)
        notes = await LearningProfileService._new_notes(book_id, meta, db)
        attempts = await LearningProfileService._new_attempts(book_id, meta, db)
        source_text = LearningProfileService._activity_text(notes, attempts)
        return {
            "should_analyze": bool(notes or attempts),
            "unprocessed_notes_count": len(notes),
            "unprocessed_quiz_count": len(attempts),
            "unprocessed_text_length": len(source_text),
            "last_analyzed_at": meta.get("last_analyzed_at"),
            "meta": meta,
        }

    @staticmethod
    def _fallback_profile(existing_profile: str, activity_text: str) -> str:
        timestamp = datetime.utcnow().isoformat()
        excerpt = activity_text[:3000].strip()
        return "\n\n".join(
            [
                existing_profile.strip() or "# User Learning Profile",
                f"## Local Analysis {timestamp}",
                "LLM analysis was unavailable. Recent notes and quiz attempts were appended as evidence for future personalization.",
                "### Recent Evidence",
                excerpt or "No new learning activity.",
                "",
            ]
        )

    @staticmethod
    async def analyze(book_id: int, db: AsyncSession) -> dict[str, Any] | None:
        book = await LearningProfileService._book_or_404(book_id, db)
        if not book:
            return None
        meta = await LearningProfileService.read_meta(book.uuid)
        notes = await LearningProfileService._new_notes(book_id, meta, db)
        attempts = await LearningProfileService._new_attempts(book_id, meta, db)
        existing_profile = await LearningProfileService.read_profile(book.uuid)
        activity_text = LearningProfileService._activity_text(notes, attempts)

        if not activity_text.strip():
            return {
                "summary": "No new notes or quiz attempts to analyze.",
                "profile_markdown": existing_profile,
                "meta": meta,
            }

        translator = TranslatorService(task="learning_profile")
        next_profile = ""
        summary = ""
        if getattr(translator, "api_key", None):
            system_prompt = (
                "You update a per-book math learning profile. Return Markdown only. "
                "Preserve useful prior profile details, then compress new notes and quiz attempts into: "
                "strengths, weak concepts, recurring mistakes, preferred next quiz targets, and evidence."
            )
            user_prompt = (
                f"Book: {book.title}\n\nExisting User.md:\n{existing_profile}\n\n"
                f"New learning activity:\n{activity_text}\n\n"
                "Write the updated User.md in Chinese where useful, preserving math notation."
            )
            try:
                next_profile = await translator.complete(user_prompt, system_prompt, temperature=0.2)
                summary = "Learning profile updated with LLM analysis."
            except Exception:
                next_profile = LearningProfileService._fallback_profile(existing_profile, activity_text)
                summary = "Learning profile updated with local fallback because LLM analysis failed."
        else:
            next_profile = LearningProfileService._fallback_profile(existing_profile, activity_text)
            summary = "Learning profile updated with local fallback because no LLM key is configured."

        now = datetime.utcnow().isoformat()
        next_meta = {
            **meta,
            "last_analyzed_at": now,
            "last_note_id": max([int(meta.get("last_note_id") or 0), *[note.id for note in notes if note.id]]),
            "last_quiz_attempt_id": max(
                [int(meta.get("last_quiz_attempt_id") or 0), *[attempt.id for attempt in attempts if attempt.id]]
            ),
            "analysis_count": int(meta.get("analysis_count") or 0) + 1,
        }
        await LearningProfileService.write_profile(book.uuid, next_profile)
        await LearningProfileService.write_meta(book.uuid, next_meta)
        return {
            "summary": summary,
            "profile_markdown": next_profile,
            "meta": next_meta,
            "processed_notes_count": len(notes),
            "processed_quiz_count": len(attempts),
        }

    @staticmethod
    async def profile(book_id: int, db: AsyncSession) -> dict[str, Any] | None:
        book = await LearningProfileService._book_or_404(book_id, db)
        if not book:
            return None
        return {
            "markdown": await LearningProfileService.read_profile(book.uuid),
            "meta": await LearningProfileService.read_meta(book.uuid),
        }
