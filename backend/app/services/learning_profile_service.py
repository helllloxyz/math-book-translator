import asyncio
import hashlib
import html
import json
import logging
import re
from datetime import datetime
from typing import Any

import aiofiles
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import SessionLocal
from app.models.schema import Book, Chapter, NoteType, QuizAttempt, UserNote
from app.services.book_storage import BookStorage
from app.services.guide_service import GuideService
from app.services.llm_json import extract_json_candidate
from app.services.settings_service import SettingsService
from app.services.translator import TranslatorService

logger = logging.getLogger("app.learning_profile")


class LearningProfileService:
    PROFILE_FILENAME = "User.md"
    META_FILENAME = "profile_meta.json"
    MAX_EVIDENCE_BATCH_CHARS = 18000
    MAX_EXISTING_SUMMARY_CHARS = 12000
    MAX_GUIDE_CHARS = 1800
    MAX_RENDERED_SUMMARY_CHARS = 4000
    PROFILE_NOTE_TYPES = {
        NoteType.custom_note,
        NoteType.chapter_chat,
        NoteType.selection_chat,
        NoteType.annotation,
    }
    _book_locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _empty_meta() -> dict[str, Any]:
        return {
            "last_analyzed_at": None,
            "last_note_id": 0,
            "last_quiz_attempt_id": 0,
            "processed_note_hashes": {},
            "reading_progress": {},
            "summary_markdown": "",
            "analysis_count": 0,
            "last_error": None,
        }

    @classmethod
    def _lock_for(cls, book_uuid: str) -> asyncio.Lock:
        lock = cls._book_locks.get(book_uuid)
        if lock is None:
            lock = asyncio.Lock()
            cls._book_locks[book_uuid] = lock
        return lock

    @staticmethod
    async def read_meta(book_uuid: str) -> dict[str, Any]:
        path = BookStorage.user_profile_meta_path(book_uuid)
        if not path.exists():
            return LearningProfileService._empty_meta()
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as handle:
                data = json.loads(await handle.read())
            merged = {**LearningProfileService._empty_meta(), **data}
            if not isinstance(merged.get("processed_note_hashes"), dict):
                merged["processed_note_hashes"] = {}
            if not isinstance(merged.get("reading_progress"), dict):
                merged["reading_progress"] = {}
            return merged
        except (OSError, json.JSONDecodeError, TypeError):
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
            return "# 学习画像\n\n## 学习进度\n\n尚未同步阅读进度。\n\n## Quiz 与笔记总结\n\n暂无足够的学习记录。\n"
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return await handle.read()

    @staticmethod
    async def write_profile(book_uuid: str, markdown: str) -> None:
        path = BookStorage.user_profile_path(book_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(markdown)

    @staticmethod
    async def _book_or_none(book_id: int, db: AsyncSession) -> Book | None:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _note_hash(note: UserNote) -> str:
        payload = {
            "type": getattr(note.type, "value", note.type),
            "title": note.title or "",
            "selected_text": note.selected_text or "",
            "note_content": note.note_content or "",
            "source_type": note.source_type or "",
            "source_id": note.source_id or "",
            "source_title": note.source_title or "",
            "chapter_id": note.chapter_id,
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    @staticmethod
    async def _new_notes(book_id: int, meta: dict[str, Any], db: AsyncSession) -> list[UserNote]:
        processed = {str(key): str(value) for key, value in (meta.get("processed_note_hashes") or {}).items()}
        result = await db.execute(
            select(UserNote)
            .options(selectinload(UserNote.chapter))
            .outerjoin(Chapter, UserNote.chapter_id == Chapter.id)
            .where(
                or_(UserNote.book_id == book_id, Chapter.book_id == book_id),
                UserNote.type.in_(LearningProfileService.PROFILE_NOTE_TYPES),
            )
            .order_by(UserNote.id)
        )
        notes = list(result.scalars().unique().all())
        return [note for note in notes if processed.get(str(note.id)) != LearningProfileService._note_hash(note)]

    @staticmethod
    async def _new_attempts(book_id: int, meta: dict[str, Any], db: AsyncSession) -> list[QuizAttempt]:
        last_attempt_id = int(meta.get("last_quiz_attempt_id") or 0)
        result = await db.execute(
            select(QuizAttempt)
            .options(selectinload(QuizAttempt.question), selectinload(QuizAttempt.chapter))
            .where(QuizAttempt.book_id == book_id, QuizAttempt.id > last_attempt_id)
            .order_by(QuizAttempt.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _decode_legacy_user_messages(content: str) -> list[str]:
        messages = []
        for match in re.finditer(r'<div\s+class="chat-user">([\s\S]*?)</div>', content, re.IGNORECASE):
            plain = re.sub(r"<[^>]*>", " ", match.group(1))
            plain = html.unescape(re.sub(r"\s+", " ", plain)).strip()
            if plain:
                messages.append(plain)
        return messages

    @staticmethod
    def _user_messages(raw_content: str) -> list[str]:
        content = str(raw_content or "").strip()
        if not content:
            return []
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return LearningProfileService._decode_legacy_user_messages(content)
        messages = parsed if isinstance(parsed, list) else parsed.get("messages", []) if isinstance(parsed, dict) else []
        if not isinstance(messages, list):
            return []
        return [
            str(message.get("content") or "").strip()
            for message in messages
            if isinstance(message, dict)
            and message.get("role") == "user"
            and str(message.get("content") or "").strip()
        ]

    @staticmethod
    def _note_evidence(note: UserNote) -> dict[str, Any] | None:
        note_type = getattr(note.type, "value", note.type)
        chapter = note.chapter
        chapter_label = ""
        if chapter:
            chapter_label = f"{chapter.chapter_index} {chapter.title_zh or chapter.title_en or ''}".strip()
        source_title = note.source_title or chapter_label
        lines = [f"Note #{note.id} type={note_type}"]
        if source_title:
            lines.append(f"Chapter/source: {source_title}")
        if note.title:
            lines.append(f"Title: {note.title}")

        if note_type in {NoteType.chapter_chat.value, NoteType.selection_chat.value}:
            if note.selected_text:
                lines.append(f"Selected context: {note.selected_text}")
            user_messages = LearningProfileService._user_messages(note.note_content or "")
            if not user_messages:
                return None
            lines.append("User questions/messages only:")
            lines.extend(f"{index}. {message}" for index, message in enumerate(user_messages, start=1))
        elif note_type == NoteType.annotation.value:
            if not str(note.selected_text or "").strip():
                return None
            lines.append(f"User highlighted: {note.selected_text}")
        else:
            if note.selected_text:
                lines.append(f"Selected context: {note.selected_text}")
            if note.note_content:
                lines.append(f"User note: {note.note_content}")

        text = "\n".join(lines).strip()
        if not text:
            return None
        return {"chapter_id": note.chapter_id, "text": text}

    @staticmethod
    def _attempt_evidence(attempt: QuizAttempt) -> dict[str, Any]:
        question = attempt.question
        chapter = attempt.chapter
        feedback = str(attempt.feedback_text or "")
        reliably_evaluated = "无法仅凭关键词可靠判断" not in feedback and "当前没有可用的模型" not in feedback
        chapter_label = ""
        if chapter:
            chapter_label = f"{chapter.chapter_index} {chapter.title_zh or chapter.title_en or ''}".strip()
        lines = [
            f"Quiz attempt #{attempt.id}",
            f"Chapter: {chapter_label}",
            f"Question type: {getattr(question, 'question_type', '')}",
            f"Target concepts: {', '.join(getattr(question, 'target_concepts', None) or [])}",
            f"Question: {getattr(question, 'question_text', '')}",
            f"User answer: {attempt.answer_text}",
            f"Evaluation: {attempt.evaluation_status if reliably_evaluated else 'unassessed'}",
            f"Evaluation reliability: {'semantic model evaluation' if reliably_evaluated else 'unavailable; do not infer mastery'}",
            f"Score: {attempt.score if reliably_evaluated and attempt.score is not None else 'not reliably scored'}",
            f"Missing points: {', '.join(attempt.missing_points or [])}",
            f"Feedback: {feedback}",
        ]
        return {"chapter_id": attempt.chapter_id, "text": "\n".join(lines).strip()}

    @staticmethod
    def _split_evidence(entries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        expanded: list[dict[str, Any]] = []
        limit = LearningProfileService.MAX_EVIDENCE_BATCH_CHARS
        for entry in entries:
            text = str(entry.get("text") or "")
            if len(text) <= limit:
                expanded.append(entry)
                continue
            parts = [text[index : index + limit] for index in range(0, len(text), limit)]
            for index, part in enumerate(parts, start=1):
                expanded.append(
                    {
                        **entry,
                        "text": f"{part}\n[Long record part {index}/{len(parts)}]",
                    }
                )

        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_size = 0
        for entry in expanded:
            size = len(str(entry.get("text") or ""))
            if current and current_size + size > limit:
                batches.append(current)
                current = []
                current_size = 0
            current.append(entry)
            current_size += size
        if current:
            batches.append(current)
        return batches

    @staticmethod
    async def _chapter_guide_context(
        book_uuid: str,
        chapter_ids: set[int],
        chapters_by_id: dict[int, Chapter],
    ) -> list[dict[str, str]]:
        if not chapter_ids:
            return []
        chapter_indexes = {
            str(chapters_by_id[chapter_id].chapter_index): chapter_id
            for chapter_id in chapter_ids
            if chapter_id in chapters_by_id
        }
        contexts = []
        for guide in await GuideService.list_guides(book_uuid):
            scope_id = str(guide.get("scope_id") or "")
            if guide.get("scope_type") != "chapter" or scope_id not in chapter_indexes:
                continue
            try:
                data = await GuideService.read_guide(book_uuid, guide["filename"])
            except (FileNotFoundError, OSError):
                continue
            contexts.append(
                {
                    "chapter_index": scope_id,
                    "title": str(guide.get("title") or "读前 60S"),
                    "guide": str(data.get("content") or "")[: LearningProfileService.MAX_GUIDE_CHARS],
                }
            )
        return contexts

    @staticmethod
    async def _compress_evidence(
        translator: TranslatorService,
        book: Book,
        batch: list[dict[str, Any]],
        guide_context: list[dict[str, str]],
    ) -> dict[str, Any]:
        system_prompt = (
            "Compress a batch of existing learning records for one mathematics book. Return strictly valid JSON with "
            "a chapters array. Each chapter item may contain chapter_id, quiz_summary, note_summary, user_questions, "
            "and improvement_points; each field other than chapter_id is a short array of Chinese strings. Analyze only "
            "what the records actually show. User questions show interest or uncertainty, not automatic failure. Reading "
            "guides are orientation context only and never evidence of mastery. Quiz evidence is stronger than notes. "
            "Do not quote long raw records, do not expose private evidence unnecessarily, and keep the full result concise."
        )
        user_prompt = json.dumps(
            {
                "book": {"id": book.id, "title": book.title},
                "chapter_guides": guide_context,
                "new_learning_records": [entry.get("text", "") for entry in batch],
            },
            ensure_ascii=False,
            indent=2,
        )
        raw = await translator.complete(user_prompt, system_prompt, temperature=0.2)
        return extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))

    @staticmethod
    async def _merge_summary(
        translator: TranslatorService,
        book: Book,
        existing_summary: str,
        digests: list[dict[str, Any]],
    ) -> str:
        system_prompt = (
            "Update a short per-book mathematics learning summary from an older summary and new structured digests. "
            "Return Markdown only, in concise Chinese. Use exactly two sections: '## Quiz 与笔记总结' and "
            "'## 潜在改进点'. Keep at most three bullets per section and roughly 500-800 Chinese characters or fewer. "
            "Merge duplicates, revise stale conclusions when newer evidence conflicts, and do not invent mastery when "
            "evidence is sparse. Do not include reading-progress counts; the application adds those deterministically."
        )
        user_prompt = json.dumps(
            {
                "book": {"id": book.id, "title": book.title},
                "existing_summary": existing_summary[: LearningProfileService.MAX_EXISTING_SUMMARY_CHARS],
                "new_digests": digests,
            },
            ensure_ascii=False,
            indent=2,
        )
        summary = (await translator.complete(user_prompt, system_prompt, temperature=0.2)).strip()
        if not summary:
            raise ValueError("Learning profile merge returned empty Markdown")
        if len(summary) > LearningProfileService.MAX_RENDERED_SUMMARY_CHARS:
            lines = []
            size = 0
            for line in summary.splitlines():
                if size + len(line) + 1 > LearningProfileService.MAX_RENDERED_SUMMARY_CHARS:
                    break
                lines.append(line)
                size += len(line) + 1
            summary = "\n".join(lines).strip()
        return summary

    @staticmethod
    def _chapter_label(chapter: Chapter) -> str:
        return f"{chapter.chapter_index} {chapter.title_zh or chapter.title_en or ''}".strip()

    @staticmethod
    async def build_reading_progress(
        book_id: int,
        reading_statuses: list[Any],
        current_chapter_id: int | None,
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        result = await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order))
        chapters = list(result.scalars().all())
        if not chapters:
            return None
        chapter_by_id = {chapter.id: chapter for chapter in chapters}
        supplied = {}
        for raw in reading_statuses:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            try:
                chapter_id = int(data.get("chapter_id"))
            except (TypeError, ValueError):
                continue
            if chapter_id not in chapter_by_id:
                continue
            progress = str(data.get("progress") or "unread")
            difficulty = str(data.get("difficulty") or "unmarked")
            if progress not in {"unread", "reading", "skipped", "finished"}:
                progress = "unread"
            if difficulty == "easy":
                difficulty = "unmarked"
            if difficulty not in {"unmarked", "confused", "hard"}:
                difficulty = "unmarked"
            supplied[chapter_id] = {"progress": progress, "difficulty": difficulty}

        counts = {"unread": 0, "reading": 0, "skipped": 0, "finished": 0}
        confused = []
        hard = []
        for chapter in chapters:
            status = supplied.get(chapter.id, {"progress": "unread", "difficulty": "unmarked"})
            counts[status["progress"]] += 1
            item = {
                "chapter_id": chapter.id,
                "chapter_index": chapter.chapter_index,
                "chapter_title": chapter.title_zh or chapter.title_en or "",
            }
            if status["difficulty"] == "confused":
                confused.append(item)
            elif status["difficulty"] == "hard":
                hard.append(item)

        current = chapter_by_id.get(current_chapter_id) if current_chapter_id else None
        return {
            "chapters_total": len(chapters),
            **counts,
            "confused_chapters": confused,
            "hard_chapters": hard,
            "current_chapter": (
                {
                    "chapter_id": current.id,
                    "chapter_index": current.chapter_index,
                    "chapter_title": current.title_zh or current.title_en or "",
                }
                if current
                else None
            ),
            "synced_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _format_chapter_list(items: list[dict[str, Any]]) -> str:
        labels = [f"{item.get('chapter_index', '')} {item.get('chapter_title', '')}".strip() for item in items]
        shown = labels[:3]
        suffix = f"，另有 {len(labels) - 3} 章" if len(labels) > 3 else ""
        return "、".join(shown) + suffix

    @staticmethod
    def render_profile(meta: dict[str, Any]) -> str:
        progress = meta.get("reading_progress") or {}
        total = int(progress.get("chapters_total") or 0)
        if total:
            progress_lines = [
                f"- 已完成 {int(progress.get('finished') or 0)}/{total} 章，在读 {int(progress.get('reading') or 0)} 章，跳过 {int(progress.get('skipped') or 0)} 章。"
            ]
            current = progress.get("current_chapter") or {}
            if current:
                current_label = f"{current.get('chapter_index', '')} {current.get('chapter_title', '')}".strip()
                progress_lines.append(f"- 最近进入：{current_label}。")
            confused = progress.get("confused_chapters") or []
            hard = progress.get("hard_chapters") or []
            if confused:
                progress_lines.append(f"- 标记为困惑：{LearningProfileService._format_chapter_list(confused)}。")
            if hard:
                progress_lines.append(f"- 标记为困难：{LearningProfileService._format_chapter_list(hard)}。")
            progress_markdown = "\n".join(progress_lines)
        else:
            progress_markdown = "尚未同步阅读进度。"

        summary = str(meta.get("summary_markdown") or "").strip()
        if not summary:
            summary = "## Quiz 与笔记总结\n\n暂无足够的 Quiz、笔记或用户提问记录。\n\n## 潜在改进点\n\n继续阅读，并在需要时完成 Quiz 或留下笔记。"
        return f"# 学习画像\n\n## 学习进度\n\n{progress_markdown}\n\n{summary}\n"

    @staticmethod
    async def sync_reading_progress(
        book_id: int,
        reading_statuses: list[Any],
        current_chapter_id: int | None,
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        book = await LearningProfileService._book_or_none(book_id, db)
        if not book:
            return None
        progress = await LearningProfileService.build_reading_progress(
            book_id, reading_statuses, current_chapter_id, db
        )
        async with LearningProfileService._lock_for(book.uuid):
            meta = await LearningProfileService.read_meta(book.uuid)
            if progress is not None:
                meta["reading_progress"] = progress
            await LearningProfileService.write_meta(book.uuid, meta)
            await LearningProfileService.write_profile(book.uuid, LearningProfileService.render_profile(meta))
        return meta

    @staticmethod
    async def status(book_id: int, db: AsyncSession) -> dict[str, Any]:
        book = await LearningProfileService._book_or_none(book_id, db)
        if not book:
            return {"book": None}
        enabled = SettingsService.learning_profile_enabled()
        meta = await LearningProfileService.read_meta(book.uuid)
        notes = await LearningProfileService._new_notes(book_id, meta, db) if enabled else []
        attempts = await LearningProfileService._new_attempts(book_id, meta, db) if enabled else []
        note_evidence = []
        for note in notes:
            evidence = LearningProfileService._note_evidence(note)
            if evidence:
                note_evidence.append(evidence)
        attempt_evidence = [LearningProfileService._attempt_evidence(attempt) for attempt in attempts]
        return {
            "enabled": enabled,
            "should_analyze": enabled and bool(notes or attempts),
            "analysis_running": LearningProfileService._lock_for(book.uuid).locked(),
            "unprocessed_notes_count": len(notes),
            "unprocessed_quiz_count": len(attempts),
            "unprocessed_text_length": sum(
                len(item.get("text", ""))
                for item in [*note_evidence, *attempt_evidence]
            ),
            "last_analyzed_at": meta.get("last_analyzed_at"),
            "meta": meta,
        }

    @staticmethod
    async def analyze(book_id: int, db: AsyncSession) -> dict[str, Any] | None:
        book = await LearningProfileService._book_or_none(book_id, db)
        if not book:
            return None
        if not SettingsService.learning_profile_enabled():
            meta = await LearningProfileService.read_meta(book.uuid)
            return {
                "summary": "自动学习画像已在设置中关闭。",
                "profile_markdown": await LearningProfileService.read_profile(book.uuid),
                "meta": meta,
                "enabled": False,
            }

        async with LearningProfileService._lock_for(book.uuid):
            meta = await LearningProfileService.read_meta(book.uuid)
            notes = await LearningProfileService._new_notes(book_id, meta, db)
            attempts = await LearningProfileService._new_attempts(book_id, meta, db)
            existing_profile = await LearningProfileService.read_profile(book.uuid)

            if not notes and not attempts:
                profile = LearningProfileService.render_profile(meta)
                await LearningProfileService.write_profile(book.uuid, profile)
                return {
                    "summary": "当前没有新的 Quiz、笔记或用户提问需要分析。",
                    "profile_markdown": profile,
                    "meta": meta,
                    "processed_notes_count": 0,
                    "processed_quiz_count": 0,
                }

            translator = TranslatorService(task="learning_profile")
            if not getattr(translator, "api_key", None):
                meta["last_error"] = "Learning profile model is not configured."
                await LearningProfileService.write_meta(book.uuid, meta)
                await LearningProfileService.write_profile(book.uuid, LearningProfileService.render_profile(meta))
                return {
                    "summary": "没有可用的画像模型；新记录已保留，稍后会自动重试。",
                    "profile_markdown": LearningProfileService.render_profile(meta),
                    "meta": meta,
                    "processed_notes_count": 0,
                    "processed_quiz_count": 0,
                }

            evidence_entries = []
            for note in notes:
                evidence = LearningProfileService._note_evidence(note)
                if evidence:
                    evidence_entries.append(evidence)
            evidence_entries.extend(
                LearningProfileService._attempt_evidence(attempt) for attempt in attempts
            )
            chapters_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id))
            chapters = list(chapters_result.scalars().all())
            chapters_by_id = {chapter.id: chapter for chapter in chapters}

            try:
                digests = []
                for batch in LearningProfileService._split_evidence(evidence_entries):
                    chapter_ids = {
                        int(entry["chapter_id"])
                        for entry in batch
                        if entry.get("chapter_id") is not None
                    }
                    guides = await LearningProfileService._chapter_guide_context(
                        book.uuid, chapter_ids, chapters_by_id
                    )
                    digests.append(
                        await LearningProfileService._compress_evidence(translator, book, batch, guides)
                    )

                existing_summary = str(meta.get("summary_markdown") or "").strip()
                if not existing_summary and "暂无足够的学习记录" not in existing_profile:
                    existing_summary = existing_profile
                next_summary = existing_summary
                if digests:
                    next_summary = await LearningProfileService._merge_summary(
                        translator, book, existing_summary, digests
                    )

                now = datetime.utcnow().isoformat()
                processed_hashes = dict(meta.get("processed_note_hashes") or {})
                processed_hashes.update(
                    {str(note.id): LearningProfileService._note_hash(note) for note in notes if note.id}
                )
                next_meta = {
                    **meta,
                    "last_analyzed_at": now,
                    "last_note_id": max(
                        [int(meta.get("last_note_id") or 0), *[note.id for note in notes if note.id]]
                    ),
                    "last_quiz_attempt_id": max(
                        [
                            int(meta.get("last_quiz_attempt_id") or 0),
                            *[attempt.id for attempt in attempts if attempt.id],
                        ]
                    ),
                    "processed_note_hashes": processed_hashes,
                    "summary_markdown": next_summary,
                    "analysis_count": int(meta.get("analysis_count") or 0) + (1 if digests else 0),
                    "last_error": None,
                }
                profile = LearningProfileService.render_profile(next_meta)
                await LearningProfileService.write_meta(book.uuid, next_meta)
                await LearningProfileService.write_profile(book.uuid, profile)
                return {
                    "summary": "学习画像已自动更新。",
                    "profile_markdown": profile,
                    "meta": next_meta,
                    "processed_notes_count": len(notes),
                    "processed_quiz_count": len(attempts),
                }
            except Exception as exc:
                logger.warning("Learning profile analysis failed for book_id=%s: %s", book_id, exc)
                meta["last_error"] = str(exc)
                await LearningProfileService.write_meta(book.uuid, meta)
                await LearningProfileService.write_profile(book.uuid, LearningProfileService.render_profile(meta))
                return {
                    "summary": "画像分析暂时失败；新记录仍待处理，下次进入阅读时会自动重试。",
                    "profile_markdown": LearningProfileService.render_profile(meta),
                    "meta": meta,
                    "processed_notes_count": 0,
                    "processed_quiz_count": 0,
                }

    @staticmethod
    async def analyze_in_background(book_id: int) -> None:
        async with SessionLocal() as db:
            try:
                await LearningProfileService.analyze(book_id, db)
            except Exception:
                logger.exception("Background learning profile analysis crashed for book_id=%s", book_id)

    @staticmethod
    async def profile(book_id: int, db: AsyncSession) -> dict[str, Any] | None:
        book = await LearningProfileService._book_or_none(book_id, db)
        if not book:
            return None
        return {
            "markdown": await LearningProfileService.read_profile(book.uuid),
            "meta": await LearningProfileService.read_meta(book.uuid),
            "enabled": SettingsService.learning_profile_enabled(),
        }
