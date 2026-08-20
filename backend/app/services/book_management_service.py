from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schema import Book, Chapter, QuizAttempt, QuizQuestion, UserNote
from app.services.book_storage import BookStorage
from app.services.chapter_source_service import ChapterSourceService
from app.services.guide_service import GuideService
from app.services.learning_profile_service import LearningProfileService
from app.services.quiz_skill_registry import get_quiz_skill


class BookManagementService:
    """Build the operational, learning, and content snapshot for one book."""

    STATUS_LABELS = {
        "loaded": "待翻译",
        "translating": "正在翻译",
        "translated": "可阅读",
        "generating": "正在生成",
        "generating_guides": "正在生成导读",
        "failed": "处理失败",
    }
    ATTEMPT_STATUS_LABELS = {
        "completed": "掌握",
        "partial": "部分掌握",
        "wrong": "需要复习",
    }

    @staticmethod
    def _file_info(path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            return {"exists": False, "characters": 0, "modified_at": None, "modified_timestamp": None}
        stat = path.stat()
        try:
            characters = len(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            characters = 0
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return {
            "exists": stat.st_size > 0,
            "characters": characters,
            "modified_at": modified.isoformat(),
            "modified_timestamp": stat.st_mtime,
        }

    @staticmethod
    def _ratio(numerator: int | float, denominator: int | float) -> float | None:
        if not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)

    @staticmethod
    def _score(value: Any) -> float | None:
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _guide_file_info(book_uuid: str, guide: dict[str, Any]) -> dict[str, Any]:
        info = BookManagementService._file_info(
            BookStorage.guide_dir(book_uuid) / str(guide.get("filename") or "")
        )
        return {**guide, **info}

    @staticmethod
    def _guide_state(source_info: dict[str, Any], guides: list[dict[str, Any]]) -> str:
        if not guides:
            return "missing"
        source_timestamp = source_info.get("modified_timestamp")
        newest_guide_timestamp = max(
            (item.get("modified_timestamp") or 0 for item in guides),
            default=0,
        )
        if source_timestamp and newest_guide_timestamp < source_timestamp:
            return "stale"
        return "ready"

    @staticmethod
    def _chapter_quiz_summary(attempts: list[QuizAttempt]) -> dict[str, Any]:
        scores = [float(item.score) for item in attempts if item.score is not None]
        completed = sum(item.evaluation_status == "completed" for item in attempts)
        partial = sum(item.evaluation_status == "partial" for item in attempts)
        wrong = sum(item.evaluation_status == "wrong" for item in attempts)
        return {
            "attempts": len(attempts),
            "completed": completed,
            "partial": partial,
            "wrong": wrong,
            "average_score": round(sum(scores) / len(scores), 4) if scores else None,
            "last_attempt_at": attempts[0].created_at.isoformat() if attempts and attempts[0].created_at else None,
        }

    @staticmethod
    async def snapshot(book_id: int, db: AsyncSession) -> dict[str, Any] | None:
        result = await db.execute(
            select(Book).options(selectinload(Book.chapters)).where(Book.id == book_id)
        )
        book = result.scalar_one_or_none()
        if not book:
            return None
        chapters = sorted(book.chapters, key=lambda item: item.order)

        guide_manifest = await GuideService.list_guides(book.uuid)
        guides = [BookManagementService._guide_file_info(book.uuid, item) for item in guide_manifest]
        chapter_guides: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for guide in guides:
            if guide.get("scope_type") == "chapter":
                chapter_guides[str(guide.get("scope_id"))].append(guide)

        attempt_result = await db.execute(
            select(QuizAttempt, QuizQuestion)
            .join(QuizQuestion, QuizAttempt.question_id == QuizQuestion.id)
            .where(QuizAttempt.book_id == book_id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
        )
        attempt_rows = list(attempt_result.all())
        attempts_by_chapter: dict[int, list[QuizAttempt]] = defaultdict(list)
        attempts_by_type: dict[str, list[QuizAttempt]] = defaultdict(list)
        for attempt, question in attempt_rows:
            if attempt.chapter_id is not None:
                attempts_by_chapter[attempt.chapter_id].append(attempt)
            attempts_by_type[question.question_type].append(attempt)

        chapter_rows = []
        translated_count = 0
        source_count = 0
        guide_ready_count = 0
        guide_stale_count = 0
        guide_missing_count = 0
        guide_skipped_count = 0
        for chapter in chapters:
            source = BookManagementService._file_info(
                BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index)
            )
            translation = BookManagementService._file_info(
                BookStorage.translated_chapter_path(book.uuid, chapter.chapter_index)
            )
            if source["exists"]:
                source_count += 1
            if translation["exists"]:
                translated_count += 1
            body_info = translation if translation["exists"] else source
            scoped_guides = chapter_guides.get(str(chapter.chapter_index), [])
            body_path = (
                BookStorage.translated_chapter_path(book.uuid, chapter.chapter_index)
                if translation["exists"]
                else BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index)
            )
            try:
                body_text = body_path.read_text(encoding="utf-8") if body_info["exists"] else ""
            except (OSError, UnicodeDecodeError):
                body_text = ""
            guide_eligible = ChapterSourceService.is_guide_body_eligible(body_text)
            guide_status = (
                "skipped"
                if body_info["exists"] and not guide_eligible
                else BookManagementService._guide_state(body_info, scoped_guides)
            )
            if guide_status == "ready":
                guide_ready_count += 1
            elif guide_status == "stale":
                guide_stale_count += 1
            elif guide_status == "missing":
                guide_missing_count += 1
            else:
                guide_skipped_count += 1
            translation_status = (
                "ready" if translation["exists"] else "missing" if source["exists"] else "source_missing"
            )
            chapter_rows.append(
                {
                    "id": chapter.id,
                    "chapter_index": chapter.chapter_index,
                    "title": chapter.title_zh or chapter.title_en or f"章节 {chapter.chapter_index}",
                    "title_en": chapter.title_en,
                    "title_zh": chapter.title_zh,
                    "content_type": chapter.content_type,
                    "order": chapter.order,
                    "source": {key: value for key, value in source.items() if key != "modified_timestamp"},
                    "translation": {
                        **{key: value for key, value in translation.items() if key != "modified_timestamp"},
                        "status": translation_status,
                    },
                    "guide": {
                        "status": guide_status,
                        "count": len(scoped_guides),
                        "titles": [str(item.get("title") or "") for item in scoped_guides],
                        "skip_reason": "正文过短，无法生成可靠导读" if guide_status == "skipped" else None,
                    },
                    "quiz": BookManagementService._chapter_quiz_summary(
                        attempts_by_chapter.get(chapter.id, [])
                    ),
                }
            )

        question_count = await db.scalar(
            select(func.count(QuizQuestion.id)).where(QuizQuestion.book_id == book_id)
        )
        note_count = await db.scalar(
            select(func.count(UserNote.id))
            .outerjoin(Chapter, UserNote.chapter_id == Chapter.id)
            .where(or_(UserNote.book_id == book_id, Chapter.book_id == book_id))
        )
        all_attempts = [attempt for attempt, _question in attempt_rows]
        total_scores = [float(item.score) for item in all_attempts if item.score is not None]
        completed_count = sum(item.evaluation_status == "completed" for item in all_attempts)
        partial_count = sum(item.evaluation_status == "partial" for item in all_attempts)
        wrong_count = sum(item.evaluation_status == "wrong" for item in all_attempts)

        type_breakdown = []
        for question_type, type_attempts in attempts_by_type.items():
            type_scores = [float(item.score) for item in type_attempts if item.score is not None]
            type_breakdown.append(
                {
                    "question_type": question_type,
                    "label": get_quiz_skill(question_type).label,
                    "attempts": len(type_attempts),
                    "completed": sum(item.evaluation_status == "completed" for item in type_attempts),
                    "partial": sum(item.evaluation_status == "partial" for item in type_attempts),
                    "wrong": sum(item.evaluation_status == "wrong" for item in type_attempts),
                    "average_score": round(sum(type_scores) / len(type_scores), 4) if type_scores else None,
                }
            )
        type_breakdown.sort(key=lambda item: (-item["attempts"], item["label"]))

        recent_attempts = []
        chapter_by_id = {chapter.id: chapter for chapter in chapters}
        for attempt, question in attempt_rows[:10]:
            chapter = chapter_by_id.get(attempt.chapter_id)
            recent_attempts.append(
                {
                    "id": attempt.id,
                    "question_id": question.id,
                    "chapter_id": attempt.chapter_id,
                    "chapter_title": (
                        chapter.title_zh or chapter.title_en or chapter.chapter_index if chapter else "全书 Quiz"
                    ),
                    "question_type": question.question_type,
                    "question_type_label": get_quiz_skill(question.question_type).label,
                    "question_text": question.question_text,
                    "answer_text": attempt.answer_text,
                    "evaluation_status": attempt.evaluation_status,
                    "evaluation_status_label": BookManagementService.ATTEMPT_STATUS_LABELS.get(
                        attempt.evaluation_status, attempt.evaluation_status
                    ),
                    "score": BookManagementService._score(attempt.score),
                    "missing_points": attempt.missing_points or [],
                    "feedback_text": attempt.feedback_text or "",
                    "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
                }
            )

        profile_status = await LearningProfileService.status(book_id, db)
        profile_data = await LearningProfileService.profile(book_id, db)
        raw_status = getattr(book.status, "value", book.status)
        is_busy = raw_status in {"translating", "generating", "generating_guides"}
        if raw_status == "failed" or translated_count < source_count:
            readiness = "needs_attention"
            readiness_label = "需要处理"
        elif is_busy:
            readiness = "processing"
            readiness_label = "处理中"
        elif guide_stale_count or guide_missing_count:
            readiness = "guide_attention"
            readiness_label = "导读待更新"
        else:
            readiness = "ready"
            readiness_label = "阅读就绪"

        return {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "book": {
                "id": book.id,
                "uuid": book.uuid,
                "title": book.title,
                "type": getattr(book.type, "value", book.type),
                "status": raw_status,
                "status_label": BookManagementService.STATUS_LABELS.get(raw_status, str(raw_status)),
                "readiness": readiness,
                "readiness_label": readiness_label,
                "is_busy": is_busy,
                "created_at": book.created_at.isoformat() if book.created_at else None,
            },
            "content": {
                "chapters_total": len(chapters),
                "source_chapters": source_count,
                "translated_chapters": translated_count,
                "translation_ratio": BookManagementService._ratio(translated_count, source_count),
                "translation_failed": int(book.translation_failed or 0),
                "guides_total": len(guides),
                "chapter_guides_ready": guide_ready_count,
                "chapter_guides_stale": guide_stale_count,
                "chapter_guides_missing": guide_missing_count,
                "chapter_guides_skipped": guide_skipped_count,
                "book_guides": sum(item.get("scope_type") == "book" for item in guides),
                "directory_guides": sum(item.get("scope_type") == "directory" for item in guides),
            },
            "activity": {
                "notes": int(note_count or 0),
                "quiz_questions": int(question_count or 0),
                "quiz_attempts": len(all_attempts),
            },
            "chapters": chapter_rows,
            "quiz": {
                "questions": int(question_count or 0),
                "attempts": len(all_attempts),
                "completed": completed_count,
                "partial": partial_count,
                "wrong": wrong_count,
                "completion_rate": BookManagementService._ratio(completed_count, len(all_attempts)),
                "average_score": round(sum(total_scores) / len(total_scores), 4) if total_scores else None,
                "type_breakdown": type_breakdown,
                "recent_attempts": recent_attempts,
            },
            "profile": {
                **profile_status,
                "markdown": (profile_data or {}).get("markdown", ""),
                "meta": (profile_data or {}).get("meta", profile_status.get("meta", {})),
            },
        }
