import json
import logging
import random
from datetime import datetime
from typing import Any

import aiofiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import Book, Chapter, QuizAttempt, QuizQuestion
from app.services.book_storage import BookStorage
from app.services.guide_service import GuideService
from app.services.learning_context_service import LearningContextService
from app.services.learning_profile_service import LearningProfileService
from app.services.llm_json import extract_json_candidate
from app.services.quiz_skill_registry import (
    QUIZ_SKILLS,
    get_quiz_skill,
    is_valid_question_type,
    question_type_weights,
)
from app.services.translator import TranslatorService

logger = logging.getLogger("app.quiz_service")


class QuizService:
    MAX_CONTEXT_CHARS = 14000
    MAX_EXCERPT_CHARS = 4500
    CHAPTER_BANK_SPARSE_THRESHOLD = 3
    CHAPTER_BANK_BATCH_SIZE = 3

    @staticmethod
    def question_to_dict(question: QuizQuestion) -> dict[str, Any]:
        return {
            "id": question.id,
            "book_id": question.book_id,
            "chapter_id": question.chapter_id,
            "source": question.source or "generated",
            "question_type": question.question_type,
            "difficulty": question.difficulty or "medium",
            "target_concepts": question.target_concepts or [],
            "question_text": question.question_text,
            "expected_points": question.expected_points or [],
            "common_mistakes": question.common_mistakes or [],
            "context_refs": question.context_refs or [],
            "evaluation_rubric": question.evaluation_rubric or {},
            "followup_strategy": question.followup_strategy or "",
        }

    @staticmethod
    async def _chapter_or_none(chapter_id: int, db: AsyncSession) -> Chapter | None:
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _book_or_none(book_id: int, db: AsyncSession) -> Book | None:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit].rstrip() + "\n\n[truncated]"

    @staticmethod
    def weighted_random_question_type() -> str:
        weights = question_type_weights()
        total = sum(max(0.0, weight) for weight in weights.values())
        if total <= 0:
            return "concept_explain"
        target = random.random() * total
        cumulative = 0.0
        selected = "concept_explain"
        for question_type, weight in weights.items():
            cumulative += max(0.0, weight)
            selected = question_type
            if target <= cumulative:
                return question_type
        return selected

    @staticmethod
    def sparse_bank_question_types(selected_type: str) -> list[str]:
        ordered = [selected_type]
        weighted_types = sorted(
            question_type_weights().items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for question_type, _weight in weighted_types:
            if question_type not in ordered:
                ordered.append(question_type)
            if len(ordered) >= QuizService.CHAPTER_BANK_BATCH_SIZE:
                break
        return ordered

    @staticmethod
    async def _read_text(path) -> str:
        if not path.exists():
            return ""
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return await handle.read()

    @staticmethod
    async def _book_guide_text(book_uuid: str) -> str:
        guides = await GuideService.list_guides(book_uuid)
        parts = []
        for guide in guides:
            if guide.get("scope_type") != "book":
                continue
            try:
                data = await GuideService.read_guide(book_uuid, guide["filename"])
            except FileNotFoundError:
                continue
            parts.append(data.get("content", ""))
        return QuizService._truncate("\n\n".join(parts), 4000)

    @staticmethod
    async def _chapter_guide_text(book_uuid: str, chapter_index: str) -> str:
        guides = await GuideService.list_guides(book_uuid)
        parts = []
        for guide in guides:
            if guide.get("scope_type") != "chapter" or str(guide.get("scope_id")) != str(chapter_index):
                continue
            try:
                data = await GuideService.read_guide(book_uuid, guide["filename"])
            except FileNotFoundError:
                continue
            parts.append(data.get("content", ""))
        return QuizService._truncate("\n\n".join(parts), 3500)

    @staticmethod
    def _learning_context_markdown(book_uuid: str, chapter: Chapter) -> str:
        context = LearningContextService.load_learning_context(book_uuid, chapter.chapter_index)
        parts = [
            f"Summary: {context.get('summary', '')}",
            "Concepts:",
            *[
                f"- {item.get('name', '')}: {item.get('description', '')}"
                for item in context.get("concepts", [])
                if isinstance(item, dict)
            ],
            "Key theorems:",
            *[
                f"- {item.get('name', '')}: {item.get('statement', item.get('description', ''))}"
                for item in context.get("key_theorems", [])
                if isinstance(item, dict)
            ],
            "Dependencies:",
            *[f"- {item}" for item in context.get("dependencies", [])],
        ]
        return QuizService._truncate("\n".join(parts), 3500)

    @staticmethod
    async def build_generation_context(book: Book, chapter: Chapter | None, question_type: str) -> str:
        skill = get_quiz_skill(question_type)
        parts = [
            f"Book: {book.title}",
            f"Question type: {skill.question_type}",
            f"Goal: {skill.goal}",
            f"Required context: {', '.join(skill.required_context)}",
            f"Question style: {skill.question_style}",
        ]
        if chapter:
            parts.append(
                f"Chapter: {chapter.chapter_index} {chapter.title_zh or chapter.title_en or ''}".strip()
            )
            raw_text = await QuizService._read_text(BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index))
            translated_text = await QuizService._read_text(
                BookStorage.translated_chapter_path(book.uuid, chapter.chapter_index)
            )
            parts.extend(
                [
                    "Learning context:",
                    QuizService._learning_context_markdown(book.uuid, chapter),
                    "Chapter guide:",
                    await QuizService._chapter_guide_text(book.uuid, chapter.chapter_index),
                    "Chapter excerpt:",
                    QuizService._truncate(translated_text or raw_text, QuizService.MAX_EXCERPT_CHARS),
                ]
            )
        parts.extend(["Book guide:", await QuizService._book_guide_text(book.uuid)])
        return QuizService._truncate("\n\n".join(parts), QuizService.MAX_CONTEXT_CHARS)

    @staticmethod
    def normalize_question_data(
        data: dict[str, Any],
        *,
        book_id: int,
        chapter_id: int | None,
        question_type: str,
        source: str,
    ) -> dict[str, Any]:
        skill = get_quiz_skill(question_type)
        expected_points = data.get("expected_points") or data.get("expected_answer_points") or []
        if isinstance(expected_points, str):
            expected_points = [expected_points]
        target_concepts = data.get("target_concepts") or []
        if isinstance(target_concepts, str):
            target_concepts = [target_concepts]
        common_mistakes = data.get("common_mistakes") or []
        if isinstance(common_mistakes, str):
            common_mistakes = [common_mistakes]
        question_text = str(data.get("question_text") or data.get("question") or "").strip()
        if not question_text:
            question_text = "Explain the central idea of this chapter and name one condition that is required."
        return {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "source": source,
            "question_type": skill.question_type,
            "difficulty": str(data.get("difficulty") or "medium"),
            "target_concepts": [str(item) for item in target_concepts if str(item).strip()],
            "question_text": question_text,
            "expected_points": [str(item) for item in expected_points if str(item).strip()],
            "common_mistakes": [str(item) for item in common_mistakes if str(item).strip()],
            "context_refs": data.get("context_refs") if isinstance(data.get("context_refs"), list) else [],
            "evaluation_rubric": data.get("evaluation_rubric")
            if isinstance(data.get("evaluation_rubric"), dict)
            else skill.evaluation_rubric,
            "followup_strategy": str(data.get("followup_strategy") or skill.next_step_rule),
        }

    @staticmethod
    def _fallback_question_data(
        *,
        book_id: int,
        chapter_id: int | None,
        chapter_title: str,
        question_type: str,
        source: str,
        personalization_context: str | None = None,
    ) -> dict[str, Any]:
        skill = get_quiz_skill(question_type)
        personalization_hint = QuizService._truncate(personalization_context or "", 600)
        question_text = (
            f"围绕「{chapter_title or '本章'}」，并结合这个个性化目标「{personalization_hint}」，"
            f"请回答：{skill.question_style} 请写出关键定义/条件，并说明它在推理中的作用。"
            if personalization_hint
            else (
                f"围绕「{chapter_title or '本章'}」，请回答：{skill.question_style} "
                "请写出关键定义/条件，并说明它在推理中的作用。"
            )
        )
        data = {
            "question_text": question_text,
            "target_concepts": [item for item in [chapter_title, personalization_hint] if item],
            "expected_points": [
                "准确指出相关定义或结论",
                "说明至少一个必要条件",
                "解释该条件如何支持推理或应用",
            ],
            "common_mistakes": [
                "只复述结论，没有说明条件",
                "把相近概念混为一谈",
            ],
        }
        return QuizService.normalize_question_data(
            data,
            book_id=book_id,
            chapter_id=chapter_id,
            question_type=question_type,
            source=source,
        )

    @staticmethod
    async def generate_question(
        *,
        book: Book,
        chapter: Chapter | None,
        question_type: str,
        db: AsyncSession,
        source: str = "generated",
        personalization_context: str | None = None,
    ) -> QuizQuestion:
        skill = get_quiz_skill(question_type)
        context = await QuizService.build_generation_context(book, chapter, skill.question_type)
        if personalization_context:
            context = QuizService._truncate(
                f"{context}\n\nPersonalization context:\n{personalization_context}",
                QuizService.MAX_CONTEXT_CHARS,
            )

        translator = TranslatorService(task="quiz")
        normalized: dict[str, Any] | None = None
        if getattr(translator, "api_key", None):
            system_prompt = (
                "You generate one structured mathematics quiz question. Return strictly valid JSON with keys: "
                "question_text, difficulty, target_concepts, expected_points, common_mistakes, context_refs, "
                "evaluation_rubric, followup_strategy. Do not invent a question_type. "
                "When personalization context is provided, the question must directly use that context."
            )
            user_prompt = (
                f"{context}\n\nGenerate exactly one {skill.question_type} question using the requested style and rubric."
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.4)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                normalized = QuizService.normalize_question_data(
                    parsed,
                    book_id=book.id,
                    chapter_id=chapter.id if chapter else None,
                    question_type=skill.question_type,
                    source=source,
                )
            except Exception as exc:
                logger.warning("Quiz question generation failed: %s", exc)

        if normalized is None:
            normalized = QuizService._fallback_question_data(
                book_id=book.id,
                chapter_id=chapter.id if chapter else None,
                chapter_title=chapter.title_zh or chapter.title_en or chapter.chapter_index if chapter else book.title,
                question_type=skill.question_type,
                source=source,
                personalization_context=personalization_context,
            )

        question = QuizQuestion(**normalized)
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return question

    @staticmethod
    async def choose_from_bank(
        *,
        book_id: int,
        chapter_id: int | None,
        question_type: str | None,
        db: AsyncSession,
    ) -> QuizQuestion | None:
        query = select(QuizQuestion).where(QuizQuestion.book_id == book_id)
        if chapter_id is None:
            query = query.where(QuizQuestion.chapter_id.is_(None))
        else:
            query = query.where(QuizQuestion.chapter_id == chapter_id)
        if question_type:
            query = query.where(QuizQuestion.question_type == question_type)
        result = await db.execute(
            query.order_by(
                QuizQuestion.attempts_count.asc(),
                QuizQuestion.times_seen.asc(),
                QuizQuestion.created_at.asc(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def chapter_bank_count(*, book_id: int, chapter_id: int, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count(QuizQuestion.id)).where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.chapter_id == chapter_id,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def generate_sparse_chapter_bank(
        *,
        book: Book,
        chapter: Chapter,
        selected_type: str,
        db: AsyncSession,
    ) -> list[QuizQuestion]:
        generated: list[QuizQuestion] = []
        for question_type in QuizService.sparse_bank_question_types(selected_type):
            existing = await QuizService.choose_from_bank(
                book_id=book.id,
                chapter_id=chapter.id,
                question_type=question_type,
                db=db,
            )
            if existing:
                continue
            try:
                generated.append(
                    await QuizService.generate_question(
                        book=book,
                        chapter=chapter,
                        question_type=question_type,
                        db=db,
                        source="runtime_batch",
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Sparse quiz bank generation failed book=%s chapter=%s type=%s error=%s",
                    book.id,
                    chapter.id,
                    question_type,
                    exc,
                )
        return generated

    @staticmethod
    async def next_chapter_question(
        chapter_id: int,
        *,
        question_type: str | None,
        personalization_context: str | None,
        db: AsyncSession,
    ) -> QuizQuestion | None:
        chapter = await QuizService._chapter_or_none(chapter_id, db)
        if not chapter:
            return None
        if question_type and not is_valid_question_type(question_type):
            raise ValueError(f"Unsupported quiz question type: {question_type}")
        selected_type = question_type or QuizService.weighted_random_question_type()
        book = await QuizService._book_or_none(chapter.book_id, db)
        if not book:
            return None

        if personalization_context:
            question = await QuizService.generate_question(
                book=book,
                chapter=chapter,
                question_type=selected_type,
                db=db,
                source="personalized",
                personalization_context=personalization_context,
            )
        else:
            question = None
            bank_count = await QuizService.chapter_bank_count(
                book_id=chapter.book_id,
                chapter_id=chapter.id,
                db=db,
            )
            if bank_count < QuizService.CHAPTER_BANK_SPARSE_THRESHOLD:
                generated = await QuizService.generate_sparse_chapter_bank(
                    book=book,
                    chapter=chapter,
                    selected_type=selected_type,
                    db=db,
                )
                question = next((item for item in generated if item.question_type == selected_type), None)
                if question is None:
                    question = await QuizService.choose_from_bank(
                        book_id=chapter.book_id,
                        chapter_id=chapter.id,
                        question_type=selected_type,
                        db=db,
                    )
                if question is None and not question_type:
                    question = generated[0] if generated else None
            if question is None:
                question = await QuizService.choose_from_bank(
                    book_id=chapter.book_id,
                    chapter_id=chapter.id,
                    question_type=question_type or selected_type,
                    db=db,
                )
        if question is None:
            question = await QuizService.generate_question(
                book=book,
                chapter=chapter,
                question_type=selected_type,
                db=db,
                source="runtime",
                personalization_context=personalization_context,
            )
        question.times_seen = int(question.times_seen or 0) + 1
        question.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(question)
        return question

    @staticmethod
    def _local_evaluation(question: QuizQuestion, answer_text: str) -> dict[str, Any]:
        expected_points = question.expected_points or []
        normalized_answer = answer_text.casefold()
        matched = [
            point
            for point in expected_points
            if any(token and token in normalized_answer for token in str(point).casefold().split()[:8])
        ]
        if expected_points and len(matched) >= max(1, len(expected_points) - 1):
            status = "completed"
        elif matched or len(answer_text.strip()) >= 80:
            status = "partial"
        else:
            status = "wrong"
        missing = [point for point in expected_points if point not in matched]
        return {
            "evaluation_status": status,
            "score": {"completed": 1.0, "partial": 0.55, "wrong": 0.0}[status],
            "missing_points": missing,
            "feedback_text": (
                "本地评估：答案已覆盖主要要点。"
                if status == "completed"
                else "本地评估：答案还需要更明确地连接定义、条件和推理步骤。"
            ),
            "followup_text": question.followup_strategy or "请补充一个关键条件，并说明为什么它必要。",
        }

    @staticmethod
    def normalize_evaluation(data: dict[str, Any], question: QuizQuestion, answer_text: str) -> dict[str, Any]:
        status = str(data.get("evaluation_status") or data.get("status") or "").strip().lower()
        if status not in {"completed", "partial", "wrong"}:
            return QuizService._local_evaluation(question, answer_text)
        missing_points = data.get("missing_points") or []
        if isinstance(missing_points, str):
            missing_points = [missing_points]
        score = data.get("score")
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = {"completed": 1.0, "partial": 0.55, "wrong": 0.0}[status]
        return {
            "evaluation_status": status,
            "score": score,
            "missing_points": [str(point) for point in missing_points if str(point).strip()],
            "feedback_text": str(data.get("feedback_text") or data.get("feedback") or ""),
            "followup_text": str(data.get("followup_text") or data.get("followup") or question.followup_strategy or ""),
        }

    @staticmethod
    async def submit_attempt(question_id: int, answer_text: str, db: AsyncSession) -> dict[str, Any] | None:
        result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
        question = result.scalar_one_or_none()
        if not question:
            return None

        translator = TranslatorService(task="quiz")
        evaluation = None
        if getattr(translator, "api_key", None):
            system_prompt = (
                "You evaluate a math quiz answer. Return strictly valid JSON with keys: "
                "evaluation_status (completed|partial|wrong), score, missing_points, feedback_text, followup_text. "
                "Use the rubric and expected points, preserve math notation, and keep feedback concise."
            )
            user_prompt = json.dumps(
                {
                    "question_text": question.question_text,
                    "question_type": question.question_type,
                    "expected_points": question.expected_points or [],
                    "evaluation_rubric": question.evaluation_rubric or {},
                    "followup_strategy": question.followup_strategy or "",
                    "answer_text": answer_text,
                },
                ensure_ascii=False,
                indent=2,
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.2)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                evaluation = QuizService.normalize_evaluation(parsed, question, answer_text)
            except Exception as exc:
                logger.warning("Quiz answer evaluation failed: %s", exc)

        if evaluation is None:
            evaluation = QuizService._local_evaluation(question, answer_text)

        attempt = QuizAttempt(
            question_id=question.id,
            book_id=question.book_id,
            chapter_id=question.chapter_id,
            answer_text=answer_text,
            **evaluation,
        )
        db.add(attempt)
        question.attempts_count = int(question.attempts_count or 0) + 1
        if evaluation["evaluation_status"] == "completed":
            question.correct_count = int(question.correct_count or 0) + 1
        elif evaluation["evaluation_status"] == "partial":
            question.partial_count = int(question.partial_count or 0) + 1
        else:
            question.wrong_count = int(question.wrong_count or 0) + 1
        await db.commit()
        await db.refresh(attempt)
        return {
            "id": attempt.id,
            "question_id": question.id,
            "book_id": question.book_id,
            "chapter_id": question.chapter_id,
            **evaluation,
            "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
        }

    @staticmethod
    async def select_target(book_id: int, personalization_context: str | None, db: AsyncSession) -> dict[str, Any] | None:
        book = await QuizService._book_or_none(book_id, db)
        if not book:
            return None
        chapters_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order))
        chapters = list(chapters_result.scalars().all())
        if not chapters:
            return None

        profile = await LearningProfileService.read_profile(book.uuid)
        attempts_result = await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.book_id == book_id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(20)
        )
        attempts = list(attempts_result.scalars().all())
        chapter_by_id = {chapter.id: chapter for chapter in chapters}

        weak_counts: dict[int, int] = {}
        for attempt in attempts:
            if attempt.chapter_id and attempt.evaluation_status in {"partial", "wrong"}:
                weak_counts[attempt.chapter_id] = weak_counts.get(attempt.chapter_id, 0) + 1
        selected_chapter = chapter_by_id.get(max(weak_counts, key=weak_counts.get)) if weak_counts else chapters[0]
        selected_type = "condition_boundary" if weak_counts else "concept_explain"

        translator = TranslatorService(task="quiz")
        if getattr(translator, "api_key", None):
            system_prompt = (
                "Select the next quiz target for a math reader. Return strictly valid JSON with "
                "chapter_id, question_type, target_concept, reason. chapter_id must be one of the provided ids; "
                f"question_type must be one of: {', '.join(QUIZ_SKILLS)}."
            )
            user_prompt = json.dumps(
                {
                    "book": {"id": book.id, "title": book.title},
                    "chapters": [
                        {
                            "id": chapter.id,
                            "chapter_index": chapter.chapter_index,
                            "title": chapter.title_zh or chapter.title_en,
                        }
                        for chapter in chapters
                    ],
                    "user_profile": profile,
                    "recent_attempts": [
                        {
                            "chapter_id": attempt.chapter_id,
                            "status": attempt.evaluation_status,
                            "missing_points": attempt.missing_points or [],
                        }
                        for attempt in attempts[:12]
                    ],
                    "personalization_context": personalization_context or "",
                },
                ensure_ascii=False,
                indent=2,
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.2)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                parsed_chapter_id = int(parsed.get("chapter_id"))
                parsed_type = str(parsed.get("question_type") or "")
                if parsed_chapter_id in chapter_by_id and is_valid_question_type(parsed_type):
                    selected_chapter = chapter_by_id[parsed_chapter_id]
                    selected_type = parsed_type
                    target_concept = str(parsed.get("target_concept") or "")
                    reason = str(parsed.get("reason") or "")
                    return {
                        "chapter_id": selected_chapter.id,
                        "chapter_index": selected_chapter.chapter_index,
                        "chapter_title": selected_chapter.title_zh or selected_chapter.title_en or "",
                        "question_type": selected_type,
                        "target_concept": target_concept,
                        "reason": (
                            f"Target concept: {target_concept}. {reason}"
                            if target_concept
                            else reason or "Selected from current learning profile and recent quiz attempts."
                        ),
                    }
            except Exception as exc:
                logger.warning("Book quiz target selection failed: %s", exc)

        return {
            "chapter_id": selected_chapter.id,
            "chapter_index": selected_chapter.chapter_index,
            "chapter_title": selected_chapter.title_zh or selected_chapter.title_en or "",
            "question_type": selected_type,
            "target_concept": selected_chapter.title_zh or selected_chapter.title_en or "",
            "reason": (
                f"Target concept: {selected_chapter.title_zh or selected_chapter.title_en or ''}. "
                "Selected by local fallback from recent partial/wrong attempts and chapter order."
            ),
        }
